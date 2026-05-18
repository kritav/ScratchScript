"""Claude (Anthropic) LLM provider."""

from __future__ import annotations

import os
from typing import Optional

from .base import Provider


class ClaudeProvider(Provider):
    def __init__(self, model: Optional[str] = None):
        self.model = model or "claude-sonnet-4-6"
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")

        try:
            import anthropic
        except ImportError:
            raise RuntimeError(
                "anthropic package not installed. Install with: pip install scratchscript[claude]"
            )

        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def generate(self, user_prompt: str, system_prompt: str) -> str:
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = response.content[0].text
        return self._strip_code_fences(text)

    async def fix(self, scratchscript: str, errors: str, system_prompt: str) -> str:
        fix_prompt = self._build_fix_prompt(scratchscript, errors)
        return await self.generate(fix_prompt, system_prompt)
