"""
Generators — palette engine, theme templates, and random skin generator.

This is the heart of the engine: it creates skins programmatically
using color theory (HSL harmony) and named theme archetypes.
"""

from __future__ import annotations

import colorsys
import hashlib
import random
from dataclasses import replace
from typing import Optional

from .core import Skin, Colors, Spinner, Branding

# ---------------------------------------------------------------------------
# Color utilities
# ---------------------------------------------------------------------------

def hex_to_hsl(hex_color: str) -> tuple[float, float, float]:
    """#RRGGBB → (h, s, l)  h:0-360, s:0-1, l:0-1"""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16) / 255, int(hex_color[2:4], 16) / 255, int(hex_color[4:6], 16) / 255
    h, s, l = colorsys.rgb_to_hls(r, g, b)
    return h * 360, s, l


def hsl_to_hex(h: float, s: float, l: float) -> str:
    """(h, s, l) → #RRGGBB  h:0-360, s:0-1, l:0-1"""
    r, g, b = colorsys.hls_to_rgb(h / 360 % 1, l, s)
    return f"#{int(r * 255):02X}{int(g * 255):02X}{int(b * 255):02X}"


def adjust_lightness(hex_color: str, delta: float) -> str:
    """Shift lightness by delta (-1..1)."""
    h, s, l = hex_to_hsl(hex_color)
    return hsl_to_hex(h, s, max(0, min(1, l + delta)))


def adjust_saturation(hex_color: str, factor: float) -> str:
    """Multiply saturation by factor."""
    h, s, l = hex_to_hsl(hex_color)
    return hsl_to_hex(h, max(0, min(1, s * factor)), l)


# ---------------------------------------------------------------------------
# Palette Engine — generates a full 15-color palette from a seed color
# ---------------------------------------------------------------------------

def generate_palette(base_hex: str, harmony: str = "complementary") -> Colors:
    """
    Generate a complete 29-color palette from a single base color.

    Harmonies:
      - complementary:  base + opposite hue
      - analogous:      base ± 30°
      - triadic:        base + 120° + 240°
      - monochrome:     base hue, varying lightness
      - split_comp:     base + (opposite ± 30°)
    """
    h, s, l = hex_to_hsl(base_hex)

    # Derive accent color from harmony
    if harmony == "complementary":
        accent_h = (h + 180) % 360
        accent_s, accent_l = s, l
    elif harmony == "analogous":
        accent_h = (h + 30) % 360
        accent_s, accent_l = s, l
    elif harmony == "triadic":
        accent_h = (h + 120) % 360
        accent_s, accent_l = s, l
    elif harmony == "monochrome":
        accent_h = h
        accent_s = s
        accent_l = min(1, l + 0.15)
    elif harmony == "split_comp":
        accent_h = (h + 150) % 360
        accent_s, accent_l = s, l
    else:
        accent_h, accent_s, accent_l = h, s, l

    accent = hsl_to_hex(accent_h, accent_s, accent_l)
    dark = hsl_to_hex(h, s, max(0.05, l - 0.35))
    dim = hsl_to_hex(h, s * 0.6, max(0.15, l - 0.20))
    bright = hsl_to_hex(h, s, min(0.85, l + 0.25))
    text = hsl_to_hex(h, s * 0.15, 0.90)

    # Semantic colors — keep readable regardless of palette
    ok = "#00AA00"
    error = "#CC0000"
    warn = "#DDAA00"

    # Status bar — dark base surface with accent highlights
    status_bg = hsl_to_hex(h, s * 0.3, max(0.08, l - 0.30))
    status_text = hsl_to_hex(h, s * 0.2, 0.70)
    status_strong = bright
    status_dim = hsl_to_hex(h, s * 0.2, 0.45)
    status_good = ok
    status_warn = warn
    status_bad = hsl_to_hex(h, min(1, s + 0.1), min(0.65, l + 0.10))
    status_critical = error

    # Voice status — same dark surface
    voice_bg = status_bg

    # TUI selection / completion menu
    sel_bg = hsl_to_hex(h, s * 0.4, max(0.12, l - 0.25))
    comp_bg = status_bg
    comp_current = hsl_to_hex(h, s * 0.5, max(0.18, l - 0.18))
    comp_meta = status_bg
    comp_meta_current = comp_current

    return Colors(
        banner_border=dark,
        banner_title=accent,
        banner_accent=bright,
        banner_dim=dim,
        banner_text=text,
        ui_accent=accent,
        ui_label=adjust_lightness(accent, -0.10),
        ui_ok=ok,
        ui_error=error,
        ui_warn=warn,
        prompt=text,
        input_rule=dark,
        response_border=accent,
        session_label=bright,
        session_border=dark,
        # Status bar
        status_bar_bg=status_bg,
        status_bar_text=status_text,
        status_bar_strong=status_strong,
        status_bar_dim=status_dim,
        status_bar_good=status_good,
        status_bar_warn=status_warn,
        status_bar_bad=status_bad,
        status_bar_critical=status_critical,
        # Voice
        voice_status_bg=voice_bg,
        # Selection / completion
        selection_bg=sel_bg,
        completion_menu_bg=comp_bg,
        completion_menu_current_bg=comp_current,
        completion_menu_meta_bg=comp_meta,
        completion_menu_meta_current_bg=comp_meta_current,
    )


# ---------------------------------------------------------------------------
# Theme Templates — named archetypes with personality
# ---------------------------------------------------------------------------

