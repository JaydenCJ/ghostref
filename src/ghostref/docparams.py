"""Check documented parameters against real function signatures.

Refactors rename or drop parameters; docstrings keep describing the old
ones. This module parses the three mainstream docstring dialects and flags
every documented parameter that the signature no longer accepts:

- **Google**: an ``Args:`` / ``Arguments:`` / ``Parameters:`` /
  ``Keyword Args:`` section with ``name (type): description`` entries.
- **Sphinx**: ``:param name:`` and ``:param type name:`` fields.
- **NumPy**: a ``Parameters`` heading underlined with dashes, then
  ``name : type`` entries.

Functions that accept ``**kwargs`` are skipped entirely — any documented
name could be a legitimate keyword — which keeps this check zero-noise.
"""

from __future__ import annotations

import ast
import re
from typing import List, Optional, Set

from ghostref.resolve import Finding

_GOOGLE_SECTION_RE = re.compile(
    r"^(\s*)(?:Args|Arguments|Parameters|Keyword Args|Keyword Arguments|Other Parameters)\s*:\s*$"
)
_GOOGLE_ENTRY_RE = re.compile(r"^(\s+)(\*{0,2})([A-Za-z_]\w*)\s*(?:\([^)]*\))?\s*:")
_SPHINX_PARAM_RE = re.compile(r"^\s*:param\s+(?:[^:]*?\s)?(\*{0,2})([A-Za-z_]\w*)\s*:")
_NUMPY_HEADING_RE = re.compile(r"^(\s*)(?:Parameters|Other Parameters)\s*$")
_NUMPY_UNDERLINE_RE = re.compile(r"^\s*-{3,}\s*$")
_NUMPY_ENTRY_RE = re.compile(r"^(\s*)(\*{0,2})([A-Za-z_]\w*)\s*(?::.*)?$")


def _signature_names(node) -> Optional[Set[str]]:
    """Accepted parameter names, or ``None`` when the check must be skipped."""
    args = node.args
    if args.kwarg is not None:
        return None  # **kwargs swallows any documented name
    names = {arg.arg for arg in getattr(args, "posonlyargs", [])}
    names.update(arg.arg for arg in args.args)
    names.update(arg.arg for arg in args.kwonlyargs)
    if args.vararg is not None:
        names.add(args.vararg.arg)
    return names


def _google_documented(lines: List[str]) -> List[tuple]:
    """(name, line_offset) pairs documented in Google-style sections."""
    documented = []
    section_indent: Optional[int] = None
    entry_indent: Optional[int] = None
    for offset, line in enumerate(lines):
        heading = _GOOGLE_SECTION_RE.match(line)
        if heading:
            section_indent = len(heading.group(1))
            entry_indent = None
            continue
        if section_indent is None:
            continue
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= section_indent:
            section_indent = None  # dedent ends the section
            continue
        entry = _GOOGLE_ENTRY_RE.match(line)
        if entry:
            this_indent = len(entry.group(1))
            if entry_indent is None:
                entry_indent = this_indent
            if this_indent == entry_indent:
                documented.append((entry.group(3), offset))
    return documented


def _numpy_documented(lines: List[str]) -> List[tuple]:
    """(name, line_offset) pairs documented under NumPy Parameters headings."""
    documented = []
    index = 0
    while index < len(lines) - 1:
        heading = _NUMPY_HEADING_RE.match(lines[index])
        if not heading or not _NUMPY_UNDERLINE_RE.match(lines[index + 1]):
            index += 1
            continue
        section_indent = len(heading.group(1))
        cursor = index + 2
        while cursor < len(lines):
            line = lines[cursor]
            if not line.strip():
                cursor += 1
                continue
            indent = len(line) - len(line.lstrip())
            if indent > section_indent:
                cursor += 1  # continuation / description line
                continue
            entry = _NUMPY_ENTRY_RE.match(line)
            if entry and len(entry.group(1)) == section_indent:
                if _NUMPY_HEADING_RE.match(line) and cursor + 1 < len(lines) and (
                    _NUMPY_UNDERLINE_RE.match(lines[cursor + 1])
                ):
                    break  # next underlined section begins
                documented.append((entry.group(3), cursor))
                cursor += 1
            else:
                break
        index = cursor
    return documented


def _sphinx_documented(lines: List[str]) -> List[tuple]:
    """(name, line_offset) pairs documented with ``:param name:`` fields."""
    documented = []
    for offset, line in enumerate(lines):
        match = _SPHINX_PARAM_RE.match(line)
        if match:
            documented.append((match.group(2), offset))
    return documented


def check_docstring_params(source: str, file: str) -> List[Finding]:
    """Findings for every documented-but-gone parameter in *source*."""
    try:
        tree = ast.parse(source, filename=file)
    except SyntaxError:
        return []
    source_lines = source.splitlines()
    findings: List[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        doc = ast.get_docstring(node, clean=False)
        if not doc or "ghostref: ignore" in doc:
            continue
        accepted = _signature_names(node)
        if accepted is None:
            continue
        literal = node.body[0].value  # type: ignore[union-attr]
        doc_lines = doc.splitlines()
        documented = (
            _google_documented(doc_lines)
            + _sphinx_documented(doc_lines)
            + _numpy_documented(doc_lines)
        )
        seen = set()
        for name, offset in documented:
            if name in accepted or name in ("self", "cls") or name in seen:
                continue
            seen.add(name)
            line = literal.lineno + offset
            context = ""
            if 1 <= line <= len(source_lines):
                context = source_lines[line - 1].strip()
            findings.append(
                Finding(
                    file=file,
                    line=line,
                    col=1,
                    token=name,
                    kind="param",
                    confidence="high",
                    message=(
                        f"docstring of '{node.name}' documents parameter "
                        f"'{name}', but the signature does not accept it"
                    ),
                    context=context,
                    suggestion=_closest(name, accepted),
                )
            )
    return findings


def _closest(name: str, accepted: Set[str]) -> Optional[str]:
    import difflib

    matches = difflib.get_close_matches(name, sorted(accepted), n=1, cutoff=0.6)
    return matches[0] if matches else None
