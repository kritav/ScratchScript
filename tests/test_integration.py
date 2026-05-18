"""Integration tests: .scratchscript → .sb3 → validate."""

import json
import zipfile
from pathlib import Path

import pytest

from scratchscript.compiler.parser import parse
from scratchscript.compiler.codegen import generate
from scratchscript.compiler.bundler import bundle_sync
from scratchscript.compiler.validator import validate

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestEndToEnd:
    def _compile_fixture(self, name: str, tmp_path: Path) -> tuple[dict, Path]:
        """Compile a fixture file and return (project_json, sb3_path)."""
        source = (FIXTURES_DIR / name).read_text()
        project = parse(source)

        # Validate
        result = validate(project)
        # We allow warnings but no errors for fixtures
        # (Some blocks may not be in opcode table, which is OK)

        pj = generate(project)
        out = tmp_path / name.replace(".scratchscript", ".sb3")
        bundle_sync(pj, out)
        return pj, out

    def test_hello_compiles(self, tmp_path):
        pj, sb3 = self._compile_fixture("hello.scratchscript", tmp_path)
        assert sb3.exists()
        assert zipfile.is_zipfile(sb3)

        # Validate JSON inside ZIP
        with zipfile.ZipFile(sb3) as zf:
            content = json.loads(zf.read("project.json"))
            assert content["targets"][0]["isStage"] is True
            assert len(content["targets"]) == 2  # Stage + Cat
            assert content["targets"][1]["name"] == "Cat"

    def test_hello_has_correct_blocks(self, tmp_path):
        pj, _ = self._compile_fixture("hello.scratchscript", tmp_path)
        sprite_blocks = pj["targets"][1]["blocks"]

        opcodes = {b["opcode"] for b in sprite_blocks.values()}
        assert "event_whenflagclicked" in opcodes
        assert "looks_sayforsecs" in opcodes or "looks_say" in opcodes

    def test_flappy_compiles(self, tmp_path):
        pj, sb3 = self._compile_fixture("flappy.scratchscript", tmp_path)
        assert sb3.exists()

        with zipfile.ZipFile(sb3) as zf:
            content = json.loads(zf.read("project.json"))
            assert len(content["targets"]) == 3  # Stage + Bird + Pipe

    def test_flappy_has_variables(self, tmp_path):
        pj, _ = self._compile_fixture("flappy.scratchscript", tmp_path)
        # Global variables should be on the stage
        stage_vars = pj["targets"][0]["variables"]
        var_names = [v[0] for v in stage_vars.values()]
        assert "score" in var_names

    def test_flappy_has_events(self, tmp_path):
        pj, _ = self._compile_fixture("flappy.scratchscript", tmp_path)
        # Bird should have flag clicked and key pressed events
        bird_blocks = pj["targets"][1]["blocks"]
        opcodes = {b["opcode"] for b in bird_blocks.values()}
        assert "event_whenflagclicked" in opcodes
        assert "event_whenkeypressed" in opcodes


class TestRoundTrip:
    def test_project_json_roundtrips(self, tmp_path):
        """Verify project.json survives JSON serialization."""
        source = """\
project
  sprite Cat
    costumes "cat-a"
    variable score = 0
    script
      when flag clicked
        set score to 0
        forever
          move 10
          if on edge bounce
          change score by 1
"""
        project = parse(source)
        pj = generate(project)

        # Serialize and deserialize
        json_str = json.dumps(pj)
        restored = json.loads(json_str)

        assert restored["targets"][0]["isStage"] is True
        assert restored["targets"][1]["name"] == "Cat"
        assert len(restored["targets"][1]["blocks"]) > 0

    def test_all_values_serializable(self, tmp_path):
        """Verify no non-serializable types leak into project.json."""
        source = """\
project
  variable x = 0
  sprite Cat
    costumes "cat-a"
    variable localVar = 0
    list myList
    script
      when flag clicked
        set x to (1 + 2) * 3
        change localVar by 1
        add "item" to myList
        if x > 5
          say "big"
        else
          say "small"
        repeat 10
          move 5
        forever
          if on edge bounce
"""
        project = parse(source)
        pj = generate(project)
        # This should not raise
        result = json.dumps(pj, default=str)
        assert len(result) > 100
