"""Baseline files: adopt ghostref without fixing history first."""

import json
from pathlib import Path

import pytest

from ghostref.baseline import Baseline, fingerprint
from ghostref.resolve import Finding


def make_finding(file="app.py", line=3, token="gone", kind="comment"):
    return Finding(
        file=file,
        line=line,
        col=1,
        token=token,
        kind=kind,
        confidence="high",
        message="no symbol",
    )


def test_baselined_findings_are_filtered_and_new_ones_pass(tmp_path):
    old = make_finding(token="old_ghost")
    fresh = make_finding(token="new_ghost")
    baseline = Baseline.from_findings([old], tmp_path)
    assert baseline.filter([old, fresh], tmp_path) == [fresh]


def test_fingerprint_ignores_line_numbers(tmp_path):
    # Moving a lying comment must not resurrect it.
    at_line_3 = make_finding(line=3)
    at_line_90 = make_finding(line=90)
    assert fingerprint(at_line_3, tmp_path) == fingerprint(at_line_90, tmp_path)


def test_fingerprint_distinguishes_file_token_and_kind(tmp_path):
    base = make_finding()
    assert fingerprint(base, tmp_path) != fingerprint(
        make_finding(file="other.py"), tmp_path
    )
    assert fingerprint(base, tmp_path) != fingerprint(
        make_finding(token="different"), tmp_path
    )
    assert fingerprint(base, tmp_path) != fingerprint(
        make_finding(kind="docstring"), tmp_path
    )


def test_dump_then_load_round_trips(tmp_path):
    findings = [make_finding(token="a"), make_finding(token="b")]
    path = tmp_path / "baseline.json"
    path.write_text(Baseline().dump(findings, tmp_path), encoding="utf-8")
    loaded = Baseline.load(path)
    assert loaded.filter(findings, tmp_path) == []


def test_dump_is_sorted_deduplicated_and_relative(tmp_path):
    findings = [
        make_finding(token="zeta", file=str(tmp_path / "pkg" / "app.py")),
        make_finding(token="alpha"),
        make_finding(token="alpha"),  # duplicate: same fingerprint
    ]
    data = json.loads(Baseline().dump(findings, tmp_path))
    entry_tokens = [entry["token"] for entry in data["entries"]]
    assert entry_tokens == ["alpha", "zeta"]
    assert data["entries"][1]["file"] == "pkg/app.py"  # relative, posix


def test_load_rejects_foreign_json(tmp_path):
    path = tmp_path / "not-baseline.json"
    path.write_text('{"something": "else"}', encoding="utf-8")
    with pytest.raises(ValueError, match="not a ghostref baseline"):
        Baseline.load(path)
