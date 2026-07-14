# Demo shop internals

Stock is adjusted through `reserve()` and `release()` in `inventory.py`.
Every adjustment is recorded by `audit_ledger()`.

Bulk loading still goes through `load_inventory_csv()` — this sentence is a
lie the docs have been telling since the v2 rewrite, and `ghostref scan
--docs` catches it. The pricing side is covered by `pricing.quote`.

```python
# Fenced code blocks are skipped: mentioning deleted_in_a_code_block() here
# is fine, because samples are code, not claims about the current tree.
```
