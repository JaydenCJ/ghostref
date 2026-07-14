"""Build the live-symbol index from Python source via the ``ast`` module.

The index is the ground truth ghostref checks comments against. It records
every name a comment could legitimately reference:

- module names derived from file paths (``pkg/util.py`` → ``util``,
  ``pkg.util``, ``pkg``),
- functions, async functions, classes, and methods (bare and dotted,
  e.g. ``Cart.total`` and ``shop.cart.Cart.total``),
- function parameters (including ``*args`` / ``**kwargs`` names),
- assignment targets everywhere — module level, class level, locals,
  ``for``/``with`` targets, comprehension variables, walrus targets —
  because comments routinely name nearby variables,
- ``self.attr`` / ``cls.attr`` assignments inside methods (indexed as the
  attribute name and as ``Class.attr``),
- imported names, including aliases (``import numpy as np`` indexes both),
- string entries of a module-level ``__all__`` list or tuple.

Collection is a single deterministic AST walk per file; no code is executed.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Set


@dataclass(frozen=True)
class Symbol:
    """One live name, with enough location data for tooling output."""

    name: str  # bare name, e.g. "total"
    qualname: str  # dotted path within the module, e.g. "Cart.total"
    kind: str  # function | class | method | parameter | variable | attribute | import | module
    file: str  # path as given to the collector
    line: int  # 1-based definition line


@dataclass
class SymbolIndex:
    """Fast membership views over every collected :class:`Symbol`."""

    symbols: List[Symbol] = field(default_factory=list)
    bare: Set[str] = field(default_factory=set)  # {"total", "Cart", ...}
    dotted: Set[str] = field(default_factory=set)  # {"Cart.total", "shop.cart.Cart", ...}
    modules: Set[str] = field(default_factory=set)  # {"cart", "shop.cart", "shop"}
    #: Modules whose *source was scanned*: for these (and only these) the
    #: symbol set is complete, so a missing attribute is provably a ghost.
    scanned_modules: Set[str] = field(default_factory=set)

    def add(self, symbol: Symbol, module: Optional[str]) -> None:
        self.symbols.append(symbol)
        self.bare.add(symbol.name)
        if "." in symbol.qualname:
            self.dotted.add(symbol.qualname)
        if module:
            self.dotted.add(f"{module}.{symbol.qualname}")

    def add_module(self, dotted_name: str) -> None:
        """Register a module path and every ancestor package prefix."""
        parts = dotted_name.split(".")
        for end in range(1, len(parts) + 1):
            prefix = ".".join(parts[:end])
            self.modules.add(prefix)
            self.bare.add(parts[end - 1])
            if end > 1:
                self.dotted.add(prefix)

    def module_prefix(self, token: str) -> Optional[str]:
        """Longest leading segment run of *token* that is a *scanned* module.

        Modules known only from import statements are excluded: their symbol
        set was never enumerated, so nothing can be proven missing in them.
        """
        parts = token.split(".")
        for end in range(len(parts) - 1, 0, -1):
            prefix = ".".join(parts[:end])
            if prefix in self.scanned_modules:
                return prefix
        return None

    def module_symbols(self, module: str) -> Set[str]:
        """Bare names defined at the top of *module* (for suggestions)."""
        prefix = module + "."
        names = set()
        for entry in self.dotted:
            if entry.startswith(prefix):
                remainder = entry[len(prefix):]
                names.add(remainder.split(".", 1)[0])
        return names

    def __len__(self) -> int:
        return len(self.symbols)


def module_name_for(path: Path, root: Path) -> Optional[str]:
    """Dotted module name of *path* relative to *root*, or ``None`` if outside."""
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    parts = list(rel.parts)
    if not parts or not parts[-1].endswith(".py"):
        return None
    stem = parts[-1][:-3]
    if stem == "__init__":
        parts = parts[:-1]
    else:
        parts[-1] = stem
    if not parts:
        return None
    # `src` layout: src/pkg/mod.py should index as pkg.mod, not src.pkg.mod.
    if parts[0] == "src" and len(parts) > 1:
        parts = parts[1:]
    if not all(part.isidentifier() for part in parts):
        return None
    return ".".join(parts)


class _Collector(ast.NodeVisitor):
    """AST walk that appends every discovered symbol to the index."""

    def __init__(self, index: SymbolIndex, file: str, module: Optional[str]) -> None:
        self.index = index
        self.file = file
        self.module = module
        self.stack: List[str] = []  # enclosing class/function names

    # -- helpers -----------------------------------------------------------

    def _qual(self, name: str) -> str:
        return ".".join(self.stack + [name]) if self.stack else name

    def _add(self, name: str, kind: str, line: int) -> None:
        if not name:
            return
        self.index.add(
            Symbol(name=name, qualname=self._qual(name), kind=kind, file=self.file, line=line),
            self.module,
        )

    def _add_target(self, target: ast.expr, kind: str) -> None:
        """Index a bind target: names, tuples/lists, star, self/cls attributes."""
        if isinstance(target, ast.Name):
            self._add(target.id, kind, target.lineno)
        elif isinstance(target, ast.Starred):
            self._add_target(target.value, kind)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                self._add_target(element, kind)
        elif isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
            if target.value.id in ("self", "cls"):
                self._add(target.attr, "attribute", target.lineno)

    def _add_arguments(self, args: ast.arguments, line: int) -> None:
        every = list(getattr(args, "posonlyargs", [])) + list(args.args) + list(args.kwonlyargs)
        for arg in every:
            self._add(arg.arg, "parameter", arg.lineno)
        for special in (args.vararg, args.kwarg):
            if special is not None:
                self._add(special.arg, "parameter", getattr(special, "lineno", line))

    # -- definitions -------------------------------------------------------

    def _visit_function(self, node) -> None:
        kind = "method" if self.stack and self._in_class() else "function"
        self._add(node.name, kind, node.lineno)
        self.stack.append(node.name)
        self._add_arguments(node.args, node.lineno)
        self.generic_visit(node)
        self.stack.pop()

    def _in_class(self) -> bool:
        return bool(self._class_depth)

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function

    _class_depth = 0

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._add(node.name, "class", node.lineno)
        self.stack.append(node.name)
        self._class_depth += 1
        self.generic_visit(node)
        self._class_depth -= 1
        self.stack.pop()

    # -- binds -------------------------------------------------------------

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            self._add_target(target, "variable")
        if not self.stack:
            self._maybe_collect_dunder_all(node)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._add_target(node.target, "variable")
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._add_target(node.target, "variable")
        self.generic_visit(node)

    def visit_NamedExpr(self, node) -> None:  # walrus
        self._add_target(node.target, "variable")
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self._add_target(node.target, "variable")
        self.generic_visit(node)

    visit_AsyncFor = visit_For

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            if item.optional_vars is not None:
                self._add_target(item.optional_vars, "variable")
        self.generic_visit(node)

    visit_AsyncWith = visit_With

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self._add_target(node.target, "variable")
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self._add(node.name, "variable", node.lineno)
        self.generic_visit(node)

    def visit_Global(self, node: ast.Global) -> None:
        for name in node.names:
            self._add(name, "variable", node.lineno)

    visit_Nonlocal = visit_Global

    # -- imports -----------------------------------------------------------

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            bound = alias.asname or alias.name.split(".", 1)[0]
            self._add(bound, "import", node.lineno)
            self.index.add_module(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self.index.add_module(node.module)
        for alias in node.names:
            if alias.name == "*":
                continue
            self._add(alias.asname or alias.name, "import", node.lineno)

    # -- __all__ -----------------------------------------------------------

    def _maybe_collect_dunder_all(self, node: ast.Assign) -> None:
        is_all = any(
            isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
        )
        if not is_all or not isinstance(node.value, (ast.List, ast.Tuple)):
            return
        for element in node.value.elts:
            if isinstance(element, ast.Constant) and isinstance(element.value, str):
                self._add(element.value, "variable", node.lineno)


def collect_file(
    index: SymbolIndex, path: Path, root: Path, source: Optional[str] = None
) -> None:
    """Parse *path* and add its symbols to *index*. Raises ``SyntaxError``.

    Pass *source* when the file content is already in memory (the scanner
    does) to avoid reading the file a second time.
    """
    if source is None:
        source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source, filename=str(path))
    module = module_name_for(path, root)
    if module:
        index.add_module(module)
        index.scanned_modules.add(module)
    _Collector(index, str(path), module).visit(tree)


def collect_symbols(paths: Iterable[Path], root: Path) -> SymbolIndex:
    """Build a :class:`SymbolIndex` from Python files, skipping unparsable ones."""
    index = SymbolIndex()
    for path in paths:
        try:
            collect_file(index, path, root)
        except SyntaxError:
            continue  # scanner records the parse error separately
    return index
