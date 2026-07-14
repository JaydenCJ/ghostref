"""End-to-end scans through the public scan_project pipeline."""

from pathlib import Path

from ghostref.scanner import ScanOptions, scan_project

from conftest import tokens


def test_comment_referencing_deleted_function_is_found(scan):
    result = scan(
        {
            "app.py": """
            # Falls back to legacy_loader() when the cache is cold.
            def loader():
                pass
            """
        }
    )
    assert tokens(result) == ["legacy_loader"]
    assert result.findings[0].kind == "comment"


def test_cross_module_references_resolve_against_the_whole_index(scan):
    # The index spans all scanned files: a comment in a.py may point at b.py.
    result = scan(
        {
            "a.py": "# uses helper_from_b() for parsing\nx = 1\n",
            "b.py": "def helper_from_b():\n    pass\n",
        }
    )
    assert result.findings == []
    haunted = scan({"c.py": "# uses helper_from_c() for output\ny = 2\n"})
    assert tokens(haunted) == ["helper_from_c"]


def test_docstring_ghosts_and_healthy_references_are_distinguished(scan):
    result = scan(
        {
            "m.py": '''
            def keep():
                """Companion of :func:`gone` and :func:`keep`."""
            '''
        }
    )
    assert tokens(result) == ["gone"]
    assert result.findings[0].kind == "docstring"


def test_markdown_files_are_scanned_only_with_include_markdown(scan):
    files = {
        "code.py": "def real():\n    pass\n",
        "README.md": "Call `imaginary_api()` then `real()`.\n",
    }
    without = scan(files)
    assert without.findings == []
    with_docs = scan(files, include_markdown=True)
    assert tokens(with_docs) == ["imaginary_api"]
    assert with_docs.findings[0].kind == "markdown"


def test_min_confidence_high_drops_medium_findings(scan):
    files = {
        "m.py": (
            "# bare mention of stale_thing here\n"
            "# strong mention of stale_thing() here\n"
            "x = 1\n"
        )
    }
    everything = scan(files)
    assert len(everything.findings) == 2
    strict = scan(files, min_confidence="high")
    assert [finding.confidence for finding in strict.findings] == ["high"]


def test_param_check_can_be_disabled(scan):
    files = {
        "m.py": '''
        def f(a):
            """Args:
                gone: Stale.
            """
        '''
    }
    assert tokens(scan(files)) == ["gone"]
    assert scan(files, check_params=False).findings == []


def test_syntax_errors_are_reported_but_do_not_abort(scan):
    result = scan(
        {
            "bad.py": "def broken(:\n",
            "good.py": "# mentions absent_helper()\nx = 1\n",
        }
    )
    assert tokens(result) == ["absent_helper"]
    assert any("syntax error" in error for error in result.errors)


def test_missing_path_is_an_error_not_a_crash(tmp_path):
    result = scan_project([tmp_path / "nope"], ScanOptions())
    assert result.findings == []
    assert "no such file" in result.errors[0]


def test_findings_are_sorted_and_deduplicated(scan):
    result = scan(
        {
            "b.py": "# gone_two() then gone_one()\nx = 1\n",
            "a.py": "# gone_three() calls gone_three() twice\ny = 2\n",
        }
    )
    ordered = [(Path(f.file).name, f.line, f.col) for f in result.findings]
    assert ordered == sorted(ordered)
    # same token on the same line is reported once
    assert tokens(result).count("gone_three") == 1


def test_skip_directories_and_exclude_globs_filter_files(project):
    root = project(
        {
            "keep.py": "# refers to lost_name()\nx = 1\n",
            ".venv/lib.py": "# refers to other_lost()\ny = 2\n",
            "__pycache__/junk.py": "# refers to cached_lost()\nz = 3\n",
            "generated/gen.py": "# refers to generated_lost()\nw = 4\n",
        }
    )
    result = scan_project(
        [root], ScanOptions(excludes=("generated/*",)), root=root
    )
    assert tokens(result) == ["lost_name"]


def test_stats_are_counted_and_scans_are_reproducible(project):
    root = project(
        {
            "m.py": (
                '"""Doc mentioning real_func()."""\n'
                "# comment mentioning gone_func()\n"
                "def real_func():\n"
                "    pass\n"
            )
        }
    )
    first = scan_project([root], ScanOptions(), root=root)
    assert first.stats.python_files == 1
    assert first.stats.blocks == 2
    assert first.stats.candidates == 2
    assert first.stats.symbols >= 1
    second = scan_project([root], ScanOptions(), root=root)
    assert first.findings == second.findings
