"""Deterministic file discovery for scan targets.

Directories are walked in sorted order with a fixed set of skip directories
(virtualenvs, caches, VCS internals, build output) plus user-supplied glob
excludes. Explicit file arguments are always accepted, whatever their
extension — naming a file is consent to scan it.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

#: Directory names never descended into.
SKIP_DIRS = frozenset(
    {
        ".git", ".hg", ".svn", ".venv", "venv", ".tox", ".nox", ".eggs",
        "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache",
        ".ruff_cache", "build", "dist", ".idea", ".vscode", "site-packages",
    }
)


def _excluded(path: Path, root: Path, excludes: Sequence[str]) -> bool:
    try:
        rel = str(path.relative_to(root))
    except ValueError:
        rel = str(path)
    return any(
        fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(path.name, pattern)
        for pattern in excludes
    )


def _walk(directory: Path, root: Path, excludes: Sequence[str]) -> Iterable[Path]:
    entries = sorted(directory.iterdir(), key=lambda entry: entry.name)
    for entry in entries:
        if entry.is_dir():
            if entry.name in SKIP_DIRS or _excluded(entry, root, excludes):
                continue
            yield from _walk(entry, root, excludes)
        elif entry.is_file() and not _excluded(entry, root, excludes):
            yield entry


def discover(
    paths: Sequence[Path],
    include_markdown: bool,
    excludes: Sequence[str] = (),
) -> Tuple[List[Path], List[Path]]:
    """Split *paths* into (python_files, markdown_files), both sorted.

    Directories yield ``*.py`` always and ``*.md`` when *include_markdown*
    is set; explicit files are classified by suffix and never filtered.
    """
    python_files: List[Path] = []
    markdown_files: List[Path] = []
    for path in paths:
        if path.is_dir():
            for entry in _walk(path, path, excludes):
                if entry.suffix == ".py":
                    python_files.append(entry)
                elif entry.suffix == ".md" and include_markdown:
                    markdown_files.append(entry)
        elif path.suffix == ".md":
            markdown_files.append(path)
        else:
            python_files.append(path)
    python_files.sort()
    markdown_files.sort()
    return python_files, markdown_files
