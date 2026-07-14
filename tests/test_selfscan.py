"""Dogfood: ghostref's own source and docs must scan clean.

The allowlist in `.ghostref-allow` covers the illustrative identifiers used
by ghostref's documentation (a fictional shop with carts and totals); with
it, the tree must contain zero ghost references. This test keeps the README
claim honest and catches new lying comments in this repository at test time.
"""

from pathlib import Path

from ghostref.cli import main

REPO = Path(__file__).resolve().parent.parent


def test_own_source_scans_clean_with_documented_allowlist(capsys):
    code = main(
        [
            "scan",
            str(REPO / "src"),
            "--root",
            str(REPO),
            "--allow-file",
            str(REPO / ".ghostref-allow"),
        ]
    )
    out = capsys.readouterr().out
    assert code == 0, f"ghostref found ghosts in its own source:\n{out}"


def test_demo_project_reports_the_documented_ghosts(capsys):
    code = main(["scan", str(REPO / "examples" / "demo_project"), "--docs"])
    out = capsys.readouterr().out
    assert code == 1
    # The staged lies that examples/demo_project exists to demonstrate:
    for token in (
        "sync_stock_levels",
        "restock_from_csv",
        "bulk_import",
        "quantiy",
        "apply_bulk_discount",
        "DiscountMatrix",
        "load_inventory_csv",
    ):
        assert f"'{token}'" in out, f"expected demo ghost {token!r}"
    # And the healthy cross-references stay quiet:
    assert "'audit_ledger'" not in out
    assert "'pricing.quote'" not in out
