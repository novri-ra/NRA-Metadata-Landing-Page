import base64
import json
import time

import requests

from packages.shared_utils.cost_tracker import CostTracker

cost_tracker_inst = CostTracker()
CostTracker_instance = CostTracker()
from google import genai
from openai import OpenAI
from pydantic import BaseModel, Field

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
    ):
        self.provider = provider
        self.failover_providers = (
            failover_providers or {}
        )  # {"Gemini": "key", "Groq": "key"}
        self._failover_attempted = False
        # Normalize to list
        if isinstance(api_keys, str):
            self.api_keys = [k.strip() for k in api_keys.splitlines() if k.strip()]
            if not self.api_keys:
                self.api_keys = [api_keys]
        elif isinstance(api_keys, list):
            self.api_keys = [k for k in api_keys if k and isinstance(k, str)]
        else:
            self.api_keys = []

        if not self.api_keys:
            self.api_keys = [""]

        self.current_key_idx = 0
        self.model = model
        self.temperature = temperature
        self.base_url = None
        self._init_clients()

    @property
    def api_key(self):
        return self.api_keys[self.current_key_idx]

    def _init_clients(self):
        if self.provider == "Gemini":
            self.gemini_client = genai.Client(api_key=self.api_key)
        elif self.provider == "OpenAI":
            self.openai_client = OpenAI(api_key=self.api_key)
        elif self.provider == "Groq":
            try:
                import groq

                self.groq_client = groq.Groq(api_key=self.api_key)
            except ImportError:
                self.groq_client = None

    def _encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def generate_metadata(
        self,
        image_path: str,
        min_kw: int = 25,
        max_kw: int = 49,
        style_preset: str = "Standard",
        extra_prompt: str = "",
        **kwargs,
    ) -> dict:
        tracker.add_call()

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

        max_retries = 3
        backoff_times = [2, 4, 8]

        for attempt in range(max_retries + 1):
            try:
                if self.provider == "Gemini":
                    if is_text_fallback:
                        with open(image_path, "r", encoding="utf-8") as f:
                            svg_content = f.read()[:20000]
                        contents = [prompt, f"SVG Content:\\n{svg_content}"]
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

                elif self.provider in ["OpenAI", "9router"]:
                    if is_text_fallback:
                        with open(image_path, "r", encoding="utf-8") as f:
                            svg_content = f.read()[:20000]
                        msgs = [
                            {
                                "role": "system",
                                "content": "You are a professional microstock SEO tagger. Always respond with strict valid JSON only containing title, description, and keywords.",
                            },
                            {
                                "role": "user",
                                "content": f"{prompt}\\n\\nSVG Content:\\n{svg_content}",
                            },
                        ]
                    else:
                        base64_image = self._encode_image(image_path)
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
                        with open(image_path, "r", encoding="utf-8") as f:
                            svg_content = f.read()[:20000]
                        content = f"{prompt}\\n\\nSVG Content:\\n{svg_content}"
                    else:
                        base64_image = self._encode_image(image_path)
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
                        with open(image_path, "r", encoding="utf-8") as f:
                            svg_content = f.read()[:20000]
                        msgs = [
                            {
                                "role": "system",
                                "content": "You are a professional microstock SEO tagger. Always respond with strict valid JSON only containing title, description, and keywords.",
                            },
                            {
                                "role": "user",
                                "content": f"{prompt}\\n\\nSVG Content:\\n{svg_content}",
                            },
                        ]
                    else:
                        base64_image = self._encode_image(image_path)
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
            except (OSError, ValueError, KeyError, RuntimeError) as e:
                err_str = str(e)
                if (
                    "ConnectionRefused" in err_str
                    or "ConnectError" in err_str
                    or "Failed to connect" in err_str
                    or "ECONNREFUSED" in err_str
                ):
                    print(
                        f"[ERROR] Connection refused to endpoint {self.base_url or 'API'}. Ensure server/proxy is active."
                    )
                    is_retryable = True
                else:
                    is_retryable = (
                        "429" in err_str
                        or "500" in err_str
                        or "502" in err_str
                        or "503" in err_str
                        or "504" in err_str
                        or "timeout" in err_str.lower()
                        or "connection" in err_str.lower()
                        or "JSON Parse Error" in err_str
                    )

                # Check for Rate Limit / Quota / Invalid Key -> Rotate Key
                if (
                    "429" in err_str
                    or "quota" in err_str.lower()
                    or "exhausted" in err_str.lower()
                    or "401" in err_str
                    or "invalid_api_key" in err_str.lower()
                    or "authentication" in err_str.lower()
                    or "403" in err_str
                ):
                    if len(self.api_keys) > 1:
                        print(
                            f"[WARNING] API Key #{self.current_key_idx + 1} limit/exhausted on {self.provider}. Rotating to key #{(self.current_key_idx + 1) % len(self.api_keys) + 1}..."
                        )
                        self.current_key_idx = (self.current_key_idx + 1) % len(
                            self.api_keys
                        )
                        self._init_clients()  # re-init clients with new key
                        if attempt < max_retries:
                            continue  # retry immediately with new key

                    if (
                        "401" in err_str
                        or "invalid_api_key" in err_str.lower()
                        or "authentication" in err_str.lower()
                    ) and (len(self.api_keys) <= 1 or attempt >= max_retries):
                        # Try failover to another provider
                        if not self._failover_attempted and self.failover_providers:
                            for (
                                alt_provider,
                                alt_key,
                            ) in self.failover_providers.items():
                                if alt_key and alt_provider != self.provider:
                                    print(
                                        f"[FAILOVER] {self.provider} exhausted. Switching to {alt_provider}..."
                                    )
                                    self._failover_attempted = True
                                    self.provider = alt_provider
                                    self.api_keys = (
                                        [alt_key]
                                        if isinstance(alt_key, str)
                                        else alt_key
                                    )
                                    self.current_key_idx = 0
                                    self._init_clients()
                                    break
                            else:
                                print(
                                    f"AI Service Error ({self.provider}): All keys exhausted. No failover provider available."
                                )
                                return self._fallback_metadata(error_details="All keys exhausted. No failover available.")
                            continue  # retry with new provider
                        print(
                            f"AI Service Error ({self.provider}): All keys exhausted or Authentication Failed. Check API Key."
                        )
                        return self._fallback_metadata(error_details="Authentication failed. Check API Key.")

                if is_retryable and attempt < max_retries:
                    wait_time = backoff_times[attempt]
                    print(
                        f"AI Service retry {attempt + 1}/{max_retries} for {self.provider} after {wait_time}s due to: {err_str}"
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    # Last chance: try provider failover if 429 exhausted all retries
                    if (
                        "429" in err_str
                        and not self._failover_attempted
                        and self.failover_providers
                    ):
                        for alt_provider, alt_key in self.failover_providers.items():
                            if alt_key and alt_provider != self.provider:
                                print(
                                    f"[FAILOVER] {self.provider} rate-limited (429). Switching to {alt_provider}..."
                                )
                                self._failover_attempted = True
                                self.provider = alt_provider
                                self.api_keys = (
                                    [alt_key] if isinstance(alt_key, str) else alt_key
                                )
                                self.current_key_idx = 0
                                self._init_clients()
                                return self.generate_metadata(
                                    image_path,
                                    min_kw,
                                    max_kw,
                                    style_preset,
                                    extra_prompt,
                                    **kwargs,
                                )
                    print(f"AI Service Error ({self.provider}): {e}")
                    return self._fallback_metadata(error_details=str(e))

        return self._fallback_metadata(error_details="Max retries exhausted")

    def _parse_json(self, text: str) -> dict:
        import json
        import re

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

    def fetch_available_models(self) -> list[str]:
        try:
            if self.provider == "OpenAI":
                response = requests.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=10,
                )
                if response.status_code == 200:
                    data = response.json()
                    models = [
                        m["id"]
                        for m in data.get("data", [])
                        if "gpt" in m["id"]
                        and "vision" not in m["id"]
                        and "instruct" not in m["id"]
                    ]
                    models.sort(reverse=True)
                    return models[:20] if models else ["gpt-4o", "gpt-4o-mini"]
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
                    models = [
                        m["id"]
                        for m in data.get("data", [])
                        if m["id"].startswith(("mistral", "pixtral", "open-"))
                    ]
                    return (
                        models
                        if models
                        else [
                            "mistral-small-latest",
                            "mistral-large-latest",
                            "pixtral-12b-2409",
                        ]
                    )
            elif self.provider == "Groq":
                response = requests.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=10,
                )
                if response.status_code == 200:
                    data = response.json()
                    models = [
                        m["id"]
                        for m in data.get("data", [])
                        if "vision" in m["id"]
                        or "llama" in m["id"]
                        or "mixtral" in m["id"]
                    ]
                    return (
                        models
                        if models
                        else [
                            "llama-3.2-11b-vision-preview",
                            "llama-3.2-90b-vision-preview",
                        ]
                    )
            elif self.provider == "Gemini":
                response = requests.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}",
                    timeout=10,
                )
                if response.status_code == 200:
                    data = response.json()
                    models = [
                        m["name"].replace("models/", "")
                        for m in data.get("models", [])
                        if "gemini" in m["name"]
                        and "generateContent" in m.get("supportedGenerationMethods", [])
                    ]
                    models = [
                        m
                        for m in models
                        if "vision" not in m or "1.5" in m or "2.0" in m
                    ]
                    models.sort(reverse=True)
                    return (
                        models
                        if models
                        else ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"]
                    )
        except (OSError, ValueError, KeyError, RuntimeError) as e:
            print(f"Fetch models failed for {self.provider}: {e}")
        return []
