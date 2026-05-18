"""Tests for the ScratchScript bundler."""

import json
import zipfile
from pathlib import Path

import pytest

from scratchscript.compiler.parser import parse
from scratchscript.compiler.codegen import generate
from scratchscript.compiler.bundler import bundle_sync


class TestBundlerSync:
    def test_creates_sb3_file(self, tmp_path):
        source = """\
project
  sprite Cat
    costumes "cat-a"
    script
      when flag clicked
        move 10
"""
        project = parse(source)
        pj = generate(project)
        out = tmp_path / "test.sb3"
        result = bundle_sync(pj, out)
        assert result.exists()
        assert result.suffix == ".sb3"

    def test_sb3_is_valid_zip(self, tmp_path):
        source = "project Test"
        project = parse(source)
        pj = generate(project)
        out = tmp_path / "test.sb3"
        bundle_sync(pj, out)
        assert zipfile.is_zipfile(out)

    def test_sb3_contains_project_json(self, tmp_path):
        source = """\
project
  sprite Cat
    script
      when flag clicked
        say "Hello"
"""
        project = parse(source)
        pj = generate(project)
        out = tmp_path / "test.sb3"
        bundle_sync(pj, out)

        with zipfile.ZipFile(out, "r") as zf:
            assert "project.json" in zf.namelist()
            content = json.loads(zf.read("project.json"))
            assert "targets" in content
            assert content["targets"][0]["isStage"] is True

    def test_sb3_contains_asset_placeholders(self, tmp_path):
        source = """\
project
  sprite Cat
    costumes "cat-a"
    script
      when flag clicked
        move 10
"""
        project = parse(source)
        pj = generate(project)
        out = tmp_path / "test.sb3"
        bundle_sync(pj, out)

        with zipfile.ZipFile(out, "r") as zf:
            files = zf.namelist()
            # Should have project.json + at least one asset
            assert len(files) >= 2

    def test_project_json_is_compact(self, tmp_path):
        source = "project Test"
        project = parse(source)
        pj = generate(project)
        out = tmp_path / "test.sb3"
        bundle_sync(pj, out)

        with zipfile.ZipFile(out, "r") as zf:
            raw = zf.read("project.json").decode("utf-8")
            # Compact JSON should not have indentation
            assert "\n" not in raw
