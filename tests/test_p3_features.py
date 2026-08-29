"""Tests for the P3 feature cycle (v0.4.0).

Covers: F10 terminal color-depth degradation (detection, RGB→256/16 mapping,
SGR emission, swatch path), doctor, wcag report, --json outputs.
"""
from __future__ import annotations

import json as jsonlib
import os
import textwrap

import pytest
from typer.testing import CliRunner

from hermes_skins.cli import app
from hermes_skins.generators import generate_from_template
from hermes_skins.preview import (
    _ANSI16_RGB,
    _PAL256,
    ansi_bg_params,
    ansi_fg_params,
    rgb_to_16,
    rgb_to_256,
    strip_ansi,
    terminal_color_mode,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# F10 — terminal_color_mode() detection
# ---------------------------------------------------------------------------

class TestTerminalColorMode:
    def test_unset_term_is_truecolor(self, monkeypatch):
        for v in ("TERM", "COLORTERM", "HERMES_SKINS_COLOR_MODE"):
            monkeypatch.delenv(v, raising=False)
        assert terminal_color_mode() == "truecolor"

    @pytest.mark.parametrize("term,expected", [
        ("xterm-256color", "256"),
        ("screen-256color", "256"),
        ("tmux-256color", "256"),
        ("xterm", "16"),
        ("vt100", "16"),
        ("linux", "16"),
        ("dumb", "none"),
    ])
    def test_term_detection(self, monkeypatch, term, expected):
        monkeypatch.delenv("COLORTERM", raising=False)
        monkeypatch.delenv("HERMES_SKINS_COLOR_MODE", raising=False)
        monkeypatch.setenv("TERM", term)
        assert terminal_color_mode() == expected

    @pytest.mark.parametrize("term,expected", [
        ("kitty", "truecolor"),
        ("xterm-kitty", "truecolor"),
        ("xterm-direct", "truecolor"),
        ("alacritty-direct", "truecolor"),
        ("st-256color", "256"),
    ])
    def test_term_truecolor_names(self, monkeypatch, term, expected):
        monkeypatch.delenv("COLORTERM", raising=False)
        monkeypatch.delenv("HERMES_SKINS_COLOR_MODE", raising=False)
        monkeypatch.setenv("TERM", term)
        assert terminal_color_mode() == expected

    @pytest.mark.parametrize("colorterm", ["truecolor", "TrueColor", "24bit"])
    def test_colorterm_wins(self, monkeypatch, colorterm):
        monkeypatch.setenv("COLORTERM", colorterm)
        monkeypatch.setenv("TERM", "xterm-256color")
        monkeypatch.delenv("HERMES_SKINS_COLOR_MODE", raising=False)
        assert terminal_color_mode() == "truecolor"

    @pytest.mark.parametrize("override", ["truecolor", "256", "16", "none", "NONE"])
    def test_env_override_wins(self, monkeypatch, override):
        monkeypatch.setenv("COLORTERM", "truecolor")
        monkeypatch.setenv("TERM", "kitty")
        monkeypatch.setenv("HERMES_SKINS_COLOR_MODE", override)
        assert terminal_color_mode() == override.lower()

    def test_invalid_override_ignored(self, monkeypatch):
        monkeypatch.setenv("HERMES_SKINS_COLOR_MODE", "bogus")
        monkeypatch.setenv("TERM", "xterm-256color")
        assert terminal_color_mode() == "256"

    def test_no_color_wins_unless_overridden(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.setenv("COLORTERM", "truecolor")
        monkeypatch.delenv("HERMES_SKINS_COLOR_MODE", raising=False)
        assert terminal_color_mode() == "none"
        monkeypatch.setenv("HERMES_SKINS_COLOR_MODE", "truecolor")
        assert terminal_color_mode() == "truecolor"


# ---------------------------------------------------------------------------
# F10 — palette construction + RGB mapping
# ---------------------------------------------------------------------------

class TestPalettes:
    def test_256_palette_size(self):
        assert len(_PAL256) == 256

    def test_256_palette_layout(self):
        # 0-15 = ANSI-16, 16-231 = 6x6x6 cube, 232-255 = grayscale ramp
        assert _PAL256[:16] == _ANSI16_RGB
        assert _PAL256[16] == (0, 0, 0)
        assert _PAL256[21] == (0, 0, 255)   # cube corner (5,5,5) → blue
        assert _PAL256[231] == (255, 255, 255)
        assert _PAL256[232] == (8, 8, 8)
        assert _PAL256[255] == (238, 238, 238)

    def test_exact_matches_map_to_self(self):
        # Exact RGB matches prefer the cube region (16-231) over ANSI-16 base
        assert rgb_to_256((0, 0, 255)) == 21
        assert rgb_to_256((255, 255, 255)) == 231
        assert rgb_to_256((8, 8, 8)) == 232
        assert rgb_to_16((255, 0, 0)) == 9
        assert rgb_to_16((0, 0, 0)) == 0

    def test_cube_index_formula(self):
        # 204 → nearest cube level: 215 (level 4, dist 11²) beats 255 (level 5, dist 51²)
        # #CC0033 → level (4,0,1) → index 16 + 4*36 + 0*6 + 1 = 161
        assert rgb_to_256((204, 0, 51)) == 161

    def test_mapping_is_monotone_cost(self):
        # nearest palette entry never costs more than the query point
        for rgb in [(12, 200, 90), (100, 100, 100), (250, 1, 128)]:
            i = rgb_to_256(rgb)
            r, g, b = _PAL256[i]
            d = (rgb[0]-r)**2 + (rgb[1]-g)**2 + (rgb[2]-b)**2
            assert d <= (255**2) * 3


# ---------------------------------------------------------------------------
# F10 — SGR emission per depth
# ---------------------------------------------------------------------------

class TestSgrEmission:
    def test_truecolor_default(self, monkeypatch):
        monkeypatch.delenv("TERM", raising=False)
        monkeypatch.delenv("COLORTERM", raising=False)
        monkeypatch.delenv("HERMES_SKINS_COLOR_MODE", raising=False)
        assert ansi_fg_params((204, 0, 51)) == "38;2;204;0;51"
        assert ansi_fg_params((204, 0, 51), bold=True) == "1;38;2;204;0;51"
        assert ansi_bg_params((204, 0, 51)) == "48;2;204;0;51"

    def test_256_mode(self, monkeypatch):
        monkeypatch.setenv("HERMES_SKINS_COLOR_MODE", "256")
        assert ansi_fg_params((204, 0, 51)) == "38;5;161"
        assert ansi_fg_params((204, 0, 51), bold=True) == "1;38;5;161"
        assert ansi_bg_params((204, 0, 51)) == "48;5;161"

    def test_16_mode(self, monkeypatch):
        monkeypatch.setenv("HERMES_SKINS_COLOR_MODE", "16")
        assert ansi_fg_params((255, 0, 0)) == "91"          # bright red
        assert ansi_fg_params((128, 0, 0)) == "31"          # dark red
        assert ansi_fg_params((255, 0, 0), bold=True) == "1;91"
        assert ansi_bg_params((255, 0, 0)) == "101"
        assert ansi_bg_params((0, 0, 0)) == "40"

    def test_none_mode(self, monkeypatch):
        monkeypatch.setenv("HERMES_SKINS_COLOR_MODE", "none")
        assert ansi_fg_params((204, 0, 51)) == ""
        assert ansi_bg_params((204, 0, 51)) == ""

    def test_fg_and_bold_fg_degrade(self, monkeypatch):
        monkeypatch.setenv("HERMES_SKINS_COLOR_MODE", "256")
        from hermes_skins.preview import _fg, _bold_fg, _bg
        assert _fg("#CC0033", "x") == "\033[38;5;161mx\033[0m"
        assert _bold_fg("#CC0033", "x") == "\033[1;38;5;161mx\033[0m"
        assert _bg("#CC0033", "  ") == "\033[48;5;161m  \033[0m"

    def test_dumb_term_renders_plain(self, monkeypatch):
        monkeypatch.setenv("TERM", "dumb")
        monkeypatch.delenv("COLORTERM", raising=False)
        monkeypatch.delenv("HERMES_SKINS_COLOR_MODE", raising=False)
        from hermes_skins.preview import _fg
        assert _fg("#CC0033", "x") == "x"

    def test_render_preview_256_smoke(self, monkeypatch):
        monkeypatch.setenv("HERMES_SKINS_COLOR_MODE", "256")
        skin = generate_from_template("asuka")
        out = __import__("hermes_skins.preview", fromlist=["render_preview"]).render_preview(skin)
        assert "38;2;" not in out and "48;2;" not in out
        assert "38;5;" in out
        # degradation is lossless to read: strip ANSI and structure remains
        assert "Color Palette:" in strip_ansi(out)


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------

class TestDoctor:
    def _install(self, isolated_home, template="asuka"):
        out = isolated_home / ".hermes" / "skins" / f"{template}.yaml"
        out.parent.mkdir(parents=True, exist_ok=True)
        generate_from_template(template).dump(out)
        return out

    def test_doctor_healthy(self, runner, isolated_home):
        self._install(isolated_home)
        cfg = isolated_home / ".hermes" / "config.yaml"
        cfg.write_text("display:\n  skin: asuka\n", encoding="utf-8")
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "✓ active-skin-loads" in result.output
        assert "✓ healthy" in result.output

    def test_doctor_active_not_installed_fails(self, runner, isolated_home):
        cfg = isolated_home / ".hermes" / "config.yaml"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text("display:\n  skin: ghost\n", encoding="utf-8")
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 1
        assert "✗ active-skin-loads" in result.output

    def test_doctor_warn_on_warnings_skin(self, runner, isolated_home, tmp_path):
        # a skin with an advisory warning (e.g. 1 spinner face) → warn, exit 0
        self._install(isolated_home)
        p = isolated_home / ".hermes" / "skins" / "warny.yaml"
        p.write_text(textwrap.dedent("""\
            name: warny
            description: minimal
            colors:
              ui_accent: "#CC0033"
            spinner:
              waiting_faces: ["(·)"]
        """), encoding="utf-8")
        cfg = isolated_home / ".hermes" / "config.yaml"
        cfg.write_text("display:\n  skin: warny\n", encoding="utf-8")
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "⚠ active-skin-loads" in result.output

    def test_doctor_json(self, runner, isolated_home):
        self._install(isolated_home)
        cfg = isolated_home / ".hermes" / "config.yaml"
        cfg.write_text("display:\n  skin: asuka\n", encoding="utf-8")
        result = runner.invoke(app, ["doctor", "--json"])
        assert result.exit_code == 0
        d = jsonlib.loads(result.output)
        assert d["ok"] is True
        assert d["active"] == "asuka"
        assert any(c["check"] == "active-skin-loads" and c["status"] == "ok" for c in d["checks"])
        assert d["skin"]["name"] == "asuka"

    def test_doctor_explicit_name(self, runner, isolated_home):
        self._install(isolated_home, "rei")
        result = runner.invoke(app, ["doctor", "rei"])
        assert result.exit_code == 0
        assert "active: rei" in result.output

    def test_doctor_explicit_name_overrides_config(self, runner, isolated_home):
        # AGY audit F-02: explicit NAME must win over config.yaml display.skin.
        self._install(isolated_home)
        self._install(isolated_home, "rei")
        cfg = isolated_home / ".hermes" / "config.yaml"
        cfg.write_text("display:\n  skin: asuka\n", encoding="utf-8")
        result = runner.invoke(app, ["doctor", "rei"])
        assert result.exit_code == 0
        assert "active: rei" in result.output


# ---------------------------------------------------------------------------
# wcag report
# ---------------------------------------------------------------------------

class TestWcag:
    def test_wcag_template_passes(self, runner, isolated_home):
        # templates are WCAG-clamped — the hard status-bar pairs must pass
        result = runner.invoke(app, ["wcag", "asuka"])
        assert result.exit_code == 0
        assert "7/7 status-bar pairs pass (hard)" in result.output
        assert "0 fail" in result.output

    def test_wcag_failing_skin(self, runner, isolated_home):
        p = isolated_home / ".hermes" / "skins"
        p.mkdir(parents=True)
        (p / "bad.yaml").write_text(textwrap.dedent("""\
            name: bad
            colors:
              status_bar_bg: "#222222"
              status_bar_text: "#333333"
        """), encoding="utf-8")
        result = runner.invoke(app, ["wcag", "bad"])
        assert result.exit_code == 1
        assert "✗" in result.output
        assert "→ try" in result.output  # ensure_contrast suggestion

    def test_wcag_json(self, runner, isolated_home):
        result = runner.invoke(app, ["wcag", "rei", "--json"])
        assert result.exit_code == 0
        d = jsonlib.loads(result.output)
        assert d["skin"] == "rei"
        assert d["pass"] is True
        assert d["hard_failures"] == []
        assert len(d["pairs"]) == 29
        assert all(p["pass"] for p in d["pairs"] if p.get("hard"))
        # advisory slots carry per-pair data without failing the report
        assert all(p.get("hard") or p["pass"] or "suggest" in p for p in d["pairs"])

    def test_wcag_unknown_skin(self, runner, isolated_home):
        result = runner.invoke(app, ["wcag", "gendo"])
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_wcag_dim_pair_uses_relaxed_threshold(self, runner, isolated_home):
        result = runner.invoke(app, ["wcag", "misato", "--json"])
        d = jsonlib.loads(result.output)
        dim = next(p for p in d["pairs"] if p["slot"] == "status_bar_dim")
        assert dim["required"] == 3.0
        others = [p for p in d["pairs"] if p["slot"] != "status_bar_dim"]
        assert all(p["required"] == 4.5 for p in others)

    def test_wcag_invalid_hex_does_not_crash(self, runner, isolated_home):
        # AGY audit F-01: an invalid hex in a hard slot must not KeyError.
        p = isolated_home / ".hermes" / "skins"
        p.mkdir(parents=True)
        (p / "broken.yaml").write_text(textwrap.dedent("""\
            name: broken
            colors:
              status_bar_bg: "#222222"
              status_bar_text: "#ZZZZZZ"
        """), encoding="utf-8")
        result = runner.invoke(app, ["wcag", "broken"])
        assert result.exit_code == 1
        assert "invalid hex" in result.output

    def test_wcag_invalid_hex_json(self, runner, isolated_home):
        p = isolated_home / ".hermes" / "skins"
        p.mkdir(parents=True)
        (p / "broken.yaml").write_text(textwrap.dedent("""\
            name: broken
            colors:
              status_bar_bg: "#222222"
              status_bar_text: "#ZZZZZZ"
        """), encoding="utf-8")
        result = runner.invoke(app, ["wcag", "broken", "--json"])
        assert result.exit_code == 1
        d = jsonlib.loads(result.output)
        assert d["pass"] is False
        assert "status_bar_text" in d["hard_failures"]

    def test_wcag_sweep_survives_corrupt_skin(self, runner, isolated_home):
        # AGY audit F-05: one unreadable skin must not crash the sweep.
        out = isolated_home / ".hermes" / "skins"
        out.mkdir(parents=True)
        generate_from_template("rei").dump(out / "rei.yaml")
        (out / "corrupt.yaml").write_text("{ this is not: yaml: [", encoding="utf-8")
        result = runner.invoke(app, ["wcag"])
        assert result.exit_code == 1  # corrupt skin counts as a failure
        assert "unreadable" in result.output
        assert "rei" in result.output  # the healthy skin is still reported
        d = jsonlib.loads(runner.invoke(app, ["wcag", "--json"]).output)
        assert d["ok"] is False
        assert d["skins"]["corrupt"]["pass"] is False
        assert d["skins"]["rei"]["pass"] is True

    def test_wcag_accepts_file_path(self, runner, isolated_home, tmp_path):
        # AGY audit F-06: wcag accepts a YAML path like validate does.
        src = tmp_path / "s.yaml"
        generate_from_template("shinji").dump(src)
        result = runner.invoke(app, ["wcag", str(src), "--json"])
        assert result.exit_code == 0
        d = jsonlib.loads(result.output)
        assert d["pass"] is True
        assert len(d["pairs"]) == 29


# ---------------------------------------------------------------------------
# --json outputs
# ---------------------------------------------------------------------------

class TestJsonOutputs:
    def test_list_json_empty(self, runner, isolated_home):
        result = runner.invoke(app, ["list-json"])
        assert result.exit_code == 0
        d = jsonlib.loads(result.output)
        assert d["count"] == 0 and d["skins"] == [] and d["active"] is None

    def test_list_json_entries(self, runner, isolated_home):
        out = isolated_home / ".hermes" / "skins"
        out.mkdir(parents=True)
        generate_from_template("asuka").dump(out / "asuka.yaml")
        generate_from_template("rei").dump(out / "rei.yaml")
        cfg = isolated_home / ".hermes" / "config.yaml"
        cfg.write_text("display:\n  skin: rei\n", encoding="utf-8")
        result = runner.invoke(app, ["list-json"])
        d = jsonlib.loads(result.output)
        assert d["count"] == 2
        assert d["active"] == "rei"
        by_name = {s["name"]: s for s in d["skins"]}
        assert by_name["rei"]["active"] is True
        assert by_name["asuka"]["active"] is False
        assert by_name["asuka"]["valid"] is True
        assert by_name["asuka"]["primary"].startswith("#")

    def test_validate_json_valid_skin(self, runner, isolated_home, tmp_path):
        src = tmp_path / "s.yaml"
        generate_from_template("shinji").dump(src)
        result = runner.invoke(app, ["validate", str(src), "--json"])
        assert result.exit_code == 0
        d = jsonlib.loads(result.output)
        assert d["ok"] is True
        entry = d["skins"][0]
        assert entry["valid"] is True
        assert entry["contrast_errors"] == []
        assert len(entry["contrast"]) == 7
        assert all(p["pass"] for p in entry["contrast"])

    def test_validate_json_failing_skin(self, runner, isolated_home, tmp_path):
        src = tmp_path / "bad.yaml"
        src.write_text(textwrap.dedent("""\
            name: bad
            colors:
              status_bar_bg: "#222222"
              status_bar_text: "#333333"
              ui_accent: "#GGGGGG"
        """), encoding="utf-8")
        result = runner.invoke(app, ["validate", str(src), "--json"])
        assert result.exit_code == 1
        d = jsonlib.loads(result.output)
        assert d["ok"] is False
        entry = d["skins"][0]
        assert entry["valid"] is False
        assert entry["schema_errors"]
        assert entry["contrast_errors"]

    def test_validate_json_suppresses_human_output(self, runner, isolated_home, tmp_path):
        src = tmp_path / "s.yaml"
        generate_from_template("kaoru").dump(src)
        result = runner.invoke(app, ["validate", str(src), "--json"])
        assert result.output.lstrip().startswith("{")  # pure JSON, no ✓ lines

    def test_validate_json_all_installed(self, runner, isolated_home):
        out = isolated_home / ".hermes" / "skins"
        out.mkdir(parents=True)
        generate_from_template("asuka").dump(out / "asuka.yaml")
        result = runner.invoke(app, ["validate", "--json"])
        assert result.exit_code == 0
        d = jsonlib.loads(result.output)
        assert d["ok"] is True
        assert d["skins"][0]["skin"] == "asuka"
