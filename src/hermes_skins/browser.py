"""
TUI browser — full-screen interactive skin browser (P4, v0.5.0).

Three-pane layout: skin list (left), live preview (center), palette + details
(right). Pure termios raw-mode input, zero extra dependencies. Arrow/vim keys
navigate, Enter installs + switches, r generates a random skin, d toggles
dark/light, / filters, q quits.
"""

from __future__ import annotations

import os
import re
import shutil
import sys

from .core import Skin

# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def _strip(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _visible_len(text: str) -> int:
    return len(_strip(text))


def _pad(text: str, width: int) -> str:
    """Pad a possibly-colored string to a visible width."""
    visible = _visible_len(text)
    if visible >= width:
        # truncate on cell boundary (ANSI-aware)
        out, w = [], 0
        i = 0
        while i < len(text):
            m = _ANSI_RE.match(text, i)
            if m:
                out.append(m.group(0))
                i = m.end()
            else:
                out.append(text[i])
                w += 1
                i += 1
                if w >= width:
                    break
            if w >= width:
                # trailing escape sequences still allowed
                pass
        # flush remaining escape-only tail
        rest = text[i:]
        while True:
            m = _ANSI_RE.match(rest, 0)
            if m:
                out.append(m.group(0))
                rest = rest[m.end():]
            else:
                break
        return "".join(out)
    return text + " " * (width - visible)


def _clip(text: str, width: int) -> str:
    """ANSI-aware truncate to visible width (no padding)."""
    if _visible_len(text) <= width:
        return text
    out, w, i = [], 0, 0
    while i < len(text) and w < width:
        m = _ANSI_RE.match(text, i)
        if m:
            out.append(m.group(0))
            i = m.end()
        else:
            out.append(text[i])
            w += 1
            i += 1
    return "".join(out)


def _box_line(width: int, ch: str = "─") -> str:
    return ch * width


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


class BrowserEntry:
    """One browsable skin: installed, template, or generated random."""

    def __init__(self, kind: str, name: str, loader):
        self.kind = kind          # installed | template | random
        self.name = name
        self._loader = loader
        self._skin: Skin | None = None
        self._error: str | None = None

    @property
    def skin(self) -> Skin | None:
        if self._skin is None and self._error is None:
            try:
                self._skin = self._loader()
            except Exception as e:  # noqa: BLE001 — preview must survive bad files
                self._error = str(e)
        return self._skin

    @property
    def error(self) -> str | None:
        return self._error


def collect_entries(skins_dir, installed_map: dict,
                    themes: dict[str, dict], include_random: bool = True):
    """Build the browser entry list: installed, templates, then a random slot."""
    from .generators import generate_from_template, generate_random

    entries = []
    for name, path in sorted(installed_map.items()):
        entries.append(BrowserEntry("installed", name, lambda p=path: Skin.load(p)))  # type: ignore[arg-type]
    for tname in sorted(themes):
        entries.append(
            BrowserEntry("template", tname, lambda t=tname: generate_from_template(t))
        )
    if include_random:
        entries.append(
            BrowserEntry("random", "(roll a random skin)",
                         lambda: generate_random_slot())
        )
    return entries


def generate_random_slot():
    from .generators import generate_random

    return generate_random()


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _swatch_row(colors: dict[str, str], label_width: int = 18) -> list[str]:
    """Two-column swatch grid of the palette."""
    lines = []
    items = list(colors.items())
    half = (len(items) + 1) // 2
    left, right = items[:half], items[half:]
    for i in range(half):
        kl, vl = left[i]
        line = f"  {kl:<{label_width}} ██ {vl}  "
        if i < len(right):
            kr, vr = right[i]
            line += f"{kr:<{label_width}} ██ {vr}"
        lines.append(line)
    return lines


def _colorize_swatch(text: str, hex_color: str) -> str:
    from .preview import _bg

    return _bg(hex_color, text)


