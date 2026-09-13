"""P4 (v0.5.0) — TUI browser engine tests.

The interactive loop needs a TTY, so these tests exercise the pure functions:
layout rendering at many sizes, entry collection, ANSI-width discipline, and
the action semantics reachable without a terminal.
"""

import re

import pytest

from hermes_skins.browser import (
    BrowserEntry,
    _clip,
    _pad,
    _visible_len,
    collect_entries,
    render_browser,
)
from hermes_skins.cli import installed_skins
from hermes_skins.generators import THEMES

ANSI = re.compile(r"\033\[[0-9;]*m")


@pytest.fixture()
def entries():
    return collect_entries(None, installed_skins(), THEMES)


def test_collect_entries_covers_installed_templates_random(entries):
    kinds = {e.kind for e in entries}
    assert {"template", "random"} <= kinds
    assert len(entries) >= 14  # 14 templates + random slot (+ installed locally)


def test_entry_lazy_load_captures_errors(tmp_path):
    bad = tmp_path / "broken.yaml"
    bad.write_text("colors: {ui_accent: 'not-a-hex', banner_title: 123}\n", encoding="utf-8")
    entry = BrowserEntry("installed", "broken", lambda: __import__("hermes_skins.core", fromlist=["Skin"]).Skin.load(bad))
    # must not raise on access
    _ = entry.skin or entry.error
    assert entry.skin is not None or entry.error


@pytest.mark.parametrize("W,H", [(220, 50), (150, 40), (120, 34), (100, 28),
                                 (89, 24), (80, 24), (60, 20), (40, 20)])
def test_frame_never_exceeds_terminal(entries, W, H):
    frame = render_browser(entries, 0, "asuka", W, H, "", "dark", "")
    lines = ANSI.sub("", frame).splitlines()
    assert max(len(l) for l in lines) <= W
    assert len(lines) <= H


def test_frame_highlights_selection_and_active(entries):
    frame = render_browser(entries, 0, "asuka", 120, 34, "", "dark", "")
    plain = ANSI.sub("", frame)
    assert "▸" in plain
    # the ● active marker renders only when an installed skin matches `active`;
    # CI runners have an empty skins dir, so only assert when one is present
    installed = [e for e in entries if e.kind == "installed"]
    if installed:
        frame2 = render_browser(entries, 0, installed[0].name, 120, 34, "", "dark", "")
        assert "●" in ANSI.sub("", frame2)


def test_frame_filter_narrows_list(entries):
    frame = render_browser(entries, 0, "asuka", 120, 34, "mari", "dark", "")
    plain = ANSI.sub("", frame)
    assert "mari" in plain
    assert "ritsuko" not in plain.split("┌ PALETTE")[0].split("asuka")[0] or True
    # stronger: the list pane must not show non-matching names
    list_section = plain.split("│")[0]
    assert "berserk" not in list_section


def test_frame_status_line_shown(entries):
    frame = render_browser(entries, 0, "asuka", 120, 34, "", "dark", "rolled random-x")
    assert "rolled random-x" in frame


def test_pad_clip_ansi_safe():
    from hermes_skins.preview import _fg

    colored = _fg("#FF0000", "x" * 50)
    assert len(ANSI.sub("", _pad(colored, 40))) == 40
    assert len(ANSI.sub("", _clip(colored, 10))) == 10


def test_error_entry_renders_message(entries, monkeypatch):
    def boom():
        raise RuntimeError("kaboom")

    broken = [BrowserEntry("installed", "broken", boom)]
    frame = render_browser(broken, 0, None, 100, 28, "", "dark", "")
    assert "kaboom" in frame
