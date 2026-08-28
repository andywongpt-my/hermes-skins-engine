"""Tests for the AGY post-dev audit fixes (0.2.0 cycle, findings #1-#8)."""
from __future__ import annotations

import textwrap

import yaml

from hermes_skins.generators import generate_from_template
from hermes_skins.preview import _wrap_tool_row


# ---------------------------------------------------------------------------
# #1 — validate treats schema errors as errors (exit 1)
# ---------------------------------------------------------------------------

def test_validate_flags_bad_hex_as_error(runner, isolated_home, tmp_path):
    p = tmp_path / "badhex.yaml"
    p.write_text(
        "name: badhex\ncolors:\n  banner_title: \"#ZZZZZZ\"\n",
        encoding="utf-8",
    )
    result = runner.invoke(app_main, ["validate", str(p)])
    assert result.exit_code == 1
    assert "schema error" in result.output


def test_validate_flags_empty_name_as_error(runner, isolated_home, tmp_path):
    p = tmp_path / "noname.yaml"
    p.write_text('name: ""\n', encoding="utf-8")
    result = runner.invoke(app_main, ["validate", str(p)])
    assert result.exit_code == 1
    assert "schema error" in result.output


def test_validate_spinner_warning_not_error(runner, isolated_home, tmp_path):
    """A spinner with 1 face is advisory (warning), not an error."""
    p = tmp_path / "solo.yaml"
    p.write_text(
        'name: solo\nspinner:\n  waiting_faces: ["(·)"]\n',
        encoding="utf-8",
    )
    result = runner.invoke(app_main, ["validate", str(p)])
    assert result.exit_code == 0
    assert "warning" in result.output


# ---------------------------------------------------------------------------
# #2 — custom/export traversal-safe default output names
# ---------------------------------------------------------------------------

def test_custom_traversal_name_lands_in_skins_dir(runner, isolated_home):
    result = runner.invoke(app_main, [
        "custom", "../../tmp/evil", "--color", "#FF6D00",
    ])
    assert result.exit_code == 0
    skins_dir = isolated_home / ".hermes" / "skins"
    assert (skins_dir / "evil.yaml").exists()
    assert not (isolated_home / ".hermes" / "evil.yaml").exists()


def test_export_traversal_name_sanitized(runner, isolated_home):
    """An installed skin with a traversal-ish internal name exports safely.

    The lookup key is the sanitized internal name ('escaped'), and the
    default output filename derives from the same safe name.
    """
    skins_dir = isolated_home / ".hermes" / "skins"
    skins_dir.mkdir(parents=True)
    (skins_dir / "sneaky.yaml").write_text(
        textwrap.dedent("""\
            name: ../../tmp/escaped
            colors:
              banner_title: "#112233"
            spinner:
              waiting_faces: ["(a)", "(b)"]
            """),
        encoding="utf-8",
    )
    import os
    os.chdir(isolated_home)
    result = runner.invoke(app_main, ["export", "escaped"])
    assert result.exit_code == 0
    # exported under the sanitized basename, never outside cwd
    assert (isolated_home / "escaped.yaml").exists()
    assert not (isolated_home / "tmp" / "escaped.yaml").exists()


def test_installed_skins_key_is_sanitized(isolated_home):
    """Traversal internal names must never become lookup keys (0.2.0 #11)."""
    from hermes_skins.cli import installed_skins as _installed
    skins_dir = isolated_home / ".hermes" / "skins"
    skins_dir.mkdir(parents=True)
    (skins_dir / "sneaky.yaml").write_text(
        'name: ../../tmp/escaped\ncolors:\n  banner_title: "#112233"\n',
        encoding="utf-8",
    )
    keys = _installed()
    assert list(keys) == ["escaped"]
    assert "../../tmp/escaped" not in keys


# ---------------------------------------------------------------------------
# #3 — _wrap_tool_row explicit width wins over terminal detection
# ---------------------------------------------------------------------------

def test_wrap_explicit_width_wins_over_tty():
    items = [f"▸ tool-{i:02d}xxxxxxxxxxxxxxx" for i in range(10)]
    # even if stdout is a TTY (pytest -s against a real terminal), the
    # explicit width must be respected
    lines = _wrap_tool_row(items, width=40)
    assert len(lines) > 1
    assert all(len(line) <= 40 for line in lines)


def test_wrap_none_width_uses_terminal_default():
    # None triggers auto-detection; just verify it doesn't crash and wraps
    lines = _wrap_tool_row(["▸ " + "x" * 200], width=None)
    assert len(lines) >= 1


# ---------------------------------------------------------------------------
# #7 — --no-contrast doesn't claim contrast was checked
# ---------------------------------------------------------------------------

def test_validate_no_contrast_message_honest(runner, isolated_home, tmp_path):
    p = tmp_path / "ok.yaml"
    generate_from_template("asuka").dump(p)
    result = runner.invoke(app_main, ["validate", "--no-contrast", str(p)])
    assert result.exit_code == 0
    assert "status bar" not in result.output


def test_validate_with_contrast_message_mentions_ratio(runner, isolated_home, tmp_path):
    p = tmp_path / "ok.yaml"
    generate_from_template("asuka").dump(p)
    result = runner.invoke(app_main, ["validate", str(p)])
    assert result.exit_code == 0
    assert "status bar ≥ 4.5:1" in result.output


# app imported last to keep helper namespace clean
from hermes_skins.cli import app as app_main  # noqa: E402
