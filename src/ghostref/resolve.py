"""Decide whether a candidate token is live, and describe it when it is not.

Resolution is a fixed rule ladder — no scoring, no models — so a token
resolves (or not) identically on every run and every machine:

1.  Allowlisted, keyword, builtin, or implicit (``self``, ``cls``) → live.
2.  Single segment: live iff it is a scanned symbol, module, or stdlib module.
3.  Dotted, exact match in the dotted index → live.
4.  Dotted, head is ``self``/``cls`` → live iff the attribute is indexed.
5.  Dotted, longest leading run of segments is a *scanned* module → live iff
    the remainder resolves inside that module; otherwise a ghost that names
    the module ("module 'cart' has no symbol 'legacy_total'").
6.  Dotted, head is a stdlib module or allowlisted → live (attributes of
    modules we did not scan cannot be verified).
7.  Dotted, head is any live bare name → live (attributes of arbitrary
    objects cannot be verified without executing code).
8.  Dotted, last segment is a live bare name → live (shorthand mentions like
    ``handlers.retry`` where ``retry`` exists).
9.  Anything else → ghost.

Every ghost gets a deterministic "did you mean" suggestion via
``difflib.get_close_matches`` over the relevant name set.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import FrozenSet, List, Optional, Sequence

from ghostref.candidates import Candidate
from ghostref.symbols import SymbolIndex
from ghostref.wordlists import (
    IMPLICIT_NAMES,
    PYTHON_BUILTINS,
    PYTHON_KEYWORDS,
    STDLIB_MODULES,
)


@dataclass(frozen=True)
class Finding:
    """One ghost reference: a token no live symbol backs up."""

    file: str
    line: int
    col: int
    token: str
    kind: str  # comment | docstring | markdown | param
    confidence: str  # high | medium
    message: str
    context: str = ""  # trimmed source excerpt containing the token
    suggestion: Optional[str] = None

    def sort_key(self):
        return (self.file, self.line, self.col, self.token)


@dataclass
class Resolver:
    """Answers :meth:`is_live` / :meth:`explain` against one symbol index."""

    index: SymbolIndex
    allow: FrozenSet[str] = field(default_factory=frozenset)

    # -- membership --------------------------------------------------------

    def _bare_live(self, name: str) -> bool:
        return (
            name in self.allow
            or name in PYTHON_KEYWORDS
            or name in PYTHON_BUILTINS
            or name in IMPLICIT_NAMES
            or name in self.index.bare
            or name in self.index.modules
            or name in STDLIB_MODULES
        )

    def is_live(self, token: str) -> bool:
        return self.explain(token) is None

    def explain(self, token: str) -> Optional[str]:
        """``None`` when *token* is live, else a human-readable reason."""
        if token in self.allow:
            return None
        segments = token.split(".")
        if len(segments) == 1:
            if self._bare_live(token):
                return None
            return f"no symbol named '{token}' exists in the scanned code"

        head, last = segments[0], segments[-1]
        if token in self.index.dotted or token in self.index.modules:
            return None
        if head in IMPLICIT_NAMES:
            if last in self.index.bare:
                return None
            return f"no attribute '{last}' is ever assigned on {head}"
        module = self.index.module_prefix(token)
        if module is not None:
            remainder = token[len(module) + 1 :]
            if f"{module}.{remainder}" in self.index.dotted or remainder in (
                self.index.module_symbols(module)
            ):
                return None
            return f"module '{module}' has no symbol '{remainder}'"
        if head in STDLIB_MODULES or head in self.allow:
            return None  # cannot verify attributes of unscanned modules
        if self._bare_live(head):
            return None  # attribute of a live object: unverifiable statically
        if last in self.index.bare:
            return None  # shorthand mention of a live name
        return f"neither '{head}' nor '{last}' exists in the scanned code"

    # -- suggestions -------------------------------------------------------

    def suggest(self, token: str) -> Optional[str]:
        """Closest live name to *token*, or ``None`` when nothing is close."""
        segments = token.split(".")
        module = self.index.module_prefix(token) if len(segments) > 1 else None
        if module is not None:
            pool = sorted(self.index.module_symbols(module))
            probe = token[len(module) + 1 :]
            matches = difflib.get_close_matches(probe, pool, n=1, cutoff=0.6)
            if matches:
                return f"{module}.{matches[0]}"
            return None
        pool = sorted(self.index.bare | self.index.modules)
        matches = difflib.get_close_matches(segments[-1], pool, n=1, cutoff=0.72)
        return matches[0] if matches else None

    # -- batch -------------------------------------------------------------

    def check(
        self,
        candidates: Sequence[Candidate],
        file: str,
        kind: str,
        source_lines: Optional[Sequence[str]] = None,
    ) -> List[Finding]:
        """Resolve *candidates*; return a :class:`Finding` per ghost."""
        findings: List[Finding] = []
        seen = set()
        for candidate in candidates:
            reason = self.explain(candidate.token)
            if reason is None:
                continue
            dedupe = (file, candidate.line, candidate.token)
            if dedupe in seen:
                continue
            seen.add(dedupe)
            context = ""
            if source_lines and 1 <= candidate.line <= len(source_lines):
                context = _trim(source_lines[candidate.line - 1], candidate.token)
            findings.append(
                Finding(
                    file=file,
                    line=candidate.line,
                    col=candidate.col,
                    token=candidate.token,
                    kind=kind,
                    confidence=candidate.confidence,
                    message=reason,
                    context=context,
                    suggestion=self.suggest(candidate.token),
                )
            )
        return findings


def _trim(line: str, token: str, width: int = 88) -> str:
    """A single-line excerpt of *line* centered on *token*."""
    text = line.strip()
    if len(text) <= width:
        return text
    anchor = text.find(token)
    if anchor < 0:
        return text[: width - 3] + "..."
    start = max(0, anchor - (width - len(token)) // 2)
    end = min(len(text), start + width)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"
