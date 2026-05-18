"""Prompt management for ScratchScript."""

from pathlib import Path

_PROMPT_DIR = Path(__file__).parent


def get_system_prompt() -> str:
    """Load the system prompt with DSL spec."""
    from .examples import FEW_SHOT_EXAMPLES

    system_text = (_PROMPT_DIR / "system.txt").read_text()
    examples_text = "\n\n## Examples\n\n" + FEW_SHOT_EXAMPLES
    return system_text + examples_text
