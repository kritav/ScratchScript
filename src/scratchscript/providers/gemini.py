"""Google Gemini LLM provider."""

from __future__ import annotations

import os
from typing import Optional

from .base import Provider


class GeminiProvider(Provider):
    def __init__(self, model: Optional[str] = None):
        self.model = model or "gemini-2.0-flash"
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY environment variable not set")

        try:
            import google.generativeai as genai
        except ImportError:
            raise RuntimeError(
                "google-generativeai package not installed. "
                "Install with: pip install scratchscript[gemini]"
            )

        genai.configure(api_key=api_key)
        self._genai = genai

    async def generate(self, user_prompt: str, system_prompt: str) -> str:
        model = self._genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system_prompt,
            generation_config=self._genai.GenerationConfig(temperature=0.3),
        )
        response = await model.generate_content_async(user_prompt)
        text = response.text or ""
        return self._strip_code_fences(text)

    async def fix(self, scratchscript: str, errors: str, system_prompt: str) -> str:
        fix_prompt = self._build_fix_prompt(scratchscript, errors)
        return await self.generate(fix_prompt, system_prompt)
