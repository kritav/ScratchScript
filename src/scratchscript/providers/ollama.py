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
        self.model = model or self._detect_model(base_url)
        self.base_url = base_url

    @staticmethod
    def _detect_model(base_url: str) -> str:
        """Pick the first installed model, fall back to 'llama3.1'."""
        try:
            resp = httpx.get(f"{base_url}/api/tags", timeout=3.0)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                if models:
                    name = models[0].get("name", "")
                    print(f"[ollama] Using model: {name}")
                    return name
        except Exception:
            pass
        return "llama3.1"

    async def generate(self, user_prompt: str, system_prompt: str) -> str:
        payload = {
            "model": self.model,
            "prompt": system_prompt + "\n\n" + user_prompt,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=600.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/generate", json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            return self._strip_code_fences(data.get("response", ""))

    async def fix(self, scratchscript: str, errors: str, system_prompt: str) -> str:
        fix_prompt = self._build_fix_prompt(scratchscript, errors)
        return await self.generate(fix_prompt, system_prompt)