THEMES: dict[str, dict] = {
    "asuka": {
        "base_color": "#CC0033",
        "harmony": "complementary",
        "description": "EVA-02 Asuka Langley — tactical red, berserker energy",
        "agent_name": "EVA-02 Agent",
        "prompt_symbol": "◤ ❯ ",
        "response_label": " ◤ EVA-02 ",
        "waiting_faces": ["(▼)", "(⊿)", "(◤)", "(◢)", "(◭)"],
        "thinking_faces": ["(▼)", "(◤)", "(⊿)", "(◭)", "(◢)"],
        "thinking_verbs": [
            "synchronizing with EVA-02",
            "calibrating A10 nerve clips",
            "activating berserker mode",
            "scanning Angel pattern",
            "charging positron rifle",
            "deploying progressive knife",
            "analyzing AT field",
            "running battle simulation",
        ],
        "wings": [["⟪▼", "▼⟫"], ["⟪⊿", "⊿⟫"], ["⟪◤", "◤⟫"], ["⟪◭", "◭⟫"]],
        "tool_prefix": "┃",
        "tool_emojis": {
            "terminal": "◤", "web_search": "◎", "read_file": "▼",
            "write_file": "◆", "search_files": "⊿", "execute_code": "⌁",
            "browser_navigate": "⊕", "delegate_task": "▣", "mixture_of_agents": "⚗",
            "memory": "◐", "clarify": "?", "cronjob": "↻", "process": "⚙", "todo": "☐",
        },
        "welcome": "AT Field detected. Type /help for tactical orders.",
        "goodbye": "Mission complete. EVA-02 undergoing maintenance...",
        "help_header": "(▼) Tactical Commands",
        "banner_logo": (
            "[bold #C98293] ██████╗ ██████╗  ██████╗  ██████╗ ██╗    ██╗███████╗███████╗███████╗[/]\n"
            "[bold #C98293]██╔═══██╗██╔══██╗██╔════╝ ██╔══██╗██║    ██║██╔════╝██╔════╝██╔════╝[/]\n"
            "[bold #C98293]██║   ██║██████╔╝██║  ███╗██████╔╝██║ █╗ ██║█████╗  ███████╗███████╗[/]\n"
            "[bold #C98293]██║   ██║██╔══██╗██║   ██║██╔══██╗██║███╗██║██╔══╝  ╚════██║╚════██║[/]\n"
            "[#E8C9D1]███████║██║  ██║╚██████╔╝██║  ██║██║  ██║██║╚██████║███████║███████║[/]\n"
            "[#E8C9D1]╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝╚══════╝[/]\n"
            "[#D8BFC5]              EVA-02 · ASUKA LANGLEY · UNIT-02[/]\n"
            "[#D8BFC5]              \"Anta baka?!?\" — 阿尼塔·兰格雷[/]"
        ),
        "banner_hero": (
            "[#C98293]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣠⣴⣶⣿⣿⣿⣶⣦⣄⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#C98293]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣶⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#E8C9D1]⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⡿⠛⠉⠉⠛⢿⣿⣿⣿⣿⣿⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#E8C9D1]⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⠋⠀⠀⠀⠀⠀⠀⠀⠙⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#FFFEFE]⠀⠀⠀⠀⠀⠀⠀⣸⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#FFFEFE]⠀⠀⠀⠀⠀⠀⣸⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢿⣿⣿⣿⡆⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#FECCCC]⠀⠀⠀⠀⠀⢀⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#FECCCC]⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#E8C9D1]⠀⠀⠀⠀⠀⢸⣿⣿⣿⣷⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#E8C9D1]⠀⠀⠀⠀⠀⠘⣿⣿⣿⣿⣿⣦⣀⠀⠀⠀⠀⠀⠀⣀⣴⣿⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#C98293]⠀⠀⠀⠀⠀⠀⠻⣿⣿⣿⣿⣿⣿⣿⣷⣶⣶⣶⣶⣿⣿⣿⣿⣿⣿⠟⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#C98293]⠀⠀⠀⠀⠀⠀⠀⠉⠛⠻⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠟⠛⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]"
        ),
    },
    "rei": {
        "base_color": "#3B7EC4",
        "harmony": "monochrome",
        "description": "EVA-00 Rei Ayanami — ethereal blue, quiet depths",
        "agent_name": "EVA-00 Agent",
        "prompt_symbol": "◇ ❯ ",
        "response_label": " ◇ EVA-00 ",
        "waiting_faces": ["(◇)", "(◯)", "(◌)", "(□)", "(△)"],
        "thinking_faces": ["(◇)", "(◌)", "(◯)", "(△)", "(□)"],
        "thinking_verbs": [
            "synchronizing with EVA-00",
            "feeling the LCL flow",
            "accessing the collective",
            "contemplating existence",
            "reading the pattern",
            "aligning AT field",
            "querying the dummy system",
            "waiting for orders",
        ],
        "wings": [["⟪◇", "◇⟫"], ["⟪◯", "◯⟫"], ["⟪◌", "◌⟫"], ["⟪△", "△⟫"]],
        "tool_prefix": "│",
        "tool_emojis": {
            "terminal": "◇", "web_search": "◯", "read_file": "□",
            "write_file": "◈", "search_files": "△", "execute_code": "⌁",
            "browser_navigate": "◎", "delegate_task": "▣", "mixture_of_agents": "⚗",
            "memory": "◐", "clarify": "?", "cronjob": "↻", "process": "⚙", "todo": "☐",
        },
        "welcome": "Synchronization active. Type /help.",
        "goodbye": "Returning to the LCL...",
        "help_header": "(◇) Available Commands",
        "banner_logo": (
            "[bold #172F47] ██████╗ ██████╗  ██████╗  ██████╗ ██╗    ██╗███████╗███████╗███████╗[/]\n"
            "[bold #172F47]██╔═══██╗██╔══██╗██╔════╝ ██╔══██╗██║    ██║██╔════╝██╔════╝██╔════╝[/]\n"
            "[bold #172F47]██║   ██║██████╔╝██║  ███╗██████╔╝██║ █╗ ██║█████╗  ███████╗███████╗[/]\n"
            "[bold #172F47]██║   ██║██╔══██╗██║   ██║██╔══██╗██║███╗██║██╔══╝  ╚════██║╚════██║[/]\n"
            "[#87AED7]███████║██║  ██║╚██████╔╝██║  ██║██║  ██║██║╚██████║███████║███████║[/]\n"
            "[#87AED7]╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝╚══════╝[/]\n"
            "[#3C556F]              EVA-00 · REI AYANAMI · PROTOTYPE[/]\n"
            "[#3C556F]              \"...I am replaceable.\" — 綾波レイ[/]"
        ),
        "banner_hero": (
            "[#172F47]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣠⣴⣶⣿⣿⣿⣶⣦⣄⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#172F47]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣶⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#ADC8E3]⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⡿⠛⠉⠉⠛⢿⣿⣿⣿⣿⣿⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#ADC8E3]⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⠋⠀⠀⠀⠀⠀⠀⠀⠙⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#E3E5E7]⠀⠀⠀⠀⠀⠀⠀⣸⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#E3E5E7]⠀⠀⠀⠀⠀⠀⣸⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢿⣿⣿⣿⡆⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#87AED7]⠀⠀⠀⠀⠀⢀⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#87AED7]⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#ADC8E3]⠀⠀⠀⠀⠀⢸⣿⣿⣿⣷⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#ADC8E3]⠀⠀⠀⠀⠀⠘⣿⣿⣿⣿⣿⣦⣀⠀⠀⠀⠀⠀⠀⣀⣴⣿⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#172F47]⠀⠀⠀⠀⠀⠀⠻⣿⣿⣿⣿⣿⣿⣿⣷⣶⣶⣶⣶⣿⣿⣿⣿⣿⣿⠟⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#172F47]⠀⠀⠀⠀⠀⠀⠀⠉⠛⠻⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠟⠛⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]"
        ),
    },
    "misato": {
        "base_color": "#8B4C6F",
        "harmony": "split_comp",
        "description": "Misato Katsuragi — tactical commander, wine and strategy",
        "agent_name": "NERV Tactical",
        "prompt_symbol": "► ❯ ",
        "response_label": " NERV ",
        "waiting_faces": ["(►)", "(◀)", "(▲)", "(▼)", "(◆)"],
        "thinking_faces": ["(►)", "(▲)", "(◆)", "(▼)", "(◀)"],
        "thinking_verbs": [
            "plotting tactical approach",
            "reviewing Angel data",
            "coordinating EVA units",
            "calculating attack vector",
            "strategizing deployment",
            "analyzing Magi output",
            "commanding bridge ops",
            "planning sortie route",
        ],
        "wings": [["⟪►", "►⟫"], ["⟪▲", "▲⟫"], ["⟪◆", "◆⟫"]],
        "tool_prefix": "║",
        "tool_emojis": {
            "terminal": "►", "web_search": "◎", "read_file": "▲",
            "write_file": "◆", "search_files": "▼", "execute_code": "⌁",
            "browser_navigate": "⊕", "delegate_task": "▣", "mixture_of_agents": "⚗",
            "memory": "◐", "clarify": "?", "cronjob": "↻", "process": "⚙", "todo": "☐",
        },
        "welcome": "Bridge online. Type /help for orders.",
        "goodbye": "Stand down. Operation complete.",
        "help_header": "(►) Tactical Commands",
        "banner_logo": (
            "[bold #12070D] ███╗   ███╗███████╗██╗  ██╗██╗   ██╗██████╗ ███████╗██╗  ██╗███████╗██████╗[/]\n"
            "[bold #12070D]████╗ ████║██╔════╝██║  ██║██║   ██║██╔══██╗██╔════╝██║  ██║██╔════╝██╔══██╗[/]\n"
            "[#2E6A2B]██╔████╔██║█████╗  ███████║██║   ██║██████╔╝█████╗  ███████║█████╗  ██║  ██║[/]\n"
            "[#2E6A2B]██║╚██╔╝██║██╔══╝  ██╔══██║██║   ██║██╔══██╗██╔══╝  ██╔══██║██╔══╝  ██║  ██║[/]\n"
            "[#BB598F]██║ ╚═╝ ██║███████╗██║  ██║╚██████╔╝██║  ██║███████╗██║  ██║███████╗██████╔╝[/]\n"
            "[#BB598F]╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚══════╝╚═════╝[/]\n"
            "[#2F1C27]              NERV TACTICAL · 葛城ミサト · OPERATIONS CHIEF[/]\n"
            "[#2F1C27]              \"Let's go, Shinji!\" — KATSURAGI[/]"
        ),
        "banner_hero": (
            "[#12070D]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣠⣴⣶⣿⣿⣿⣶⣦⣄⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#12070D]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣶⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#BB598F]⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⡿⠛⠉⠉⠛⢿⣿⣿⣿⣿⣿⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#BB598F]⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⠋⠀⠀⠀⠀⠀⠀⠀⠙⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#E7E3E5]⠀⠀⠀⠀⠀⠀⠀⣸⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#E7E3E5]⠀⠀⠀⠀⠀⠀⣸⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢿⣿⣿⣿⡆⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#2E6A2B]⠀⠀⠀⠀⠀⢀⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#2E6A2B]⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#BB598F]⠀⠀⠀⠀⠀⢸⣿⣿⣿⣷⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#BB598F]⠀⠀⠀⠀⠀⠘⣿⣿⣿⣿⣿⣦⣀⠀⠀⠀⠀⠀⠀⣀⣴⣿⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#12070D]⠀⠀⠀⠀⠀⠀⠻⣿⣿⣿⣿⣿⣿⣿⣷⣶⣶⣶⣶⣿⣿⣿⣿⣿⣿⠟⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#12070D]⠀⠀⠀⠀⠀⠀⠀⠉⠛⠻⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠟⠛⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]"
        ),
    },
    "shinji": {
        "base_color": "#4A6FA5",
        "harmony": "analogous",
        "description": "EVA-01 Shinji Ikari — introspective blue-violet, hedgehog dilemma",
        "agent_name": "EVA-01 Agent",
        "prompt_symbol": "▶ ❯ ",
        "response_label": " ▶ EVA-01 ",
        "waiting_faces": ["(▶)", "◁)", "(◯)", "(▬)", "(▽)"],
        "thinking_faces": ["(▶)", "(▽)", "(◯)", "(▬)"],
        "thinking_verbs": [
            "synchronizing with EVA-01",
            "running away",
            "getting in the robot",
            "listening to SDAT",
            "processing hedgehog dilemma",
            "feeling the LCL pressure",
            "questioning everything",
            "finding resolve",
        ],
        "wings": [["⟪▶", "▶⟫"], ["⟪◯", "◯⟫"]],
        "tool_prefix": "┊",
        "tool_emojis": {
            "terminal": "▶", "web_search": "◎", "read_file": "◯",
            "write_file": "◆", "search_files": "▽", "execute_code": "⌁",
            "browser_navigate": "⊕", "delegate_task": "▣", "mixture_of_agents": "⚗",
            "memory": "◐", "clarify": "?", "cronjob": "↻", "process": "⚙", "todo": "☐",
        },
        "welcome": "Get in the robot. Type /help.",
        "goodbye": "I mustn't run away. I mustn't run away.",
        "help_header": "(▶) Available Commands",
        "banner_logo": (
            "[bold #060B12] ██████╗ ██████╗  ██████╗  ██████╗ ██╗    ██╗███████╗███████╗███████╗[/]\n"
            "[bold #060B12]██╔═══██╗██╔══██╗██╔════╝ ██╔══██╗██║    ██║██╔════╝██╔════╝██╔════╝[/]\n"
            "[bold #060B12]██║   ██║██████╔╝██║  ███╗██████╔╝██║ █╗ ██║█████╗  ███████╗███████╗[/]\n"
            "[bold #060B12]██║   ██║██╔══██╗██║   ██║██╔══██╗██║███╗██║██╔══╝  ╚════██║╚════██║[/]\n"
            "[#7498CC]███████║██║  ██║╚██████╔╝██║  ██║██║  ██║██║╚██████║███████║███████║[/]\n"
            "[#7498CC]╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝╚══════╝[/]\n"
            "[#3C338E]              EVA-01 · SHINJI IKARI · TEST TYPE[/]\n"
            "[#3C338E]              \"I mustn't run away...\" — 碇シンジ[/]"
        ),
        "banner_hero": (
            "[#060B12]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣠⣴⣶⣿⣿⣿⣶⣦⣄⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#060B12]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣶⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#7498CC]⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⡿⠛⠉⠉⠛⢿⣿⣿⣿⣿⣿⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#7498CC]⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⠋⠀⠀⠀⠀⠀⠀⠀⠙⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#E3E5E7]⠀⠀⠀⠀⠀⠀⠀⣸⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#E3E5E7]⠀⠀⠀⠀⠀⠀⣸⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢿⣿⣿⣿⡆⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#3C338E]⠀⠀⠀⠀⠀⢀⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#3C338E]⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#7498CC]⠀⠀⠀⠀⠀⢸⣿⣿⣿⣷⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#7498CC]⠀⠀⠀⠀⠀⠘⣿⣿⣿⣿⣿⣦⣀⠀⠀⠀⠀⠀⠀⣀⣴⣿⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#060B12]⠀⠀⠀⠀⠀⠀⠻⣿⣿⣿⣿⣿⣿⣿⣷⣶⣶⣶⣶⣿⣿⣿⣿⣿⣿⠟⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#060B12]⠀⠀⠀⠀⠀⠀⠀⠉⠛⠻⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠟⠛⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]"
        ),
    },
    "kaoru": {
        "base_color": "#C0C0C0",
        "harmony": "monochrome",
        "description": "Kaworu Nagisa — silver serenity, the final messenger",
        "agent_name": "Tabris Agent",
        "prompt_symbol": "✦ ❯ ",
        "response_label": " ✦ Tabris ",
        "waiting_faces": ["(✦)", "(✧)", "(◇)", "(◯)", "(✩)"],
        "thinking_faces": ["(✦)", "(✧)", "(◇)", "(✩)"],
        "thinking_verbs": [
            "playing the piano of fate",
            "offering salvation",
            "reading the Book of Life",
            "smiling at the inevitable",
            "walking the path of Lilim",
            "singing the Ode to Joy",
            "contemplating the final decision",
            "loving unconditionally",
        ],
        "wings": [["⟪✦", "✦⟫"], ["⟪✧", "✧⟫"], ["⟪◇", "◇⟫"]],
        "tool_prefix": "┊",
        "tool_emojis": {
            "terminal": "✦", "web_search": "✧", "read_file": "◇",
            "write_file": "◆", "search_files": "✩", "execute_code": "⌁",
            "browser_navigate": "◎", "delegate_task": "▣", "mixture_of_agents": "⚗",
            "memory": "◐", "clarify": "?", "cronjob": "↻", "process": "⚙", "todo": "☐",
        },
        "welcome": "You are worthy of my grace. Type /help.",
        "goodbye": "I will love you for all eternity. Goodbye.",
        "help_header": "(✦) Available Commands",
        "banner_logo": (
            "[bold #160303] ██████╗ ██████╗  ██████╗  ██████╗ ██╗    ██╗███████╗███████╗███████╗[/]\n"
            "[bold #160303]██╔═══██╗██╔══██╗██╔════╝ ██╔══██╗██║    ██║██╔════╝██╔════╝██╔════╝[/]\n"
            "[bold #160303]██║   ██║██████╔╝██║  ███╗██████╔╝██║ █╗ ██║█████╗  ███████╗███████╗[/]\n"
            "[bold #160303]██║   ██║██╔══██╗██║   ██║██╔══██╗██║███╗██║██╔══╝  ╚════██║╚════██║[/]\n"
            "[#6F0F0F]███████║██║  ██║╚██████╔╝██║  ██║██║  ██║██║╚██████║███████║███████║[/]\n"
            "[#6F0F0F]╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝╚══════╝[/]\n"
            "[#430909]              KAWORU NAGISA · ANGEL OF FREE WILL · TABRIS[/]\n"
            "[#430909]              \"I love you.\" — 渚カヲル[/]"
        ),
        "banner_hero": (
            "[#160303]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣠⣴⣶⣿⣿⣿⣶⣦⣄⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#160303]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣶⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#6F0F0F]⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⡿⠛⠉⠉⠛⢿⣿⣿⣿⣿⣿⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#6F0F0F]⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⠋⠀⠀⠀⠀⠀⠀⠀⠙⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#E8E2E2]⠀⠀⠀⠀⠀⠀⠀⣸⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#E8E2E2]⠀⠀⠀⠀⠀⠀⣸⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢿⣿⣿⣿⡆⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#430909]⠀⠀⠀⠀⠀⢀⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#430909]⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#6F0F0F]⠀⠀⠀⠀⠀⢸⣿⣿⣿⣷⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#6F0F0F]⠀⠀⠀⠀⠀⠘⣿⣿⣿⣿⣿⣦⣀⠀⠀⠀⠀⠀⠀⣀⣴⣿⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#160303]⠀⠀⠀⠀⠀⠀⠻⣿⣿⣿⣿⣿⣿⣿⣷⣶⣶⣶⣶⣿⣿⣿⣿⣿⣿⠟⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#160303]⠀⠀⠀⠀⠀⠀⠀⠉⠛⠻⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠟⠛⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]"
        ),
    },
    "nerv": {
        "base_color": "#2B7A2B",
        "harmony": "complementary",
        "description": "NERV HQ — military green, command center, Magi systems",
        "agent_name": "NERV Agent",
        "prompt_symbol": "▣ ❯ ",
        "response_label": " NERV ",
        "waiting_faces": ["(▣)", "(▤)", "(▥)", "(▦)", "(▨)"],
        "thinking_faces": ["(▣)", "(▦)", "(▤)", "(▨)"],
        "thinking_verbs": [
            "running Magi analysis",
            "monitoring GeoFront",
            "tracking Angel approach",
            "coordinating bridge operations",
            "processing Magi vote",
            "authorizing sortie",
            "calculating self-destruct",
            "deploying N² mine",
        ],
        "wings": [["⟪▣", "▣⟫"], ["⟪▦", "▦⟫"]],
        "tool_prefix": "╟",
        "tool_emojis": {
            "terminal": "▣", "web_search": "◎", "read_file": "▤",
            "write_file": "◆", "search_files": "▥", "execute_code": "⌁",
            "browser_navigate": "⊕", "delegate_task": "▣", "mixture_of_agents": "⚗",
            "memory": "◐", "clarify": "?", "cronjob": "↻", "process": "⚙", "todo": "☐",
        },
        "welcome": "NERV HQ online. Magi systems nominal. Type /help.",
        "goodbye": "Bridge operations suspended. Magi entering standby.",
        "help_header": "(▣) NERV Commands",
        "banner_logo": (
            "[bold #162B16] ███╗   ██╗██████╗ ███████╗███████╗███████╗██████╗ ███████╗██╗  ██╗███████╗██████╗[/]\n"
            "[bold #162B16]████╗  ██║██╔══██╗██╔════╝██╔════╝██╔════╝██╔════╝██╔══██╗██╔════╝██║  ██║██╔════╝██╔══██╗[/]\n"
            "[#A3D0A3]██╔██╗ ██║██║  ██║█████╗  ███████║█████╗  █████╗  ██████╔╝█████╗  ███████║██████╔╝[/]\n"
            "[#A3D0A3]██║╚██╗██║██║  ██║██╔══╝  ██╔══██║██╔══╝  ██╔══╝  ██╔══██╗██╔══╝  ██╔══██║██╔══██╗[/]\n"
            "[#A152A1]██║ ╚████║██████╔╝███████╗██║  ██║███████╗███████╗██║  ██║███████╗██║  ██║[/]\n"
            "[#A152A1]╚═╝  ╚═══╝╚═════╝ ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝[/]\n"
            "[#395439]              NERV · GOD'S MESSAGE · SPECIAL AGENCY[/]\n"
            "[#395439]              \"God is in his heaven. All is right with the world.\"[/]"
        ),
        "banner_hero": (
            "[#162B16]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣠⣴⣶⣿⣿⣿⣶⣦⣄⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#162B16]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣶⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#A3D0A3]⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⡿⠛⠉⠉⠛⢿⣿⣿⣿⣿⣿⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#A3D0A3]⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⠋⠀⠀⠀⠀⠀⠀⠀⠙⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#E4E6E4]⠀⠀⠀⠀⠀⠀⠀⣸⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#E4E6E4]⠀⠀⠀⠀⠀⠀⣸⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢿⣿⣿⣿⡆⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#A152A1]⠀⠀⠀⠀⠀⢀⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#A152A1]⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#A3D0A3]⠀⠀⠀⠀⠀⢸⣿⣿⣿⣷⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#A3D0A3]⠀⠀⠀⠀⠀⠘⣿⣿⣿⣿⣿⣦⣀⠀⠀⠀⠀⠀⠀⣀⣴⣿⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#162B16]⠀⠀⠀⠀⠀⠀⠻⣿⣿⣿⣿⣿⣿⣿⣷⣶⣶⣶⣶⣿⣿⣿⣿⣿⣿⠟⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#162B16]⠀⠀⠀⠀⠀⠀⠀⠉⠛⠻⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠟⠛⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]"
        ),
    },
    "berserk": {
        "base_color": "#FF0000",
        "harmony": "monochrome",
        "description": "EVA-01 Berserk Mode — feral, unpredictable, eyes glowing",
        "agent_name": "BERSERK Unit",
        "prompt_symbol": "☠ ❯ ",
        "response_label": " ☠ BERSERK ",
        "waiting_faces": ["(☠)", "(✖)", "(◤)", "(@)", "(▓)"],
        "thinking_faces": ["(☠)", "(@)", "(✖)", "(_)", "(▓)"],
        "thinking_verbs": [
            "BREAKING CONTAINMENT",
            "DEVOURING THE ANGEL",
            "ROARING IN THE LCL",
            "EYES GLOWING RED",
            "RIPPING THE ENTRY PLUG",
            "ZERO SYNCHRO — STILL MOVING",
            "AT FIELD EXPLODING",
            "AWAKENING — S2 ENGINE ONLINE",
        ],
        "wings": [["⟪☠", "☠⟫"], ["⟪✖", "✖⟫"]],
        "tool_prefix": "╳",
        "tool_emojis": {
            "terminal": "☠", "web_search": "✖", "read_file": "▓",
            "write_file": "◆", "search_files": "@", "execute_code": "⌁",
            "browser_navigate": "⊕", "delegate_task": "▣", "mixture_of_agents": "⚗",
            "memory": "◐", "clarify": "?", "cronjob": "↻", "process": "⚙", "todo": "☐",
        },
        "welcome": "■■■■■ BERSERK MODE ■■■■■",
        "goodbye": "...the roaring stops. Silence.",
        "help_header": "(☠) NO COMMANDS — ONLY RAGE",
        "banner_logo": (
            "[bold #D27979]████████╗██████╗ ███████╗███████╗██████╗███████╗██╗  ██╗███████╗██████╗[/]\n"
            "[bold #D27979]╚══██╔══╝██╔══██╗██╔════╝██╔════╝██╔════╝██╔═══██╗██╔════╝██╔══██╗[/]\n"
            "[#EBC5C5]   ██║   ██████╔╝█████╗  ███████║█████╗  ██║  ██║█████╗  ██████╔╝██████╔╝[/]\n"
            "[#EBC5C5]   ██║   ██╔══██╗██╔══╝  ╚════██║██╔══╝  ██║  ██║██╔══╝  ██╔══██╗██╔══██╗[/]\n"
            "[#FFFFFF]   ██║   ██║  ██║███████╗███████║███████╗██████╔╝███████╗██║  ██║██████╔╝[/]\n"
            "[#FFFFFF]   ╚═╝   ╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝╚═════╝ ╚══════╝╚═╝  ╚═╝╚═════╝[/]\n"
            "[#DBBCBC]              ■■ BERSERK UNIT-01 · EYES GLOWING RED ■■[/]\n"
            "[#DBBCBC]              \"▓▓▓ AAAAAGH ▓▓▓\" — THE BEAST AWAKENS[/]"
        ),
        "banner_hero": (
            "[#D27979]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣠⣴⣶⣿⣿⣿⣶⣦⣄⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#D27979]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣶⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#FFFFFF]⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⡿⠛⠉⠉⠛⢿⣿⣿⣿⣿⣿⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#FFFFFF]⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⠋⠀⠀⠀⠀⠀⠀⠀⠙⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[bold #CC0000]⠀⠀⠀⠀⠀⠀⠀⣸⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[bold #CC0000]⠀⠀⠀⠀⠀⠀⣸⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢿⣿⣿⣿⡆⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#EBC5C5]⠀⠀⠀⠀⠀⢀⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#EBC5C5]⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#FFFFFF]⠀⠀⠀⠀⠀⢸⣿⣿⣿⣷⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#FFFFFF]⠀⠀⠀⠀⠀⠘⣿⣿⣿⣿⣿⣦⣀⠀⠀⠀⠀⠀⠀⣀⣴⣿⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#D27979]⠀⠀⠀⠀⠀⠀⠻⣿⣿⣿⣿⣿⣿⣿⣷⣶⣶⣶⣶⣿⣿⣿⣿⣿⣿⠟⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#D27979]⠀⠀⠀⠀⠀⠀⠀⠉⠛⠻⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠟⠛⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]"
        ),
    },
    "seele": {
        "base_color": "#1a1a2e",
        "harmony": "monochrome",
        "description": "SEELE — the committee, shadowy monolith, Instrumentality",
        "agent_name": "SEELE Committee",
        "prompt_symbol": "❒ ❯ ",
        "response_label": " SEELE ",
        "waiting_faces:": ["(❒)", "(❑)", "(❏)", "(■)", "(□)"],
        "thinking_faces": ["(❒)", "(■)", "(❑)", "(□)"],
        "thinking_verbs": [
            "convening the committee",
            "reviewing the scenario",
            "orchestrating Instrumentality",
            "consulting the Dead Sea Scrolls",
            "allocating the budget",
            "directing the scenario",
            "manipulating the Marduk Institute",
            "planning the Third Impact",
        ],
        "wings": [["⟪❒", "❒⟫"], ["⟪■", "■⟫"]],
        "tool_prefix": "╠",
        "tool_emojis": {
            "terminal": "❒", "web_search": "◎", "read_file": "❑",
            "write_file": "❏", "search_files": "■", "execute_code": "⌁",
            "browser_navigate": "⊕", "delegate_task": "▣", "mixture_of_agents": "⚗",
            "memory": "◐", "clarify": "?", "cronjob": "↻", "process": "⚙", "todo": "☐",
        },
        "welcome": "The committee is in session. Type /help.",
        "goodbye": "The scenario proceeds as planned.",
        "help_header": "(❒) Committee Directives",
        "banner_logo": (
            "[bold #0A0A0E]███████╗██████╗ ███████╗███╗   ███╗███████╗███████╗██╗  ██╗███████╗██████╗[/]\n"
            "[bold #0A0A0E]██╔════╝██╔══██╗██╔════╝████╗ ████║██╔════╝██╔════╝██║  ██║██╔════╝██╔══██╗[/]\n"
            "[#5D5D7C]███████╗██████╔╝█████╗  ██╔████╔██║█████╗  ███████║██████╔╝█████╗  ██║  ██║[/]\n"
            "[#5D5D7C]╚════██║██╔══██╗██╔══╝  ██║╚██╔╝██║██╔══╝  ╚════██║██╔══██╗██╔══╝  ██║  ██║[/]\n"
            "[#757597]███████║██║  ██║███████╗██║ ╚═╝ ██║███████╗███████║██║  ██║███████╗██████╔╝[/]\n"
            "[#757597]╚══════╝╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝╚══════╝╚═════╝[/]\n"
            "[#232329]              SEELE · ゼーレ · THE COMMITTEE · INSTRUMENTALITY[/]\n"
            "[#232329]              \"All is according to the scenario.\" — KEEL LORENZ[/]"
        ),
        "banner_hero": (
            "[#0A0A0E]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣠⣴⣶⣿⣿⣿⣶⣦⣄⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#0A0A0E]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣶⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#757597]⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⡿⠛⠉⠉⠛⢿⣿⣿⣿⣿⣿⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#757597]⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⠋⠀⠀⠀⠀⠀⠀⠀⠙⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#E4E4E6]⠀⠀⠀⠀⠀⠀⠀⣸⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#E4E4E6]⠀⠀⠀⠀⠀⠀⣸⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢿⣿⣿⣿⡆⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#5D5D7C]⠀⠀⠀⠀⠀⢀⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#5D5D7C]⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#757597]⠀⠀⠀⠀⠀⢸⣿⣿⣿⣷⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#757597]⠀⠀⠀⠀⠀⠘⣿⣿⣿⣿⣿⣦⣀⠀⠀⠀⠀⠀⠀⣀⣴⣿⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#0A0A0E]⠀⠀⠀⠀⠀⠀⠻⣿⣿⣿⣿⣿⣿⣿⣷⣶⣶⣶⣶⣿⣿⣿⣿⣿⣿⠟⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]\n"
            "[#0A0A0E]⠀⠀⠀⠀⠀⠀⠀⠉⠛⠻⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠟⠛⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]"
        ),
    },
}

