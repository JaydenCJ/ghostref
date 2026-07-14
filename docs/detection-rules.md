# Detection rules

ghostref's promise is determinism: the same tree always produces the same
findings, so it can gate CI without flakiness. This document is the
normative description of both halves of the pipeline. Any behavioral change
to these rules must update this file in the same pull request
(see CONTRIBUTING.md).

## 1. What counts as a candidate reference

Prose (comments, docstrings, Markdown) is scanned line by line. Only tokens
carrying an explicit code-reference signal are considered, strongest signal
first; each match claims its character span so weaker signals never
re-report it.

| Order | Signal | Example | Confidence |
|---|---|---|---|
| 1 | Sphinx role | `` :func:`compute_total` `` | high |
| 2 | Backtick span | `` `compute_total` ``, `` `Cart.add(item)` `` | high |
| 3 | Call syntax | `compute_total()` (no space before `(`) | high |
| 4 | Dotted path | `cart.compute_total` | medium |
| 5 | snake_case word | `compute_total` | medium |
| 6 | CamelCase word | `CartSnapshot` (two humps or more) | medium |

Before matching, URLs are masked. After matching, these are dropped as
prose conventions, not references:

- marker idioms: `TODO(alice)`, `FIXME`, `NOTE`, ... (all-caps markers);
- dotted abbreviations: `e.g.`, `i.e.`, `a.k.a.`, ...;
- filenames and hostnames: dotted tokens ending in a known file extension
  or domain tail (`config.yaml`, `api.example.test`);
- mixed-case product names (`GitHub`, `NumPy`, `PyPI`, ...) and naming-style
  words (`snake_case`, `CamelCase`) — a small curated list, not a dictionary;
- backtick spans whose content is code but not a name (`--force`, `a + b`).

A comment containing `ghostref: ignore` suppresses itself entirely.
Tool-directive comments (`# noqa`, `# type:`, `# pylint:`, shebangs, coding
cookies) are never scanned. In Markdown, only inline code spans and Sphinx
roles are inspected, and fenced code blocks are skipped.

## 2. What counts as a live symbol

One `ast` walk per Python file collects, without executing anything:

- module names derived from file paths relative to the scan root
  (`pkg/util.py` → `util`, `pkg.util`, `pkg`; a leading `src/` is stripped);
- functions, async functions, classes; methods both bare and dotted
  (`Cart.add`), plus module-qualified forms (`shop.cart.Cart.add`);
- every parameter name, including `*args`/`**kwargs` names;
- every assignment target at any scope: globals, locals, `for`/`with`
  targets, comprehension variables, walrus and unpacking targets,
  `except ... as` names, `global`/`nonlocal` declarations;
- `self.attr` / `cls.attr` assignment targets (as `attr` and `Class.attr`);
- imported names and aliases; `__all__` string entries.

Files that fail to parse are reported as errors and skipped; they never
abort the scan. The index spans **all** scanned files, so a comment in one
module may reference a symbol defined in another.

## 3. The resolution ladder

Each candidate token is resolved by the first matching rule. No scoring, no
heuristics beyond this list:

1. Allowlisted (`--allow`, `--allow-file`) → live.
2. Python keyword, builtin, implicit name (`self`, `cls`, `__name__`, ...)
   → live.
3. Single segment: live iff it is an indexed name, a scanned or imported
   module, or a standard-library module.
4. Dotted, exact match in the dotted index → live.
5. Dotted, head is `self`/`cls`: live iff the attribute is indexed;
   otherwise a ghost ("no attribute 'x' is ever assigned on self").
6. Dotted, longest leading segment run is a **scanned** module: live iff
   the remainder resolves inside that module; otherwise a provable ghost
   ("module 'cart' has no symbol 'legacy_total'").
7. Dotted, head is a stdlib module or allowlisted → live (attributes of
   unscanned modules cannot be verified).
8. Dotted, head or last segment is any live bare name → live (attributes of
   arbitrary objects, and shorthand mentions, cannot be disproven
   statically).
9. Anything else → ghost.

The asymmetry is deliberate: ghostref only reports what it can defend.
Rules 6–8 mean a dotted path is flagged either when *nothing* on either end
exists, or when it points into a module whose full symbol set is known.

## 4. Documented parameters

For every function with a docstring (and without `**kwargs`), parameter
entries in Google (`Args:`), Sphinx (`:param name:`), and NumPy
(`Parameters` + dashes) styles are compared against the real signature.
Names the signature does not accept are high-confidence `param` findings
with a `difflib` suggestion — the classic renamed-parameter lie.

## 5. Exit codes and gating

`ghostref scan` exits `0` when clean, `1` when any finding survives the
`--min-confidence` and `--baseline` filters, `2` on usage or input errors.
Baseline fingerprints are `sha256(relative_path | token | kind)` truncated
to 16 hex chars — line numbers are excluded on purpose, so moving a lying
comment does not resurrect it.
