"""The resolution rule ladder: live vs ghost, deterministically."""

from pathlib import Path

import pytest

from ghostref.resolve import Resolver
from ghostref.symbols import collect_symbols


@pytest.fixture
def resolver(tmp_path):
    (tmp_path / "shop").mkdir()
    (tmp_path / "shop" / "cart.py").write_text(
        "import json\n"
        "class Cart:\n"
        "    def __init__(self):\n"
        "        self.items = []\n"
        "    def total(self):\n"
        "        subtotal = 0\n"
        "        return subtotal\n"
        "def checkout(order_id):\n"
        "    pass\n",
        encoding="utf-8",
    )
    index = collect_symbols([tmp_path / "shop" / "cart.py"], tmp_path)
    return Resolver(index=index)


def test_defined_names_are_live(resolver):
    for name in ("Cart", "total", "checkout", "order_id", "subtotal", "items"):
        assert resolver.is_live(name), name


def test_unknown_single_names_are_ghosts(resolver):
    assert not resolver.is_live("legacy_checkout")
    assert "no symbol named 'legacy_checkout'" in resolver.explain("legacy_checkout")


def test_keywords_builtins_and_stdlib_are_live(resolver):
    for name in ("yield", "ValueError", "len", "os", "json"):
        assert resolver.is_live(name), name


def test_dotted_path_into_scanned_module_resolves_exactly(resolver):
    assert resolver.is_live("shop.cart.Cart.total")
    assert resolver.is_live("cart.checkout")


def test_missing_symbol_in_scanned_module_names_the_module(resolver):
    reason = resolver.explain("shop.cart.legacy_checkout")
    assert reason == "module 'shop.cart' has no symbol 'legacy_checkout'"


def test_attributes_of_unscanned_modules_are_unverifiable_hence_live(resolver):
    # `json` is imported, never scanned: nothing can be proven missing in it.
    assert resolver.is_live("json.dumps")
    assert resolver.is_live("os.path.join")


def test_self_attributes_resolve_against_indexed_attributes(resolver):
    assert resolver.is_live("self.items")
    reason = resolver.explain("self.legacy_cache")
    assert "is ever assigned on self" in reason


def test_attribute_of_live_object_is_live(resolver):
    # `subtotal.frobnicate` cannot be verified without running code.
    assert resolver.is_live("subtotal.frobnicate")


def test_dotted_mentions_need_a_live_head_or_tail(resolver):
    # Shorthand mention: tail exists even though the head does not — live.
    assert resolver.is_live("unknown_head.checkout")
    # Nothing resolves on either end — ghost.
    reason = resolver.explain("phantom.zone")
    assert reason == "neither 'phantom' nor 'zone' exists in the scanned code"


def test_allowlist_wins_over_everything(tmp_path):
    index = collect_symbols([], tmp_path)
    resolver = Resolver(index=index, allow=frozenset({"blessed_name"}))
    assert resolver.is_live("blessed_name")
    assert resolver.is_live("blessed_name.attribute")


def test_suggestions_find_close_live_names_or_stay_silent(resolver):
    assert resolver.suggest("chekout") == "checkout"
    assert resolver.suggest("shop.cart.chekout") == "shop.cart.checkout"
    assert resolver.suggest("zzz_qqq_xxx") is None  # no misleading guesses


def test_resolution_is_deterministic_across_calls(resolver):
    # Same token, same answer, every time — the whole point of the tool.
    results = {resolver.explain("shop.cart.legacy_checkout") for _ in range(50)}
    assert len(results) == 1
