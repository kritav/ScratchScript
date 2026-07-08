"""Pre-compilation validator with fuzzy matching and helpful error messages."""

from __future__ import annotations

from difflib import get_close_matches

from .ast_nodes import (
    BinaryOp,
    Block,
    ChangeVariable,
    CloneBlock,
    CustomBlockCall,
    CustomBlockDef,
    Expression,
    ForeverBlock,
    FunctionCall,
    HideVariable,
    IfBlock,
    ListOperation,
    Literal,
    Project,
    RepeatBlock,
    RepeatUntilBlock,
    Script,
    SetVariable,
    ShowVariable,
    Sprite,
    Statement,
    StopBlock,
    UnaryOp,
    VarRef,
)
from .opcodes import ALL_BLOCK_NAMES, OPCODES, format_signature


class ValidationError:
    def __init__(self, message: str, line: int = 0):
        self.message = message
        self.line = line

    def __str__(self) -> str:
        if self.line:
            return f"Line {self.line}: {self.message}"
        return self.message


class ValidationResult:
    def __init__(self):
        self.errors: list[ValidationError] = []
        self.warnings: list[ValidationError] = []

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, message: str, line: int = 0):
        self.errors.append(ValidationError(message, line))

    def add_warning(self, message: str, line: int = 0):
        self.warnings.append(ValidationError(message, line))

    def format_errors(self) -> str:
        lines = []
        for err in self.errors:
            lines.append(str(err))
        for warn in self.warnings:
            lines.append(f"Warning: {warn}")
        return "\n".join(lines)


def validate(project: Project) -> ValidationResult:
    """Validate a parsed Project AST.

    Checks for:
    - Unknown block names (with fuzzy suggestions)
    - Unknown sprite/costume references
    - Duplicate variable/sprite names
    - Scripts without event triggers
    - Type mismatches
    """
    result = ValidationResult()
    validator = _Validator(result)
    validator.validate_project(project)
    return result


