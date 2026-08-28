"""Preview renderer tests — ANSI conversion, rich markup, tool-row wrapping.

Regression anchors: B2 (malformed color crash), B7 (rich tag leakage),
B12 (tool row overflow).
"""
from __future__ import annotations

from hermes_skins.core import Skin
from hermes_skins.generators import generate_from_template
from hermes_skins.preview import (
    _rgb,
    _fg,
    _wrap_tool_row,
    convert_rich_markup,
    render_preview,
)


# ---------------------------------------------------------------------------
# _rgb
# ---------------------------------------------------------------------------

def test_rgb_parses_basic():
    assert _rgb("#CC0033") == (204, 0, 51)
    assert _rgb("#cc0033") == (204, 0, 51)


def test_rgb_none_on_malformed():
    assert _rgb("#ZZZZZZ") is None
    assert _rgb("#FFF") is None
    assert _rgb(123456) is None      # type: ignore[arg-type]  # non-string from hand-edited YAML (B2)
    assert _rgb(None) is None        # type: ignore[arg-type]
    assert _rgb("") is None


def test_rgb_ignores_alpha():
    assert _rgb("#CC003380") == (204, 0, 51)


def test_fg_passthrough_on_bad_color():
    assert _fg("#ZZZZZZ", "text") == "text"
    from hermes_skins.preview import _bold_fg
    assert _bold_fg(42, "bold") == "bold"  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Rich markup conversion (B7)
# ---------------------------------------------------------------------------

def test_convert_bold_tag():
    out = convert_rich_markup("[bold #C98293]ASUKA[/]")
    assert out == "\033[1;38;2;201;130;147mASUKA\033[0m"


def test_convert_plain_tag():
    out = convert_rich_markup("[#E8C9D1]hero[/]")
    assert out == "\033[38;2;232;201;209mhero\033[0m"


def test_convert_multiline_and_mixed():
    text = "[bold #172F47]AAA[/]\n[#87AED7]BBB[/]\nplain"
    out = convert_rich_markup(text)
    assert "\x1b[" in out
    assert "plain" in out
    assert "[bold" not in out and "[#87AED7]" not in out


def test_convert_no_tags_unchanged():
    assert convert_rich_markup("no tags here") == "no tags here"


def test_convert_invalid_inner_color_left_alone():
    # Only well-formed #HEX tags convert; others stay visible rather than vanish
    assert convert_rich_markup("[bold #nothex]x[/]") == "[bold #nothex]x[/]"


# ---------------------------------------------------------------------------
# Tool row wrapping (B12)
# ---------------------------------------------------------------------------

def test_wrap_short_row_single_line():
    items = ["▸ terminal", "◎ search"]
    assert _wrap_tool_row(items, width=80) == ["▸ terminal  ◎ search"]


def test_wrap_long_row_splits():
    items = [f"▸ tool-{i:02d}xxxxxxxxxxxxxxx" for i in range(10)]
    lines = _wrap_tool_row(items, width=40)
    assert len(lines) > 1
    # every emitted line respects the width
    assert all(len(line) <= 40 for line in lines)


def test_wrap_single_long_item_kept_intact():
    lines = _wrap_tool_row(["▸ " + "x" * 100], width=40)
    assert len(lines) == 1  # can't split one item; must not drop it


def test_wrap_empty():
    assert _wrap_tool_row([], width=80) == []


# ---------------------------------------------------------------------------
# render_preview
# ---------------------------------------------------------------------------

def test_preview_valid_skin_has_ok_line():
    skin = generate_from_template("asuka")
    out = render_preview(skin)
    assert "✓ Skin valid" in out


def test_preview_warns_on_invalid_skin():
    skin = Skin.from_dict({"name": "broken", "colors": {"banner_title": "#ZZZZZZ"}})
    out = render_preview(skin)
    assert "Validation warnings" in out
    assert "banner_title" in out


def test_preview_contains_all_29_slots():
    skin = generate_from_template("rei")
    out = render_preview(skin)
    for slot in skin.colors.to_dict():
        assert slot in out


def test_preview_banner_art_no_raw_rich_tags():
    skin = generate_from_template("asuka")
    out = render_preview(skin)
    # Rich tags must be converted, not leaked (B7)
    assert "[bold #" not in out
    assert "\x1b[" in out  # ANSI present


def test_preview_without_banner_art():
    skin = Skin(name="plain")
    out = render_preview(skin)
    assert "Banner Logo" not in out
    assert "✓ Skin valid" in out


def test_preview_status_bar_section_shows_swatch():
    skin = generate_from_template("shinji")
    out = render_preview(skin)
    assert "status_bar_bg" in out
