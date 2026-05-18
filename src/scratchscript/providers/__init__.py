"""LLM provider auto-detection and factory."""

from __future__ import annotations

import os
from typing import Optional

from .base import Provider


async def detect_provider(
    provider_name: Optional[str] = None,
    model: Optional[str] = None,
) -> Provider:
    """Auto-detect and return an LLM provider.

    Priority: explicit flag > Ollama (if running) > first available API key.
    """
    if provider_name:
        return _create_provider(provider_name, model)

    # Try Ollama first
    try:
        import httpx

        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            if resp.status_code == 200:
                from .ollama import OllamaProvider

                return OllamaProvider(model=model)
    except Exception:
        pass

    # Check for API keys
    if os.environ.get("ANTHROPIC_API_KEY"):
        from .claude import ClaudeProvider

        return ClaudeProvider(model=model)

    if os.environ.get("OPENAI_API_KEY"):
        from .openai import OpenAIProvider

        return OpenAIProvider(model=model)

    if os.environ.get("GEMINI_API_KEY"):
        from .gemini import GeminiProvider

        return GeminiProvider(model=model)

    raise RuntimeError(
        "No LLM provider available. Either:\n"
        "  - Start Ollama locally (ollama serve)\n"
        "  - Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or GEMINI_API_KEY\n"
        "  - Use --provider to specify one explicitly"
    )


def _create_provider(name: str, model: Optional[str] = None) -> Provider:
    name = name.lower()
    if name == "ollama":
        from .ollama import OllamaProvider

        return OllamaProvider(model=model)
    elif name == "claude":
        from .claude import ClaudeProvider

        return ClaudeProvider(model=model)
    elif name == "openai":
        from .openai import OpenAIProvider

        return OpenAIProvider(model=model)
    elif name == "gemini":
        from .gemini import GeminiProvider

        return GeminiProvider(model=model)
    else:
        raise ValueError(f"Unknown provider: {name!r}. Use: ollama, claude, openai, gemini")
