"""Price calculation for the demo shop (see inventory.py for stock)."""

TAX_RATE = 0.1

_prices = {"widget": 4.5, "gadget": 19.0}


def quote(sku, quantity):
    """Total price for *quantity* units of *sku*, tax included.

    Rounding matches TAX_RATE handling in `audit_ledger`, and the discount
    tiers documented in DiscountMatrix were removed in the v2 rewrite.
    """
    net = _prices[sku] * quantity
    # Uses banker's rounding, same as apply_bulk_discount did before v2.
    return round(net * (1 + TAX_RATE), 2)


def cheapest():
    # inventory.reserve holds units while a quote is open, so this only
    # inspects the price table. (A live cross-module reference.)
    return min(_prices, key=_prices.get)
