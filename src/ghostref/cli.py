"""Command-line interface: ``ghostref scan | symbols | baseline``.

Exit codes are CI-friendly and documented:

- ``0`` — clean (or informational subcommand succeeded)
- ``1`` — ghost references found by ``scan``
- ``2`` — usage or input error (bad path, unreadable baseline, ...)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from ghostref.baseline import Baseline
from ghostref.report import FORMATS, RENDERERS, pluralize
from ghostref.scanner import ScanOptions, scan_project

EXIT_CLEAN = 0
EXIT_GHOSTS = 1
EXIT_ERROR = 2


def _version() -> str:
    from ghostref import __version__

    return __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ghostref",
        description=(
            "Find comments and docs referencing identifiers that no longer "
            "exist in your code."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"ghostref {_version()}"
    )
    subparsers = parser.add_subparsers(dest="command", metavar="command")

    scan = subparsers.add_parser(
        "scan", help="scan for ghost references (exit 1 when any are found)"
    )
    _add_scan_arguments(scan)
    scan.add_argument(
        "--format",
        choices=FORMATS,
        default="text",
        help="output format (default: text)",
    )
    scan.add_argument(
        "--baseline",
        type=Path,
        metavar="FILE",
        help="suppress findings recorded in this baseline file",
    )

    symbols = subparsers.add_parser(
        "symbols", help="print the live-symbol index ghostref resolves against"
    )
    symbols.add_argument("paths", nargs="+", type=Path, help="files or directories")
    symbols.add_argument(
        "--kind", action="append", default=None, help="only show these symbol kinds"
    )
    symbols.add_argument(
        "--root",
        type=Path,
        default=None,
        metavar="DIR",
        help="project root for module names (default: first path)",
    )

    baseline = subparsers.add_parser(
        "baseline", help="record current findings so future scans ignore them"
    )
    _add_scan_arguments(baseline)
    baseline.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path(".ghostref-baseline.json"),
        metavar="FILE",
        help="where to write the baseline (default: .ghostref-baseline.json)",
    )
    return parser


def _add_scan_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("paths", nargs="+", type=Path, help="files or directories")
    parser.add_argument(
        "--docs",
        action="store_true",
        help="also scan Markdown files found in directories",
    )
    parser.add_argument(
        "--no-params",
        action="store_true",
        help="skip the documented-parameter-vs-signature check",
    )
    parser.add_argument(
        "--min-confidence",
        choices=("medium", "high"),
        default="medium",
        help="report only findings at or above this confidence (default: medium)",
    )
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        metavar="NAME",
        help="treat NAME as live (repeatable)",
    )
    parser.add_argument(
        "--allow-file",
        type=Path,
        metavar="FILE",
        help="file with one allowed name per line ('#' comments ok)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="skip paths matching this glob, relative to each scanned root",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        metavar="DIR",
        help="project root for module names and relative paths (default: first path)",
    )


def _load_allow(names: Sequence[str], allow_file: Optional[Path]) -> frozenset:
    allowed = set(names)
    if allow_file is not None:
        for raw in allow_file.read_text(encoding="utf-8").splitlines():
            entry = raw.split("#", 1)[0].strip()
            if entry:
                allowed.add(entry)
    return frozenset(allowed)


def _options_from(args: argparse.Namespace) -> ScanOptions:
    return ScanOptions(
        include_markdown=args.docs,
        check_params=not args.no_params,
        min_confidence=args.min_confidence,
        allow=_load_allow(args.allow, args.allow_file),
        excludes=tuple(args.exclude),
    )


def _resolve_root(args: argparse.Namespace) -> Path:
    if args.root is not None:
        return args.root
    first = args.paths[0]
    return first if first.is_dir() else first.parent


def _run_scan(args: argparse.Namespace) -> int:
    root = _resolve_root(args)
    result = scan_project(args.paths, _options_from(args), root=root)
    if result.errors and not result.findings and not result.stats.python_files:
        for error in result.errors:
            print(f"ghostref: error: {error}", file=sys.stderr)
        return EXIT_ERROR
    findings = result.findings
    if args.baseline is not None:
        try:
            baseline = Baseline.load(args.baseline)
        except (OSError, ValueError, KeyError) as exc:
            print(f"ghostref: error: {exc}", file=sys.stderr)
            return EXIT_ERROR
        findings = baseline.filter(findings, root)
    renderer = RENDERERS[args.format]
    sys.stdout.write(renderer(findings, result.stats, root, result.errors))
    return EXIT_GHOSTS if findings else EXIT_CLEAN


def _run_symbols(args: argparse.Namespace) -> int:
    root = _resolve_root(args)
    result = scan_project(
        args.paths, ScanOptions(check_params=False), root=root
    )
    if result.errors and not result.stats.python_files:
        for error in result.errors:
            print(f"ghostref: error: {error}", file=sys.stderr)
        return EXIT_ERROR
    wanted = set(args.kind) if args.kind else None
    rows = sorted(
        (
            (symbol.qualname, symbol.kind, symbol.file, symbol.line)
            for symbol in result.index.symbols
            if wanted is None or symbol.kind in wanted
        ),
    )
    for qualname, kind, file, line in rows:
        print(f"{qualname}\t{kind}\t{file}:{line}")
    print(f"# {pluralize(len(rows), 'symbol')}", file=sys.stderr)
    return EXIT_CLEAN


def _run_baseline(args: argparse.Namespace) -> int:
    root = _resolve_root(args)
    result = scan_project(args.paths, _options_from(args), root=root)
    if result.errors and not result.stats.python_files:
        for error in result.errors:
            print(f"ghostref: error: {error}", file=sys.stderr)
        return EXIT_ERROR
    args.output.write_text(
        Baseline().dump(result.findings, root), encoding="utf-8"
    )
    print(
        f"baseline written: {args.output} "
        f"({pluralize(len(result.findings), 'finding')})"
    )
    return EXIT_CLEAN


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return EXIT_ERROR
    try:
        if args.command == "scan":
            return _run_scan(args)
        if args.command == "symbols":
            return _run_symbols(args)
        return _run_baseline(args)
    except OSError as exc:
        print(f"ghostref: error: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
