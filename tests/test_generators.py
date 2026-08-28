"""Generator engine tests — color math, WCAG contrast, templates, random/custom.

Regression anchors for the audit root-cause bug B1 (colorsys (h, L, s)
contract) and the ensure_contrast engine (bidirectional search, mid-gray).
"""
from __future__ import annotations

import colorsys
import math

import pytest

from hermes_skins.generators import (
    adjust_lightness,
    adjust_saturation,
    contrast_ratio,
    ensure_contrast,
    generate_custom,
    generate_from_template,
    generate_palette,
    generate_random,
    hex_to_hsl,
    hsl_to_hex,
    list_templates,
    THEMES,
)
from hermes_skins.core import Colors, Skin


# ---------------------------------------------------------------------------
# hex_to_hsl — the B1 regression guard
# ---------------------------------------------------------------------------

class TestHexToHsl:
    def test_red(self):
        # #FF0000: hue 0, S=1, L=0.5.  If s/l were swapped this returns
        # (0, 0.5, 1.0) — an impossible S>1... actually valid-looking, hence
        # the numeric anchor below.
        h, s, l = hex_to_hsl("#FF0000")
        assert (h, s, l) == (0.0, 1.0, 0.5)

    def test_asuka_base(self):
        """#CC0033 ground truth: L=0.40, S=1.00 (was (345, 0.4, 1.0) pre-B1)."""
        h, s, l = hex_to_hsl("#CC0033")
        assert math.isclose(l, 0.40, abs_tol=1e-6)
        assert math.isclose(s, 1.00, abs_tol=1e-6)
        assert math.isclose(h, 345.0, abs_tol=1e-6)

    def test_h_matches_colorsys_contract(self):
        for hexc in ("#CC0033", "#3B7EC4", "#C0C0C0", "#1a1a2e", "#00FF7F"):
            r, g, b = (int(hexc.lstrip("#")[i:i+2], 16) / 255 for i in (0, 2, 4))
            ch, cl, cs = colorsys.rgb_to_hls(r, g, b)
            h, s, l = hex_to_hsl(hexc)
            assert math.isclose(h, ch * 360, abs_tol=1e-6)
            assert math.isclose(s, cs, abs_tol=1e-6)
            assert math.isclose(l, cl, abs_tol=1e-6)

    def test_grayscale_has_zero_saturation(self):
        h, s, l = hex_to_hsl("#808080")
        assert s == 0.0
        assert math.isclose(l, 128 / 255, abs_tol=1e-6)

    def test_alpha_accepted_ignored(self):
        assert hex_to_hsl("#CC003380") == hex_to_hsl("#CC0033")

    @pytest.mark.parametrize("bad", ["", "CC0033", "#ZZZZZZ", "#CC00", "red", "#CC0033XX"])
    def test_invalid_raises_valueerror(self, bad):
        with pytest.raises(ValueError):
            hex_to_hsl(bad)


class TestHslToHex:
    def test_round_trip(self):
        for hexc in ("#CC0033", "#3B7EC4", "#ABCDEF", "#000000", "#FFFFFF"):
            h, s, l = hex_to_hsl(hexc)
            assert hsl_to_hex(h, s, l) == hexc.upper()

    def test_hue_wraps(self):
        assert hsl_to_hex(360, 1, 0.5) == hsl_to_hex(0, 1, 0.5)

    def test_black_white_extremes(self):
        assert hsl_to_hex(0, 0, 0) == "#000000"
        assert hsl_to_hex(0, 0, 1) == "#FFFFFF"

    def test_no_truncation_drift(self):
        # int() truncation used to give 0x32 for 50.9999/255-scale values
        assert hsl_to_hex(120.0, 1.0, 0.2) == "#006600"


