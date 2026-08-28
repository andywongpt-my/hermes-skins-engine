"""Tests for the `validate` subcommand and active-skin listing (P1)."""
from __future__ import annotations

import textwrap

import yaml

from hermes_skins.generators import generate_from_template, hsl_to_hex, hex_to_hsl


def _mk_invalid_contrast_skin(tmp_path):
    """A skin whose status_bar_text is unreadable on its bg (audit headline)."""
    p = tmp_path / "unreadable.yaml"
    p.write_text(
        "name: unreadable\n"
        "colors:\n"
        "  status_bar_bg: \"#CCCCCC\"\n"
        "  status_bar_text: \"#BBBBBB\"\n"
        "  status_bar_strong: \"#DDDDDD\"\n"
        "  status_bar_dim: \"#CCCCCC\"\n",
        encoding="utf-8",
    )
    return p


def test_validate_file_valid(runner, isolated_home, tmp_path):
    src = tmp_path / "ok.yaml"
    generate_from_template("asuka").dump(src)
    result = runner.invoke(app_main, ["validate", str(src)])
    assert result.exit_code == 0
    assert "✓" in result.output


def test_validate_file_with_contrast_errors(runner, isolated_home, tmp_path):
    p = _mk_invalid_contrast_skin(tmp_path)
    result = runner.invoke(app_main, ["validate", str(p)])
    assert result.exit_code == 1
    assert "contrast error" in result.output
    assert "status_bar_text" in result.output


def test_validate_file_no_contrast_flag(runner, isolated_home, tmp_path):
    p = _mk_invalid_contrast_skin(tmp_path)
    result = runner.invoke(app_main, ["validate", "--no-contrast", str(p)])
    # schema warnings only (that skin has valid hex) → no error exit
    assert result.exit_code == 0


def test_validate_missing_file(runner, isolated_home, tmp_path):
    result = runner.invoke(app_main, ["validate", str(tmp_path / "nope.yaml")])
    assert result.exit_code == 1


def test_validate_all_installed_empty(runner, isolated_home):
    result = runner.invoke(app_main, ["validate"])
    assert result.exit_code == 0
    assert "nothing to validate" in result.output


def test_validate_all_installed_ok(runner, isolated_home):
    skins = isolated_home / ".hermes" / "skins"
    skins.mkdir(parents=True)
    for t in ("asuka", "rei", "nerv", "seele"):
        generate_from_template(t).dump(skins / f"{t}.yaml")
    result = runner.invoke(app_main, ["validate"])
    assert result.exit_code == 0
    assert result.output.count("✓") == 4


def test_validate_all_flags_bad_skin(runner, isolated_home):
    skins = isolated_home / ".hermes" / "skins"
    skins.mkdir(parents=True)
    bad = _mk_invalid_contrast_skin(skins.parent)  # outside skins dir
    import shutil
    shutil.copy2(bad, skins / "bad.yaml")
    result = runner.invoke(app_main, ["validate"])
    assert result.exit_code == 1
    assert "contrast error" in result.output


def test_validate_missing_file_arg(runner, isolated_home, tmp_path):
    result = runner.invoke(app_main, ["validate", str(tmp_path / "nope.yaml")])
    assert result.exit_code == 1


def test_list_marks_active_skin(runner, isolated_home):
    cfg = isolated_home / ".hermes" / "config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("display:\n  skin: asuka\n", encoding="utf-8")
    skins = isolated_home / ".hermes" / "skins"
    skins.mkdir(parents=True)
    generate_from_template("asuka").dump(skins / "asuka.yaml")
    generate_from_template("rei").dump(skins / "rei.yaml")
    result = runner.invoke(app_main, ["list"])
    assert result.exit_code == 0
    assert "← active" in result.output
    # marker attaches to asuka's row, not rei's
    asuka_row = next(l for l in result.output.splitlines() if l.strip().startswith("asuka"))
    assert "← active" in asuka_row


def test_list_notes_active_not_installed(runner, isolated_home):
    cfg = isolated_home / ".hermes" / "config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("display:\n  skin: ghost\n", encoding="utf-8")
    skins = isolated_home / ".hermes" / "skins"
    skins.mkdir(parents=True)
    generate_from_template("asuka").dump(skins / "asuka.yaml")
    result = runner.invoke(app_main, ["list"])
    assert result.exit_code == 0
    assert "not installed here" in result.output


def test_list_no_active_no_marker(runner, isolated_home):
    skins = isolated_home / ".hermes" / "skins"
    skins.mkdir(parents=True)
    generate_from_template("asuka").dump(skins / "asuka.yaml")
    result = runner.invoke(app_main, ["list"])
    assert result.exit_code == 0
    assert "← active" not in result.output


# app imported after helpers to keep the module namespace clean
from hermes_skins.cli import app as app_main  # noqa: E402
