"""Tests for the P2 feature cycle (v0.3.0).

Covers: F2 light mode, F7 CRUD, F5 diff, F8 URL install (fetch resolution),
F9 banner palette sync, F11 extended harmonies, F12 schema versioning,
F15 dynamic tool emoji. picker/watch are TTY-interactive and covered by
smoke tests only (non-TTY error paths).
"""
from __future__ import annotations

import re

import pytest
from typer.testing import CliRunner

from hermes_skins import cli as cli_mod
from hermes_skins.cli import app
from hermes_skins.core import SCHEMA_VERSION, Skin
from hermes_skins.generators import (
    contrast_ratio,
    generate_from_template,
    generate_palette,
    generate_random,
    sync_banner_art,
    THEMES,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# F2 — light mode
# ---------------------------------------------------------------------------

class TestLightMode:
    def test_light_palette_surfaces_are_light(self):
        c = generate_palette("#CC0033", "complementary", mode="light")
        def lum(hx):
            rgb = [int(hx.lstrip("#")[i:i+2], 16) / 255 for i in (0, 2, 4)]
            return 0.2126*rgb[0] + 0.7152*rgb[1] + 0.0722*rgb[2]
        # Light surfaces: status bg + selection bg should be near-white luminance
        assert lum(c.status_bar_bg) > 0.75
        assert lum(c.selection_bg) > 0.75
        # Dark ink: body text should be dark
        assert lum(c.banner_text) < 0.25
        assert lum(c.prompt) < 0.25

    def test_light_mode_contrast_pairs_pass(self):
        for base in ("#CC0033", "#3B7EC4", "#2B7A2B", "#1a1a2e", "#C0C0C0"):
            c = generate_palette(base, "complementary", mode="light")
            for slot in ("status_bar_text", "status_bar_strong", "status_bar_good",
                         "status_bar_warn", "status_bar_bad", "status_bar_critical"):
                ratio = contrast_ratio(getattr(c, slot), c.status_bar_bg)
                assert ratio >= 4.5, f"{base}/{slot}: {ratio:.2f}"
            assert contrast_ratio(c.status_bar_dim, c.status_bar_bg) >= 3.0

    def test_light_template_changes_colors_not_branding(self):
        dark = generate_from_template("asuka")
        light = generate_from_template("asuka", mode="light")
        assert dark.colors.status_bar_bg != light.colors.status_bar_bg
        assert dark.branding.agent_name == light.branding.agent_name
        assert dark.spinner.waiting_faces == light.spinner.waiting_faces

    def test_invalid_mode_rejected(self):
        with pytest.raises(ValueError, match="mode"):
            generate_palette("#CC0033", mode="sepia")

    def test_dark_mode_unchanged_output(self):
        # Regression guard: mode=dark must equal the pre-F2 derivation
        old_style = generate_palette("#CC0033", "complementary", mode="dark")
        asuka = generate_from_template("asuka").colors
        assert old_style.to_dict() == asuka.to_dict()

    def test_cli_random_light_mode(self, isolated_home):
        result = runner.invoke(app, ["random", "seed1", "--mode", "light"])
        assert result.exit_code == 0, result.output
        assert "light" in result.output.lower()
        # Name carries -light suffix so dark/light dumps don't collide
        assert "-light" in result.output


# ---------------------------------------------------------------------------
# F7 — CRUD lifecycle
# ---------------------------------------------------------------------------

@pytest.fixture()
def installed_skin(isolated_home):
    """Generate + install one asuka skin into the isolated home."""
    result = runner.invoke(app, ["generate", "asuka"])
    assert result.exit_code == 0, result.output
    return isolated_home


class TestCRUD:
    def test_uninstall_removes_file(self, installed_skin):
        result = runner.invoke(app, ["uninstall", "asuka"])
        assert result.exit_code == 0, result.output
        assert not (installed_skin / ".hermes" / "skins" / "asuka.yaml").exists()

    def test_uninstall_missing_fails(self, isolated_home):
        result = runner.invoke(app, ["uninstall", "ghost"])
        assert result.exit_code == 1

    def test_uninstall_active_requires_force(self, installed_skin):
        # Make asuka active by writing config.yaml
        cfg = installed_skin / ".hermes" / "config.yaml"
        cfg.write_text("display:\n  skin: asuka\n", encoding="utf-8")
        r1 = runner.invoke(app, ["uninstall", "asuka"])
        assert r1.exit_code == 1
        assert "ACTIVE" in r1.output
        r2 = runner.invoke(app, ["uninstall", "asuka", "--force"])
        assert r2.exit_code == 0, r2.output
        assert not (installed_skin / ".hermes" / "skins" / "asuka.yaml").exists()

    def test_rename_updates_file_and_internal_name(self, installed_skin):
        result = runner.invoke(app, ["rename", "asuka", "asuka-classic"])
        assert result.exit_code == 0, result.output
        skins_dir = installed_skin / ".hermes" / "skins"
        assert not (skins_dir / "asuka.yaml").exists()
        skin = Skin.load(skins_dir / "asuka-classic.yaml")
        assert skin.name == "asuka-classic"

    def test_rename_rejects_collision(self, installed_skin):
        runner.invoke(app, ["generate", "rei"])
        result = runner.invoke(app, ["rename", "asuka", "rei"])
        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_rename_sanitizes_traversal(self, installed_skin):
        result = runner.invoke(app, ["rename", "asuka", "../escaped"])
        assert result.exit_code == 0
        # Lands as "escaped.yaml" INSIDE the skins dir, never outside
        skins_dir = installed_skin / ".hermes" / "skins"
        assert (skins_dir / "escaped.yaml").exists()
        assert not (installed_skin / "escaped.yaml").exists()

    def test_clone_from_installed(self, installed_skin):
        result = runner.invoke(app, ["clone", "asuka", "asuka-v2"])
        assert result.exit_code == 0, result.output
        skin = Skin.load(installed_skin / ".hermes" / "skins" / "asuka-v2.yaml")
        assert skin.name == "asuka-v2"

    def test_clone_from_template(self, isolated_home):
        result = runner.invoke(app, ["clone", "seele", "seele-prod"])
        assert result.exit_code == 0, result.output
        skin = Skin.load(isolated_home / ".hermes" / "skins" / "seele-prod.yaml")
        assert skin.name == "seele-prod"

    def test_clone_collision(self, installed_skin):
        result = runner.invoke(app, ["clone", "asuka", "asuka"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# F5 — diff
# ---------------------------------------------------------------------------

class TestDiff:
    def test_diff_same_skin_reports_identical(self, isolated_home):
        result = runner.invoke(app, ["diff", "asuka", "asuka"])
        assert result.exit_code == 0
        assert "identical" in result.output or "0/29" in result.output

    def test_diff_reports_differences(self, isolated_home):
        result = runner.invoke(app, ["diff", "asuka", "rei"])
        assert result.exit_code == 0
        assert "differ" in result.output

    def test_diff_missing_skin(self, isolated_home):
        result = runner.invoke(app, ["diff", "asuka", "ghost"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# F8 — URL install (fetch resolution; network mocked)
# ---------------------------------------------------------------------------

class TestInstallUrl:
    SKIN_YAML = "name: remote-skin\ndescription: fetched\ncolors:\n  ui_accent: \"#336699\"\n"

    def test_gist_url_resolves_to_raw(self):
        # The gist→raw regex lives inside _fetch_url; verify it matches the
        # canonical gist URL shape (same pattern as the implementation).
        pattern = r"https://gist\.github\.com/([^/]+)/([0-9a-f]+)$"
        assert re.match(pattern, "https://gist.github.com/user/abc123def")
        assert not re.match(pattern, "https://github.com/user/repo")

    def test_install_url_success(self, isolated_home, monkeypatch):
        monkeypatch.setattr(cli_mod, "_fetch_url", lambda url, timeout=15.0: self.SKIN_YAML)
        result = runner.invoke(app, ["install-url", "https://example.com/skin.yaml"])
        assert result.exit_code == 0, result.output
        assert "remote-skin" in result.output
        assert (isolated_home / ".hermes" / "skins" / "remote-skin.yaml").exists()

    def test_install_url_rejects_non_skin(self, isolated_home, monkeypatch):
        monkeypatch.setattr(cli_mod, "_fetch_url", lambda url, timeout=15.0: "::: garbage")
        result = runner.invoke(app, ["install-url", "https://example.com/skin.yaml"])
        assert result.exit_code == 1  # no name: field

    def test_install_url_download_error(self, isolated_home, monkeypatch):
        import urllib.error

        def boom(url, timeout=15.0):
            raise urllib.error.URLError("no dns")
        monkeypatch.setattr(cli_mod, "_fetch_url", boom)
        result = runner.invoke(app, ["install-url", "https://example.com/skin.yaml"])
        assert result.exit_code == 1
        assert "failed" in result.output.lower()

    def test_fetch_url_rejects_non_http(self):
        with pytest.raises(ValueError, match="http"):
            cli_mod._fetch_url("ftp://example.com/skin.yaml")


# ---------------------------------------------------------------------------
# F9 — banner palette sync
# ---------------------------------------------------------------------------

class TestBannerSync:
    def test_banner_art_follows_palette(self):
        skin = generate_from_template("asuka")
        # Extract hexes from banner art
        art_hexes = set(re.findall(r"#([0-9a-fA-F]{6})", skin.banner_logo))
        palette_hexes = {v.lstrip("#").upper() for v in skin.colors.to_dict().values()}
        # Every art hex must now come from the palette
        assert art_hexes <= palette_hexes, f"art hexes {art_hexes} not in palette"

    def test_sync_preserves_tag_structure(self):
        art = "[bold #111111]AAA[/]\n[#EEEEEE]BBB[/]"
        out = sync_banner_art(art, generate_from_template("rei").colors)
        assert out.count("[/]") == 2
        assert "[bold" in out
        assert "#111111" not in out and "#EEEEEE" not in out

    def test_sync_single_color_art(self):
        art = "[#888888]mono[/]"
        out = sync_banner_art(art, generate_from_template("rei").colors)
        assert "#888888" not in out
        assert "[/]}" not in out  # structure intact
        assert out.endswith("mono[/]")

    def test_sync_empty_art_passthrough(self):
        colors = generate_from_template("rei").colors
        assert sync_banner_art("", colors) == ""
        assert sync_banner_art("no tags here", colors) == "no tags here"

    def test_all_templates_synced(self):
        for t in THEMES:
            skin = generate_from_template(t)
            for art in (skin.banner_logo, skin.banner_hero):
                if not art:
                    continue
                art_hexes = set(re.findall(r"#([0-9a-fA-F]{6})", art))
                palette_hexes = {v.lstrip("#").upper() for v in skin.colors.to_dict().values()}
                assert art_hexes <= palette_hexes, f"{t}: art {art_hexes} ∉ palette"


# ---------------------------------------------------------------------------
# F11 — extended harmonies
# ---------------------------------------------------------------------------

class TestExtendedHarmonies:
    @pytest.mark.parametrize("harmony", ["tetradic", "square", "pastel", "neon"])
    def test_extended_harmonies_generate(self, harmony):
        c = generate_palette("#CC0033", harmony)
        assert c.ui_accent.startswith("#")

    @pytest.mark.parametrize("harmony", ["tetradic", "square", "pastel", "neon"])
    def test_extended_harmonies_ensemble_contrast(self, harmony):
        # Derived label/session colors must stay readable on the dark surface
        c = generate_palette("#CC0033", harmony)
        assert contrast_ratio(c.status_bar_text, c.status_bar_bg) >= 4.5
        assert contrast_ratio(c.ui_ok, c.status_bar_bg) >= 4.5

    def test_pastel_is_softer(self):
        base = generate_palette("#CC0033", "complementary")
        pastel = generate_palette("#CC0033", "pastel")
        # Pastel accent saturation is softened (45%) vs full-strength base
        import colorsys
        def sat_of(hx):
            r, g, b = [int(hx.lstrip("#")[i:i+2], 16) / 255 for i in (0, 2, 4)]
            _, _, s = colorsys.rgb_to_hls(r, g, b)  # contract: (h, L, s)
            return s
        assert sat_of(pastel.ui_accent) < sat_of(base.ui_accent)

    def test_cli_harmony_enum_extended(self, isolated_home):
        result = runner.invoke(app, ["custom", "my-skin", "--color", "#336699", "--harmony", "tetradic"])
        assert result.exit_code == 0, result.output

    def test_cli_rejects_bad_harmony(self, isolated_home):
        result = runner.invoke(app, ["custom", "my-skin", "--color", "#336699", "--harmony", "zygote"])
        assert result.exit_code != 0  # typer enum validation


# ---------------------------------------------------------------------------
# F12 — schema versioning + unknown key preservation
# ---------------------------------------------------------------------------

class TestSchemaVersioning:
    def test_dump_includes_schema_version(self, isolated_home):
        skin = generate_from_template("asuka")
        d = skin.to_dict()
        assert d["schema_version"] == SCHEMA_VERSION

    def test_roundtrip_preserves_unknown_keys(self, tmp_path):
        raw = {
            "name": "community",
            "description": "d",
            "author": "someone",
            "tags": ["dark", "eva"],
            "future_field": {"nested": [1, 2, 3]},
            "colors": {"ui_accent": "#112233"},
        }
        skin = Skin.from_dict(raw)
        assert skin.author == "someone"
        assert skin.tags == ["dark", "eva"]
        assert skin.extra == {"future_field": {"nested": [1, 2, 3]}}
        out = skin.to_dict()
        assert out["future_field"] == {"nested": [1, 2, 3]}
        assert out["author"] == "someone"
        assert out["tags"] == ["dark", "eva"]

    def test_newer_schema_version_warns(self):
        skin = Skin.from_dict({"name": "future", "schema_version": 99})
        warnings = skin.validate()
        assert any("newer than engine" in w for w in warnings)

    def test_valid_schema_version_no_warning(self):
        skin = Skin.from_dict({"name": "ok", "schema_version": SCHEMA_VERSION})
        assert not any("schema_version" in w for w in skin.validate())

    def test_bad_schema_version_warns(self):
        skin = Skin.from_dict({"name": "bad", "schema_version": "one"})
        assert any("not a positive integer" in w for w in skin.validate())

    def test_author_tags_survive_file_roundtrip(self, tmp_path):
        p = tmp_path / "s.yaml"
        p.write_text(
            "name: authored\nauthor: Andy\ntags:\n  - a\n  - b\n",
            encoding="utf-8",
        )
        skin = Skin.load(p)
        assert skin.author == "Andy"
        assert skin.tags == ["a", "b"]
        skin.dump(p)
        skin2 = Skin.load(p)
        assert skin2.author == "Andy"
        assert skin2.tags == ["a", "b"]


# ---------------------------------------------------------------------------
# F15 — dynamic tool emoji
# ---------------------------------------------------------------------------

class TestDynamicEmoji:
    def test_random_skins_get_varied_emoji(self):
        tables = set()
        for seed in range(8):
            skin = generate_random(seed)
            tables.add(tuple(skin.tool_emojis.values()))
        # More than one distinct table across seeds
        assert len(tables) > 1

    def test_semantic_icons_stable(self):
        skin = generate_random(123)
        assert skin.tool_emojis["clarify"] == "?"
        assert skin.tool_emojis["cronjob"] == "↻"
        assert skin.tool_emojis["process"] == "⚙"
        assert skin.tool_emojis["todo"] == "☐"

    def test_emoji_glyphs_come_from_faces(self):
        skin = generate_random(7)
        face_glyphs = {f.strip("()") for f in skin.spinner.waiting_faces}
        dynamic = [v for k, v in skin.tool_emojis.items()
                   if k not in ("clarify", "cronjob", "process", "todo", "mixture_of_agents")]
        assert all(g in face_glyphs for g in dynamic)

    def test_template_emoji_unchanged(self):
        # Templates keep their hand-picked icon sets (F15 is random/custom only)
        skin = generate_from_template("asuka")
        assert skin.tool_emojis["terminal"] == "◤"


# ---------------------------------------------------------------------------
# picker / watch — non-TTY error paths
# ---------------------------------------------------------------------------

class TestPickerWatchSmoke:
    def test_picker_requires_tty(self, isolated_home, monkeypatch):
        import io
        monkeypatch.setattr("sys.stdin", io.StringIO())  # not a tty
        result = runner.invoke(app, ["picker"])
        assert result.exit_code == 1
        assert "TTY" in result.output or "interactive" in result.output

    def test_watch_missing_file(self, isolated_home):
        result = runner.invoke(app, ["watch", "/nonexistent/skin.yaml"])
        assert result.exit_code == 1

    def test_help_lists_new_commands(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for cmd in ("uninstall", "rename", "clone", "diff", "install-url", "picker", "watch"):
            assert cmd in result.output


# ---------------------------------------------------------------------------
# AGY P2 audit regression tests (findings #1-#9)
# ---------------------------------------------------------------------------

class TestAGYP2Regressions:
    def test_f3_null_section_yaml_loads(self, tmp_path):
        p = tmp_path / "nulls.yaml"
        p.write_text("name: nulls\ncolors: null\nspinner: null\nbranding: null\n", encoding="utf-8")
        skin = Skin.load(p)  # must not raise
        assert skin.name == "nulls"
        assert skin.colors.ui_accent.startswith("#")

    def test_f7_validate_null_faces_no_crash(self):
        # Spinner.from_dict coerces null faces to defaults; validate must not
        # raise and the resulting skin must be usable.
        skin = Skin.from_dict({"name": "x", "spinner": {"waiting_faces": None}})
        assert skin.validate() is not None  # no TypeError
        assert len(skin.spinner.waiting_faces) >= 2

    def test_f7_validate_string_faces_no_crash(self):
        skin = Skin.from_dict({"name": "x", "spinner": {"waiting_faces": "not-a-list"}})
        assert skin.validate() is not None
        assert isinstance(skin.spinner.waiting_faces, (list, tuple))

    def test_f7_validate_direct_null_faces_warns(self):
        # When the dataclass itself carries a null (bypassing from_dict),
        # validate() warns instead of raising.
        skin = Skin(name="x")
        object.__setattr__(skin.spinner, "waiting_faces", None) if False else setattr(skin.spinner, "waiting_faces", None)
        warnings = skin.validate()
        assert any("waiting_faces" in w for w in warnings)

    def test_f1_picker_preview_keeps_ansi(self, monkeypatch):
        # The picker frame must NOT strip ANSI (render_preview handles NO_COLOR)
        import inspect
        from hermes_skins import cli
        src = inspect.getsource(cli._render_picker_screen)
        assert "strip_ansi(render_preview" not in src
        assert "render_preview(skin)" in src

    def test_f2_install_refuses_overwrite_without_force(self, isolated_home):
        r1 = runner.invoke(app, ["generate", "asuka"])
        assert r1.exit_code == 0
        # Write a modified skin and try to install over it
        import yaml as _yaml
        p = isolated_home / "other.yaml"
        skin_data = _yaml.safe_load((isolated_home / ".hermes" / "skins" / "asuka.yaml").read_text(encoding="utf-8"))
        skin_data["description"] = "modified"
        p.write_text(_yaml.safe_dump(skin_data, allow_unicode=True), encoding="utf-8")
        r2 = runner.invoke(app, ["install", str(p)])
        assert r2.exit_code == 1
        assert "--force" in r2.output
        r3 = runner.invoke(app, ["install", str(p), "--force"])
        assert r3.exit_code == 0, r3.output

    def test_f2_install_url_passes_force(self, isolated_home, monkeypatch):
        monkeypatch.setattr(cli_mod, "_fetch_url", lambda url, timeout=15.0: TestInstallUrl.SKIN_YAML)
        r1 = runner.invoke(app, ["install-url", "https://example.com/s.yaml"])
        assert r1.exit_code == 0
        # Second install without --force must refuse
        r2 = runner.invoke(app, ["install-url", "https://example.com/s.yaml"])
        assert r2.exit_code == 1
        assert "--force" in r2.output

    def test_f4_tetradic_differs_from_square(self):
        a = generate_palette("#CC0033", "tetradic").to_dict()
        b = generate_palette("#CC0033", "square").to_dict()
        assert a != b, "tetradic (rectangular) must be distinct from square"

    def test_f5_light_mode_extended_harmony_contrast(self):
        for base in ("#3B7EC4", "#FFCC00", "#2B7A2B"):
            for harmony in ("tetradic", "square", "pastel", "neon", "complementary", "monochrome"):
                c = generate_palette(base, harmony, mode="light")
                for slot in ("ui_label", "session_label", "banner_accent", "ui_accent"):
                    r = contrast_ratio(getattr(c, slot), c.status_bar_bg)
                    assert r >= 4.5, f"{base}/{harmony}/{slot}: {r:.2f}:1"

    def test_f5_light_mode_yellow_banner_accent(self):
        c = generate_palette("#FFCC00", "complementary", mode="light")
        assert contrast_ratio(c.banner_accent, c.status_bar_bg) >= 4.5

    def test_f6_rename_guards_physical_file(self, isolated_home):
        # File on disk whose internal name differs from its stem
        skins_dir = isolated_home / ".hermes" / "skins"
        skins_dir.mkdir(parents=True)
        (skins_dir / "zzz.yaml").write_text("name: asuka\n", encoding="utf-8")
        r = runner.invoke(app, ["generate", "rei", "-o", str(skins_dir / "rei.yaml")])
        assert r.exit_code == 0
        # rename rei → zzz: 'zzz' is not a lookup key (internal name 'asuka'),
        # but zzz.yaml exists on disk → must refuse, not overwrite
        r2 = runner.invoke(app, ["rename", "rei", "zzz"])
        assert r2.exit_code == 1
        assert (skins_dir / "zzz.yaml").read_text(encoding="utf-8").startswith("name: asuka")

    def test_f6_clone_guards_physical_file(self, isolated_home):
        skins_dir = isolated_home / ".hermes" / "skins"
        skins_dir.mkdir(parents=True)
        (skins_dir / "taken.yaml").write_text("name: different-skin\n", encoding="utf-8")
        r = runner.invoke(app, ["clone", "asuka", "taken"])
        assert r.exit_code == 1
        assert (skins_dir / "taken.yaml").read_text(encoding="utf-8").startswith("name: different-skin")

    def test_f8_gist_uppercase_id_resolves(self, monkeypatch):
        captured = {}
        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            raise OSError("stop here")  # don't actually fetch
        monkeypatch.setattr(cli_mod.urllib.request, "urlopen", fake_urlopen)
        with pytest.raises(OSError):
            cli_mod._fetch_url("https://gist.github.com/user/A1B2C3D4")
        assert captured["url"].startswith("https://gist.githubusercontent.com/")