# Default tool emojis for random/custom generation
DEFAULT_TOOL_EMOJIS = {
    "terminal": "▸", "web_search": "◎", "read_file": "▸",
    "write_file": "◆", "search_files": "▸", "execute_code": "⌁",
    "browser_navigate": "⊕", "delegate_task": "▣", "mixture_of_agents": "⚗",
    "memory": "◐", "clarify": "?", "cronjob": "↻", "process": "⚙", "todo": "☐",
}


def generate_from_template(template_name: str) -> Skin:
    """Generate a Skin from a named theme template."""
    if template_name not in THEMES:
        raise ValueError(f"Unknown template: {template_name!r}. Available: {list(THEMES.keys())}")

    t = THEMES[template_name]
    colors = generate_palette(t["base_color"], t.get("harmony", "complementary"))
    spinner = Spinner(
        waiting_faces=t.get("waiting_faces", ["(·)", "(◦)"]),
        thinking_faces=t.get("thinking_faces", t.get("waiting_faces", ["(·)", "(◦)"])),
        thinking_verbs=t.get("thinking_verbs", ["thinking"]),
        wings=t.get("wings", [["⟪·", "·⟫"]]),
    )
    branding = Branding(
        agent_name=t.get("agent_name", "Agent"),
        welcome=t.get("welcome", "Ready."),
        goodbye=t.get("goodbye", "Goodbye."),
        response_label=t.get("response_label", " Agent "),
        prompt_symbol=t.get("prompt_symbol", "❯ "),
        help_header=t.get("help_header", "Available Commands"),
    )

    return Skin(
        name=template_name,
        description=t.get("description", ""),
        colors=colors,
        spinner=spinner,
        branding=branding,
        tool_prefix=t.get("tool_prefix", "┊"),
        tool_emojis=t.get("tool_emojis", dict(DEFAULT_TOOL_EMOJIS)),
        banner_logo=t.get("banner_logo"),
        banner_hero=t.get("banner_hero"),
    )


