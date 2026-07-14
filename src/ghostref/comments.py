"""Extract comments and docstrings from Python source, with exact positions.

Comments come from :mod:`tokenize` (the only stdlib layer that sees them);
docstrings come from :mod:`ast`. Both are returned as :class:`TextBlock`
values whose ``line`` is the 1-based line of the block's first text line, so
candidate extraction can point findings at the real source line.

Tooling directives (``# noqa``, ``# type:``, ``# pylint:``, shebangs, coding
cookies) are dropped: their payloads are machine syntax, not prose that can
lie. A comment containing ``ghostref: ignore`` suppresses itself.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from dataclasses import dataclass
from typing import List

#: Comments whose body is a directive for another tool, not human prose.
_DIRECTIVE_RE = re.compile(
    r"^\s*(?:type:|noqa\b|nosec\b|pragma\b|pylint:|mypy:|ruff:|flake8:|isort:|"
    r"fmt:|yapf:|coding[:=]|!/|-\*-)"
)

_IGNORE_MARK = "ghostref: ignore"


@dataclass(frozen=True)
class TextBlock:
    """A run of prose extracted from source: one comment or one docstring."""

    file: str
    line: int  # 1-based line of the first line of `text`
    col: int  # 0-based column where the text starts on its first line
    text: str  # comment body without the leading '#', or the raw docstring
    kind: str  # "comment" | "docstring"


def extract_comments(source: str, file: str) -> List[TextBlock]:
    """Return every prose comment in *source* as a :class:`TextBlock`.

    Tokenization errors (typically an unterminated string at EOF) end the
    scan early but keep everything collected up to that point, so a broken
    tail never hides ghosts in the healthy part of the file.
    """
    blocks: List[TextBlock] = []
    reader = io.StringIO(source).readline
    try:
        for token in tokenize.generate_tokens(reader):
            if token.type != tokenize.COMMENT:
                continue
            body = token.string.lstrip("#")
            stripped_leading = len(token.string) - len(body)
            if _DIRECTIVE_RE.match(body) or _IGNORE_MARK in body:
                continue
            blocks.append(
                TextBlock(
                    file=file,
                    line=token.start[0],
                    col=token.start[1] + stripped_leading,
                    text=body,
                    kind="comment",
                )
            )
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return blocks


def extract_docstrings(source: str, file: str) -> List[TextBlock]:
    """Return module, class, and function docstrings as :class:`TextBlock`\\ s.

    The block line is the line of the string literal itself; multi-line
    docstrings are handled downstream by adding the in-text line offset.
    Returns an empty list when the file does not parse.
    """
    try:
        tree = ast.parse(source, filename=file)
    except SyntaxError:
        return []
    blocks: List[TextBlock] = []
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        doc = ast.get_docstring(node, clean=False)
        if not doc or _IGNORE_MARK in doc:
            continue
        literal = node.body[0].value  # type: ignore[union-attr]
        blocks.append(
            TextBlock(
                file=file,
                line=literal.lineno,
                col=literal.col_offset,
                text=doc,
                kind="docstring",
            )
        )
    return blocks


def extract_blocks(source: str, file: str) -> List[TextBlock]:
    """All prose blocks in *source*, comments first, in source order."""
    blocks = extract_comments(source, file) + extract_docstrings(source, file)
    blocks.sort(key=lambda block: (block.line, block.col))
    return blocks
