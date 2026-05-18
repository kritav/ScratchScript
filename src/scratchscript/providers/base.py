"""Abstract base class for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Provider(ABC):
    """Base interface for all LLM providers."""

    @abstractmethod
    async def generate(self, user_prompt: str, system_prompt: str) -> str:
        """Generate ScratchScript from a user prompt.

        Args:
            user_prompt: The user's natural language description
            system_prompt: The system prompt with DSL spec

        Returns:
            Generated ScratchScript code
        """
        ...

    @abstractmethod
    async def fix(self, scratchscript: str, errors: str, system_prompt: str) -> str:
        """Fix ScratchScript code based on compiler errors.

        Args:
            scratchscript: The original ScratchScript code that failed
            errors: Compiler error messages
            system_prompt: The system prompt with DSL spec

        Returns:
            Fixed ScratchScript code
        """
        ...

    def _build_fix_prompt(self, scratchscript: str, errors: str) -> str:
        return (
            f"The following ScratchScript code has errors. Fix them and return ONLY "
            f"the corrected ScratchScript code with no explanation or markdown fences.\n\n"
            f"--- ScratchScript Code ---\n{scratchscript}\n\n"
            f"--- Compiler Errors ---\n{errors}\n\n"
            f"Return ONLY the fixed ScratchScript code:"
        )

    def _strip_code_fences(self, text: str) -> str:
        """Remove markdown code fences if present."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```scratchscript or ```)
            lines = lines[1:]
            # Remove last line if it's ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        return text.strip()