# ---------------------------------------------------------------------------
# Random skin generator
# ---------------------------------------------------------------------------

RANDOM_PALETTE_NAMES = [
    "Crimson Lotus", "Azure Drift", "Neon Phantom", "Golden Mirage",
    "Violet Storm", "Emerald Echo", "Coral Sunset", "Steel Tempest",
    "Obsidian Flame", "Ivory Shadow", "Jade Mist", "Amber Veil",
    "Slate River", "Indigo Pulse", "Rose Quartz", "Onyx Spark",
]

RANDOM_HARMONIES = ["complementary", "analogous", "triadic", "monochrome", "split_comp"]

RANDOM_FACES = [
    ["(◆)", "(◇)", "(◈)", "(◉)", "(○)"],
    ["(▲)", "(△)", "(▼)", "(▽)", "(◇)"],
    ["(★)", "(☆)", "(✦)", "(✧)", "(✩)"],
    ["(●)", "(◐)", "(◑)", "(◒)", "(◓)"],
    ["(■)", "(□)", "(◆)", "(◇)", "(◈)"],
    ["(◢)", "(◣)", "(◤)", "(◥)", "(◆)"],
    ["(⬢)", "(⬡)", "(⬣)", "(△)", "(▽)"],
]

RANDOM_VERBS = [
    ["processing", "analyzing", "computing", "rendering", "scanning"],
    ["weaving patterns", "tracing signals", "mapping routes", "decoding layers", "aligning vectors"],
    ["charging circuits", "calibrating sensors", "running diagnostics", "syncing data", "compiling results"],
    ["reading the stream", "folding space", "threading logic", "bending light", "shaping form"],
    ["synchronizing", "orchestrating", "harmonizing", "calibrating", "optimizing"],
]