class TestAdjust:
    def test_lightness_up(self):
        assert adjust_lightness("#000000", 0.5) == "#808080"

    def test_lightness_clamped(self):
        assert adjust_lightness("#FFFFFF", 0.5) == "#FFFFFF"
        assert adjust_lightness("#000000", -0.5) == "#000000"

    def test_saturation_kill(self):
        # #CC0033 has L=0.40; desaturating keeps that lightness → #666666
        assert adjust_saturation("#CC0033", 0.0) == "#666666"
        h, s, l = hex_to_hsl(adjust_saturation("#FF6D00", 0.0))
        assert s == 0.0


# ---------------------------------------------------------------------------
# WCAG contrast engine
# ---------------------------------------------------------------------------

class TestContrast:
    def test_known_ratios(self):
        assert math.isclose(contrast_ratio("#FFFFFF", "#FFFFFF"), 1.0)
        assert math.isclose(contrast_ratio("#000000", "#FFFFFF"), 21.0)
        assert contrast_ratio("#000000", "#808080") > 4.5

    def test_symmetric(self):
        assert contrast_ratio("#CC0033", "#111111") == contrast_ratio("#111111", "#CC0033")

    def test_ensure_contrast_noop_when_ok(self):
        assert ensure_contrast("#FFFFFF", "#000000") == "#FFFFFF"

    def test_ensure_contrast_meets_target(self):
        for bg in ("#1A1A2E", "#808080", "#CCCCCC", "#000000", "#FFFFFF", "#C0C0C0"):
            out = ensure_contrast("#888888", bg, 4.5)
            assert contrast_ratio(out, bg) >= 4.5, (out, bg)

    def test_ensure_contrast_mid_gray_bg(self):
        # The audit's killer case: mid-gray background, single-direction
        # brightening caps at ~4.0:1. Bidirectional search must solve it.
        out = ensure_contrast("#999999", "#CCCCCC", 4.5)
        assert contrast_ratio(out, "#CCCCCC") >= 4.5

    def test_ensure_contrast_preserves_hue(self):
        h_in, _, _ = hex_to_hsl("#8844AA")
        out = ensure_contrast("#8844AA", "#AAAAAA", 4.5)
        h_out, _, _ = hex_to_hsl(out)
        assert math.isclose(h_in, h_out, abs_tol=0.5) or h_in == h_out

    def test_ensure_contrast_keeps_already_valid(self):
        # A saturated red on white is already 5.9:1 — must not be dimmed
        red = "#CC0033"
        assert ensure_contrast(red, "#FFFFFF", 4.5) == red


# ---------------------------------------------------------------------------
# Palette engine
# ---------------------------------------------------------------------------

def _aa_all(colors: Colors, fg_slots, bg_hex, ratio=4.5):
    for slot in fg_slots:
        c = getattr(colors, slot)
        assert contrast_ratio(c, bg_hex) >= ratio, (slot, c, bg_hex)


def test_palette_status_bar_aa_dark_base():
    colors = generate_palette("#CC0033", "complementary")
    bg = colors.status_bar_bg
    _aa_all(colors, ["status_bar_text", "status_bar_strong"], bg, 4.5)
    _aa_all(colors, ["status_bar_dim"], bg, 3.0)


def test_palette_light_base_readable():
    """Pre-B1: light bases produced ~1:1 status bars. Must stay readable."""
    for base in ("#C0C0C0", "#EEEEEE", "#DDDDDD"):
        colors = generate_palette(base, "monochrome")
        bg = colors.status_bar_bg
        assert contrast_ratio(colors.status_bar_text, bg) >= 4.5
        assert contrast_ratio(colors.status_bar_strong, bg) >= 4.5


def test_palette_complementary_accent_differs_from_base():
    """Complement of 345° must land near 165°, not echo the base hue
    (audit 0.2.0 #6: the old range allowed the base hue through)."""
    colors = generate_palette("#CC0033", "complementary")
    h, _, _ = hex_to_hsl(colors.banner_title)
    assert 120 <= h <= 210, f"complement hue {h} out of expected sector"


