"""Report rendering: text, JSON schema, and GitHub annotations."""

import json
from pathlib import Path

from ghostref.report import render_github, render_json, render_text
from ghostref.resolve import Finding
from ghostref.scanner import ScanStats


ROOT = Path("/project")

FINDINGS = [
    Finding(
        file="/project/app.py",
        line=4,
        col=7,
        token="legacy_sync",
        kind="comment",
        confidence="high",
        message="no symbol named 'legacy_sync' exists in the scanned code",
        context="# still calls legacy_sync() nightly",
        suggestion="sync",
    ),
    Finding(
        file="/project/docs/guide.md",
        line=9,
        col=2,
        token="OldWidget",
        kind="markdown",
        confidence="medium",
        message="no symbol named 'OldWidget' exists in the scanned code",
    ),
]

STATS = ScanStats(python_files=3, markdown_files=1, symbols=42, blocks=10, candidates=7)


def test_text_report_groups_by_file_and_shows_suggestions():
    text = render_text(FINDINGS, STATS, ROOT)
    assert "app.py" in text.splitlines()[0]
    assert "4:7  ghost 'legacy_sync'" in text
    assert "did you mean 'sync'?" in text
    assert "docs/guide.md" in text


def test_text_summary_line_counts_everything():
    text = render_text(FINDINGS, STATS, ROOT)
    assert (
        "2 ghost references in 2 files — scanned 3 Python files, "
        "1 Markdown file, 42 live symbols, 7 candidate tokens"
    ) in text
    # singular counts read as English, not as "1 files"
    single = render_text(FINDINGS[:1], STATS, ROOT)
    assert "1 ghost reference in 1 file — scanned" in single
    # a clean scan collapses to a single summary line
    assert render_text([], STATS, ROOT).startswith("0 ghost references")


def test_json_report_has_a_stable_schema():
    data = json.loads(render_json(FINDINGS, STATS, ROOT))
    assert data["version"] == 1
    assert data["summary"]["ghosts"] == 2
    first = data["findings"][0]
    assert first["file"] == "app.py"  # relative to root, posix separators
    assert set(first) == {
        "file", "line", "col", "token", "kind", "confidence",
        "message", "context", "suggestion",
    }
    # byte-identical on every render: sorted keys, no timestamps
    assert render_json(FINDINGS, STATS, ROOT) == render_json(FINDINGS, STATS, ROOT)


def test_github_format_maps_confidence_to_severity():
    lines = render_github(FINDINGS, STATS, ROOT).splitlines()
    assert lines[0].startswith("::error file=app.py,line=4,col=7,title=ghostref::")
    assert lines[1].startswith("::warning file=docs/guide.md,line=9")
    assert "did you mean 'sync'?" in lines[0]


def test_github_format_is_empty_for_clean_scans():
    assert render_github([], STATS, ROOT) == ""


def test_errors_are_rendered_in_every_format():
    errors = ["bad.py:1: syntax error: invalid syntax"]
    assert "error: bad.py:1" in render_text([], STATS, ROOT, errors)
    assert json.loads(render_json([], STATS, ROOT, errors))["errors"] == errors
    assert "::error title=ghostref::" in render_github([], STATS, ROOT, errors)
