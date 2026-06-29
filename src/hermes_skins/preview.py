"""
Preview — render a skin to the terminal so you can see what it looks like
without starting a full Hermes session.
"""

from __future__ import annotations

from .core import Skin

# ANSI 24-bit truecolor helpers
def _fg(hex_color: str, text: str) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"\033[38;2;{r};{g};{b}m{text}\033[0m"

def _bold_fg(hex_color: str, text: str) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"\033[1;38;2;{r};{g};{b}m{text}\033[0m"


def render_preview(skin: Skin) -> str:
    """Return a terminal-rendered preview string for a skin."""
    c = skin.colors
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

    # Tool emojis
    lines.append(_fg(c.ui_label, "  Tool Icons:"))
    tools_row = "  ".join(f"{emoji} {name}" for name, emoji in skin.tool_emojis.items())
    lines.append(f"  {_fg(c.banner_text, tools_row)}")
    lines.append("")

    # Banner art (if present)
    if skin.banner_logo:
        lines.append(_fg(c.banner_border, "  " + "─" * 50))
        lines.append(_fg(c.ui_label, "  Banner Logo:"))
        lines.append(skin.banner_logo.rstrip("\n"))
        lines.append("")

    if skin.banner_hero:
        lines.append(_fg(c.ui_label, "  Banner Hero:"))
        lines.append(skin.banner_hero.rstrip("\n"))
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
    return "\n".join(lines)