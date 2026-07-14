#!/usr/bin/env bash
# Smoke test for ghostref: scan the demo project, verify the staged ghosts
# are found (and the healthy references are not), then exercise the JSON
# output, baseline workflow, symbols dump, self-scan, and version/help.
# Self-contained: pure stdlib, no network, idempotent (works from a clean tree).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

# The package has zero runtime dependencies, so running from src/ needs no install.
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/ghostref-smoke.XXXXXX")"
trap 'rm -rf "$WORKDIR"' EXIT

fail() { echo "SMOKE FAIL: $1" >&2; exit 1; }

echo "[smoke] python: $("$PYTHON" --version 2>&1)"

# 1. Scan the demo project: staged ghosts must be reported, exit code 1.
set +e
scan_out="$("$PYTHON" -m ghostref scan "$ROOT/examples/demo_project" --docs)"
scan_rc=$?
set -e
echo "$scan_out" | sed 's/^/[scan] /'
[ "$scan_rc" -eq 1 ] || fail "scan of haunted demo should exit 1, got $scan_rc"
for token in sync_stock_levels restock_from_csv bulk_import quantiy \
             apply_bulk_discount DiscountMatrix load_inventory_csv; do
  echo "$scan_out" | grep -q "ghost '$token'" || fail "missing demo ghost '$token'"
done
echo "$scan_out" | grep -q "did you mean 'quantity'?" || fail "missing typo suggestion"
echo "$scan_out" | grep -q "ghost 'audit_ledger'" && fail "live symbol flagged as ghost"
echo "$scan_out" | grep -q "8 ghost references in 3 files" || fail "unexpected summary"

# 2. JSON output parses and agrees on the count.
json_count="$("$PYTHON" -m ghostref scan "$ROOT/examples/demo_project" --docs --format json \
  | "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["summary"]["ghosts"])' \
  || true)"
[ "$json_count" = "8" ] || fail "JSON summary expected 8 ghosts, got '$json_count'"

# 3. GitHub annotation format emits ::error lines for high-confidence ghosts.
github_out="$("$PYTHON" -m ghostref scan "$ROOT/examples/demo_project" --format github || true)"
echo "$github_out" | grep -q '^::error file=inventory.py' \
  || fail "github format missing ::error line"

# 4. Baseline workflow: record findings, then the same scan gates clean.
"$PYTHON" -m ghostref baseline "$ROOT/examples/demo_project" --docs \
  -o "$WORKDIR/baseline.json" | sed 's/^/[baseline] /'
"$PYTHON" -m ghostref scan "$ROOT/examples/demo_project" --docs \
  --baseline "$WORKDIR/baseline.json" >/dev/null \
  || fail "baselined scan should exit 0"

# 5. A new lie on top of the baseline still fails the gate.
cp -R "$ROOT/examples/demo_project" "$WORKDIR/drifted"
printf '\n# pricing is validated by verify_totals() nightly\n' >> "$WORKDIR/drifted/pricing.py"
set +e
"$PYTHON" -m ghostref scan "$WORKDIR/drifted" --docs \
  --baseline "$WORKDIR/baseline.json" > "$WORKDIR/drift.out"
drift_rc=$?
set -e
[ "$drift_rc" -eq 1 ] || fail "new ghost over baseline should exit 1, got $drift_rc"
grep -q "ghost 'verify_totals'" "$WORKDIR/drift.out" || fail "new ghost not reported"
grep -q "ghost 'sync_stock_levels'" "$WORKDIR/drift.out" && fail "baselined ghost resurfaced"

# 6. Symbols dump lists the demo functions with locations.
# (Capture first: piping straight into `grep -q` races — grep exits at the
# first match and the resulting EPIPE fails the pipeline under `pipefail`.)
symbols_out="$("$PYTHON" -m ghostref symbols "$ROOT/examples/demo_project" 2>/dev/null)"
echo "$symbols_out" | grep -q "^reserve	function	" \
  || fail "symbols dump missing 'reserve'"

# 7. Dogfood: ghostref's own source scans clean with the documented allowlist.
"$PYTHON" -m ghostref scan "$ROOT/src" --root "$ROOT" \
  --allow-file "$ROOT/.ghostref-allow" >/dev/null \
  || fail "self-scan of src/ should be clean"

# 8. --version agrees with the package, --help mentions the subcommands.
version_out="$("$PYTHON" -m ghostref --version)"
pkg_version="$("$PYTHON" -c 'import ghostref; print(ghostref.__version__)')"
[ "$version_out" = "ghostref $pkg_version" ] \
  || fail "--version mismatch: '$version_out' vs package '$pkg_version'"
help_out="$("$PYTHON" -m ghostref --help)"
echo "$help_out" | grep -q "baseline" || fail "--help missing baseline command"

echo "SMOKE OK"
