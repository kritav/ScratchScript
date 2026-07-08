"""Deterministic auto-repair for near-miss block, event, and reporter names.

Runs after parsing, before validation. LLM-hallucinated names that are a
confident fuzzy match for a real block are rewritten in place, so they never
reach codegen (which silently drops unknown statements and turns unknown
reporters into 0) and never burn an LLM fix round-trip.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Optional

from .ast_nodes import (
    BinaryOp,
    Block,
    ChangeVariable,
    CustomBlockCall,
    CustomBlockDef,
    Expression,
    ForeverBlock,
    FunctionCall,
    IfBlock,
    ListOperation,
    Project,
    RepeatBlock,
    RepeatUntilBlock,
    Script,
    SetVariable,
    Sprite,
    Statement,
    UnaryOp,
)
from .opcodes import OPCODES

# A match must score at least CONFIDENCE, and beat the runner-up by MARGIN,
# to be applied without asking the LLM.
CONFIDENCE = 0.8
MARGIN = 0.1

_STATEMENT_NAMES = [
    n for n, e in OPCODES.items() if not (e.is_hat or e.is_reporter or e.is_boolean)
]
_REPORTER_NAMES = [n for n, e in OPCODES.items() if e.is_reporter or e.is_boolean]
_HAT_NAMES = [n for n, e in OPCODES.items() if e.is_hat]

# Reporter spellings the parser accepts outside the opcode table — never
# rewrite these (see parser func_reporters).
_SPECIAL_REPORTERS = {
    "pick random", "join", "letter of", "length of", "contains", "round",
    "item of", "item # of in", "length of list", "list contains", "distance to",
}


def best_match(
    name: str,
    candidates: list[str],
    confidence: float = CONFIDENCE,
    margin: float = MARGIN,
) -> Optional[str]:
    """Return the single confident fuzzy match for name, or None.

    None means either nothing scored above the confidence cutoff, or the top
    two candidates were too close to call (within margin).
    """
    scored = sorted(
        ((SequenceMatcher(None, name, c).ratio(), c) for c in candidates),
        reverse=True,
    )
    if not scored or scored[0][0] < confidence:
        return None
    if len(scored) > 1 and scored[0][0] - scored[1][0] < margin:
        return None
    return scored[0][1]


def repair_project(project: Project) -> list[str]:
    """Rewrite confident near-miss names in place. Returns repair notes."""
    repairer = _Repairer()
    repairer.repair_project(project)
    return repairer.notes


class _Repairer:
    def __init__(self):
        self.notes: list[str] = []

    def repair_project(self, project: Project):
        for sprite in project.sprites:
            self._repair_sprite(sprite)
        for script in project.stage_scripts:
            self._repair_script(script)
        for cb in project.stage_custom_blocks:
            self._repair_statements(cb.body)

    def _repair_sprite(self, sprite: Sprite):
        for script in sprite.scripts:
            self._repair_script(script)
        for cb in sprite.custom_blocks:
            self._repair_statements(cb.body)

    def _repair_script(self, script: Script):
        event = script.event.lower().strip()
        if event not in _HAT_NAMES:
            match = best_match(event, _HAT_NAMES)
            if match:
                self._note("event", script.event, match, script.line)
                script.event = match
        self._repair_statements(script.body)

    def _repair_statements(self, stmts: list[Statement]):
        for stmt in stmts:
            self._repair_statement(stmt)

    def _repair_statement(self, stmt: Statement):
        if isinstance(stmt, Block):
            name = stmt.name.lower().strip()
            if name not in OPCODES:
                match = best_match(name, _STATEMENT_NAMES)
                if match:
                    self._note("block", stmt.name, match, stmt.line)
                    stmt.name = match
            for arg in stmt.args:
                self._repair_expression(arg)
        elif isinstance(stmt, IfBlock):
            self._repair_expression(stmt.condition)
            self._repair_statements(stmt.body)
            self._repair_statements(stmt.else_body)
        elif isinstance(stmt, ForeverBlock):
            self._repair_statements(stmt.body)
        elif isinstance(stmt, RepeatBlock):
            self._repair_expression(stmt.times)
            self._repair_statements(stmt.body)
        elif isinstance(stmt, RepeatUntilBlock):
            self._repair_expression(stmt.condition)
            self._repair_statements(stmt.body)
        elif isinstance(stmt, (SetVariable, ChangeVariable)):
            self._repair_expression(stmt.value)
        elif isinstance(stmt, (ListOperation, CustomBlockCall)):
            for arg in stmt.args:
                self._repair_expression(arg)
        elif isinstance(stmt, CustomBlockDef):
            self._repair_statements(stmt.body)

    def _repair_expression(self, expr: Expression):
        if isinstance(expr, BinaryOp):
            self._repair_expression(expr.left)
            self._repair_expression(expr.right)
        elif isinstance(expr, UnaryOp):
            self._repair_expression(expr.operand)
        elif isinstance(expr, FunctionCall):
            name = expr.name.lower().strip()
            if name not in OPCODES and name not in _SPECIAL_REPORTERS:
                match = best_match(name, _REPORTER_NAMES)
                if match:
                    self._note("reporter", expr.name, match, expr.line)
                    expr.name = match
            for arg in expr.args:
                self._repair_expression(arg)

    def _note(self, kind: str, original: str, fixed: str, line: int):
        prefix = f"Line {line}: " if line else ""
        self.notes.append(f"{prefix}auto-repaired {kind} {original!r} to {fixed!r}")
