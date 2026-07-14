"""Candidate extraction: which prose tokens count as code references."""

from ghostref.candidates import extract_from_line, parse_inline_code

def one(line):
    found = extract_from_line(line, 1)
    assert len(found) == 1, f"expected one candidate, got {found}"
    return found[0]


def all_tokens(line):
    return [candidate.token for candidate in extract_from_line(line, 1)]


def test_backticked_names_are_high_confidence():
    candidate = one("uses `frobnicate` internally")
    assert candidate.token == "frobnicate"
    assert candidate.confidence == "high"
    assert candidate.signal == "backtick"
    # Calls normalize to the callee; RST double backticks work too.
    assert one("see `Cart.add(item)` for details").token == "Cart.add"
    assert one("uses ``frobnicate`` internally").token == "frobnicate"


def test_call_syntax_is_high_confidence():
    candidate = one("delegates to sync_levels() when stale")
    assert candidate.token == "sync_levels"
    assert candidate.confidence == "high"
    assert candidate.signal == "call"


def test_sphinx_roles_are_recognized():
    candidate = one("see :func:`pkg.compute` for details")
    assert candidate.token == "pkg.compute"
    assert candidate.signal == "role"


def test_dotted_snake_and_camel_are_medium_confidence():
    for line, token in (
        ("configured via cart.total_price here", "cart.total_price"),
        ("the retry_budget is exceeded", "retry_budget"),
        ("returns a CartSnapshot value", "CartSnapshot"),
    ):
        candidate = one(line)
        assert candidate.token == token
        assert candidate.confidence == "medium"


def test_plain_english_words_are_never_candidates():
    assert all_tokens("the quick brown fox jumps over the lazy dog") == []


def test_prose_conventions_are_never_candidates():
    # Each line is a comment idiom that *looks* identifier-shaped but is not
    # a code reference; flagging any of them would make the gate unusable.
    for line in (
        "docs at https://example.test/api.reference_v2 here",  # URLs
        "TODO(alice): revisit later, FIXME(bob) too",  # marker calls
        "bounded, e.g. by config; i.e. the default",  # abbreviations
        "edit config.yaml then ping api.example.test",  # files / hosts
        "published to GitHub and PyPI, parsed with NumPy",  # proper nouns
    ):
        assert all_tokens(line) == [], line


def test_stronger_signals_claim_spans_before_weaker_ones():
    # `cart.add()` must surface once as a call, not again as dotted/snake.
    found = extract_from_line("calls cart.add_item() then logs", 1)
    assert [candidate.signal for candidate in found] == ["call"]
    assert found[0].token == "cart.add_item"


def test_backticked_non_identifier_code_produces_no_candidate():
    assert all_tokens("pass `--force` or `a + b` to override") == []
    # ...and columns stay 1-based, pointing at the token itself
    assert one("x stale_name here").col == 3


def test_parse_inline_code_normalizes_tilde_and_calls():
    assert parse_inline_code("~pkg.Cart") == "pkg.Cart"
    assert parse_inline_code("compute()") == "compute"
    assert parse_inline_code("a + b") is None
    assert parse_inline_code("--flag") is None
