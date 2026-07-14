"""Inventory bookkeeping for the demo shop.

This module was "refactored at AI speed": ``sync_stock_levels`` was split
into :func:`reserve` and :func:`release`, and the old bulk loader is gone —
but several comments and docstrings still describe the deleted code.
ghostref finds every one of them.
"""

WAREHOUSE = "central"

_stock = {"widget": 12, "gadget": 3}


def reserve(sku, quantity):
    """Reserve stock for an order.

    Args:
        sku: Product identifier to reserve.
        quantiy: How many units to reserve.

    Falls back to `restock_from_csv()` when the SKU is unknown.
    """
    # Delegates the heavy lifting to sync_stock_levels() so the ledger
    # stays consistent with the warehouse counts.
    available = _stock.get(sku, 0)
    if quantity > available:
        raise ValueError(f"only {available} unit(s) of {sku} left")
    _stock[sku] = available - quantity
    return _stock[sku]


def release(sku, quantity):
    """Return previously reserved units to stock.

    The inverse of :func:`reserve`; see also :func:`bulk_import` for the
    initial load. Adjustments are audited by `audit_ledger`.
    """
    _stock[sku] = _stock.get(sku, 0) + quantity
    return _stock[sku]


def audit_ledger():
    # A healthy comment: reserve() and release() both funnel through here.
    return dict(sorted(_stock.items()))
