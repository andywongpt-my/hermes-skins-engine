"""P4 (v0.5.0) — the six original non-EVA-pilot templates.

Mari, Ritsuko, Gendo, Kaji, Lilith, Magi extend the Evangelion roster to
supporting cast and systems. Every template must generate a valid skin with
WCAG-AA status-bar contrast and palette-synced banner art.
"""

import re

import pytest

from hermes_skins.generators import (
    THEMES,
    contrast_ratio,
    generate_from_template,
    list_templates,
)

P4_TEMPLATES = ["mari", "ritsuko", "gendo", "kaji", "lilith", "magi"]


def test_p4_templates_registered():
    names = set(list_templates())
    for name in P4_TEMPLATES:
        assert name in names


def test_total_template_count_is_14():
    assert len(list_templates()) == 14


@pytest.mark.parametrize("name", P4_TEMPLATES)
def test_p4_generates_valid_skin(name):
    skin = generate_from_template(name)
    assert skin.validate() == []


@pytest.mark.parametrize("name", P4_TEMPLATES)
def test_p4_status_bar_meets_aa(name):
    skin = generate_from_template(name)
    d = skin.colors.to_dict()
    ratio = contrast_ratio(d["status_bar_text"], skin.colors.status_bar_bg)
    assert ratio >= 4.5, f"{name}: {ratio:.2f}"


@pytest.mark.parametrize("name", P4_TEMPLATES)
def test_p4_banner_art_synced(name):
    """Banner hexes must map onto the generated palette, not stay hand-picked."""
    skin = generate_from_template(name)
    palette_hexes = set(skin.colors.to_dict().values())
    art = (skin.banner_logo or "") + (skin.banner_hero or "")
    art_hexes = set(re.findall(r"\[(?:bold )?(#[0-9A-Fa-f]{6})\]", art))
    orphan = art_hexes - palette_hexes
    # Every distinct art hex must exist in the palette (sync_banner_art contract)
    assert not orphan, f"{name}: art colors {orphan} missing from palette"


@pytest.mark.parametrize("name", P4_TEMPLATES)
def test_p4_light_mode_works(name):
    skin = generate_from_template(name, mode="light")
    assert skin.validate() == []


@pytest.mark.parametrize("name", P4_TEMPLATES)
def test_p4_branding_complete(name):
    skin = generate_from_template(name)
    b = skin.branding
    assert b.agent_name and b.welcome and b.goodbye
    assert b.prompt_symbol.endswith(" ")
    assert len(skin.spinner.waiting_faces) >= 2
    assert len(skin.spinner.thinking_verbs) >= 4


def test_p4_tool_emojis_cover_core_tools():
    for name in P4_TEMPLATES:
        skin = generate_from_template(name)
        for tool in ("terminal", "web_search", "read_file", "write_file",
                     "execute_code", "delegate_task"):
            assert tool in skin.tool_emojis, f"{name}: missing {tool}"


def test_p4_roundtrip_yaml():
    """Dump + load preserves all slots."""
    import tempfile
    from pathlib import Path

    from hermes_skins.core import Skin

    for name in P4_TEMPLATES:
        skin = generate_from_template(name)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / f"{name}.yaml"
            skin.dump(p)
            loaded = Skin.load(p)
        assert loaded.colors.to_dict() == skin.colors.to_dict()
        assert loaded.banner_logo == skin.banner_logo
        assert loaded.branding.to_dict() == skin.branding.to_dict()
