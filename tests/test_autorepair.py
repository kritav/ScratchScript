"""Tests for deterministic auto-repair of near-miss names."""

from scratchscript.compiler.autorepair import best_match, repair_project
from scratchscript.compiler.opcodes import format_signature
from scratchscript.compiler.parser import parse
from scratchscript.compiler.validator import validate


def _repair(source: str):
    project = parse(source)
    notes = repair_project(project)
    return project, notes


class TestBestMatch:
    def test_confident_match(self):
        assert best_match("moove", ["move", "turn right"]) == "move"

    def test_no_match_below_cutoff(self):
        assert best_match("frobnicate", ["move", "turn right"]) is None

    def test_ambiguous_top_two_rejected(self):
        # Equidistant candidates should not be silently picked
        assert best_match("turn", ["turn right", "turn left"]) is None

    def test_margin_zero_allows_close_runner_up(self):
        result = best_match("dinosaur-a", ["dinosaur1-a", "dinosaur1-b"], margin=0.0)
        assert result == "dinosaur1-a"


class TestBlockRepair:
    def test_misspelled_block_is_repaired(self):
        project, notes = _repair("""\
project
  sprite Cat
    costumes "cat-a"
    script
      when flag clicked
        moove 10
""")
        block = project.sprites[0].scripts[0].body[0]
        assert block.name == "move"
        assert len(notes) == 1
        assert "moove" in notes[0]

    def test_repaired_project_passes_validation(self):
        project, _ = _repair("""\
project
  sprite Cat
    costumes "cat-a"
    script
      when flag clicked
        moove 10
""")
        result = validate(project)
        assert result.is_valid

    def test_valid_blocks_untouched(self):
        project, notes = _repair("""\
project
  sprite Cat
    costumes "cat-a"
    script
      when flag clicked
        move 10
        turn right 15
""")
        assert notes == []
        names = [b.name for b in project.sprites[0].scripts[0].body]
        assert names == ["move", "turn right"]

    def test_unrecognizable_block_left_for_llm(self):
        project, notes = _repair("""\
project
  sprite Cat
    costumes "cat-a"
    script
      when flag clicked
        do a backflip
""")
        assert notes == []
        result = validate(project)
        assert not result.is_valid

    def test_repair_inside_nested_bodies(self):
        project, notes = _repair("""\
project
  sprite Cat
    costumes "cat-a"
    script
      when flag clicked
        forever
          if touching "edge"
            moove 10
""")
        assert len(notes) == 1
        forever = project.sprites[0].scripts[0].body[0]
        assert forever.body[0].body[0].name == "move"


class TestSignatures:
    def test_signature_includes_inputs(self):
        assert format_signature("glide to x y") == "glide to x y <secs> <x> <y>"

    def test_unknown_block_error_shows_signatures(self):
        project = parse("""\
project
  sprite Cat
    costumes "cat-a"
    script
      when flag clicked
        glide 1 100 100
""")
        result = validate(project)
        assert not result.is_valid
        assert "glide to x y <secs> <x> <y>" in result.format_errors()