def test_palette_harmonies_all_produce_29_slots():
    for harmony in ("complementary", "analogous", "triadic", "monochrome", "split_comp"):
        colors = generate_palette("#3B7EC4", harmony)
        assert len(colors.to_dict()) == 29


def test_palette_unknown_harmony_falls_back_to_base():
    """Unknown harmony keeps base hue (documented fallback), never crashes."""
    colors = generate_palette("#3B7EC4", "not-a-harmony")
    assert len(colors.to_dict()) == 29


def test_palette_semantic_bad_is_fixed_orange():
    """B5: 'bad' must be a warning hue regardless of base (nerv green)."""
    colors = generate_palette("#2B7A2B", "complementary")
    assert colors.status_bar_bad == "#FF8C00"


def test_random_palettes_20_seeds_aa():
    for seed in range(20):
        colors = generate_palette(hsl_to_hex(seed * 17.3, 0.65, 0.45), "complementary")
        bg = colors.status_bar_bg
        assert contrast_ratio(colors.status_bar_text, bg) >= 4.5, seed
        assert contrast_ratio(colors.status_bar_strong, bg) >= 4.5, seed


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

def test_list_templates_returns_8():
    assert len(list_templates()) == 8


def test_all_template_names_listed():
    assert set(list_templates()) == {
        "asuka", "rei", "shinji", "misato", "kaoru", "nerv", "berserk", "seele",
    }


def test_unknown_template_raises():
    with pytest.raises(ValueError, match="Unknown template"):
        generate_from_template("gendo")


@pytest.mark.parametrize("name", sorted(THEMES))
def test_template_generates_valid_skin(name):
    skin = generate_from_template(name)
    assert isinstance(skin, Skin)
    assert skin.name == name
    assert skin.validate() == []
    assert len(skin.colors.to_dict()) == 29
    assert len(skin.spinner.waiting_faces) >= 2


@pytest.mark.parametrize("name", sorted(THEMES))
def test_template_banner_art_present(name):
    skin = generate_from_template(name)
    assert skin.banner_logo and skin.banner_hero
    assert "[/" in skin.banner_logo and "[/" in skin.banner_hero


@pytest.mark.parametrize("name", sorted(THEMES))
def test_template_status_bar_aa(name):
    """The audit's headline regression: every template's status bar ≥4.5:1."""
    skin = generate_from_template(name)
    bg = skin.colors.status_bar_bg
    assert contrast_ratio(skin.colors.status_bar_text, bg) >= 4.5, name
    assert contrast_ratio(skin.colors.status_bar_strong, bg) >= 4.5, name


def test_seele_template_faces_not_default():
    """B3: seele had a `waiting_faces:` typo so its faces never applied."""
    skin = generate_from_template("seele")
    assert skin.spinner.waiting_faces == ["(❒)", "(❑)", "(❏)", "(■)", "(□)"]


def test_berserk_thinking_verbs_are_feral():
    skin = generate_from_template("berserk")
    assert "BREAKING CONTAINMENT" in skin.spinner.thinking_verbs


# ---------------------------------------------------------------------------
# Random + custom
# ---------------------------------------------------------------------------

def test_random_deterministic_with_seed():
    a, b = generate_random("eva"), generate_random("eva")
    assert a.to_dict() == b.to_dict()


def test_random_no_seed_differs_eventually():
    seen = {generate_random().to_dict()["name"] for _ in range(10)}
    assert len(seen) > 1


def test_random_skin_is_valid():
    for seed in ("a", "b", 42, "eva-unit-01"):
        assert generate_random(seed).validate() == []


def test_random_name_prefixed():
    assert generate_random("x").name.startswith("random-")


def test_custom_generates_valid_skin():
    skin = generate_custom("mytheme", "#FF6D00", "triadic")
    assert skin.name == "mytheme"
    assert skin.validate() == []
    assert len(skin.colors.to_dict()) == 29


def test_custom_bad_color_raises():
    with pytest.raises(ValueError):
        generate_custom("bad", "#ZZZZZZ")
