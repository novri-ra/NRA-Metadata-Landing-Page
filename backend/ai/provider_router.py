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
from packages.shared_utils.cost_tracker import CostTracker

cost_tracker_inst = CostTracker()
CostTracker_instance = CostTracker()

from packages.shared_utils.tracker import tracker


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
        return "https://api.9router.com/v1"
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
    ):
        self.provider = provider
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
        elif self.provider in ("9router", "Custom"):
            self.base_url = normalize_base_url(None)
        self._init_clients()

    @property
    def api_key(self):
        return self.failover.api_key()

    def _init_clients(self):
        if self.provider == "Gemini":
            self.gemini_client = genai.Client(api_key=self.api_key)
        elif self.provider in ("OpenAI", "9router", "Custom"):
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

    def generate_metadata(
        self,
        image_path: str,
        min_kw: int = 25,
        max_kw: int = 49,
        style_preset: str = "Standard",
        extra_prompt: str = "",
        log_callback=None,
        **kwargs,
    ) -> dict:
        tracker.add_call()
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

        _log(f"[{filename}] Sending vision prompt to {self.provider} | Model: {self.model or 'default'}...", "info")

        for attempt in range(max_retries + 1):
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
                        config=genai.types.GenerateContentConfig(
                            temperature=self.temperature,
                            response_mime_type="application/json",
                            response_schema=MetadataModel,
                        ),
                    )
                    return json.loads(response.text)

                elif self.provider in ["OpenAI", "9router", "Custom"]:
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

                    default_model = (
                        "gpt-4o-mini" if self.provider == "OpenAI" else "9router/auto"
                    )
                    response = self.openai_client.chat.completions.create(
                        model=self.model or default_model,
                        messages=msgs,
                        temperature=self.temperature,
                        response_format={"type": "json_object"},
                    )
                    return self._parse_json(response.choices[0].message.content)

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
                    res = requests.post(
                        "https://api.mistral.ai/v1/chat/completions",
                        headers=headers,
                        json=data,
                        timeout=30,
                    )
                    res.raise_for_status()
                    return self._parse_json(
                        res.json()["choices"][0]["message"]["content"]
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
                    return self._parse_json(response.choices[0].message.content)
            except Exception as e:
                err_str = str(e)
                _log(f"[{filename}] {self.provider} error: {err_str}", "error")
                if detect_connection_refused(err_str):
                    print(
                        f"[ERROR] Connection refused to endpoint {self.base_url or 'API'}. Ensure server/proxy is active."
                    )
                    is_retryable = True
                else:
                    is_retryable = detect_retryable(err_str)

                # Check for Rate Limit / Quota / Invalid Key -> Rotate Key
                if detect_rate_limit(err_str) or detect_auth_failure(err_str):
                    if "429" in err_str:
                        delay = backoff_times[attempt] if attempt < len(backoff_times) else 30
                        _log(f"[{filename}] Rate limit (429) on {self.provider}/{self.model or 'default'}. Delaying {delay}s (Attempt {attempt+1}/{max_retries})...", "warn")
                        time.sleep(delay)

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
                                return self._fallback_metadata(error_details="All keys exhausted. No failover available.")
                            continue  # retry with new provider
                        print(
                            f"[{filename}] {self.provider}: Authentication failed. Check API Key."
                        )
                        return self._fallback_metadata(error_details="Authentication failed. Check API Key.")

                if is_retryable and attempt < max_retries:
                    wait_time = backoff_times[attempt]
                    print(
                        f"[{filename}] Retry {attempt + 1}/{max_retries} for {self.provider} after {wait_time}s..."
                    )
                    time.sleep(wait_time)
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
                                    **kwargs,
                                )
                    _log(f"[{filename}] {self.provider}: {e}", "error")
                    return self._fallback_metadata(error_details=str(e))

        return self._fallback_metadata(error_details="Max retries exhausted")

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

    def _fallback_metadata(self, error_details: str = "Unknown error") -> dict:
        return {
            "title": "Unknown Title",
            "description": "Metadata generation failed.",
            "category": "Unknown",
            "primary_category": "Miscellaneous",
            "secondary_category": "",
            "keywords": ["error", "fallback"],
            "error": True,
            "error_details": error_details,
        }

    # --- Vision capability registry (research-backed, Sep 2026) ---
    # Models confirmed to accept image input for metadata generation.
    # ponytail: hardcoded whitelist; upgrade to API introspection when providers stabilize schema
    VISION_WHITELIST = {
        "Gemini": {
            "gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro",
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