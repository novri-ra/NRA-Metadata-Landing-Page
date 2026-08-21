import json
import base64
import requests
import time
from packages.shared_utils.cost_tracker import CostTracker
cost_tracker_inst = CostTracker()
CostTracker_instance = CostTracker()
from google import genai
from openai import OpenAI
from pydantic import BaseModel, Field
from packages.shared_utils.tracker import tracker
from packages.shared_utils.config import load_config

class MetadataModel(BaseModel):
    title: str = Field(description="A concise title")
    description: str = Field(description="A detailed description")
    category: str = Field(description="A broad category")
    primary_category: str = Field(description="Primary Shutterstock category", default="")
    secondary_category: str = Field(description="Secondary Shutterstock category", default="")
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
    def __init__(self, provider: str, api_key: str, model: str = None, temperature: float = 0.3):
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.base_url = None
        
        if self.provider == "Gemini":
            self.gemini_client = genai.Client(api_key=self.api_key)
        elif self.provider == "OpenAI":
            self.openai_client = OpenAI(api_key=self.api_key)
        elif self.provider == "Groq":
            import groq
            self.groq_client = groq.Groq(api_key=self.api_key)
        elif self.provider == "9router":
            config = load_config()
            raw_url = config.get("custom_base_url", config.get("9router_base_url", "https://api.9router.com/v1"))
            self.base_url = normalize_base_url(raw_url)
            self.openai_client = OpenAI(api_key=self.api_key or "sk-9router", base_url=self.base_url)

    def _encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def generate_metadata(self, image_path: str, min_kw: int = 25, max_kw: int = 49, style_preset: str = "Standard", extra_prompt: str = "", **kwargs) -> dict:
        tracker.add_call()
        
        style_prompts = {
            "General Commercial": "Balanced visual description for general stock assets.",
            "Icons & Clipart": "Focus on style (flat, line, glyph), UI/UX functionality, and simple search intent keywords.",
            "Backgrounds & Patterns": "Focus on texture, copy space, backdrop, seamless, and wallpaper attributes.",
            "Characters & Mascot": "Focus on pose, expression, emotional theme, and persona."
        }
        style_guide = style_prompts.get(style_preset, style_prompts["General Commercial"])

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
        
        is_text_fallback = image_path.endswith('.svg') and not image_path.endswith('.jpg')

        max_retries = 3
        backoff_times = [2, 4, 8]

        for attempt in range(max_retries + 1):
            try:
                if self.provider == "Gemini":
                    if is_text_fallback:
                        with open(image_path, 'r', encoding='utf-8') as f:
                            svg_content = f.read()[:20000]
                        contents = [prompt, f"SVG Content:\\n{svg_content}"]
                    else:
                        import PIL.Image
                        img = PIL.Image.open(image_path)
                        contents = [prompt, img]
                        
                    response = self.gemini_client.models.generate_content(
                        model=self.model or 'gemini-1.5-flash',
                        contents=contents,
                        config=genai.types.GenerateContentConfig(
                            temperature=self.temperature,
                            response_mime_type="application/json",
                            response_schema=MetadataModel
                        )
                    )
                    return json.loads(response.text)

                elif self.provider in ["OpenAI", "9router"]:
                    if is_text_fallback:
                        with open(image_path, 'r', encoding='utf-8') as f:
                            svg_content = f.read()[:20000]
                        msgs = [{"role": "user", "content": f"{prompt}\\n\\nSVG Content:\\n{svg_content}"}]
                    else:
                        base64_image = self._encode_image(image_path)
                        msgs = [{"role": "user", "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                        ]}]
                        
                    default_model = "gpt-4o-mini" if self.provider == "OpenAI" else "9router/auto"
                    response = self.openai_client.chat.completions.create(
                        model=self.model or default_model,
                        messages=msgs,
                        temperature=self.temperature,
                        response_format={ "type": "json_object" }
                    )
                    return self._parse_json(response.choices[0].message.content)

                elif self.provider == "Mistral":
                    if is_text_fallback:
                        with open(image_path, 'r', encoding='utf-8') as f:
                            svg_content = f.read()[:20000]
                        content = f"{prompt}\\n\\nSVG Content:\\n{svg_content}"
                    else:
                        base64_image = self._encode_image(image_path)
                        content = [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                        ]
                    headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
                    data = {
                        "model": self.model or "mistral-small-latest",
                        "messages": [{"role": "user", "content": content}],
                        "temperature": self.temperature,
                        "response_format": {"type": "json_object"}
                    }
                    res = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=data, timeout=30)
                    res.raise_for_status()
                    return self._parse_json(res.json()["choices"][0]["message"]["content"])

                elif self.provider == "Groq":
                    if is_text_fallback:
                        with open(image_path, 'r', encoding='utf-8') as f:
                            svg_content = f.read()[:20000]
                        msgs = [{"role": "user", "content": f"{prompt}\\n\\nSVG Content:\\n{svg_content}"}]
                    else:
                        base64_image = self._encode_image(image_path)
                        msgs = [{"role": "user", "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                        ]}]
                        
                    response = self.groq_client.chat.completions.create(
                        model=self.model or "llama-3.2-11b-vision-preview",
                        messages=msgs,
                        temperature=self.temperature,
                        response_format={"type": "json_object"}
                    )
                    return self._parse_json(response.choices[0].message.content)
            except Exception as e:
                err_str = str(e)
                if "ConnectionRefused" in err_str or "ConnectError" in err_str or "Failed to connect" in err_str or "ECONNREFUSED" in err_str:
                    print(f"[ERROR] Connection refused to endpoint {self.base_url or 'API'}. Ensure server/proxy is active.")
                    is_retryable = True
                else:
                    is_retryable = "429" in err_str or "500" in err_str or "502" in err_str or "503" in err_str or "504" in err_str or "timeout" in err_str.lower() or "connection" in err_str.lower()
                
                if "401" in err_str or "invalid_api_key" in err_str.lower() or "authentication" in err_str.lower():
                    print(f"AI Service Error ({self.provider}): Authentication Failed. Check API Key.")
                    return self._fallback_metadata()

                if is_retryable and attempt < max_retries:
                    wait_time = backoff_times[attempt]
                    print(f"AI Service retry {attempt+1}/{max_retries} for {self.provider} after {wait_time}s due to: {err_str}")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"AI Service Error ({self.provider}): {e}")
                    return self._fallback_metadata()

        return self._fallback_metadata()

    def _parse_json(self, text: str) -> dict:
        try:
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1:
                return json.loads(text[start:end+1])
            return json.loads(text)
        except json.JSONDecodeError:
            return self._fallback_metadata()

    def _fallback_metadata(self) -> dict:
        return {
            "title": "Unknown Title",
            "description": "Metadata generation failed.",
            "category": "Unknown",
            "primary_category": "Miscellaneous",
            "secondary_category": "",
            "keywords": ["error", "fallback"]
        }
