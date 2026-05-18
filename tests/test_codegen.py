"""Tests for the ScratchScript code generator."""

import json
from scratchscript.compiler.parser import parse
from scratchscript.compiler.codegen import generate


def _compile(source: str) -> dict:
    """Helper: parse + generate project.json dict."""
    project = parse(source)
    return generate(project)


class TestProjectStructure:
    def test_minimal_project(self):
        pj = _compile("project MyProject")
        assert "targets" in pj
        assert "meta" in pj
        assert pj["meta"]["semver"] == "3.0.0"
        # Should have at least a stage
        assert len(pj["targets"]) >= 1
        assert pj["targets"][0]["isStage"] is True

    def test_stage_has_required_fields(self):
        pj = _compile("project Test")
        stage = pj["targets"][0]
        assert stage["name"] == "Stage"
        assert "variables" in stage
        assert "lists" in stage
        assert "broadcasts" in stage
        assert "blocks" in stage
        assert "costumes" in stage
        assert stage["layerOrder"] == 0

    def test_sprite_target(self):
        pj = _compile("""\
project
  sprite Cat
    costumes "cat-a"
""")
        assert len(pj["targets"]) == 2
        sprite = pj["targets"][1]
        assert sprite["isStage"] is False
        assert sprite["name"] == "Cat"
        assert sprite["layerOrder"] == 1


class TestBlockGeneration:
    def test_flag_clicked_hat(self):
        pj = _compile("""\
project
  sprite Cat
    script
      when flag clicked
        move 10
""")
        blocks = pj["targets"][1]["blocks"]
        # Find the hat block
        hat = None
        for bid, block in blocks.items():
            if block["opcode"] == "event_whenflagclicked":
                hat = block
                break
        assert hat is not None
        assert hat["topLevel"] is True

    def test_move_block(self):
        pj = _compile("""\
project
  sprite Cat
    script
      when flag clicked
        move 10
""")
        blocks = pj["targets"][1]["blocks"]
        move = None
        for block in blocks.values():
            if block["opcode"] == "motion_movesteps":
                move = block
                break
        assert move is not None
        assert "STEPS" in move["inputs"]

    def test_block_chain(self):
        pj = _compile("""\
project
  sprite Cat
    script
      when flag clicked
        move 10
        turn right 90
""")
        blocks = pj["targets"][1]["blocks"]
        move = None
        turn = None
        for block in blocks.values():
            if block["opcode"] == "motion_movesteps":
                move = block
            elif block["opcode"] == "motion_turnright":
                turn = block
        assert move is not None
        assert turn is not None
        # They should be chained
        assert move["next"] is not None


class TestControlBlocks:
    def test_if_block(self):
        pj = _compile("""\
project
  sprite Cat
    script
      when flag clicked
        if touching "edge"
          turn right 180
""")
        blocks = pj["targets"][1]["blocks"]
        if_block = None
        for block in blocks.values():
            if block["opcode"] == "control_if":
                if_block = block
                break
        assert if_block is not None
        assert "CONDITION" in if_block["inputs"]
        assert "SUBSTACK" in if_block["inputs"]

    def test_if_else_block(self):
        pj = _compile("""\
project
  sprite Cat
    script
      when flag clicked
        if touching "edge"
          turn right 180
        else
          move 10
""")
        blocks = pj["targets"][1]["blocks"]
        if_else = None
        for block in blocks.values():
            if block["opcode"] == "control_if_else":
                if_else = block
                break
        assert if_else is not None
        assert "SUBSTACK" in if_else["inputs"]
        assert "SUBSTACK2" in if_else["inputs"]

    def test_forever_block(self):
        pj = _compile("""\
project
  sprite Cat
    script
      when flag clicked
        forever
          move 10
""")
        blocks = pj["targets"][1]["blocks"]
        forever = None
        for block in blocks.values():
            if block["opcode"] == "control_forever":
                forever = block
                break
        assert forever is not None
        assert "SUBSTACK" in forever["inputs"]

    def test_repeat_block(self):
        pj = _compile("""\
project
  sprite Cat
    script
      when flag clicked
        repeat 10
          move 5
""")
        blocks = pj["targets"][1]["blocks"]
        repeat = None
        for block in blocks.values():
            if block["opcode"] == "control_repeat":
                repeat = block
                break
        assert repeat is not None
        assert "TIMES" in repeat["inputs"]
        assert "SUBSTACK" in repeat["inputs"]


class TestVariables:
    def test_variable_declaration(self):
        pj = _compile("""\
project
  sprite Cat
    variable score = 0
    script
      when flag clicked
        set score to 10
""")
        sprite = pj["targets"][1]
        assert len(sprite["variables"]) > 0
        var_names = [v[0] for v in sprite["variables"].values()]
        assert "score" in var_names

    def test_set_variable_block(self):
        pj = _compile("""\
project
  sprite Cat
    variable score = 0
    script
      when flag clicked
        set score to 10
""")
        blocks = pj["targets"][1]["blocks"]
        set_block = None
        for block in blocks.values():
            if block["opcode"] == "data_setvariableto":
                set_block = block
                break
        assert set_block is not None
        assert "VALUE" in set_block["inputs"]
        assert "VARIABLE" in set_block["fields"]


class TestExpressions:
    def test_binary_op_generates_reporter(self):
        pj = _compile("""\
project
  sprite Cat
    variable x = 0
    script
      when flag clicked
        set x to 1 + 2
""")
        blocks = pj["targets"][1]["blocks"]
        add_block = None
        for block in blocks.values():
            if block["opcode"] == "operator_add":
                add_block = block
                break
        assert add_block is not None


class TestEvents:
    def test_key_pressed_event(self):
        pj = _compile("""\
project
  sprite Cat
    script
      when key space pressed
        move 10
""")
        blocks = pj["targets"][1]["blocks"]
        hat = None
        for block in blocks.values():
            if block["opcode"] == "event_whenkeypressed":
                hat = block
                break
        assert hat is not None
        assert hat["fields"]["KEY_OPTION"][0] == "space"

    def test_broadcast_event(self):
        pj = _compile("""\
project
  sprite Cat
    script
      when I receive "game over"
        stop all
""")
        blocks = pj["targets"][1]["blocks"]
        hat = None
        for block in blocks.values():
            if block["opcode"] == "event_whenbroadcastreceived":
                hat = block
                break
        assert hat is not None


class TestJsonSerializable:
    def test_output_is_json_serializable(self):
        pj = _compile("""\
project
  sprite Cat
    costumes "cat-a"
    variable score = 0
    script
      when flag clicked
        forever
          move 10
          if on edge bounce
          if touching "edge"
            change score by 1
            say "Bounce!"
""")
        # Should not raise
        result = json.dumps(pj)
        assert len(result) > 0

        # Verify it roundtrips
        parsed = json.loads(result)
        assert parsed["targets"][0]["isStage"] is True
