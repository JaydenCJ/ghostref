"""CLI behavior: subcommands, exit codes, and output formats."""

import json

import pytest

from ghostref.cli import main


HAUNTED = {
    "app.py": (
        "# nightly job still calls legacy_sync() here\n"
        "def sync():\n"
        "    pass\n"
    )
}

CLEAN = {"app.py": "# calls sync() nightly\ndef sync():\n    pass\n"}


def run(capsys, *argv):
    code = main([str(part) for part in argv])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_scan_exits_1_and_reports_when_ghosts_exist(project, capsys):
    root = project(HAUNTED)
    code, out, _ = run(capsys, "scan", root)
    assert code == 1
    assert "ghost 'legacy_sync'" in out
    assert "no symbol named 'legacy_sync'" in out


def test_scan_suggests_close_live_names(project, capsys):
    root = project(
        {"m.py": "# validated by check_totals() upstream\ndef check_total():\n    pass\n"}
    )
    code, out, _ = run(capsys, "scan", root)
    assert code == 1
    assert "did you mean 'check_total'?" in out


def test_scan_exits_0_on_a_clean_tree(project, capsys):
    root = project(CLEAN)
    code, out, _ = run(capsys, "scan", root)
    assert code == 0
    assert out.startswith("0 ghost references")


def test_scan_alternative_formats(project, capsys):
    root = project(HAUNTED)
    code, out, _ = run(capsys, "scan", root, "--format", "json")
    assert code == 1
    assert json.loads(out)["findings"][0]["token"] == "legacy_sync"
    code, out, _ = run(capsys, "scan", root, "--format", "github")
    assert code == 1
    assert out.startswith("::error file=app.py,line=1")


def test_input_errors_exit_2(project, capsys, tmp_path):
    code, _, err = run(capsys, "scan", tmp_path / "missing")
    assert code == 2
    assert "no such file" in err
    root = project(HAUNTED)
    bogus = tmp_path / "bogus.json"
    bogus.write_text("{}", encoding="utf-8")
    code, _, err = run(capsys, "scan", root, "--baseline", bogus)
    assert code == 2
    assert "baseline" in err


def test_allow_flag_and_allow_file_suppress_named_ghosts(project, capsys, tmp_path):
    root = project(HAUNTED)
    code, _, _ = run(capsys, "scan", root, "--allow", "legacy_sync")
    assert code == 0
    allow = tmp_path / "allow.txt"
    allow.write_text("# vendored names\nlegacy_sync\n", encoding="utf-8")
    code, _, _ = run(capsys, "scan", root, "--allow-file", allow)
    assert code == 0


def test_baseline_workflow_records_then_suppresses(project, capsys, tmp_path):
    root = project(HAUNTED)
    baseline = tmp_path / "baseline.json"
    code, out, _ = run(capsys, "baseline", root, "-o", baseline)
    assert code == 0
    assert "(1 finding)" in out
    code, _, _ = run(capsys, "scan", root, "--baseline", baseline)
    assert code == 0  # existing ghost is baselined


def test_baseline_still_fails_on_new_ghosts(project, capsys, tmp_path):
    root = project(HAUNTED)
    baseline = tmp_path / "baseline.json"
    run(capsys, "baseline", root, "-o", baseline)
    (root / "app.py").write_text(
        "# nightly job still calls legacy_sync() here\n"
        "# and now also brand_new_ghost()\n"
        "def sync():\n    pass\n",
        encoding="utf-8",
    )
    code, out, _ = run(capsys, "scan", root, "--baseline", baseline)
    assert code == 1
    assert "brand_new_ghost" in out
    assert "legacy_sync" not in out


def test_symbols_lists_the_index_and_filters_by_kind(project, capsys):
    root = project(CLEAN)
    code, out, _ = run(capsys, "symbols", root)
    assert code == 0
    assert any(line.startswith("sync\tfunction\t") for line in out.splitlines())
    root = project({"m.py": "X = 1\ndef f():\n    pass\n"})
    code, out, _ = run(capsys, "symbols", root, "--kind", "function")
    assert code == 0
    kinds = {line.split("\t")[1] for line in out.splitlines() if line}
    assert kinds == {"function"}


def test_no_command_prints_help_and_version_flag_reports_package_version(capsys):
    from ghostref import __version__

    code, out, _ = run(capsys)
    assert code == 2
    assert "usage: ghostref" in out
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert capsys.readouterr().out.strip() == f"ghostref {__version__}"


def test_docs_flag_extends_scan_to_markdown(project, capsys):
    root = project(
        {
            "app.py": "def sync():\n    pass\n",
            "GUIDE.md": "Use `vanished_api()` to start.\n",
        }
    )
    code_without, _, _ = run(capsys, "scan", root)
    assert code_without == 0
    code_with, out, _ = run(capsys, "scan", root, "--docs")
    assert code_with == 1
    assert "vanished_api" in out
    # --min-confidence high keeps a bare medium-confidence mention from gating
    strict = project({"m.py": "# a bare stale_mention in prose\nx = 1\n"})
    code, _, _ = run(capsys, "scan", strict, "--min-confidence", "high")
    assert code == 0