RANDOM_PROMPT_SYMBOLS = ["▸ ❯ ", "◆ ❯ ", "▲ ❯ ", "✦ ❯ ", "► ❯ ", "◣ ❯ ", "⬢ ❯ ", "● ❯ "]

RANDOM_TOOL_PREFIXES = ["┊", "┃", "│", "║", "╟", "╠", "╳", "┆"]


def generate_random(seed: Optional[str | int] = None) -> Skin:
    """
    Generate a completely random skin.

    If seed is provided, generation is deterministic (same seed → same skin).
    """
    if seed is not None:
        if isinstance(seed, str):
            seed_hash = int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16)
        else:
            seed_hash = seed
        rng = random.Random(seed_hash)
    else:
        rng = random.Random()

    # Pick a random base hue and saturation
    hue = rng.uniform(0, 360)
    sat = rng.uniform(0.45, 0.85)
    light = rng.uniform(0.35, 0.55)
    base_hex = hsl_to_hex(hue, sat, light)

    harmony = rng.choice(RANDOM_HARMONIES)
    colors = generate_palette(base_hex, harmony)

    name = rng.choice(RANDOM_PALETTE_NAMES).replace(" ", "-").lower()
    faces = rng.choice(RANDOM_FACES)
    verbs = rng.choice(RANDOM_VERBS)
    prompt_sym = rng.choice(RANDOM_PROMPT_SYMBOLS)
    prefix = rng.choice(RANDOM_TOOL_PREFIXES)

    # Wings derived from faces
    wings = [[f"⟪{f.strip('()')}", f"{f.strip('()')}⟫"] for f in faces[:3]]

    spinner = Spinner(
        waiting_faces=faces,
        thinking_faces=faces,
        thinking_verbs=verbs,
        wings=wings,
    )
    branding = Branding(
        agent_name=f"{name.title()} Agent",
        welcome=f"Ready. Type /help for commands.",
        goodbye="Session closed.",
        response_label=f" {faces[0]} {name.title()} ",
        prompt_symbol=prompt_sym,
        help_header=f"{faces[0]} Available Commands",
    )

    return Skin(
        name=f"random-{name}",
        description=f"Randomly generated skin — {harmony} harmony, base {base_hex}",
        colors=colors,
        spinner=spinner,
        branding=branding,
        tool_prefix=prefix,
        tool_emojis=dict(DEFAULT_TOOL_EMOJIS),
    )


