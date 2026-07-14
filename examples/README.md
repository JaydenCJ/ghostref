# ghostref examples

`demo_project/` is a deliberately haunted two-module "shop" plus one
Markdown guide. It was written as if a fast refactor had just landed:
`sync_stock_levels` was split into `reserve`/`release`, the CSV bulk loader
was deleted, a parameter was renamed — and the comments, docstrings, and
docs were never updated.

Run the gate against it from the repository root:

```bash
python -m ghostref scan examples/demo_project --docs
```

Expected: exit code 1 and eight findings —

| Where | Ghost | Why it is a lie |
|---|---|---|
| `inventory.py` docstring | `sync_stock_levels` (×2, also a comment) | split into `reserve`/`release` long ago |
| `inventory.py` docstring | `quantiy` | parameter is `quantity`; a typo the signature check catches |
| `inventory.py` docstring | `restock_from_csv` | the CSV path was deleted |
| `inventory.py` docstring | `bulk_import` | Sphinx role points at a removed function |
| `pricing.py` docstring | `DiscountMatrix` | class removed in the v2 rewrite |
| `pricing.py` comment | `apply_bulk_discount` | function removed in the v2 rewrite |
| `GUIDE.md` | `load_inventory_csv` | docs describing a deleted loader |

Equally important is what stays quiet: `reserve()`, `release()`,
`audit_ledger`, `TAX_RATE`, and the cross-module mentions `inventory.reserve`
and `pricing.quote` are all live, so none of them are flagged. The fenced
code block in `GUIDE.md` is skipped by design.

Try the adoption workflow on the same tree:

```bash
python -m ghostref baseline examples/demo_project --docs -o /tmp/baseline.json
python -m ghostref scan examples/demo_project --docs --baseline /tmp/baseline.json  # exits 0
```

`scripts/smoke.sh` runs all of the above (plus a drift case) and asserts on
the output.
