"""Symbol index construction: everything a comment may legitimately name."""

from pathlib import Path

from ghostref.symbols import SymbolIndex, collect_symbols, module_name_for


def index_of(tmp_path, source, name="mod.py"):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return collect_symbols([path], tmp_path)


def test_functions_classes_and_methods_are_indexed(tmp_path):
    index = index_of(
        tmp_path,
        "class Cart:\n"
        "    def add(self, item):\n"
        "        pass\n"
        "def checkout():\n"
        "    pass\n",
    )
    assert {"Cart", "add", "checkout"} <= index.bare
    assert "Cart.add" in index.dotted


def test_methods_are_qualified_with_module_name(tmp_path):
    index = index_of(tmp_path, "class Cart:\n    def add(self):\n        pass\n")
    # module-qualified entries let dotted mentions like `mod.Cart.add` resolve
    assert "mod.Cart.add" in index.dotted
    assert "mod.Cart" in index.dotted


def test_parameters_including_star_args_are_indexed(tmp_path):
    index = index_of(tmp_path, "def f(a, /, b, *rest, c=1, **extras):\n    pass\n")
    assert {"a", "b", "rest", "c", "extras"} <= index.bare


def test_assignment_targets_at_every_scope_are_indexed(tmp_path):
    # Comments routinely name nearby variables, so *every* bind form counts:
    # module globals, locals, loop/with targets, and comprehension variables.
    index = index_of(
        tmp_path,
        "TOP = 1\n"
        "def f():\n"
        "    local_var = 2\n"
        "    for loop_var in range(3):\n"
        "        pass\n"
        "    with open('x') as handle:\n"
        "        pass\n"
        "    squares = [n * n for n in range(3)]\n",
    )
    assert {"TOP", "local_var", "loop_var", "handle", "squares", "n"} <= index.bare


def test_unpacking_walrus_except_and_global_targets_are_indexed(tmp_path):
    index = index_of(
        tmp_path,
        "first, (second, third) = 1, (2, 3)\n"
        "if (flag := True):\n"
        "    pass\n"
        "def f():\n"
        "    global shared_state\n"
        "    try:\n"
        "        pass\n"
        "    except ValueError as caught:\n"
        "        pass\n",
    )
    assert {"first", "second", "third", "flag", "shared_state", "caught"} <= index.bare


def test_self_attribute_assignments_index_the_attribute_name(tmp_path):
    index = index_of(
        tmp_path,
        "class Cart:\n"
        "    def __init__(self):\n"
        "        self.items = []\n",
    )
    # comments saying "self.items holds ..." must resolve
    assert "items" in index.bare


def test_imports_and_aliases_are_indexed(tmp_path):
    index = index_of(
        tmp_path,
        "import json\n"
        "import collections.abc as cabc\n"
        "from pathlib import Path as P\n",
    )
    assert {"json", "cabc", "P"} <= index.bare
    assert "collections.abc" in index.modules


def test_dunder_all_string_entries_are_indexed(tmp_path):
    index = index_of(tmp_path, "__all__ = ['exported_name']\n")
    assert "exported_name" in index.bare


def test_module_names_derive_from_relative_paths(tmp_path):
    index = index_of(tmp_path, "x = 1\n", name="pkg/util.py")
    assert {"pkg", "pkg.util"} <= index.modules
    assert "pkg.util" in index.scanned_modules
    # `src` layout is stripped; `__init__.py` names the package itself.
    src_index = index_of(tmp_path, "x = 1\n", name="src/pkg/core.py")
    assert "pkg.core" in src_index.modules
    assert "src.pkg.core" not in src_index.modules
    assert module_name_for(tmp_path / "pkg" / "__init__.py", tmp_path) == "pkg"


def test_module_prefix_only_matches_scanned_modules():
    index = SymbolIndex()
    index.add_module("imported.thing")  # known from an import, not scanned
    assert index.module_prefix("imported.thing.attr") is None
    index.scanned_modules.add("imported.thing")
    assert index.module_prefix("imported.thing.attr") == "imported.thing"


def test_syntax_error_files_are_skipped_not_fatal(tmp_path):
    good = tmp_path / "good.py"
    good.write_text("def fine():\n    pass\n", encoding="utf-8")
    bad = tmp_path / "bad.py"
    bad.write_text("def broken(:\n", encoding="utf-8")
    index = collect_symbols([good, bad], tmp_path)
    assert "fine" in index.bare
