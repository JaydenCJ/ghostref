"""Comment and docstring extraction with exact source positions."""

from ghostref.comments import extract_blocks, extract_comments, extract_docstrings


def test_hash_comments_are_extracted_with_line_numbers():
    source = "x = 1\n# references old_thing here\ny = 2\n"
    blocks = extract_comments(source, "f.py")
    assert len(blocks) == 1
    assert blocks[0].line == 2
    assert "old_thing" in blocks[0].text
    assert blocks[0].kind == "comment"
    # inline trailing comments keep a column pointing into the comment
    (inline,) = extract_comments("value = compute()  # from legacy_pipe\n", "f.py")
    assert (inline.line, inline.col > 15) == (1, True)


def test_tool_directives_are_not_treated_as_prose():
    source = (
        "#!/usr/bin/env python3\n"
        "# -*- coding: utf-8 -*-\n"
        "x = []  # type: list[int]\n"
        "y = 1  # noqa: E501\n"
        "z = 2  # pylint: disable=invalid-name\n"
        "# a real comment about stale_helper\n"
    )
    blocks = extract_comments(source, "f.py")
    assert len(blocks) == 1
    assert "stale_helper" in blocks[0].text


def test_ghostref_ignore_suppresses_the_comment():
    source = "# mentions gone_function() but ghostref: ignore\n# gone_function()\n"
    blocks = extract_comments(source, "f.py")
    assert len(blocks) == 1
    assert blocks[0].line == 2


def test_module_class_and_function_docstrings_are_extracted():
    source = (
        '"""Module doc."""\n'
        "class C:\n"
        '    """Class doc."""\n'
        "    def m(self):\n"
        '        """Method doc."""\n'
    )
    blocks = extract_docstrings(source, "f.py")
    assert [block.line for block in blocks] == [1, 3, 5]
    assert all(block.kind == "docstring" for block in blocks)


def test_docstring_line_is_the_string_literal_line():
    source = "def f():\n\n    '''Doc on line three.'''\n"
    (block,) = extract_docstrings(source, "f.py")
    assert block.line == 3


def test_unterminated_string_keeps_earlier_comments():
    # A broken tail must not hide ghosts in the healthy part of the file.
    source = "# early comment about lost_symbol\nx = '''unterminated\n"
    blocks = extract_comments(source, "f.py")
    assert len(blocks) == 1
    assert "lost_symbol" in blocks[0].text


def test_extract_blocks_merges_and_sorts_by_position():
    source = '"""Doc."""\n# comment one\n# comment two\n'
    blocks = extract_blocks(source, "f.py")
    assert [block.line for block in blocks] == [1, 2, 3]
    assert [block.kind for block in blocks] == ["docstring", "comment", "comment"]
    # ordinary string literals are neither docstrings nor comments
    assert extract_blocks('x = "mentions phantom_func()"\n', "f.py") == []
