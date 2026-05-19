"""Ollama LLM provider — local models via Ollama API."""

from __future__ import annotations

import json
import re
from typing import Callable, Optional

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

    async def generate(
        self,
        user_prompt: str,
        system_prompt: str,
        *,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        payload = {
            "model": self.model,
            "prompt": system_prompt + "\n\n" + user_prompt,
            "stream": on_token is not None,
        }

        async with httpx.AsyncClient(timeout=600.0) as client:
            if on_token is None:
                resp = await client.post(
                    f"{self.base_url}/api/generate", json=payload
                )
                resp.raise_for_status()
                data = resp.json()
                return self._strip_code_fences(data.get("response", ""))

            # Streaming mode — use aiter_bytes to avoid buffering issues
            print("[ollama] Streaming mode active")
            full_response: list[str] = []
            async with client.stream(
                "POST", f"{self.base_url}/api/generate", json=payload
            ) as resp:
                resp.raise_for_status()
                token_count = 0
                buf = b""
                async for raw in resp.aiter_bytes():
                    buf += raw
                    # Split on newlines — each line is a JSON object
                    while b"\n" in buf:
                        line_bytes, buf = buf.split(b"\n", 1)
                        line = line_bytes.decode("utf-8", errors="replace").strip()
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                            token = chunk.get("response", "")
                            if token:
                                full_response.append(token)
                                on_token(token)
                                token_count += 1
                                if token_count == 1:
                                    print("[ollama] First token received")
                        except (json.JSONDecodeError, KeyError):
                            continue
                # Handle any remaining data in buffer
                if buf.strip():
                    try:
                        chunk = json.loads(buf.decode("utf-8", errors="replace"))
                        token = chunk.get("response", "")
                        if token:
                            full_response.append(token)
                            on_token(token)
                            token_count += 1
                    except (json.JSONDecodeError, KeyError):
                        pass
                print(f"[ollama] Stream done, {token_count} tokens")

            text = "".join(full_response)
            text = self._strip_think_tags(text)
            return self._strip_code_fences(text)

    async def fix(
        self,
        scratchscript: str,
        errors: str,
        system_prompt: str,
        *,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        fix_prompt = self._build_fix_prompt(scratchscript, errors)
        return await self.generate(fix_prompt, system_prompt, on_token=on_token)

    @staticmethod
    def _strip_think_tags(text: str) -> str:
        """Remove <think>...</think> blocks from the response."""
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
