# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-13

### Added

- Live-symbol index built with a single `ast` walk per file: functions,
  classes, methods (bare, dotted, and module-qualified), parameters
  (including `*args`/`**kwargs` names), assignment targets at every scope,
  `self.attr`/`cls.attr` attributes, imports with aliases, `__all__`
  entries, and module names derived from file paths (`src/` layout aware).
- Comment extraction via `tokenize` and docstring extraction via `ast`, with
  exact line/column positions; tool directives (`# noqa`, `# type:`,
  `# pylint:`, shebangs, coding cookies) excluded, and a
  `ghostref: ignore` marker for deliberate exceptions.
- Signal-based candidate extraction from prose: Sphinx roles, backtick
  spans, and call syntax at high confidence; dotted paths, snake_case, and
  CamelCase words at medium confidence — with URL masking, span claiming,
  and noise filters for marker idioms, abbreviations, filenames/hostnames,
  and mixed-case product names.
- Deterministic nine-rule resolution ladder (documented in
  `docs/detection-rules.md`), including provable "module 'x' has no symbol
  'y'" findings for scanned modules and "did you mean" suggestions via
  `difflib`.
- Documented-parameter checking against real signatures for Google, Sphinx,
  and NumPy docstring styles; functions accepting `**kwargs` are skipped by
  design.
- Markdown documentation scanning (`--docs`): inline code spans and Sphinx
  roles, with fenced code blocks skipped.
- Baseline workflow (`ghostref baseline`, `scan --baseline`) with stable,
  line-number-independent fingerprints for incremental adoption.
- `ghostref` CLI: `scan` (text/JSON/GitHub-annotation output, exit 1 on
  ghosts), `symbols` (index dump), `baseline`; `--allow`, `--allow-file`,
  `--exclude`, `--min-confidence`, `--no-params`, `--root` options.
- Haunted demo project under `examples/demo_project/` with seven staged
  lies, and a dogfood self-scan (`.ghostref-allow`) kept clean by the test
  suite.
- 90 pytest tests and `scripts/smoke.sh` (prints `SMOKE OK`).

### Notes

- The repository ships no CI workflow; verification is local — `pip install -e '.[dev]' && pytest && bash scripts/smoke.sh`.

[0.1.0]: https://github.com/JaydenCJ/ghostref/releases/tag/v0.1.0
