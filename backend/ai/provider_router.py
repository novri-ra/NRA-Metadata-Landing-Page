"""Multi-provider AI routing for metadata generation.

Extracted from ``packages/ai_engine/service.py``. Decoupled concerns:

- ``provider_router``        — provider dispatch (Gemini/OpenAI/Mistral/Groq),
  prompt construction, JSON parsing, fallback metadata, vision registry.
- ``failover_handler``       — HTTP 429 detection, exponential backoff,
  thread-safe key rotation & provider failover decisions.
- ``token_optimizer``        — image resizing (max 1024px) & SVG text fallback.
"""

import json
import os
import re
import threading
import time

import requests
from google import genai
from openai import OpenAI
from pydantic import BaseModel, Field

from backend.ai.failover_handler import (
    FailoverHandler,
    detect_auth_failure,
    detect_connection_refused,
    detect_rate_limit,
    detect_retryable,
)
from backend.ai.token_optimizer import encode_image, read_text_asset
from packages.shared_utils import cost_tracker as _cost_tracker


VISION_MIN_INTERVAL = 1.5
_vision_lock = threading.Lock()
_last_vision_call = 0.0


def _throttle_vision_request() -> None:
    """Stagger concurrent vision calls so a batch does not slam the provider.

    Worker threads run several files in parallel; without a shared cadence gate
    they all hit the vision endpoint at once and trip the Mistral RPM limit.
    ponytail: one global gate for every provider; key it per provider if a batch
    ever mixes providers with different rate ceilings.
    """
    global _last_vision_call
    with _vision_lock:
        now = time.monotonic()
        wait = VISION_MIN_INTERVAL - (now - _last_vision_call)
        if wait > 0:
            time.sleep(wait)
            now = time.monotonic()
        _last_vision_call = now


def _retry_after_seconds(exc) -> float | None:
    """Read the ``Retry-After`` header off a raised HTTP error, clamped to 60s."""
    response = getattr(exc, "response", None)
    if response is None or not getattr(response, "headers", None):
        return None
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        return min(max(float(value), 1), 60)
    except (TypeError, ValueError):
        return None


def _interruptible_sleep(seconds, cancel_check=None, step=0.25) -> bool:
    """Sleep in small slices so a batch cancel cuts through long backoffs.

    Returns False if ``cancel_check`` turned True before the sleep elapsed.
    """
    remaining = float(seconds)
    while remaining > 0 and not (cancel_check and cancel_check()):
        chunk = min(step, remaining)
        time.sleep(chunk)
        remaining -= chunk
    return not (cancel_check and cancel_check())


MISTRAL_MIN_INTERVAL = 2.5
MISTRAL_429_MIN_SLEEP = 5.0
_mistral_lock = threading.Lock()
_mistral_last_call = 0.0


def _mistral_chat_completion(
    headers: dict, data: dict, log=None, preview_name: str = "", model: str = ""
) -> requests.Response:
    """Serialize Mistral vision requests: one in flight at a time, spaced at
    least ``MISTRAL_MIN_INTERVAL`` seconds after the previous one *finished*.
    The standard tier rejects concurrent requests, so the lock is held for the
    whole HTTP exchange. The "Sending vision prompt" log is emitted inside the
    lock so log timestamps reflect the actual request time, not queue-join time.
    ponytail: hard-coded 2.5s cadence for the standard tier; make it configurable
    if a permissive tier is ever used.
    """
    global _mistral_last_call
    with _mistral_lock:
        elapsed = time.time() - _mistral_last_call
        if elapsed < MISTRAL_MIN_INTERVAL:
            time.sleep(MISTRAL_MIN_INTERVAL - elapsed)
        if log:
            log(
                f"[{preview_name}] Sending vision prompt to Mistral | Model: {model}...",
                "info",
            )
        response = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30,
        )
        _mistral_last_call = time.time()
        return response


class MetadataModel(BaseModel):
    title: str = Field(description="A concise title")
    description: str = Field(description="A detailed description")
    category: str = Field(description="A broad category")
    primary_category: str = Field(
        description="Primary Shutterstock category", default=""
    )
    secondary_category: str = Field(
        description="Secondary Shutterstock category", default=""
    )
    keywords: list[str] = Field(description="Array of descriptive keywords")


