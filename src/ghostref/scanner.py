"""The scan pipeline: discover → index symbols → extract → resolve → report.

:func:`scan_project` is the single entry point used by the CLI, the test
suite, and any embedding tool. It is pure with respect to its inputs: the
same tree and options always produce the same findings in the same order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import FrozenSet, List, Optional, Sequence

from ghostref.candidates import HIGH, extract_candidates
from ghostref.comments import extract_blocks
from ghostref.discover import discover
from ghostref.docparams import check_docstring_params
from ghostref.markdown import extract_markdown_candidates
from ghostref.resolve import Finding, Resolver
from ghostref.symbols import SymbolIndex, collect_file


@dataclass(frozen=True)
class ScanOptions:
    """Everything that can change what a scan reports."""

    include_markdown: bool = False
    check_params: bool = True
    min_confidence: str = "medium"  # "medium" reports all, "high" only high
    allow: FrozenSet[str] = frozenset()
    excludes: Sequence[str] = ()


@dataclass
class ScanStats:
    """Counters surfaced in every report format."""

    python_files: int = 0
    markdown_files: int = 0
    symbols: int = 0
    blocks: int = 0
    candidates: int = 0


@dataclass
class ScanResult:
    findings: List[Finding] = field(default_factory=list)
    stats: ScanStats = field(default_factory=ScanStats)
    errors: List[str] = field(default_factory=list)
    index: SymbolIndex = field(default_factory=SymbolIndex)


def scan_project(
    paths: Sequence[Path],
    options: ScanOptions = ScanOptions(),
    root: Optional[Path] = None,
) -> ScanResult:
    """Scan *paths* and return every ghost reference found.

    *root* anchors module-name derivation and relative paths in reports;
    it defaults to the first path (or its parent when it is a file).
    """
    paths = [Path(p) for p in paths]
    if root is None:
        first = paths[0] if paths else Path(".")
        root = first if first.is_dir() else first.parent
    result = ScanResult()

    missing = [p for p in paths if not p.exists()]
    if missing:
        result.errors.extend(f"{p}: no such file or directory" for p in missing)
        return result

    python_files, markdown_files = discover(
        paths, options.include_markdown, options.excludes
    )
    result.stats.python_files = len(python_files)
    result.stats.markdown_files = len(markdown_files)

    # Pass 1: the live-symbol index covers *all* scanned Python files, so a
    # comment in one module may legitimately reference a symbol in another.
    sources = {}
    for path in python_files:
        try:
            sources[path] = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            result.errors.append(f"{path}: {exc.strerror or exc}")
    for path, source in sources.items():
        try:
            collect_file(result.index, path, root, source=source)
        except SyntaxError as exc:
            result.errors.append(
                f"{path}:{exc.lineno or 0}: syntax error: {exc.msg}"
            )
    result.stats.symbols = len(result.index)
    resolver = Resolver(index=result.index, allow=options.allow)

    # Pass 2: extract prose, resolve candidates, collect ghosts.
    findings: List[Finding] = []
    for path, source in sources.items():
        source_lines = source.splitlines()
        blocks = extract_blocks(source, str(path))
        result.stats.blocks += len(blocks)
        for block in blocks:
            candidates = extract_candidates(block.text, block.line)
            result.stats.candidates += len(candidates)
            findings.extend(
                resolver.check(candidates, str(path), block.kind, source_lines)
            )
        if options.check_params:
            findings.extend(check_docstring_params(source, str(path)))

    for path in markdown_files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            result.errors.append(f"{path}: {exc.strerror or exc}")
            continue
        candidates = extract_markdown_candidates(text)
        result.stats.candidates += len(candidates)
        findings.extend(
            resolver.check(candidates, str(path), "markdown", text.splitlines())
        )

    if options.min_confidence == HIGH:
        findings = [finding for finding in findings if finding.confidence == HIGH]

    findings.sort(key=Finding.sort_key)
    result.findings = findings
    return result
