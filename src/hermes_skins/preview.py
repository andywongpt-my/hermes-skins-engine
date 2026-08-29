"""
Preview — render a skin to the terminal so you can see what it looks like
without starting a full Hermes session.
"""

from __future__ import annotations

import os
import re
import shutil

from .core import Skin

# ANSI helpers — 24-bit truecolor with automatic degradation to xterm-256,
# ANSI-16, or none, based on TERM/COLORTERM detection (F10, v0.4.0).

# NO_COLOR support (https://no-color.org): when the NO_COLOR env var is set
# (to any value, per the spec), the preview renders as plain text. CLICOLOR=0
# disables color too; CLICOLOR_FORCE=1 always wins over NO_COLOR.
_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def _color_enabled() -> bool:
    if os.environ.get("CLICOLOR_FORCE", "") not in ("", "0"):
        return True
    if "NO_COLOR" in os.environ and os.environ["NO_COLOR"] != "":
        return False
    return os.environ.get("CLICOLOR", "1") != "0"


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _rgb(hex_color: str) -> tuple[int, int, int] | None:
    """Parse #RRGGBB to an (r, g, b) tuple. Returns None on malformed input
    (including non-string values from hand-edited YAML) so a broken installed
    skin previews with validation warnings instead of crashing (audit B2)."""
    if not isinstance(hex_color, str):
        return None
    h = hex_color.strip().lstrip("#")
    if len(h) < 6:
        return None
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return None


def _fg(hex_color: str, text: str) -> str:
    rgb = _rgb(hex_color)
    if rgb is None:
        return text
    return _seq(ansi_fg_params(rgb), text)


def _bold_fg(hex_color: str, text: str) -> str:
    rgb = _rgb(hex_color)
    if rgb is None:
        return text
    return _seq(ansi_fg_params(rgb, bold=True), text)


def _bg(hex_color: str, text: str) -> str:
    """Paint text with a background color at the detected depth (F10)."""
    rgb = _rgb(hex_color)
    if rgb is None:
        return text
    return _seq(ansi_bg_params(rgb), text)


# ---------------------------------------------------------------------------
# Terminal color-depth detection + degradation (F10, v0.4.0)
#
# Truecolor previews on a plain `ssh user@box` with TERM=xterm render
# garbage-ish 38;2 sequences. Detect the terminal's color depth and degrade:
#   truecolor → 24-bit RGB (TERM=*truecolor*/24bit, COLORTERM=truecolor/24bit)
#   256       → nearest xterm-256 palette index (TERM=*-256color)
#   16        → nearest classic ANSI-16 color (any other TERM)
#   none      → TERM=dumb (no escape sequences at all)
# Unset TERM (CI, pipes) keeps truecolor — the historical behavior.
# HERMES_SKINS_COLOR_MODE overrides everything (truecolor|256|16|none).
# ---------------------------------------------------------------------------

_COLOR_MODES = ("truecolor", "256", "16", "none")


def terminal_color_mode() -> str:
    """Return the effective color mode: truecolor | 256 | 16 | none."""
    override = os.environ.get("HERMES_SKINS_COLOR_MODE", "").strip().lower()
    if override in _COLOR_MODES:
        return override
    if not _color_enabled():
        return "none"
    colorterm = os.environ.get("COLORTERM", "").lower()
    if colorterm in ("truecolor", "24bit"):
        return "truecolor"
    term = os.environ.get("TERM", "")
    if not term:
        return "truecolor"  # undetectable (CI/pipes): keep historical default
    if "truecolor" in term or "24bit" in term:
        return "truecolor"
    # Known-truecolor terminals whose TERM doesn't advertise it
    if "kitty" in term or "it2." in term or term.startswith("iterm"):
        return "truecolor"
    if term.endswith("-direct") or "-direct" in term:
        return "truecolor"  # "direct" (Colon.semi directColor) = 24-bit capable
    if "256color" in term:
        return "256"
    if term == "dumb":
        return "none"
    return "16"


# Classic ANSI-16 palette (the values xterm-derived terminals actually show)
_ANSI16_RGB: tuple[tuple[int, int, int], ...] = (
    (0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0),
    (0, 0, 128), (128, 0, 128), (0, 128, 128), (192, 192, 192),
    (128, 128, 128), (255, 0, 0), (0, 255, 0), (255, 255, 0),
    (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255),
)


def _cube_level(i: int) -> int:
    return 0 if i == 0 else 55 + 40 * i