def generate_custom(
    name: str,
    base_color: str,
    harmony: str = "complementary",
    agent_name: Optional[str] = None,
    prompt_symbol: Optional[str] = None,
    description: str = "",
) -> Skin:
    """Generate a skin from a custom base color and harmony."""
    colors = generate_palette(base_color, harmony)

    return Skin(
        name=name,
        description=description or f"Custom skin — {harmony} harmony from {base_color}",
        colors=colors,
        spinner=Spinner(
            waiting_faces=["(◆)", "(◇)", "(◈)", "(◉)", "(○)"],
            thinking_faces=["(◆)", "(◉)", "(◇)", "(◈)"],
            thinking_verbs=["processing", "analyzing", "computing", "rendering", "scanning"],
            wings=[["⟪◆", "◆⟫"], ["⟪◇", "◇⟫"], ["⟪◈", "◈⟫"]],
        ),
        branding=Branding(
            agent_name=agent_name or f"{name.title()} Agent",
            welcome="Ready. Type /help for commands.",
            goodbye="Session closed.",
            response_label=f" ◆ {name.title()} ",
            prompt_symbol=prompt_symbol or "◆ ❯ ",
            help_header="(◆) Available Commands",
        ),
        tool_prefix="┊",
        tool_emojis=dict(DEFAULT_TOOL_EMOJIS),
    )


# ---------------------------------------------------------------------------
# List available templates
# ---------------------------------------------------------------------------

def list_templates() -> dict[str, str]:
    """Return {template_name: description}."""
    return {name: t.get("description", "") for name, t in THEMES.items()}