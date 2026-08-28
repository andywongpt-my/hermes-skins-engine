"""
Preview — render a skin to the terminal so you can see what it looks like
without starting a full Hermes session.
"""

from __future__ import annotations

import os
import re
import shutil

from .core import Skin

# ANSI 24-bit truecolor helpers

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
    r, g, b = rgb
    return f"\033[38;2;{r};{g};{b}m{text}\033[0m"


def _bold_fg(hex_color: str, text: str) -> str:
    rgb = _rgb(hex_color)
    if rgb is None:
        return text
    r, g, b = rgb
    return f"\033[1;38;2;{r};{g};{b}m{text}\033[0m"


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
