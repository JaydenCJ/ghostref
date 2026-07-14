# Contributing to ghostref

Thanks for your interest in contributing. Issues, discussions, and pull
requests are all welcome.

## Getting started

You need Python 3.9 or newer; nothing else.

```bash
git clone https://github.com/JaydenCJ/ghostref
cd ghostref
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
bash scripts/smoke.sh
```

`scripts/smoke.sh` drives the real CLI end-to-end — haunted-demo scan, JSON
and GitHub output, baseline record/gate cycle, symbols dump, self-scan — and
must print `SMOKE OK`.

## Before you open a pull request

1. Format touched files consistently with the surrounding code (PEP 8,
   4-space indents, double quotes; formatting is enforced in review).
2. Keep `python3 -m compileall src` warning-free and imports sorted.
3. `pytest` — all tests must pass.
4. `bash scripts/smoke.sh` — must print `SMOKE OK`.
5. Add tests for behavior changes; keep logic in pure, unit-testable modules.

## Ground rules

- **No runtime dependencies.** The package is standard-library only; that is
  a feature, not an accident. Test-only tools belong in the `dev` extra.
- **Determinism is the contract.** Detection and resolution rules must be
  exact — no scoring models, no environment-dependent behavior, no network.
  A rule change needs an update to `docs/detection-rules.md` in the same PR.
- **The self-scan must stay clean.** `ghostref scan src --root . --allow-file
  .ghostref-allow` has to exit 0; new illustrative names in docstrings go
  into `.ghostref-allow` with a comment.
- Code comments and doc comments are written in English.
- Keep the three READMEs aligned: `README.md`, `README.zh.md`, and
  `README.ja.md` share the same line-for-line structure; English is
  authoritative.

## Reporting bugs

Please include your `ghostref --version` output, the exact command, the
report (text or `--format json`), and a minimal file that reproduces the
false positive or missed ghost — one comment plus one stub function is
usually enough.

## Security

Please do not report security issues in public GitHub issues. Use GitHub's
private vulnerability reporting on this repository instead.