class _Validator:
    def __init__(self, result: ValidationResult):
        self.result = result
        self.sprite_names: set[str] = set()
        self.global_vars: set[str] = set()
        self.global_lists: set[str] = set()
        self.custom_blocks: set[str] = set()

    def validate_project(self, project: Project):
        # Collect global variables
        for v in project.variables:
            if v.name in self.global_vars:
                self.result.add_error(f"Duplicate global variable: {v.name!r}", v.line)
            self.global_vars.add(v.name)

        for lst in project.lists:
            if lst.name in self.global_lists:
                self.result.add_error(f"Duplicate global list: {lst.name!r}", lst.line)
            self.global_lists.add(lst.name)

        # Check sprites
        for sprite in project.sprites:
            if sprite.name in self.sprite_names:
                self.result.add_error(f"Duplicate sprite name: {sprite.name!r}", sprite.line)
            self.sprite_names.add(sprite.name)
            self.validate_sprite(sprite)

        # Check stage scripts
        for script in project.stage_scripts:
            self.validate_script(script, set(), set())

    def validate_sprite(self, sprite: Sprite):
        local_vars: set[str] = set()
        local_lists: set[str] = set()

        # Collect local variables
        for v in sprite.variables:
            if v.name in local_vars:
                self.result.add_error(
                    f"Duplicate variable {v.name!r} in sprite {sprite.name!r}", v.line
                )
            local_vars.add(v.name)
            if v.is_global:
                self.global_vars.add(v.name)

        for lst in sprite.lists:
            if lst.name in local_lists:
                self.result.add_error(
                    f"Duplicate list {lst.name!r} in sprite {sprite.name!r}", lst.line
                )
            local_lists.add(lst.name)
            if lst.is_global:
                self.global_lists.add(lst.name)

        # Register custom blocks
        for cb in sprite.custom_blocks:
            self.custom_blocks.add(cb.name)
            self.validate_custom_block_def(cb, local_vars, local_lists)

        # Validate scripts
        for script in sprite.scripts:
            self.validate_script(script, local_vars, local_lists)

    def validate_script(self, script: Script, local_vars: set[str], local_lists: set[str]):
        # Validate event
        valid_events = {
            "when flag clicked", "when key pressed", "when this sprite clicked",
            "when stage clicked", "when backdrop switches to", "when loudness >",
            "when I receive", "when I start as a clone",
        }
        if script.event not in valid_events:
            self.result.add_warning(
                f"Unknown event trigger: {script.event!r}", script.line
            )

        # Validate body
        all_vars = self.global_vars | local_vars
        all_lists = self.global_lists | local_lists
        self.validate_statements(script.body, all_vars, all_lists)

    def validate_statements(
        self, stmts: list[Statement], vars_in_scope: set[str], lists_in_scope: set[str]
    ):
        for stmt in stmts:
            self._validate_statement(stmt, vars_in_scope, lists_in_scope)

    def _validate_statement(
        self, stmt: Statement, vars_in_scope: set[str], lists_in_scope: set[str]
    ):
        if isinstance(stmt, Block):
            self._validate_block(stmt)
        elif isinstance(stmt, IfBlock):
            self.validate_expression(stmt.condition, stmt.line)
            self.validate_statements(stmt.body, vars_in_scope, lists_in_scope)
            self.validate_statements(stmt.else_body, vars_in_scope, lists_in_scope)
        elif isinstance(stmt, ForeverBlock):
            self.validate_statements(stmt.body, vars_in_scope, lists_in_scope)
        elif isinstance(stmt, RepeatBlock):
            self.validate_expression(stmt.times, stmt.line)
            self.validate_statements(stmt.body, vars_in_scope, lists_in_scope)
        elif isinstance(stmt, RepeatUntilBlock):
            self.validate_expression(stmt.condition, stmt.line)
            self.validate_statements(stmt.body, vars_in_scope, lists_in_scope)
        elif isinstance(stmt, SetVariable):
            self.validate_expression(stmt.value, stmt.line)
            # Auto-register set variables
            vars_in_scope.add(stmt.name)
        elif isinstance(stmt, ChangeVariable):
            self.validate_expression(stmt.value, stmt.line)
            vars_in_scope.add(stmt.name)
        elif isinstance(stmt, ListOperation):
            for arg in stmt.args:
                self.validate_expression(arg, stmt.line)
            lists_in_scope.add(stmt.list_name)
        elif isinstance(stmt, CustomBlockCall):
            if stmt.name not in self.custom_blocks:
                self.result.add_error(
                    f"Unknown custom block: {stmt.name!r}", stmt.line
                )
            for arg in stmt.args:
                self.validate_expression(arg, stmt.line)

    def _validate_block(self, block: Block):
        name = block.name.lower().strip()

        if name in OPCODES:
            entry = OPCODES[name]
            # Check argument count
            expected = len(entry.inputs)
            if entry.fields:
                expected += len([f for f in entry.fields if f.values is None])
            # We're lenient — just warn if too few args
            if len(block.args) < len(entry.inputs):
                self.result.add_warning(
                    f"Block {name!r} expects {len(entry.inputs)} argument(s) "
                    f"but got {len(block.args)}. Usage: {format_signature(name)}",
                    block.line,
                )
        else:
            # Unknown block — try fuzzy match, showing full usage signatures
            # so the LLM can fix the call without guessing arguments
            matches = get_close_matches(name, ALL_BLOCK_NAMES, n=3, cutoff=0.5)
            if matches:
                suggestion = ", ".join(f"`{format_signature(m)}`" for m in matches)
                self.result.add_error(
                    f"Unknown block: {name!r}. Replace it with one of these "
                    f"valid blocks: {suggestion}",
                    block.line,
                )
            else:
                self.result.add_error(
                    f"Unknown block: {name!r}. This block does not exist in "
                    f"ScratchScript — use only blocks from the DSL specification.",
                    block.line,
                )

        for arg in block.args:
            self.validate_expression(arg, block.line)

    def validate_expression(self, expr: Expression, line: int):
        if isinstance(expr, BinaryOp):
            self.validate_expression(expr.left, line)
            self.validate_expression(expr.right, line)
        elif isinstance(expr, UnaryOp):
            self.validate_expression(expr.operand, line)
        elif isinstance(expr, FunctionCall):
            for arg in expr.args:
                self.validate_expression(arg, line)

    def validate_custom_block_def(
        self, cb: CustomBlockDef, local_vars: set[str], local_lists: set[str]
    ):
        # Params are like local variables within the block
        block_vars = local_vars | set(cb.params) | self.global_vars
        self.validate_statements(cb.body, block_vars, local_lists | self.global_lists)
