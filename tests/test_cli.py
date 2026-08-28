"""CLI tests — full command surface via Typer's CliRunner.

Uses the `isolated_home` fixture so ~/.hermes/skins and ~/.hermes/config.yaml
are sandboxed into tmp dirs. Regression anchors: B6 (no-arg preview),
B9 (install validation + name sanitization + idempotency).
"""
from __future__ import annotations

import textwrap

import yaml

from hermes_skins import __version__
from hermes_skins.cli import (
    app,
    active_skin_name,
    installed_skins,
)


# ---------------------------------------------------------------------------
# version / templates / list
# ---------------------------------------------------------------------------

def test_version_command(runner):
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert f"hermes-skins v{__version__}" in result.output


def test_templates_command_lists_8(runner):
    result = runner.invoke(app, ["templates"])
    assert result.exit_code == 0
    assert "Built-in templates (8)" in result.output
    for name in ("asuka", "seele", "berserk"):
        assert name in result.output


def test_list_empty_home(runner, isolated_home):
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "No skins installed" in result.output


def test_list_after_generate(runner, isolated_home):
    runner.invoke(app, ["generate", "asuka", "-o", str(isolated_home / ".hermes" / "skins" / "asuka.yaml")])
    # ensure file landed where we asked (only works because we passed -o)
    assert (isolated_home / ".hermes" / "skins" / "asuka.yaml").exists()
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "asuka" in result.output


# ---------------------------------------------------------------------------
# generate / random / custom
# ---------------------------------------------------------------------------