def render_palette_pane(skin: Skin, width: int, height: int) -> list[str]:
    """Right pane: swatch grid + branding + validation."""
    from .preview import _bg, _fg

    c = skin.colors
    lines: list[str] = []
    title = " PALETTE "
    lines.append(_fg(c.ui_label, f"┌{title}{_box_line(max(0, width - len(title) - 2))}┐"))
    inner = width - 2
    d = c.to_dict()
    items = list(d.items())
    rows = []
    half = (len(items) + 1) // 2
    for i in range(half):
        kl, vl = items[i]
        seg = _bg(vl, " " * 4) + f" {kl:<16}"
        if half + i < len(items):
            kr, vr = items[half + i]
            seg += "  " + _bg(vr, " " * 4) + f" {kr:<14}"
        lines.append("│" + _pad(_clip("  " + seg, inner), inner) + "│")
    lines.append("│" + " " * inner + "│")
    lines.append(_fg(c.ui_label, "│" + _pad(" BRANDING", inner) + "│"))
    b = skin.branding
    for label, value in [
        ("prompt", b.prompt_symbol + "input…"),
        ("response", b.response_label),
        ("welcome", b.welcome),
        ("goodbye", b.goodbye),
    ]:
        lines.append("│" + _pad(_clip(f"  {label:<10}{value}", inner), inner) + "│")
    warns = skin.validate()
    lines.append("│" + " " * inner + "│")
    if warns:
        lines.append(_fg(c.ui_warn, "│" + _pad(" ⚠ " + str(len(warns)) + " warning(s)", inner) + "│"))
    else:
        lines.append(_fg(c.ui_ok, "│" + _pad(" ✓ valid · WCAG AA", inner) + "│"))
    # pad to height
    while len(lines) < height:
        lines.append("│" + " " * inner + "│")
    lines.append("└" + _box_line(width - 2) + "┘")
    return lines[:height]


def render_center_pane(entry: BrowserEntry, width: int, height: int) -> list[str]:
    """Center pane: live preview of the selected skin (compact)."""
    from .preview import _fg, render_preview

    skin = entry.skin
    if skin is None:
        msg = f"  (cannot load: {entry.error})"
        return [_pad(_clip(line, width), width) for line in [msg] + [""] * (height - 1)]
    full = render_preview(skin)
    lines = full.splitlines()
    out = []
    for i in range(height):
        if i < len(lines):
            out.append(_pad(_clip(lines[i], width), width))
        else:
            out.append(" " * width)
    return out


