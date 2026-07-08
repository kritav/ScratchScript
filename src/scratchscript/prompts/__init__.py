"""Prompt management for ScratchScript."""

from pathlib import Path

_PROMPT_DIR = Path(__file__).parent


def get_system_prompt() -> str:
    """Load the system prompt with DSL spec."""
    from .examples import FEW_SHOT_EXAMPLES

    system_text = (_PROMPT_DIR / "system.txt").read_text()
    examples_text = "\n\n## Examples\n\n" + FEW_SHOT_EXAMPLES
    return system_text + examples_text


def build_asset_hint(user_prompt: str, library) -> str:
    """Build a prompt section listing real library asset names relevant to
    the request, so the model picks from verified names instead of guessing."""
    found = library.find_relevant_names(user_prompt)
    sections = []
    for label, names in (
        ("Costumes", found["costumes"]),
        ("Backdrops", found["backdrops"]),
        ("Sounds", found["sounds"]),
    ):
        if names:
            sections.append(f"{label}: " + ", ".join(f'"{n}"' for n in names))

    if not sections:
        return ""

    return (
        "\n\n## Built-in Assets Matching This Request\n\n"
        "These Scratch library assets match the request. Use these EXACT "
        "names — do not invent asset names:\n\n"
        + "\n".join(sections)
        + '\n\nIf none fit a sprite, fall back to costumes "cat-a", "cat-b".'
    )
