"""Find identifier-shaped tokens inside prose, with a confidence per signal.

Prose is full of words; ghostref only inspects tokens that carry an explicit
code-reference signal. Signals are matched in priority order on each line and
claim their span, so a backticked name is never re-reported by the weaker
snake_case rule:

===============================  ==========  =========================================
signal                           confidence  example
===============================  ==========  =========================================
Sphinx role                      high        ``:func:`compute_total```
backtick span                    high        ```compute_total``` / ```Cart.add(item)```
call syntax                      high        ``compute_total()`` (no space before ``(``)
dotted path                      medium      ``cart.compute_total``
snake_case word                  medium      ``compute_total``
CamelCase word                   medium      ``CartSnapshot``
===============================  ==========  =========================================

URLs are masked before matching, marker idioms (``TODO(alice)``, ``e.g.``)
are dropped, and dotted tokens ending in a file extension or hostname tail
(``config.yaml``, ``example.test``) are treated as paths, not attributes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from ghostref.wordlists import (
    DOTTED_ABBREVIATIONS,
    FILE_AND_HOST_TAILS,
    MARKER_WORDS,
    STYLE_WORDS,
    TECH_PROPER_NOUNS,
)

HIGH = "high"
MEDIUM = "medium"

_URL_RE = re.compile(r"(?:https?|ftp|file)://\S+|\bwww\.\S+")
_ROLE_RE = re.compile(
    r":(?:py:)?(?:func|meth|class|attr|mod|data|obj|exc|const|deco):`~?([A-Za-z_][\w.]*)`"
)
_BACKTICK_RE = re.compile(r"``?([^`]+)``?")
_CALL_RE = re.compile(r"(?<![\w.`])([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\(")
_DOTTED_RE = re.compile(r"(?<![\w.`])([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)(?![\w(])")
_SNAKE_RE = re.compile(r"(?<![\w.`])([A-Za-z_]\w*_\w+)(?![\w.(])")
_CAMEL_RE = re.compile(r"(?<![\w.`])([A-Z][a-z0-9]+(?:[A-Z][a-z0-9]*)+)(?![\w.(])")

#: What the inside of a backtick span must look like to count as a reference:
#: an identifier or dotted path, optionally called with arguments.
_INLINE_CODE_RE = re.compile(
    r"^~?([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)(?:\([^()]*\))?$"
)


@dataclass(frozen=True)
class Candidate:
    """One identifier-shaped token found in a prose line."""

    token: str  # normalized name, e.g. "Cart.add" (no parens or backticks)
    line: int  # 1-based source line
    col: int  # 1-based source column of the token
    confidence: str  # HIGH | MEDIUM
    signal: str  # role | backtick | call | dotted | snake | camel | code-span


class _Mask:
    """Tracks claimed character spans so weaker signals skip stronger ones."""

    def __init__(self) -> None:
        self._spans: List[Tuple[int, int]] = []

    def claim(self, start: int, end: int) -> None:
        self._spans.append((start, end))

    def overlaps(self, start: int, end: int) -> bool:
        return any(start < e and end > s for s, e in self._spans)


def parse_inline_code(inner: str) -> Optional[str]:
    """Normalize the inside of a backtick span to a token, or ``None``.

    ``compute_total()`` → ``compute_total``; ``~pkg.Cart`` → ``pkg.Cart``;
    ``--flag`` / ``a + b`` → ``None`` (code, but not a name reference).
    """
    match = _INLINE_CODE_RE.match(inner.strip())
    return match.group(1) if match else None


def is_noise(token: str, signal: str) -> bool:
    """True for tokens that look like identifiers but are prose conventions."""
    if token.upper() in MARKER_WORDS and token.isupper():
        return True
    if token in TECH_PROPER_NOUNS and signal in ("camel", "snake"):
        return True
    lowered = token.lower()
    if lowered in STYLE_WORDS and signal in ("camel", "snake"):
        return True
    if lowered in DOTTED_ABBREVIATIONS or lowered.rstrip(".") in DOTTED_ABBREVIATIONS:
        return True
    if "." in token and token.rsplit(".", 1)[1].lower() in FILE_AND_HOST_TAILS:
        return True
    if signal in ("snake", "camel") and len(token.strip("_")) < 3:
        return True
    if set(token) <= {"_"}:
        return True
    return False


def extract_from_line(line_text: str, line_number: int) -> List[Candidate]:
    """All candidates on one line of prose, strongest signals first."""
    mask = _Mask()
    found: List[Candidate] = []

    for match in _URL_RE.finditer(line_text):
        mask.claim(match.start(), match.end())

    def emit(token: str, start: int, end: int, confidence: str, signal: str) -> None:
        if mask.overlaps(start, end):
            return
        mask.claim(start, end)
        if is_noise(token, signal):
            return
        found.append(
            Candidate(
                token=token,
                line=line_number,
                col=start + 1,
                confidence=confidence,
                signal=signal,
            )
        )

    for match in _ROLE_RE.finditer(line_text):
        emit(match.group(1), match.start(), match.end(), HIGH, "role")

    for match in _BACKTICK_RE.finditer(line_text):
        if mask.overlaps(match.start(), match.end()):
            continue
        token = parse_inline_code(match.group(1))
        if token is None:
            mask.claim(match.start(), match.end())  # code, but not a reference
            continue
        emit(token, match.start(), match.end(), HIGH, "backtick")

    for match in _CALL_RE.finditer(line_text):
        emit(match.group(1), match.start(1), match.end(1), HIGH, "call")

    for match in _DOTTED_RE.finditer(line_text):
        emit(match.group(1), match.start(1), match.end(1), MEDIUM, "dotted")

    for pattern, signal in ((_SNAKE_RE, "snake"), (_CAMEL_RE, "camel")):
        for match in pattern.finditer(line_text):
            emit(match.group(1), match.start(1), match.end(1), MEDIUM, signal)

    found.sort(key=lambda candidate: candidate.col)
    return found


def extract_candidates(text: str, first_line: int) -> List[Candidate]:
    """Candidates for a whole prose block starting at source line *first_line*."""
    results: List[Candidate] = []
    for offset, line_text in enumerate(text.splitlines()):
        results.extend(extract_from_line(line_text, first_line + offset))
    return results
