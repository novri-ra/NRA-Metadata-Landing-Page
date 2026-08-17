import json
import base64
import requests
from google import genai
from openai import OpenAI
from pydantic import BaseModel, Field
from packages.shared_utils.tracker import tracker

class MetadataModel(BaseModel):
    title: str = Field(description="A concise title")
    description: str = Field(description="A detailed description")
    category: str = Field(description="A broad category")
    keywords: list[str] = Field(description="Array of descriptive keywords")

class AIService:
    def __init__(self, provider: str, api_key: str):
        self.provider = provider
        self.api_key = api_key
        if self.provider == "Gemini":
            self.gemini_client = genai.Client(api_key=self.api_key)
        elif self.provider == "OpenAI":
            self.openai_client = OpenAI(api_key=self.api_key)

    def _encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def generate_metadata(self, image_path: str, min_kw: int, max_kw: int, style_preset: str = "General Commercial") -> dict:
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
        "title": a concise title,
        "description": a detailed description,
        "category": a broad category,
        "keywords": an array of {min_kw} to {max_kw} descriptive keywords.
        Style Focus: {style_guide}
        Return ONLY valid JSON.
        """
        
        is_text_fallback = image_path.endswith('.svg') and not image_path.endswith('.jpg')

        try:
            if self.provider == "Gemini":
                if is_text_fallback:
                    with open(image_path, 'r', encoding='utf-8') as f:
                        svg_content = f.read()[:20000] # Cap 20KB
                    contents = [prompt, f"SVG Content:\n{svg_content}"]
                else:
                    import PIL.Image
                    img = PIL.Image.open(image_path)
                    contents = [prompt, img]
                    
                response = self.gemini_client.models.generate_content(
                    model='gemini-1.5-flash',
                    contents=contents,
                    config=genai.types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=MetadataModel
                    )
                )
                return json.loads(response.text)

            elif self.provider == "OpenAI":
                if is_text_fallback:
                    with open(image_path, 'r', encoding='utf-8') as f:
                        svg_content = f.read()[:20000]
                    msgs = [{"role": "user", "content": f"{prompt}\n\nSVG Content:\n{svg_content}"}]
                else:
                    base64_image = self._encode_image(image_path)
                    msgs = [{"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]}]
                    
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=msgs,
                    response_format={ "type": "json_object" }
                )
                return self._parse_json(response.choices[0].message.content)

            elif self.provider == "Mistral":
                if is_text_fallback:
                    with open(image_path, 'r', encoding='utf-8') as f:
                        svg_content = f.read()[:20000]
                    content = f"{prompt}\n\nSVG Content:\n{svg_content}"
                else:
                    base64_image = self._encode_image(image_path)
                    content = [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": f"data:image/jpeg;base64,{base64_image}"}
                    ]
                headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
                data = {
                    "model": "pixtral-12b-2409",
                    "messages": [{"role": "user", "content": content}],
                    "response_format": {"type": "json_object"}
                }
                res = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=data)
                res.raise_for_status()
                return self._parse_json(res.json()["choices"][0]["message"]["content"])
        except Exception as e:
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
            "keywords": ["error", "fallback"]
        }