def test_generate_to_output_file(runner, tmp_path):
    out = tmp_path / "asuka.yaml"
    result = runner.invoke(app, ["generate", "asuka", "-o", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert data["name"] == "asuka"
    assert len(data["colors"]) == 29


def test_generate_unknown_template_fails_cleanly(runner, tmp_path):
    result = runner.invoke(app, ["generate", "gendo", "-o", str(tmp_path / "x.yaml")])
    assert result.exit_code == 1
    assert "Unknown template" in result.output


def test_random_seed_deterministic_files(runner, tmp_path):
    o1, o2 = tmp_path / "r1.yaml", tmp_path / "r2.yaml"
    runner.invoke(app, ["random", "seed-x", "-o", str(o1)])
    runner.invoke(app, ["random", "seed-x", "-o", str(o2)])
    assert o1.read_text(encoding="utf-8") == o2.read_text(encoding="utf-8")


def test_custom_writes_valid_skin(runner, tmp_path):
    out = tmp_path / "mycustom.yaml"
    result = runner.invoke(app, ["custom", "mycustom", "--color", "#FF6D00",
                                 "--harmony", "triadic", "-o", str(out)])
    assert result.exit_code == 0
    assert "triadic" in result.output  # enum repr must not leak (AGY finding)
    assert "Harmony.complementary" not in result.output
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert data["name"] == "mycustom"


def test_custom_rejects_bad_color(runner, tmp_path):
    result = runner.invoke(app, ["custom", "bad", "--color", "#ZZZZZZ", "-o", str(tmp_path / "b.yaml")])
    assert result.exit_code == 1
    assert "Invalid color" in result.output
    assert "Traceback" not in result.output


# ---------------------------------------------------------------------------
# preview (B6)
# ---------------------------------------------------------------------------

def test_preview_no_args_no_active_skin(runner, isolated_home):
    result = runner.invoke(app, ["preview"])
    assert result.exit_code == 1
    assert "No active skin" in result.output


def test_preview_no_args_shows_active(runner, isolated_home):
    cfg_dir = isolated_home / ".hermes"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.yaml").write_text("display:\n  skin: asuka\n", encoding="utf-8")
    result = runner.invoke(app, ["preview"])
    assert result.exit_code == 0
    assert "Active skin" in result.output
    assert "asuka" in result.output


def test_preview_active_name_missing_skin_fails(runner, isolated_home):
    cfg_dir = isolated_home / ".hermes"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.yaml").write_text("display:\n  skin: ghost\n", encoding="utf-8")
    result = runner.invoke(app, ["preview"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_preview_installed_skin(runner, isolated_home):
    out = isolated_home / ".hermes" / "skins" / "asuka.yaml"
    out.parent.mkdir(parents=True)
    import subprocess, sys
    from hermes_skins.generators import generate_from_template
    generate_from_template("asuka").dump(out)
    result = runner.invoke(app, ["preview", "asuka"])
    assert result.exit_code == 0
    assert "✓ Skin valid" in result.output


def test_preview_template_fallback(runner, isolated_home):
    result = runner.invoke(app, ["preview", "seele"])
    assert result.exit_code == 0
    assert "SEELE" in result.output


def test_preview_all_flag_dumps_8(runner):
    result = runner.invoke(app, ["preview", "--all"])
    assert result.exit_code == 0
    assert result.output.count("Color Palette:") == 8


def test_preview_unknown_name(runner, isolated_home):
    result = runner.invoke(app, ["preview", "gendo"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_active_skin_name_reads_nested_config(isolated_home):
    cfg = isolated_home / ".hermes" / "config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("display:\n  skin: rei\n", encoding="utf-8")
    assert active_skin_name() == "rei"


def test_active_skin_name_missing_config(isolated_home):
    assert active_skin_name() is None


def test_active_skin_name_malformed_config(isolated_home):
    cfg = isolated_home / ".hermes" / "config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("::: garbage\n", encoding="utf-8")
    assert active_skin_name() is None


def test_active_skin_name_non_string(isolated_home):
    cfg = isolated_home / ".hermes" / "config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("display:\n  skin: 42\n", encoding="utf-8")
    assert active_skin_name() is None


# ---------------------------------------------------------------------------
# install (B9)
# ---------------------------------------------------------------------------

def _write_skin(tmp_path, body: str, filename="skin.yaml"):
    p = tmp_path / filename
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def test_install_rejects_nameless_yaml(runner, isolated_home, tmp_path):
    src = _write_skin(tmp_path, """\
        ::: garbage
        """)
    result = runner.invoke(app, ["install", str(src)])
    assert result.exit_code == 1
    assert "no 'name:' field" in result.output
    assert not (isolated_home / ".hermes" / "skins").exists() or \
           not list((isolated_home / ".hermes" / "skins").glob("*.yaml"))


def test_install_rejects_non_mapping(runner, isolated_home, tmp_path):
    src = tmp_path / "list.yaml"
    src.write_text("- a\n- b\n", encoding="utf-8")
    result = runner.invoke(app, ["install", str(src)])
    assert result.exit_code == 1


def test_install_missing_file(runner, isolated_home, tmp_path):
    result = runner.invoke(app, ["install", str(tmp_path / "nope.yaml")])
    assert result.exit_code == 1
    assert "File not found" in result.output


def test_install_valid_skin(runner, isolated_home, tmp_path):
    from hermes_skins.generators import generate_from_template
    src = tmp_path / "mine.yaml"
    generate_from_template("rei").dump(src)
    result = runner.invoke(app, ["install", str(src)])
    assert result.exit_code == 0
    dst = isolated_home / ".hermes" / "skins" / "rei.yaml"
    assert dst.exists()


def test_install_renames_to_internal_name(runner, isolated_home, tmp_path):
    from hermes_skins.generators import generate_from_template
    src = tmp_path / "whatever-name.yaml"
    generate_from_template("shinji").dump(src)
    result = runner.invoke(app, ["install", str(src)])
    assert result.exit_code == 0
    assert "saved as 'shinji.yaml'" in result.output


def test_install_idempotent_same_file(runner, isolated_home, tmp_path):
    from hermes_skins.generators import generate_from_template
    skins_dir = isolated_home / ".hermes" / "skins"
    skins_dir.mkdir(parents=True)
    src = skins_dir / "misato.yaml"  # installed in place
    generate_from_template("misato").dump(src)
    result = runner.invoke(app, ["install", str(src)])
    assert result.exit_code == 0
    assert "Nothing to do" in result.output


def test_install_traversal_name_sanitized(runner, isolated_home, tmp_path):
    src = _write_skin(tmp_path, """\
        name: ../../tmp/evil
        colors:
          banner_title: "#FF0000"
        spinner:
          waiting_faces: ["(a)", "(b)"]
        """)
    result = runner.invoke(app, ["install", str(src)])
    assert result.exit_code == 0  # installed, but under a sanitized name
    skins_dir = isolated_home / ".hermes" / "skins"
    assert not (skins_dir.parent / "tmp" / "evil.yaml").exists()
    landed = list(skins_dir.glob("*.yaml"))
    assert len(landed) == 1 and landed[0].name == "evil.yaml"


def test_installed_skins_keys_on_internal_name(isolated_home):
    from hermes_skins.generators import generate_from_template
    skins_dir = isolated_home / ".hermes" / "skins"
    skins_dir.mkdir(parents=True)
    generate_from_template("kaoru").dump(skins_dir / "file-name-mismatch.yaml")
    keys = installed_skins()
    assert "kaoru" in keys


def test_installed_skins_handles_malformed_yaml_gracefully(isolated_home):
    """Broken YAML must not crash the listing; it falls back to the file stem
    (renamed from 'skips_broken_files' — nothing is skipped, audit 0.2.0 #8)."""
    skins_dir = isolated_home / ".hermes" / "skins"
    skins_dir.mkdir(parents=True)
    (skins_dir / "broken.yaml").write_text("::: garbage\n", encoding="utf-8")
    (skins_dir / "good.yaml").write_text("name: good\n", encoding="utf-8")
    keys = installed_skins()
    assert set(keys) == {"good", "unnamed"}  # broken loads as unnamed; keyed by stem fallback


# ---------------------------------------------------------------------------
# switch — must not touch the real hermes CLI in tests
# ---------------------------------------------------------------------------

def test_switch_reports_missing_heres_cli(runner, isolated_home, monkeypatch):
    """hermes CLI absent → warn, not crash (audit 0.2.0 #5: mock which directly)."""
    monkeypatch.setattr("shutil.which", lambda name: None)
    result = runner.invoke(app, ["switch", "asuka"])
    assert result.exit_code == 0
    assert "cannot switch automatically" in result.output
    assert "hermes config set display.skin asuka" in result.output


def test_export_installed_skin(runner, isolated_home, tmp_path):
    from hermes_skins.generators import generate_from_template
    skins = isolated_home / ".hermes" / "skins"
    skins.mkdir(parents=True)
    generate_from_template("nerv").dump(skins / "nerv.yaml")
    out = tmp_path / "exported.yaml"
    result = runner.invoke(app, ["export", "nerv", "-o", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    assert yaml.safe_load(out.read_text(encoding="utf-8"))["name"] == "nerv"


def test_export_unknown_fails(runner, isolated_home):
    result = runner.invoke(app, ["export", "gendo"])
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# NO_COLOR support (P1) — implemented in this cycle
# ---------------------------------------------------------------------------

def test_no_color_env_strips_ansi(isolated_home, monkeypatch):
    """NO_COLOR → render_preview returns plain text (tested at the renderer
    level because Typer's CliRunner strips ANSI from result.output)."""
    from hermes_skins.generators import generate_from_template
    from hermes_skins.preview import render_preview
    monkeypatch.setenv("NO_COLOR", "1")
    out = render_preview(generate_from_template("asuka"))
    assert "\x1b[" not in out
    assert "EVA-02 Agent" in out  # content intact


def test_clicolor_zero_strips_ansi(isolated_home, monkeypatch):
    from hermes_skins.generators import generate_from_template
    from hermes_skins.preview import render_preview
    monkeypatch.setenv("CLICOLOR", "0")
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert "\x1b[" not in render_preview(generate_from_template("asuka"))


def test_clicolor_force_beats_no_color(isolated_home, monkeypatch):
    from hermes_skins.generators import generate_from_template
    from hermes_skins.preview import render_preview
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("CLICOLOR_FORCE", "1")
    assert "\x1b[" in render_preview(generate_from_template("asuka"))


def test_color_by_default(isolated_home, monkeypatch):
    from hermes_skins.generators import generate_from_template
    from hermes_skins.preview import render_preview
    for var in ("NO_COLOR", "CLICOLOR", "CLICOLOR_FORCE"):
        monkeypatch.delenv(var, raising=False)
    assert "\x1b[" in render_preview(generate_from_template("asuka"))
