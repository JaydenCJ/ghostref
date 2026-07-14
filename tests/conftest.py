"""Shared fixtures: build throwaway project trees and run scans against them.

Every test works on files under pytest's ``tmp_path`` — nothing touches the
repository itself, no network is involved, and results are deterministic.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

# Make `import ghostref` work from a plain checkout without installation.
SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ghostref.scanner import ScanOptions, scan_project  # noqa: E402


@pytest.fixture
def project(tmp_path):
    """Factory that materializes ``{relative_path: source}`` under tmp_path."""

    def build(files):
        for relative, source in files.items():
            target = tmp_path / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(textwrap.dedent(source), encoding="utf-8")
        return tmp_path

    return build


@pytest.fixture
def scan(project):
    """Build a tree and scan it in one step; returns the ScanResult."""

    def run(files, **option_kwargs):
        root = project(files)
        options = ScanOptions(**option_kwargs)
        return scan_project([root], options, root=root)

    return run


def tokens(result):
    """The ghost tokens of a scan result, in report order."""
    return [finding.token for finding in result.findings]