def normalize_base_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    while url.endswith("/"):
        url = url[:-1]
    if not url.endswith("/v1"):
        url += "/v1"
    return url


class AIService:
    def __init__(
        self,
        provider: str,
        api_keys,
        model: str | None = None,
        temperature: float = 0.3,
        failover_providers: dict | None = None,
        custom_base_url: str | None = None,
        cost_tracker=None,
    ):
        self.provider = provider
        self.cost_tracker = cost_tracker or _cost_tracker.cost_tracker
        self.failover = FailoverHandler(
            api_keys,
            failover_providers=failover_providers,
        )
        self.failover.bind_provider(provider)
        self.model = model
        self.temperature = temperature
        self.base_url = None
        if custom_base_url:
            self.base_url = normalize_base_url(custom_base_url)
        elif self.provider == "Custom":
            self.base_url = normalize_base_url(None)
        self._init_clients()

    @property
    def api_key(self):
        return self.failover.api_key()

    def _init_clients(self):
        if self.provider == "Gemini":
            self.gemini_client = genai.Client(api_key=self.api_key)
        elif self.provider in ("OpenAI", "Custom"):
            kwargs = {}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self.openai_client = OpenAI(api_key=self.api_key, **kwargs)
        elif self.provider == "Groq":
            try:
                import groq

                self.groq_client = groq.Groq(api_key=self.api_key)
            except ImportError:
                self.groq_client = None

    def _gemini_generation_config(self):
        kwargs = dict(
            temperature=self.temperature,
            response_mime_type="application/json",
            response_schema=MetadataModel,
        )
        if hasattr(genai.types, "AutomaticFunctionCallingConfig"):
            kwargs["automatic_function_calling"] = (
                genai.types.AutomaticFunctionCallingConfig(disable=True)
            )
        return genai.types.GenerateContentConfig(**kwargs)

    # ── Token usage extraction ─────────────────────────────────────────

    def _extract_usage(self, response) -> tuple[int, int]:
        """Return (prompt_tokens, completion_tokens) from any provider response.

        Handles OpenAI-style ``.usage`` and Gemini-style ``usage_metadata``.
        """
        usage = getattr(response, "usage", None)
        if usage is None:
            usage = getattr(response, "usage_metadata", None)
        if usage is None:
            return 0, 0
        prompt = (
            getattr(usage, "prompt_tokens", None)
            or getattr(usage, "prompt_token_count", 0)
        )
        completion = (
            getattr(usage, "completion_tokens", None)
            or getattr(usage, "candidates_token_count", 0)
        )
        return prompt or 0, completion or 0

    def _finalize(
        self,
        meta: dict,
        model: str,
        response=None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> dict:
        """Record token usage into the cost tracker and return the metadata dict."""
        if response is not None:
            prompt_tokens, completion_tokens = self._extract_usage(response)
        self.cost_tracker.record_usage(
            self.provider, model, prompt_tokens, completion_tokens
        )
        return meta

    # ── Main entry point ───────────────────────────────────────────────

    def generate_metadata(
        self,
        image_path: str,
        min_kw: int = 25,
        max_kw: int = 49,
        style_preset: str = "Standard",
        extra_prompt: str = "",
        log_callback=None,
        cancel_check=None,
        **kwargs,
    ) -> dict:
        filename = os.path.basename(image_path) if image_path else "unknown"

        def _log(msg, level="info"):
            if log_callback:
                log_callback(msg, level)
            else:
                print(f"[{level.upper()}] {msg}")

        style_prompts = {
            "General Commercial": "Balanced visual description for general stock assets.",
            "Icons & Clipart": "Focus on style (flat, line, glyph), UI/UX functionality, and simple search intent keywords.",
            "Backgrounds & Patterns": "Focus on texture, copy space, backdrop, seamless, and wallpaper attributes.",
            "Characters & Mascot": "Focus on pose, expression, emotional theme, and persona.",
        }
        style_guide = style_prompts.get(
            style_preset, style_prompts["General Commercial"]
        )

        prompt = f"""
        Analyze this image/file and return a JSON object with:
        "title": a concise, SEO-optimized title (max 180 chars),
        "description": a detailed description for microstock search (max 200 chars),
        "category": a broad category,
        "primary_category": primary Shutterstock category from Abstract, Animals/Wildlife, Backgrounds/Textures, Beauty/Fashion, Buildings/Landmarks, Business/Finance, Celebrities, Education, Food and Drink, Healthcare/Medical, Holidays, Illustrations/Clip-Art, Industrial, Interiors, Miscellaneous, Nature, Objects, Parks/Outdoor, People, Religion, Science, Signs/Symbols, Sports/Recreation, Technology, The Arts, Transportation, Vintage,
        "secondary_category": optional secondary Shutterstock category,
        "keywords": an array of {min_kw} to {max_kw} descriptive keywords.

        Generate strictly between {min_kw} and {max_kw} highly relevant, comma-separated keywords. Do not output fewer than {min_kw} keywords. The keyword array MUST be {min_kw}-{max_kw} items long; count them before returning.

        KEYWORD PRIORITY ORDER (most important first):
        1. Primary subject, main action, and central visual elements (first 5-10 keywords)
        2. Visual style, format (vector, flat, isolated, silhouette, 3d), colors, and mood (middle keywords)
        3. Abstract concepts, business use-cases, and general search intent (final keywords)

        Style Focus: {style_guide}
        Return ONLY valid JSON. Keywords must be in priority order as specified above.
        """

        is_text_fallback = image_path.endswith(".svg") and not image_path.endswith(
            ".jpg"
        )

        max_retries = self.failover.max_retries
        backoff_times = self.failover.backoff_times

        if self.provider != "Mistral":
            _log(f"[{filename}] Sending vision prompt to {self.provider} | Model: {self.model or 'default'}...", "info")

        fail_reason = None
        for attempt in range(max_retries + 1):
            if cancel_check and cancel_check():
                return self._fallback_metadata(
                    error_details="Batch canceled", fail_reason="cancelled"
                )
            if not is_text_fallback:
                _throttle_vision_request()
            try:
                if self.provider == "Gemini":
                    if is_text_fallback:
                        contents = [prompt, f"SVG Content:\\n{read_text_asset(image_path)}"]
                    else:
                        import PIL.Image

                        img = PIL.Image.open(image_path)
                        contents = [prompt, img]

                    response = self.gemini_client.models.generate_content(
                        model=self.model or "gemini-1.5-flash",
                        contents=contents,
                        config=self._gemini_generation_config(),
                    )
                    return self._finalize(
                        json.loads(response.text),
                        self.model or "gemini-1.5-flash",
                        response,
                    )

                elif self.provider in ("OpenAI", "Custom"):
                    if is_text_fallback:
                        msgs = [
                            {
                                "role": "system",
                                "content": "You are a professional microstock SEO tagger. Always respond with strict valid JSON only containing title, description, and keywords.",
                            },
                            {
                                "role": "user",
                                "content": f"{prompt}\\n\\nSVG Content:\\n{read_text_asset(image_path)}",
                            },
                        ]
                    else:
                        base64_image = encode_image(image_path)
                        msgs = [
                            {
                                "role": "system",
                                "content": "You are a professional microstock SEO tagger. Always respond with strict valid JSON only containing title, description, and keywords.",
                            },
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/jpeg;base64,{base64_image}"
                                        },
                                    },
                                ],
                            },
                        ]

                    default_model = "gpt-4o-mini"
                    response = self.openai_client.chat.completions.create(
                        model=self.model or default_model,
                        messages=msgs,
                        temperature=self.temperature,
                        response_format={"type": "json_object"},
                    )
                    return self._finalize(
                        self._parse_json(response.choices[0].message.content),
                        self.model or default_model,
                        response,
                    )

                elif self.provider == "Mistral":
                    if is_text_fallback:
                        content = f"{prompt}\\n\\nSVG Content:\\n{read_text_asset(image_path)}"
                    else:
                        base64_image = encode_image(image_path)
                        content = [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ]
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    }
                    data = {
                        "model": self.model or "mistral-small-latest",
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a professional microstock SEO tagger. Always respond with strict valid JSON only containing title, description, and keywords.",
                            },
                            {"role": "user", "content": content},
                        ],
                        "temperature": self.temperature,
                        "response_format": {"type": "json_object"},
                    }
                    res = _mistral_chat_completion(
                        headers,
                        data,
                        log=_log,
                        preview_name=filename,
                        model=self.model or "mistral-small-latest",
                    )
                    res.raise_for_status()
                    data = res.json()
                    usage = data.get("usage") or {}
                    return self._finalize(
                        self._parse_json(data["choices"][0]["message"]["content"]),
                        self.model or "mistral-small-latest",
                        prompt_tokens=usage.get("prompt_tokens", 0),
                        completion_tokens=usage.get("completion_tokens", 0),
                    )

                elif self.provider == "Groq":
                    if is_text_fallback:
                        msgs = [
                            {
                                "role": "system",
                                "content": "You are a professional microstock SEO tagger. Always respond with strict valid JSON only containing title, description, and keywords.",
                            },
                            {
                                "role": "user",
                                "content": f"{prompt}\\n\\nSVG Content:\\n{read_text_asset(image_path)}",
                            },
                        ]
                    else:
                        base64_image = encode_image(image_path)
                        msgs = [
                            {
                                "role": "system",
                                "content": "You are a professional microstock SEO tagger. Always respond with strict valid JSON only containing title, description, and keywords.",
                            },
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/jpeg;base64,{base64_image}"
                                        },
                                    },
                                ],
                            },
                        ]

                    response = self.groq_client.chat.completions.create(
                        model=self.model or "llama-3.2-11b-vision-preview",
                        messages=msgs,
                        temperature=self.temperature,
                        response_format={"type": "json_object"},
                    )
                    return self._finalize(
                        self._parse_json(response.choices[0].message.content),
                        self.model or "llama-3.2-11b-vision-preview",
                        response,
                    )
            except Exception as e:
                err_str = str(e)
                if detect_rate_limit(err_str):
                    _log(
                        f"[{filename}] {self.provider} rate limit (429/quota): {err_str}",
                        "warn",
                    )
                else:
                    _log(f"[{filename}] {self.provider} error: {err_str}", "error")
                if detect_connection_refused(err_str):
                    print(
                        f"[ERROR] Connection refused to endpoint {self.base_url or 'API'}. Ensure server/proxy is active."
                    )
                    is_retryable = True
                else:
                    is_retryable = detect_retryable(err_str)

                if detect_rate_limit(err_str):
                    fail_reason = "rate_limit"
                elif detect_auth_failure(err_str):
                    fail_reason = "auth"
                elif is_retryable and attempt >= max_retries:
                    fail_reason = "retries_exhausted"
                else:
                    fail_reason = None

                # Check for Rate Limit / Quota / Invalid Key -> Rotate Key
                if detect_rate_limit(err_str) or detect_auth_failure(err_str):
                    if "429" in err_str:
                        delay = backoff_times[attempt] if attempt < len(backoff_times) else 30
                        retry_after = _retry_after_seconds(e)
                        if retry_after is not None:
                            delay = retry_after
                        if self.provider == "Mistral":
                            delay = max(delay, MISTRAL_429_MIN_SLEEP)
                        _log(f"[{filename}] Rate limit (429) on {self.provider}/{self.model or 'default'}. Delaying {int(delay)}s (Attempt {attempt+1}/{max_retries})...", "warn")
                        if not _interruptible_sleep(delay, cancel_check):
                            return self._fallback_metadata(
                                error_details="Batch canceled while backing off",
                                fail_reason="cancelled",
                            )
                        # Already backed off for 429; retry the same key/provider
                        # through the full retry budget (max_retries, default 5)
                        # before any failover/fallback decision.
                        if attempt < max_retries and self.failover.keyring.size() <= 1:
                            continue

                    if self.failover.keyring.size() > 1:
                        _log(
                            f"[{filename}] API Key #{self.failover.keyring.index() + 1} exhausted on {self.provider}. Rotating to next key...", "warn"
                        )
                        self.failover.rotate_key()
                        self._init_clients()  # re-init clients with new key
                        if attempt < max_retries:
                            continue  # retry immediately with new key

                    if detect_auth_failure(err_str) and (
                        self.failover.keyring.size() <= 1 or attempt >= max_retries
                    ):
                        # Try failover to another provider
                        if not self.failover.failover_attempted and self.failover.has_failovers():
                            for (
                                alt_provider,
                                alt_key,
                            ) in self.failover.failover_providers.items():
                                if alt_key and alt_provider != self.provider:
                                    print(
                                        f"[FAILOVER] {self.provider} auth failed. Switching to {alt_provider}..."
                                    )
                                    self.failover.mark_failover_attempted()
                                    self.provider = alt_provider
                                    self.failover.bind_provider(alt_provider)
                                    self.failover.replace_keys(alt_key)
                                    self._init_clients()
                                    break
                            else:
                                _log(
                                    f"[{filename}] All API keys exhausted. No failover provider available.", "error"
                                )
                                return self._fallback_metadata(error_details="All keys exhausted. No failover available.", fail_reason="auth")
                            continue  # retry with new provider
                        print(
                            f"[{filename}] {self.provider}: Authentication failed. Check API Key."
                        )
                        return self._fallback_metadata(error_details="Authentication failed. Check API Key.", fail_reason="auth")

                if is_retryable and attempt < max_retries:
                    wait_time = backoff_times[attempt]
                    print(
                        f"[{filename}] Retry {attempt + 1}/{max_retries} for {self.provider} after {wait_time}s..."
                    )
                    if not _interruptible_sleep(wait_time, cancel_check):
                        return self._fallback_metadata(
                            error_details="Batch canceled while retrying",
                            fail_reason="cancelled",
                        )
                    continue
                else:
                    # Last chance: try provider failover if 429 exhausted all retries
                    if (
                        detect_rate_limit(err_str)
                        and not self.failover.failover_attempted
                        and self.failover.has_failovers()
                    ):
                        for alt_provider, alt_key in self.failover.failover_providers.items():
                            if alt_key and alt_provider != self.provider:
                                print(
                                    f"[FAILOVER] {self.provider} rate-limited (429). Switching to {alt_provider}..."
                                )
                                self.failover.mark_failover_attempted()
                                self.provider = alt_provider
                                self.failover.bind_provider(alt_provider)
                                self.failover.replace_keys(alt_key)
                                self._init_clients()
                                return self.generate_metadata(
                                    image_path,
                                    min_kw,
                                    max_kw,
                                    style_preset,
                                    extra_prompt,
                                    cancel_check=cancel_check,
                                    **kwargs,
                                )
                    _log(f"[{filename}] {self.provider}: {e}", "error")
                    return self._fallback_metadata(error_details=str(e), fail_reason=fail_reason)

        return self._fallback_metadata(error_details="Max retries exhausted", fail_reason=fail_reason)

    def _parse_json(self, text: str) -> dict:
        parsed = None
        try:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                parsed = json.loads(text[start : end + 1])
            else:
                parsed = json.loads(text)
        except json.JSONDecodeError as e:
            print(f"[WARN] JSONDecodeError: {e}. Raw response: {text[:200]}...")
            # Try regex extraction
            title_match = re.search(r'"title"\s*:\s*"([^"]+)"', text, re.IGNORECASE)
            desc_match = re.search(
                r'"description"\s*:\s*"([^"]+)"', text, re.IGNORECASE
            )
            kw_match = re.search(
                r'"keywords"\s*:\s*\[(.*?)\]', text, re.DOTALL | re.IGNORECASE
            )

            if title_match and desc_match and kw_match:
                title = title_match.group(1)
                desc = desc_match.group(1)
                kw_raw = kw_match.group(1)
                # Parse keywords string
                keywords = [k.strip(' "') for k in kw_raw.split(",") if k.strip(' "')]
                parsed = {"title": title, "description": desc, "keywords": keywords}
            else:
                raise ValueError(
                    f"JSON Parse Error: Failed to extract fallback via regex. Raw response: {text[:200]}..."
                )

        required = {"title", "description", "keywords"}
        if not isinstance(parsed, dict) or not required.issubset(parsed.keys()):
            raise ValueError(
                f"JSON Parse Error: Missing required fields. Raw response: {text[:200]}..."
            )
        if not isinstance(parsed.get("keywords"), list) or len(parsed["keywords"]) < 5:
            raise ValueError(
                f"JSON Parse Error: Invalid keywords format or < 5 keywords. Raw response: {text[:200]}..."
            )
        return parsed

    def _fallback_metadata(
        self, error_details: str = "Unknown error", fail_reason: str | None = None
    ) -> dict:
        meta = {
            "title": "Unknown Title",
            "description": "Metadata generation failed.",
            "category": "Unknown",
            "primary_category": "Miscellaneous",
            "secondary_category": "",
            "keywords": ["error", "fallback"],
            "error": True,
            "error_details": error_details,
        }
        if fail_reason:
            meta["fail_reason"] = fail_reason
        return meta

    # --- Vision capability registry (research-backed, Sep 2026) ---
    # Models confirmed to accept image input for metadata generation.
    # ponytail: hardcoded whitelist; upgrade to API introspection when providers stabilize schema
    VISION_WHITELIST = {
        "Gemini": {
            "gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash",
            "gemini-3.1-flash-lite", "gemini-3.5-flash-lite",
            "gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.8-flash",
            "gemini-3.1-pro-preview",
        },
        "OpenAI": {"gpt-4o-mini", "gpt-4o", "chatgpt-4o-latest"},
        "Mistral": {
            "pixtral-12b-2409", "pixtral-large-2411",
            "mistral-large-latest", "ministral-3-8b",
            "ministral-3-14b", "ministral-3-3b",
            "mistral-medium-latest",
        },
        "Groq": {
            "llama-3.2-11b-vision-preview", "llama-3.2-90b-vision-preview",
        },
    }

    NON_VISION_PATTERNS = [
        "embed", "tts", "whisper", "moderation", "transcrib", "codestral",
        "text-embedding", "davinci", "babbage", "ada", "curie",
        "gpt-3.5", "audio", "realtime", "image-gen", "dall-e",
        "mistral-small", "magistral", "leanstral", "voxtral",
        "shieldstral", "nano-banana", "lyria", "veo", "imagen",
        "gemini-embedding", "gemini-robotics", "deep-research",
        "antigravity", "omni-flash",
    ]

    def _is_vision_capable(self, model_id: str) -> bool:
        mid = model_id.lower()
        for pat in self.NON_VISION_PATTERNS:
            if pat in mid:
                return False
        whitelist = self.VISION_WHITELIST.get(self.provider, set())
        if model_id in whitelist:
            return True
        if "vision" in mid or "pixtral" in mid:
            return True
        if self.provider == "Gemini" and ("flash" in mid or "pro" in mid):
            return True
        if self.provider == "OpenAI" and "gpt-4o" in mid:
            return True
        return False

    def fetch_available_models(self) -> list[str]:
        """Fetch models from API and filter to vision-capable only."""
        try:
            if self.provider == "OpenAI":
                response = requests.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=10,
                )
                if response.status_code == 200:
                    data = response.json()
                    all_models = [m["id"] for m in data.get("data", [])]
                    models = [m for m in all_models if self._is_vision_capable(m)]
                    models.sort()
                    return models[:20] if models else ["gpt-4o-mini (Optimal)", "gpt-4o"]

            elif self.provider == "Mistral":
                response = requests.get(
                    "https://api.mistral.ai/v1/models",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Accept": "application/json",
                    },
                    timeout=10,
                )
                if response.status_code == 200:
                    data = response.json()
                    all_models = [m["id"] for m in data.get("data", [])]
                    models = [m for m in all_models if self._is_vision_capable(m)]
                    return models if models else ["pixtral-12b-2409 (Cost Efficient)", "mistral-large-latest"]

            elif self.provider == "Groq":
                response = requests.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=10,
                )
                if response.status_code == 200:
                    data = response.json()
                    all_models = [m["id"] for m in data.get("data", [])]
                    models = [m for m in all_models if self._is_vision_capable(m)]
                    return models if models else ["llama-3.2-11b-vision-preview (Recommended)", "llama-3.2-90b-vision-preview"]

            elif self.provider == "Gemini":
                response = requests.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}",
                    timeout=10,
                )
                if response.status_code == 200:
                    data = response.json()
                    all_models = [
                        m["name"].replace("models/", "")
                        for m in data.get("models", [])
                        if "generateContent" in m.get("supportedGenerationMethods", [])
                    ]
                    models = [m for m in all_models if self._is_vision_capable(m)]
                    models.sort(reverse=True)
                    return models if models else ["gemini-2.5-flash-lite (Recommended)", "gemini-2.5-flash"]

        except (OSError, ValueError, KeyError, RuntimeError) as e:
            print(f"Fetch models failed for {self.provider}: {e}")
        return []