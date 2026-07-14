"""Scan Markdown documentation for ghost references in inline code spans.

Docs lie longer than comments: a README survives many refactors untouched.
This scanner is deliberately narrow to stay deterministic and quiet:

- Only inline code spans (backticks) and Sphinx roles are inspected — plain
  prose in docs is not identifier-shaped often enough to be worth the noise.
- Fenced code blocks (``` / ~~~) are skipped entirely: they are code samples,
  and judging whole samples is a different (roadmap) problem.
- A line containing ``ghostref: ignore`` (typically in an HTML comment)
  suppresses itself.
"""

from __future__ import annotations

import re
from typing import List

from ghostref.candidates import HIGH, Candidate, _ROLE_RE, is_noise, parse_inline_code

_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_SPAN_RE = re.compile(r"``?([^`\n]+)``?")
_IGNORE_MARK = "ghostref: ignore"


def extract_markdown_candidates(text: str) -> List[Candidate]:
    """Candidates from inline code spans of a Markdown document."""
    candidates: List[Candidate] = []
    in_fence = False
    fence_marker = ""
    for line_number, line in enumerate(text.splitlines(), start=1):
        fence = _FENCE_RE.match(line)
        if fence:
            marker = fence.group(1)
            if not in_fence:
                in_fence, fence_marker = True, marker
            elif marker == fence_marker:
                in_fence = False
            continue
        if in_fence or _IGNORE_MARK in line:
            continue
        claimed: List[tuple] = []
        for match in _ROLE_RE.finditer(line):
            claimed.append((match.start(), match.end()))
            candidates.append(
                Candidate(
                    token=match.group(1),
                    line=line_number,
                    col=match.start() + 1,
                    confidence=HIGH,
                    signal="role",
                )
            )
        for match in _SPAN_RE.finditer(line):
            if any(match.start() < e and match.end() > s for s, e in claimed):
                continue
            token = parse_inline_code(match.group(1))
            if token is None or is_noise(token, "code-span"):
                continue
            candidates.append(
                Candidate(
                    token=token,
                    line=line_number,
                    col=match.start() + 1,
                    confidence=HIGH,
                    signal="code-span",
                )
            )
    return candidates
