"""Unit tests for runner.tools._common — exit codes, frontmatter parsing, CLI helpers."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner.tools import _common


def test_exit_codes_constants():
    assert _common.EXIT_OK == 0
    assert _common.EXIT_USER_ERROR == 2
    assert _common.EXIT_CONTRACT_VIOLATION == 3
    assert _common.EXIT_INTERNAL_ERROR == 4


def test_parse_frontmatter_happy(tmp_path: Path):
    path = tmp_path / "a.md"
    path.write_text("---\nkey: value\nnum: 3\n---\n\n## Body\n\ntext\n")
    fm, body = _common.parse_frontmatter(path)
    assert fm == {"key": "value", "num": 3}
    assert "## Body" in body


def test_parse_frontmatter_missing_delimiters_raises(tmp_path: Path):
    path = tmp_path / "b.md"
    path.write_text("no frontmatter here\n")
    with pytest.raises(_common.FrontmatterError):
        _common.parse_frontmatter(path)


def test_parse_frontmatter_invalid_yaml_raises(tmp_path: Path):
    path = tmp_path / "c.md"
    path.write_text("---\n: bad yaml :\n---\nbody\n")
    with pytest.raises(_common.FrontmatterError):
        _common.parse_frontmatter(path)


def test_emit_json_roundtrip(capsys):
    _common.emit_json({"a": 1, "b": [2, 3]})
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"a": 1, "b": [2, 3]}
