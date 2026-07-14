"""Static allowlists that keep ghostref quiet on tokens that are never ghosts.

Everything here is deterministic and versioned with the package: no dictionary
files are loaded from disk and no locale-dependent behavior is involved. The
lists are deliberately small — resolution against the *live* symbol index does
most of the work; these only cover names that exist outside the scanned tree
(Python keywords, builtins, the standard library) and comment idioms that look
like identifiers but are prose (``e.g.``, ``TODO(alice)``).
"""

from __future__ import annotations

import builtins
import keyword
import sys

#: Python keywords (`if`, `while`, ...) plus soft keywords (`match`, `type`).
PYTHON_KEYWORDS = frozenset(keyword.kwlist) | frozenset(
    getattr(keyword, "softkwlist", ())
)

#: Names importable from `builtins` in the running interpreter (`len`, `dict`,
#: `ValueError`, ...). Comments referencing these are always live.
PYTHON_BUILTINS = frozenset(dir(builtins))

# `sys.stdlib_module_names` exists from Python 3.10. The fallback below covers
# 3.9 with the modules that realistically appear in comments; it does not need
# to be exhaustive because a miss only means one extra (accurate) finding.
_STDLIB_FALLBACK = frozenset(
    {
        "abc", "argparse", "ast", "asyncio", "base64", "bisect", "builtins",
        "calendar", "collections", "concurrent", "configparser", "contextlib",
        "copy", "csv", "ctypes", "dataclasses", "datetime", "decimal",
        "difflib", "dis", "email", "enum", "errno", "fnmatch", "functools",
        "gc", "getpass", "glob", "gzip", "hashlib", "heapq", "hmac", "html",
        "http", "importlib", "inspect", "io", "ipaddress", "itertools",
        "json", "keyword", "logging", "math", "mimetypes", "multiprocessing",
        "operator", "os", "pathlib", "pickle", "platform", "pprint",
        "queue", "random", "re", "sched", "secrets", "select", "shlex",
        "shutil", "signal", "site", "socket", "sqlite3", "ssl", "stat",
        "statistics", "string", "struct", "subprocess", "sys", "sysconfig",
        "tempfile", "textwrap", "threading", "time", "timeit", "token",
        "tokenize", "traceback", "types", "typing", "unicodedata", "unittest",
        "urllib", "uuid", "venv", "warnings", "weakref", "xml", "zipfile",
        "zlib",
    }
)

#: Top-level standard-library module names (`os`, `json`, `typing`, ...).
STDLIB_MODULES = frozenset(getattr(sys, "stdlib_module_names", _STDLIB_FALLBACK))

#: Marker words that grab call syntax (`TODO(alice)`) or look like constants
#: (`NOTE`, `WARNING`) but are conventions, not identifiers.
MARKER_WORDS = frozenset(
    {
        "TODO", "FIXME", "XXX", "HACK", "NOTE", "NOTES", "WARNING", "BUG",
        "DEPRECATED", "OPTIMIZE", "REVIEW", "SAFETY", "PERF", "WIP",
    }
)

#: Dotted prose abbreviations, compared case-insensitively (`e.g.`, `i.e.`).
DOTTED_ABBREVIATIONS = frozenset(
    {"e.g", "i.e", "n.b", "p.s", "a.k.a", "q.e.d", "et.al", "w.r.t", "a.m", "p.m"}
)

#: If a dotted token's last segment is one of these, treat it as a file name
#: or hostname rather than an attribute path (`config.yaml`, `example.test`).
FILE_AND_HOST_TAILS = frozenset(
    {
        # file extensions commonly named in comments
        "py", "pyi", "md", "txt", "json", "yaml", "yml", "toml", "ini",
        "cfg", "csv", "tsv", "html", "css", "js", "ts", "sh", "bash",
        "lock", "log", "xml", "sql", "db", "gz", "zip", "tar", "whl",
        "env", "sock", "pid", "bak", "tmpl", "jinja",
        # hostname / domain tails seen in examples and tests
        "com", "org", "net", "io", "dev", "test", "local", "localhost",
        "example", "invalid",
    }
)

#: Mixed-case product and technology names that match the CamelCase signal
#: but are prose, not identifiers. Curated, not a dictionary: each entry is a
#: word that shows up in ordinary code comments across many projects.
TECH_PROPER_NOUNS = frozenset(
    {
        "CamelCase", "CommonMark", "CPython", "DataFrame", "DevOps", "DjangoORM",
        "DotEnv", "FastAPI", "GitHub", "GitLab", "GraphQL", "HomeBrew", "IPv4",
        "IPv6", "JavaScript", "JetBrains", "KaTeX", "LaTeX", "MacOS", "MyPy",
        "MongoDB", "NumPy", "OAuth", "OpenAPI", "OpenSSL", "PascalCase",
        "PostgreSQL", "PowerShell", "PyPI", "PyPy", "PyTest", "PyTorch",
        "SciPy", "SemVer", "SQLite", "TypeScript", "UniCode", "WebSocket",
        "WebSockets", "YAML",
    }
)

#: Naming-convention words that match the snake_case signal but describe a
#: style rather than a symbol.
STYLE_WORDS = frozenset(
    {"snake_case", "camel_case", "kebab_case", "screaming_snake_case", "pascal_case"}
)

#: Names that are conventionally in scope even though no file defines them.
IMPLICIT_NAMES = frozenset({"self", "cls", "__name__", "__file__", "__doc__", "__all__"})