def _build_256_palette() -> tuple[tuple[int, int, int], ...]:
    pal: list[tuple[int, int, int]] = list(_ANSI16_RGB)
    for r in range(6):
        for g in range(6):
            for b in range(6):
                pal.append((_cube_level(r), _cube_level(g), _cube_level(b)))
    for i in range(24):
        v = 8 + 10 * i
        pal.append((v, v, v))
    return tuple(pal)


_PAL256 = _build_256_palette()


def _nearest(rgb: tuple[int, int, int], palette: tuple[tuple[int, int, int], ...]) -> tuple[int, int]:
    """Return (index, squared distance) of the closest palette entry to rgb."""
    best_i, best_d = 0, 1 << 30
    for i, (r, g, b) in enumerate(palette):
        d = (rgb[0] - r) ** 2 + (rgb[1] - g) ** 2 + (rgb[2] - b) ** 2
        if d < best_d:
            best_i, best_d = i, d
            if d == 0:
                break
    return best_i, best_d


def rgb_to_256(rgb: tuple[int, int, int]) -> int:
    """Nearest xterm-256 palette index for an RGB tuple.

    Exact RGB matches prefer the 6x6x6 cube region over the ANSI-16 base
    (both contain pure blue/green/red), so #0000FF maps to the cube corner
    (index 21) rather than ANSI blue (12) — consistent with xterm's own
    lookup tables. A strictly closer ANSI-16 base color still wins, e.g.
    #800000 (exact ANSI dark red, index 1) beats its nearest cube entry
    (95 = #870000).
    """
    best_i, best_d = _nearest(rgb, _ANSI16_RGB)
    for i in range(16, len(_PAL256)):
        r, g, b = _PAL256[i]
        d = (rgb[0] - r) ** 2 + (rgb[1] - g) ** 2 + (rgb[2] - b) ** 2
        if d <= best_d:
            best_i, best_d = i, d
            if d == 0:
                break
    return best_i


def rgb_to_16(rgb: tuple[int, int, int]) -> int:
    """Nearest classic ANSI-16 palette index for an RGB tuple."""
    return _nearest(rgb, _ANSI16_RGB)[0]


def ansi_fg_params(rgb: tuple[int, int, int], bold: bool = False) -> str:
    """SGR parameter string for a foreground color at the detected depth.

    truecolor → "1;38;2;R;G;B" / "38;2;R;G;B"
    256       → "1;38;5;N" / "38;5;N"
    16        → "1;9m"-style (30-37 / 90-97) / "30-37"
    none      → "" (caller emits the text unstyled)
    """
    mode = terminal_color_mode()
    if mode == "truecolor":
        return ("1;38;2;%d;%d;%d" if bold else "38;2;%d;%d;%d") % rgb
    if mode == "256":
        return ("1;38;5;%d" if bold else "38;5;%d") % rgb_to_256(rgb)
    if mode == "16":
        idx = rgb_to_16(rgb)
        base = (idx + 90 - 8) if idx >= 8 else idx + 30
        return f"1;{base}" if bold else f"{base}"
    return ""


def ansi_bg_params(rgb: tuple[int, int, int]) -> str:
    """SGR parameter string for a background color at the detected depth."""
    mode = terminal_color_mode()
    if mode == "truecolor":
        return "48;2;%d;%d;%d" % rgb
    if mode == "256":
        return "48;5;%d" % rgb_to_256(rgb)
    if mode == "16":
        idx = rgb_to_16(rgb)
        return str(idx + 100 - 8) if idx >= 8 else str(idx + 40)
    return ""


def _seq(params: str, text: str) -> str:
    return f"\033[{params}m{text}\033[0m" if params else text


# Rich markup → ANSI (audit B7). Template banner art uses Rich-style tags
# like "[bold #C98293]...[/]" / "[#E8C9D1]...[/]" which the ANSI renderer
# used to print as raw text. Convert the two tag forms we actually emit.
_RICH_TAG = re.compile(r"\[(bold\s+)?(#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?)\](.*?)\[/\]", re.DOTALL)


def convert_rich_markup(text: str) -> str:
    """Convert `[bold #HEX]...[/]` and `[#HEX]...[/]` to ANSI truecolor."""

    def _sub(m: re.Match) -> str:
        bold, color, _, body = m.group(1), m.group(2), m.group(3), m.group(4)
        return _bold_fg(color, body) if bold else _fg(color, body)

    return _RICH_TAG.sub(_sub, text)


