"""AST node definitions for ScratchScript."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union


# --- Expressions ---


@dataclass
class Literal:
    value: Union[str, int, float]
    line: int = 0


@dataclass
class ColorLiteral:
    value: str  # "#rrggbb"
    line: int = 0


@dataclass
class BinaryOp:
    op: str  # +, -, *, /, >, <, =, and, or, mod, join
    left: Expression
    right: Expression
    line: int = 0


@dataclass
class UnaryOp:
    op: str  # not, -
    operand: Expression
    line: int = 0


@dataclass
class FunctionCall:
    name: str
    args: list[Expression] = field(default_factory=list)
    line: int = 0


@dataclass
class VarRef:
    name: str
    line: int = 0


@dataclass
class ListRef:
    name: str
    line: int = 0


Expression = Union[Literal, ColorLiteral, BinaryOp, UnaryOp, FunctionCall, VarRef, ListRef]


# --- Blocks (statements) ---


@dataclass
class Block:
    name: str
    args: list[Expression] = field(default_factory=list)
    line: int = 0


@dataclass
class IfBlock:
    condition: Expression
    body: list[Statement] = field(default_factory=list)
    else_body: list[Statement] = field(default_factory=list)
    line: int = 0


@dataclass
class ForeverBlock:
    body: list[Statement] = field(default_factory=list)
    line: int = 0


@dataclass
class RepeatBlock:
    times: Expression
    body: list[Statement] = field(default_factory=list)
    line: int = 0


@dataclass
class RepeatUntilBlock:
    condition: Expression
    body: list[Statement] = field(default_factory=list)
    line: int = 0


@dataclass
class SetVariable:
    name: str
    value: Expression
    line: int = 0


@dataclass
class ChangeVariable:
    name: str
    value: Expression
    line: int = 0


@dataclass
class ShowVariable:
    name: str
    line: int = 0


@dataclass
class HideVariable:
    name: str
    line: int = 0


@dataclass
class ListOperation:
    """add/delete/insert/replace on a list."""

    operation: str  # add, delete, insert, replace
    list_name: str
    args: list[Expression] = field(default_factory=list)
    line: int = 0


@dataclass
class CustomBlockDef:
    name: str
    params: list[str] = field(default_factory=list)
    param_types: list[str] = field(default_factory=list)  # "string", "boolean"
    body: list[Statement] = field(default_factory=list)
    line: int = 0


@dataclass
class CustomBlockCall:
    name: str
    args: list[Expression] = field(default_factory=list)
    line: int = 0


@dataclass
class CloneBlock:
    """create clone of / when I start as a clone / delete this clone."""

    action: str  # "create", "delete"
    target: Optional[str] = None  # sprite name or "myself"
    line: int = 0


@dataclass
class StopBlock:
    mode: str  # "all", "this script", "other scripts in sprite"
    line: int = 0


Statement = Union[
    Block,
    IfBlock,
    ForeverBlock,
    RepeatBlock,
    RepeatUntilBlock,
    SetVariable,
    ChangeVariable,
    ShowVariable,
    HideVariable,
    ListOperation,
    CustomBlockDef,
    CustomBlockCall,
    CloneBlock,
    StopBlock,
]


# --- Top-level structures ---


@dataclass
class VariableDecl:
    name: str
    initial_value: Union[str, int, float] = 0
    is_global: bool = False
    line: int = 0


@dataclass
class ListDecl:
    name: str
    initial_values: list[Union[str, int, float]] = field(default_factory=list)
    is_global: bool = False
    line: int = 0


@dataclass
class Script:
    event: str  # "when flag clicked", "when key ... pressed", etc.
    event_args: list[str] = field(default_factory=list)
    body: list[Statement] = field(default_factory=list)
    line: int = 0


@dataclass
class Sprite:
    name: str
    costumes: list[str] = field(default_factory=list)
    sounds: list[str] = field(default_factory=list)
    x: float = 0
    y: float = 0
    size: float = 100
    direction: float = 90
    visible: bool = True
    rotation_style: str = "all around"
    layer: Optional[int] = None
    variables: list[VariableDecl] = field(default_factory=list)
    lists: list[ListDecl] = field(default_factory=list)
    scripts: list[Script] = field(default_factory=list)
    custom_blocks: list[CustomBlockDef] = field(default_factory=list)
    line: int = 0


@dataclass
class Project:
    name: str = "ScratchScript Project"
    backdrops: list[str] = field(default_factory=list)
    tempo: int = 60
    volume: int = 100
    variables: list[VariableDecl] = field(default_factory=list)
    lists: list[ListDecl] = field(default_factory=list)
    sprites: list[Sprite] = field(default_factory=list)
    stage_scripts: list[Script] = field(default_factory=list)
    stage_custom_blocks: list[CustomBlockDef] = field(default_factory=list)
    line: int = 0
