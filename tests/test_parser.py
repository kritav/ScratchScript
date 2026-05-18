"""Tests for the ScratchScript parser."""

import pytest
from scratchscript.compiler.parser import parse, ParseError
from scratchscript.compiler.ast_nodes import (
    Block, IfBlock, ForeverBlock, RepeatBlock, RepeatUntilBlock,
    SetVariable, ChangeVariable, Literal, BinaryOp, UnaryOp, VarRef,
    FunctionCall, CustomBlockDef, CustomBlockCall, ListOperation,
    StopBlock, CloneBlock,
)


class TestProjectParsing:
    def test_empty_project(self):
        p = parse("project MyProject")
        assert p.name == "MyProject"
        assert p.sprites == []

    def test_project_with_sprite(self):
        src = """\
project
  sprite Cat
    costumes "cat-a"
"""
        p = parse(src)
        assert len(p.sprites) == 1
        assert p.sprites[0].name == "Cat"
        assert p.sprites[0].costumes == ["cat-a"]

    def test_project_with_backdrops(self):
        src = """\
project
  backdrops "Blue Sky"
  sprite Cat
    costumes "cat-a"
"""
        p = parse(src)
        assert p.backdrops == ["Blue Sky"]


class TestSpriteParsing:
    def test_sprite_properties(self):
        src = """\
project
  sprite Ball
    costumes "ball-a"
    position 100, 50
    size 75
    direction 180
"""
        p = parse(src)
        s = p.sprites[0]
        assert s.name == "Ball"
        assert s.x == 100
        assert s.y == 50
        assert s.size == 75
        assert s.direction == 180

    def test_sprite_variable(self):
        src = """\
project
  sprite Cat
    variable score = 0
"""
        p = parse(src)
        assert len(p.sprites[0].variables) == 1
        assert p.sprites[0].variables[0].name == "score"
        assert p.sprites[0].variables[0].initial_value == 0

    def test_sprite_list(self):
        src = """\
project
  sprite Cat
    list items
"""
        p = parse(src)
        assert len(p.sprites[0].lists) == 1
        assert p.sprites[0].lists[0].name == "items"


class TestScriptParsing:
    def test_when_flag_clicked(self):
        src = """\
project
  sprite Cat
    script
      when flag clicked
        move 10
"""
        p = parse(src)
        script = p.sprites[0].scripts[0]
        assert script.event == "when flag clicked"
        assert len(script.body) == 1

    def test_when_key_pressed(self):
        src = """\
project
  sprite Cat
    script
      when key space pressed
        move 10
"""
        p = parse(src)
        script = p.sprites[0].scripts[0]
        assert script.event == "when key pressed"
        assert script.event_args == ["space"]

    def test_when_key_arrow_pressed(self):
        src = """\
project
  sprite Cat
    script
      when key up arrow pressed
        change y by 10
"""
        p = parse(src)
        script = p.sprites[0].scripts[0]
        assert script.event == "when key pressed"
        assert script.event_args == ["up arrow"]

    def test_when_receive(self):
        src = """\
project
  sprite Cat
    script
      when I receive "game over"
        stop all
"""
        p = parse(src)
        script = p.sprites[0].scripts[0]
        assert script.event == "when I receive"
        assert script.event_args == ["game over"]


class TestControlFlow:
    def test_if_block(self):
        src = """\
project
  sprite Cat
    script
      when flag clicked
        if touching "edge"
          turn right 180
"""
        p = parse(src)
        body = p.sprites[0].scripts[0].body
        assert len(body) == 1
        assert isinstance(body[0], IfBlock)
        assert len(body[0].body) == 1

    def test_if_else_block(self):
        src = """\
project
  sprite Cat
    script
      when flag clicked
        if x position > 200
          set x to -200
        else
          move 10
"""
        p = parse(src)
        body = p.sprites[0].scripts[0].body
        assert isinstance(body[0], IfBlock)
        assert len(body[0].body) == 1
        assert len(body[0].else_body) == 1

    def test_forever_block(self):
        src = """\
project
  sprite Cat
    script
      when flag clicked
        forever
          move 10
          if on edge bounce
"""
        p = parse(src)
        body = p.sprites[0].scripts[0].body
        assert isinstance(body[0], ForeverBlock)
        assert len(body[0].body) == 2

    def test_repeat_block(self):
        src = """\
project
  sprite Cat
    script
      when flag clicked
        repeat 10
          move 5
          turn right 36
"""
        p = parse(src)
        body = p.sprites[0].scripts[0].body
        assert isinstance(body[0], RepeatBlock)
        assert isinstance(body[0].times, Literal)
        assert body[0].times.value == 10

    def test_repeat_until_block(self):
        src = """\
project
  sprite Cat
    script
      when flag clicked
        repeat until touching "edge"
          move 5
"""
        p = parse(src)
        body = p.sprites[0].scripts[0].body
        assert isinstance(body[0], RepeatUntilBlock)


class TestExpressions:
    def test_binary_op(self):
        src = """\
project
  sprite Cat
    script
      when flag clicked
        set x to 1 + 2
"""
        p = parse(src)
        stmt = p.sprites[0].scripts[0].body[0]
        assert isinstance(stmt, SetVariable)
        assert isinstance(stmt.value, BinaryOp)
        assert stmt.value.op == "+"

    def test_comparison(self):
        src = """\
project
  sprite Cat
    script
      when flag clicked
        if score > 10
          say "You win!"
"""
        p = parse(src)
        cond = p.sprites[0].scripts[0].body[0]
        assert isinstance(cond, IfBlock)
        assert isinstance(cond.condition, BinaryOp)
        assert cond.condition.op == ">"

    def test_logical_and(self):
        src = """\
project
  sprite Cat
    script
      when flag clicked
        if touching "edge" and score > 5
          say "combo!"
"""
        p = parse(src)
        cond = p.sprites[0].scripts[0].body[0].condition
        assert isinstance(cond, BinaryOp)
        assert cond.op == "and"

    def test_not_expression(self):
        src = """\
project
  sprite Cat
    script
      when flag clicked
        if not touching "edge"
          move 10
"""
        p = parse(src)
        cond = p.sprites[0].scripts[0].body[0].condition
        assert isinstance(cond, UnaryOp)
        assert cond.op == "not"


class TestVariables:
    def test_set_variable(self):
        src = """\
project
  sprite Cat
    variable score = 0
    script
      when flag clicked
        set score to 10
"""
        p = parse(src)
        body = p.sprites[0].scripts[0].body
        assert isinstance(body[0], SetVariable)
        assert body[0].name == "score"

    def test_change_variable(self):
        src = """\
project
  sprite Cat
    variable score = 0
    script
      when flag clicked
        change score by 1
"""
        p = parse(src)
        body = p.sprites[0].scripts[0].body
        assert isinstance(body[0], ChangeVariable)
        assert body[0].name == "score"


class TestListOperations:
    def test_add_to_list(self):
        src = """\
project
  sprite Cat
    list items
    script
      when flag clicked
        add "hello" to items
"""
        p = parse(src)
        body = p.sprites[0].scripts[0].body
        assert isinstance(body[0], ListOperation)
        assert body[0].operation == "add"
        assert body[0].list_name == "items"


class TestCustomBlocks:
    def test_define_and_call(self):
        src = """\
project
  sprite Cat
    define jump(height)
      change y by height
    script
      when flag clicked
        jump 50
"""
        p = parse(src)
        assert len(p.sprites[0].custom_blocks) == 1
        cb = p.sprites[0].custom_blocks[0]
        assert cb.name == "jump"
        assert cb.params == ["height"]
