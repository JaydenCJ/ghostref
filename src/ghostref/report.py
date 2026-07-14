"""Render scan results as text, JSON, or GitHub workflow annotations.

All formats are deterministic: findings arrive pre-sorted, JSON keys are
sorted, and no timestamps or absolute machine paths are emitted (paths are
made relative to the scan root).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Sequence

from ghostref.resolve import Finding
from ghostref.scanner import ScanStats

FORMATS = ("text", "json", "github")


def pluralize(count: int, noun: str) -> str:
    """``1 file`` / ``2 files`` — every human-facing count goes through here."""
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _relative(file: str, root: Path) -> str:
    try:
        return Path(file).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return Path(file).as_posix()


def render_text(
    findings: Sequence[Finding], stats: ScanStats, root: Path, errors: Sequence[str] = ()
) -> str:
    """Human-readable report, grouped by file."""
    lines: List[str] = []
    current_file = None
    for finding in findings:
        rel = _relative(finding.file, root)
        if rel != current_file:
            if current_file is not None:
                lines.append("")
            lines.append(rel)
            current_file = rel
        lines.append(
            f"  {finding.line}:{finding.col}  ghost '{finding.token}'"
            f"  [{finding.kind}, {finding.confidence}]"
        )
        lines.append(f"      {finding.message}")
        if finding.context:
            lines.append(f"      > {finding.context}")
        if finding.suggestion:
            lines.append(f"      did you mean '{finding.suggestion}'?")
    if findings:
        lines.append("")
    for error in errors:
        lines.append(f"error: {error}")
    if errors:
        lines.append("")
    ghost_files = len({finding.file for finding in findings})
    lines.append(
        f"{pluralize(len(findings), 'ghost reference')} in "
        f"{pluralize(ghost_files, 'file')} — scanned "
        f"{pluralize(stats.python_files, 'Python file')}, "
        f"{pluralize(stats.markdown_files, 'Markdown file')}, "
        f"{pluralize(stats.symbols, 'live symbol')}, "
        f"{pluralize(stats.candidates, 'candidate token')}"
    )
    return "\n".join(lines) + "\n"


def render_json(
    findings: Sequence[Finding], stats: ScanStats, root: Path, errors: Sequence[str] = ()
) -> str:
    """Machine-readable report with a stable schema."""
    payload = {
        "version": 1,
        "findings": [
            {
                "file": _relative(finding.file, root),
                "line": finding.line,
                "col": finding.col,
                "token": finding.token,
                "kind": finding.kind,
                "confidence": finding.confidence,
                "message": finding.message,
                "context": finding.context,
                "suggestion": finding.suggestion,
            }
            for finding in findings
        ],
        "errors": list(errors),
        "summary": {
            "ghosts": len(findings),
            "python_files": stats.python_files,
            "markdown_files": stats.markdown_files,
            "symbols": stats.symbols,
            "blocks": stats.blocks,
            "candidates": stats.candidates,
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_github(
    findings: Sequence[Finding], stats: ScanStats, root: Path, errors: Sequence[str] = ()
) -> str:
    """GitHub Actions workflow commands: ``::error`` for high-confidence
    findings, ``::warning`` for medium-confidence ones."""
    lines = []
    for finding in findings:
        rel = _relative(finding.file, root)
        level = "error" if finding.confidence == "high" else "warning"
        message = f"ghost reference '{finding.token}': {finding.message}"
        if finding.suggestion:
            message += f" (did you mean '{finding.suggestion}'?)"
        lines.append(
            f"::{level} file={rel},line={finding.line},col={finding.col},"
            f"title=ghostref::{message}"
        )
    for error in errors:
        lines.append(f"::error title=ghostref::{error}")
    return "\n".join(lines) + ("\n" if lines else "")


RENDERERS = {"text": render_text, "json": render_json, "github": render_github}