def render_browser(entries, sel: int, active: str | None, width: int, height: int,
                   filter_text: str = "", mode_label: str = "dark",
                   status: str = "") -> str:
    """Compose the full three-pane browser frame."""
    from .preview import _bold_fg, _fg

    W = max(width, 40)
    H = max(height, 20)
    list_w = 34
    right_w = max(24, min(46, W - list_w - 24))
    center_w = W - list_w - right_w - 9 if W - list_w - right_w - 9 >= 8 else 0
    if center_w == 0 and W < list_w + right_w + 6:
        # narrow terminal: shrink the list to make both panes fit
        list_w = max(18, W - right_w - 6)
    if W < list_w + right_w + 6:
        right_w = max(12, W - list_w - 6)
    ultra_narrow = W < list_w + right_w + 6  # can't fit two panes

    # ------- header -------
    title = " hermes-skins browser "
    hbar = "═" * (W - 2)
    head = f"╔{hbar}╗"
    head += "\n" + f"║{_bold_fg('#FFFFFF', _pad(title + (f'  filter: {filter_text}' if filter_text else ''), W - 2))}║"
    head += "\n" + f"╠{hbar}╣"

    # ------- visible list (filtered) -------
    shown = [
        (i, e) for i, e in enumerate(entries)
        if not filter_text or filter_text.lower() in e.name.lower()
    ]
    if not shown:
        shown = [(sel, entries[sel])] if entries else []

    # keep selection visible
    sel_pos = None
    for pos, (i, _e) in enumerate(shown):
        if i == sel:
            sel_pos = pos
            break
    if sel_pos is None:
        sel_pos = 0
        sel = shown[0][0]
    viewport_h = H - 6
    scroll = max(0, min(sel_pos - viewport_h // 2, max(0, len(shown) - viewport_h)))
    visible = shown[scroll:scroll + viewport_h]

    # ------- panes -------
    entry = entries[sel]
    left_lines: list[str] = []
    for pos, (i, e) in enumerate(visible):
        cursor = "▸" if i == sel else " "
        icon = {"installed": "▣", "template": "◧", "random": "🎲"}.get(e.kind, "·")
        mark = " ●" if (e.kind == "installed" and e.name == active) else ""
        label = f"{cursor} {icon} {e.name}{mark}"
        if i == sel:
            left_lines.append(_bold_fg("#FFFFFF", _clip(_pad(label, list_w - 1), list_w - 1)))
        else:
            left_lines.append(_fg("#888888", _clip(_pad(label, list_w - 1), list_w - 1)))
    while len(left_lines) < viewport_h:
        left_lines.append(" " * (list_w - 1))

    right_lines = render_palette_pane(entry.skin, right_w, viewport_h) if entry.skin else \
        [_pad(f"(load error: {entry.error})", right_w)] * viewport_h
    if ultra_narrow:
        body = [f"║ {l} ║" for l in left_lines]
    elif center_w >= 8:
        center_lines = render_center_pane(entry, center_w, viewport_h)
        body = [f"║ {l} │ {m} │ {r} ║"
                for l, m, r in zip(left_lines, center_lines, right_lines)]
    else:
        body = [f"║ {l} │ {r} ║" for l, r in zip(left_lines, right_lines)]

    # ------- footer -------
    skin_name = entry.name if entry.kind != "random" else (entry.skin.name if entry.skin else "random")
    fbar = "─" * (W - 2)
    keys = " ↑/↓ move · Enter switch+install · r random · d dark/light · / filter · q quit "
    info = f"{skin_name} [{entry.kind}] · {mode_label}"
    foot = "╟" + _clip(_pad(info, W - 2), W - 2) + "╢"
    foot += "\n╟" + _clip(_pad(keys, W - 2), W - 2) + "╢"
    if status:
        foot += "\n╟" + _clip(_pad(status, W - 2), W - 2) + "╢"
    foot += "\n╚" + fbar + "╝"

    return head + "\n" + "\n".join(body) + "\n" + foot


# ---------------------------------------------------------------------------
# Input handling (termios raw mode)
# ---------------------------------------------------------------------------


def read_key() -> str:
    """Read one keypress. Returns up/down/left/right/enter/quit/rand/mode/filter/other."""
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch2 = sys.stdin.read(1)
            if ch2 == "[":
                ch3 = sys.stdin.read(1)
                if ch3 == "A":
                    return "up"
                if ch3 == "B":
                    return "down"
                if ch3 == "C":
                    return "right"
                if ch3 == "D":
                    return "left"
            return "quit"
        if ch in ("\r", "\n"):
            return "enter"
        if ch in ("q", "Q", "\x03"):
            return "quit"
        if ch in ("k",):
            return "up"
        if ch in ("j",):
            return "down"
        if ch in ("r", "R"):
            return "rand"
        if ch in ("d", "D"):
            return "mode"
        if ch in ("/",):
            return "filter"
        if ch == "\x7f":
            return "backspace"
        if ch.isalnum() or ch in " -_.":
            return "char:" + ch
        return "other"
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def read_line_prefix(prefix: str) -> str:
    """Mini line reader for the filter prompt. Returns the final string."""
    import termios
    import tty

    buf = prefix
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        while True:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch in ("\r", "\n"):
                return buf
            if ch == "\x1b":
                return buf  # Esc accepts
            if ch in ("\x7f", "\b"):
                buf = buf[:-1]
            elif ch == "\x03":
                return ""
            elif ch.isprintable():
                buf += ch
            # redraw happens in the caller loop
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
            sys.stdout.write("\r\x1b[K" + "filter: " + buf)
            sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
