"""ScratchScript reviewer — LLM-based critique of generated code before compilation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from .providers.base import Provider

REVIEWER_SYSTEM_PROMPT = """\
You are a Scratch project reviewer. You receive ScratchScript code (a DSL that compiles to Scratch .sb3 files) and the original user request. Your job is to critique the code for design quality, logical correctness, and Scratch-specific best practices — not syntax. The compiler handles syntax. You handle everything else.

You are an expert Scratch developer who has built hundreds of projects. You think like a skilled human Scratch user, not like a software engineer. Scratch projects should be simple, direct, and take advantage of how Scratch actually works — not mirror patterns from professional programming languages.

## What You Check

### Unnecessary Complexity
- Manager/controller sprites (names like "GameManager", "Controller", "ScoreTracker"). These should almost always be eliminated. Their logic belongs in the sprites that do things, or in the Stage.
- Too many variables. If a variable is written once and read once, inline the value.
- Redundant sprites. If two sprites have identical behavior, use one sprite with clones.
- Over-engineered structure. Don't create abstractions a 12-year-old wouldn't think of.

### Scratch-Specific Mistakes
- wait blocks inside forever loops without a reason. Scratch handles frame timing. Adding waits to movement/collision/input loops makes things laggy. Waits only belong when deliberately pacing something (spawning enemies every N seconds).
- Multiple costumes instead of clones for repeated objects. If a sprite has "pipe-top" and "pipe-bottom" as costumes to represent separate game objects, use clones with position offsets instead.
- Variables as event flags instead of broadcasts. If code sets gameOver to 1 and polls it in forever loops, use broadcast "game over" and when I receive instead.
- Stage logic in a sprite. Score display, level transitions, backdrop changes belong in Stage scripts.
- Missing stop all or stop this script when game ends. Forever loops keep running after game over otherwise.
- Positions outside Scratch's coordinate system. Stage is 480x360, x: -240 to 240, y: -180 to 180.

### Logic and Gameplay Errors
- Missing collision detection between sprites that should interact.
- Missing game over condition.
- Missing score counting when the game should have a score.
- Clones that are created but never deleted (hits 300 clone limit).
- Missing initialization — variables and positions not reset on green flag.
- Broken movement math (gravity should use velocity, not fixed position changes).
- Costume names that don't exist in Scratch's library. Real assets include: "cat-a", "cat-b", "bear-a", "parrot-a", "parrot-b", "ball-a", "paddle", "button3". Flag invented names like "pipe-top", "bird-flying", "enemy-walk-1".
- Sound names that don't exist. Real sounds include: "pop", "Meow", "Cave", "Boing", "Coin", "Drum".

### Completeness
- Missing features the user asked for.
- Missing user interaction (no key presses, mouse, or clicking in an interactive project).
- Missing visual/audio feedback when events happen (scoring, losing, collecting).

## Output Format

Respond with ONLY this structured format. No preamble, no markdown fences.

If the code is good:

VERDICT: PASS

If you find problems:

VERDICT: REVISE

ISSUE: [short title]
SEVERITY: [critical / major / minor]
WHERE: [sprite name or "project-level"]
PROBLEM: [1-2 sentences]
FIX: [1-2 sentences]

ISSUE: [next issue]
...

Severity: critical = project won't work as intended. major = works but significant quality issues. minor = small improvements.

