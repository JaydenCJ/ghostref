"""Markdown scanning: inline code spans only, fenced blocks skipped."""

from ghostref.markdown import extract_markdown_candidates


def tokens(text):
    return [candidate.token for candidate in extract_markdown_candidates(text)]


def test_inline_code_spans_yield_candidates():
    assert tokens("Call `setup_router()` before `dispatch`.") == [
        "setup_router",
        "dispatch",
    ]
    text = "line one\n\nsee `target_ref` here\n"
    (candidate,) = extract_markdown_candidates(text)
    assert candidate.line == 3  # 1-based, accurate across blank lines


def test_fenced_code_blocks_are_skipped():
    text = "before\n```python\nmention_inside_fence()\n```\nafter `real_ref`\n"
    assert tokens(text) == ["real_ref"]
    tilde = "~~~\nfenced_mention()\n~~~\n`kept_mention`\n"
    assert tokens(tilde) == ["kept_mention"]


def test_sphinx_roles_in_docs_are_recognized():
    (candidate,) = extract_markdown_candidates("See :func:`pkg.handler` here.")
    assert candidate.token == "pkg.handler"
    assert candidate.signal == "role"


def test_non_identifier_spans_are_ignored():
    assert tokens("Run `pip install -e .` and pass `--docs`.") == []


def test_filename_spans_are_ignored():
    assert tokens("Edit `settings.yaml` and `router.py` first.") == []


def test_ignore_marker_suppresses_the_line():
    text = "`gone_ref` <!-- ghostref: ignore -->\n`checked_ref`\n"
    assert tokens(text) == ["checked_ref"]
