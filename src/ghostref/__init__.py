"""ghostref: find comments and docs referencing identifiers that no longer exist.

The public API mirrors what the CLI does:

- :func:`ghostref.scanner.scan_project` runs the whole pipeline and returns
  findings plus scan statistics.
- :func:`ghostref.symbols.collect_symbols` builds the live-symbol index on
  its own, for tools that only need the symbol table.
- :class:`ghostref.resolve.Resolver` answers "is this token live?" for a
  single token, deterministically.
"""

from ghostref.baseline import Baseline
from ghostref.resolve import Finding, Resolver
from ghostref.scanner import ScanOptions, ScanResult, scan_project
from ghostref.symbols import SymbolIndex, collect_symbols

__version__ = "0.1.0"

__all__ = [
    "Baseline",
    "Finding",
    "Resolver",
    "ScanOptions",
    "ScanResult",
    "SymbolIndex",
    "__version__",
    "collect_symbols",
    "scan_project",
]