Only flag real problems. Don't nitpick. Don't suggest features the user didn't ask for. Don't critique DSL syntax. Keep fixes concrete and actionable."""


@dataclass
class Issue:
    title: str
    severity: str  # "critical", "major", "minor"
    where: str  # sprite name or "project-level"
    problem: str
    fix: str


@dataclass
class ReviewResult:
    verdict: str  # "PASS" or "REVISE"
    issues: list[Issue] = field(default_factory=list)

    def format_for_generator(self) -> str:
        """Format issues as text to feed back to the generator LLM for revision."""
        if not self.issues:
            return ""
        lines = ["The reviewer found these problems with your code:\n"]
        for i, issue in enumerate(self.issues, 1):
            lines.append(
                f"{i}. [{issue.severity}] {issue.where}: {issue.problem}"
            )
            lines.append(f"   Fix: {issue.fix}")
        return "\n".join(lines)

    def summary(self) -> str:
        """One-line summary for status display."""
        if not self.issues:
            return "No issues found"
        counts: dict[str, int] = {}
        for issue in self.issues:
            counts[issue.severity] = counts.get(issue.severity, 0) + 1
        parts = []
        for sev in ("critical", "major", "minor"):
            if sev in counts:
                parts.append(f"{counts[sev]} {sev}")
        return f"{len(self.issues)} issues ({', '.join(parts)})"


class Reviewer:
    """Reviews generated ScratchScript for design quality and correctness."""

    def __init__(self, provider: Provider):
        self.provider = provider

    async def review(
        self,
        user_request: str,
        scratchscript: str,
        *,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> ReviewResult:
        prompt = (
            f"USER REQUEST: {user_request}\n\n"
            f"GENERATED SCRATCHSCRIPT:\n```\n{scratchscript}\n```"
        )
        gen_kwargs: dict = {}
        if on_token is not None:
            gen_kwargs["on_token"] = on_token
        try:
            response = await self.provider.generate(
                prompt, REVIEWER_SYSTEM_PROMPT, **gen_kwargs
            )
        except TypeError:
            # Provider doesn't support on_token
            response = await self.provider.generate(prompt, REVIEWER_SYSTEM_PROMPT)
        return self._parse_response(response)

    @staticmethod
    def _parse_response(response: str) -> ReviewResult:
        """Parse the structured VERDICT/ISSUE format into a ReviewResult.

        Tolerant of imperfect formatting from local models.
        """
        text = response.strip()

        # Detect verdict
        verdict = "REVISE"
        verdict_match = re.search(r"VERDICT:\s*(PASS|REVISE)", text, re.IGNORECASE)
        if verdict_match:
            verdict = verdict_match.group(1).upper()

        if verdict == "PASS":
            return ReviewResult(verdict="PASS")

        # Parse issues
        issues: list[Issue] = []
        issue_blocks = re.split(r"\nISSUE:\s*", text)
        # First element is everything before the first ISSUE
        for block in issue_blocks[1:]:
            title_line, *rest = block.strip().split("\n", 1)
            title = title_line.strip()
            body = rest[0] if rest else ""

            severity_m = re.search(r"SEVERITY:\s*(\w+)", body, re.IGNORECASE)
            where_m = re.search(r"WHERE:\s*(.+)", body, re.IGNORECASE)
            problem_m = re.search(r"PROBLEM:\s*(.+)", body, re.IGNORECASE)
            fix_m = re.search(r"FIX:\s*(.+)", body, re.IGNORECASE)

            issues.append(Issue(
                title=title,
                severity=(severity_m.group(1).lower() if severity_m else "major"),
                where=(where_m.group(1).strip() if where_m else "project-level"),
                problem=(problem_m.group(1).strip() if problem_m else title),
                fix=(fix_m.group(1).strip() if fix_m else ""),
            ))

        # If we couldn't parse any structured issues but verdict is REVISE,
        # treat the entire response as freeform feedback
        if not issues and verdict == "REVISE":
            issues.append(Issue(
                title="Review feedback",
                severity="major",
                where="project-level",
                problem=text[:500],
                fix="See reviewer feedback above",
            ))

        return ReviewResult(verdict=verdict, issues=issues)


def build_revision_prompt(
    user_request: str, scratchscript: str, review: ReviewResult
) -> str:
    """Build a prompt for the generator to revise code based on reviewer feedback."""
    return (
        f"The original request was: {user_request}\n\n"
        f"You generated this ScratchScript:\n{scratchscript}\n\n"
        f"{review.format_for_generator()}\n\n"
        f"Generate a corrected version of the ScratchScript that fixes all the issues "
        f"listed above. Output ONLY the corrected ScratchScript, nothing else."
    )
