"""Ollama LLM provider — local models via Ollama API."""

from __future__ import annotations

from typing import Optional

import httpx

from .base import Provider


class OllamaProvider(Provider):
    def __init__(
        self,
        model: Optional[str] = None,
        base_url: str = "http://localhost:11434",
    ):
        self.model = model or "llama3.1"
        self.base_url = base_url

    async def generate(self, user_prompt: str, system_prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": 0.3},
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return self._strip_code_fences(
                data.get("message", {}).get("content", "")
            )

    async def fix(self, scratchscript: str, errors: str, system_prompt: str) -> str:
        fix_prompt = self._build_fix_prompt(scratchscript, errors)
        return await self.generate(fix_prompt, system_prompt)
