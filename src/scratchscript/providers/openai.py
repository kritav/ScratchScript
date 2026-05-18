"""OpenAI LLM provider."""

from __future__ import annotations

import os
from typing import Optional

from .base import Provider


class OpenAIProvider(Provider):
    def __init__(self, model: Optional[str] = None):
        self.model = model or "gpt-4o"
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY environment variable not set")

        try:
            import openai
        except ImportError:
            raise RuntimeError(
                "openai package not installed. Install with: pip install scratchscript[openai]"
            )

        self.client = openai.AsyncOpenAI(api_key=api_key)

    async def generate(self, user_prompt: str, system_prompt: str) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )
        text = response.choices[0].message.content or ""
        return self._strip_code_fences(text)

    async def fix(self, scratchscript: str, errors: str, system_prompt: str) -> str:
        fix_prompt = self._build_fix_prompt(scratchscript, errors)
        return await self.generate(fix_prompt, system_prompt)