def _wrap_tool_row(items: list[str], width: int | None = 80) -> list[str]:
    """Wrap tool icon entries so narrow terminals don't overflow (audit B12).

    An explicit width argument always wins (audit 0.2.0 #3): terminal
    auto-detection only applies to the default render path (width=None).
    """
    if width is None:
        try:
            width = max(40, shutil.get_terminal_size((80, 24)).columns - 4)
        except Exception:
            width = 80
    lines: list[str] = []
    current = ""
    for item in items:
        if current and len(current) + 2 + len(item) > width:
            lines.append(current)
            current = item
        else:
            current = f"{current}  {item}" if current else item
    if current:
        lines.append(current)
    return lines


def render_preview(skin: Skin) -> str:
    """Return a terminal-rendered preview string for a skin."""
    c = skin.colors
    color_on = _color_enabled()

    def out(s: str) -> str:
        return s if color_on else strip_ansi(s)

    lines: list[str] = []

    # Banner title
    lines.append("")
    lines.append(_bold_fg(c.banner_title, f"  {skin.branding.agent_name}"))
    lines.append(_fg(c.banner_dim, f"  {skin.description}"))
    lines.append(_fg(c.banner_border, "  " + "─" * 50))
    lines.append("")

    # Color palette swatches
    lines.append(_fg(c.ui_label, "  Color Palette:"))
    for slot, color in c.to_dict().items():
        swatch = _fg(color, "██████")
        label = _fg(c.banner_text, f"  {slot:20s}")
        hexval = _fg(c.banner_dim, color)
        lines.append(f"  {label} {swatch} {hexval}")
    lines.append("")

    # Spinner preview
    lines.append(_fg(c.ui_label, "  Spinner (waiting):"))
    faces = "  ".join(skin.spinner.waiting_faces)
    lines.append(f"  {_fg(c.ui_accent, faces)}")
    lines.append("")
    lines.append(_fg(c.ui_label, "  Thinking verbs:"))
    for verb in skin.spinner.thinking_verbs:
        lines.append(f"  {_fg(c.banner_text, '· ' + verb)}")
    lines.append("")

    # Branding
    lines.append(_fg(c.ui_label, "  Branding:"))
    lines.append(f"  {_fg(c.banner_dim, 'prompt:     ')}{_fg(c.prompt, skin.branding.prompt_symbol + 'type here...')}")
    lines.append(f"  {_fg(c.banner_dim, 'response:   ')}{_fg(c.ui_accent, skin.branding.response_label)}")
    lines.append(f"  {_fg(c.banner_dim, 'welcome:    ')}{_fg(c.banner_text, skin.branding.welcome)}")
    lines.append(f"  {_fg(c.banner_dim, 'goodbye:    ')}{_fg(c.banner_text, skin.branding.goodbye)}")
    lines.append(f"  {_fg(c.banner_dim, 'help:       ')}{_fg(c.banner_text, skin.branding.help_header)}")
    lines.append("")

    # Tool emojis — wrapped to terminal width
    lines.append(_fg(c.ui_label, "  Tool Icons:"))
    tools = [f"{emoji} {name}" for name, emoji in skin.tool_emojis.items()]
    for row in _wrap_tool_row(tools):
        lines.append(f"  {_fg(c.banner_text, row)}")
    lines.append("")

    # Banner art (if present) — Rich markup converted to ANSI
    if skin.banner_logo:
        lines.append(_fg(c.banner_border, "  " + "─" * 50))
        lines.append(_fg(c.ui_label, "  Banner Logo:"))
        lines.append(convert_rich_markup(skin.banner_logo.rstrip("\n")))
        lines.append("")

    if skin.banner_hero:
        lines.append(_fg(c.ui_label, "  Banner Hero:"))
        lines.append(convert_rich_markup(skin.banner_hero.rstrip("\n")))
        lines.append("")

    lines.append(_fg(c.banner_border, "  " + "─" * 50))

    # Validation
    warnings = skin.validate()
    if warnings:
        lines.append(_fg(c.ui_warn, "  ⚠ Validation warnings:"))
        for w in warnings:
            lines.append(f"    {_fg(c.ui_warn, '· ' + w)}")
    else:
        lines.append(_fg(c.ui_ok, "  ✓ Skin valid — no warnings"))

    lines.append("")
    return out("\n".join(lines))
