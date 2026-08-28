"""Core schema tests — Skin/Colors/Spinner/Branding, YAML round-trip, validation.

Regression anchors for audit bugs B2 (hex validation), B9 (nameless YAML),
and the schema-compat contract (29 color slots).
"""
from __future__ import annotations

import textwrap

import pytest
import yaml

from hermes_skins.core import Colors, Skin, Spinner, Branding


# ---------------------------------------------------------------------------
# Schema shape
# ---------------------------------------------------------------------------

def test_colors_has_29_slots():
    assert len(Colors().to_dict()) == 29


def test_colors_slot_groups_present():
    d = Colors().to_dict()
    for prefix, minimum in (("banner_", 5), ("status_bar_", 8),
                            ("completion_menu_", 4)):
        assert sum(1 for k in d if k.startswith(prefix)) >= minimum
    for slot in ("voice_status_bg", "selection_bg"):
        assert slot in d


def test_defaults_are_valid_hex():
    # validate() lives on Skin; make sure default Colors pass through it
    skin = Skin(name="defaults")
    assert skin.validate() == []


# ---------------------------------------------------------------------------
# from_dict behavior
# ---------------------------------------------------------------------------

def test_from_dict_ignores_unknown_keys():
    c = Colors.from_dict({"banner_title": "#FF0000", "not_a_slot": "#00FF00"})
    assert c.banner_title == "#FF0000"
    assert not hasattr(c, "not_a_slot")


def test_skin_from_dict_defaults():
    s = Skin.from_dict({"name": "mini"})
    assert s.name == "mini"
    assert s.colors == Colors()
    assert s.spinner == Spinner()
    assert s.branding == Branding()
    assert s.banner_logo is None and s.banner_hero is None


# ---------------------------------------------------------------------------
# YAML round-trip
# ---------------------------------------------------------------------------

def test_round_trip_full_skin(tmp_path):
    skin = Skin.from_dict({
        "name": "roundtrip",
        "description": "desc",
        "colors": {"banner_title": "#123456", "status_bar_bg": "#0A0A0A"},
        "spinner": {"waiting_faces": ["(a)", "(b)"]},
        "branding": {"agent_name": "RT Agent"},
        "tool_emojis": {"terminal": "▸"},
        "banner_logo": "[bold #C98293]LOGO[/]",
        "banner_hero": "[#E8C9D1]HERO[/]",
    })
    p = skin.dump(tmp_path / "sub" / "roundtrip.yaml")
    loaded = Skin.load(p)
    assert loaded == skin


def test_round_trip_preserves_unknown_color_keys_not_required():
    """Unknown color keys are dropped silently (schema-forward compat)."""
    raw = {"name": "x", "colors": {"banner_title": "#111111", "future_slot": "#222222"}}
    skin = Skin.from_dict(raw)
    assert not hasattr(skin.colors, "future_slot")


# ---------------------------------------------------------------------------
# Load errors
# ---------------------------------------------------------------------------

def test_load_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        Skin.load(tmp_path / "nope.yaml")


def test_load_non_mapping_yaml_raises(tmp_path):
    p = tmp_path / "list.yaml"
    p.write_text(yaml.dump(["a", "b"]), encoding="utf-8")
    with pytest.raises(ValueError):
        Skin.load(p)


def test_load_nameless_yaml_yields_unnamed(tmp_path):
    """'::: garbage' is legal YAML parsing to a mapping — Skin.load must not
    crash, but the resulting name='unnamed' must be rejected upstream (B9)."""
    p = tmp_path / "garbage.yaml"
    p.write_text("::: garbage\n", encoding="utf-8")
    skin = Skin.load(p)
    assert skin.name == "unnamed"


# ---------------------------------------------------------------------------
# validate() — B2 regression
# ---------------------------------------------------------------------------

def test_validate_rejects_bad_hex_chars():
    skin = Skin.from_dict({"name": "bad", "colors": {"banner_title": "#ZZZZZZ"}})
    warnings = skin.validate()
    assert any("banner_title" in w for w in warnings)


def test_validate_accepts_8_digit_alpha():
    skin = Skin.from_dict({"name": "alpha", "colors": {"banner_title": "#FF000080"}})
    assert skin.validate() == []


def test_validate_rejects_short_hex():
    skin = Skin.from_dict({"name": "short", "colors": {"banner_title": "#FFF"}})
    assert any("banner_title" in w for w in skin.validate())


def test_validate_rejects_non_string_color():
    skin = Skin.from_dict({"name": "num", "colors": {"banner_title": 123456}})
    assert any("banner_title" in w for w in skin.validate())


def test_validate_empty_name():
    skin = Skin(name="")
    assert "name is empty" in skin.validate()


def test_validate_spinner_needs_two_faces():
    skin = Skin(name="solo", spinner=Spinner(waiting_faces=["(·)"]))
    assert any("waiting_faces" in w for w in skin.validate())


def test_validate_clean_skin_has_no_warnings():
    skin = Skin.from_dict({
        "name": "clean",
        "colors": {k: "#123456" for k in Colors().to_dict()},
        "spinner": {"waiting_faces": ["(·)", "(•)"]},
    })
    assert skin.validate() == []
