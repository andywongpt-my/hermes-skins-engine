# hermes-skins-engine

Independent skin engine and generator for [Hermes Agent](https://github.com/NousResearch/hermes-agent) CLI.

![Hermes Skins Preview](assets/hermes-skins-preview.png)

[![CI](https://github.com/andywongpt-my/hermes-skins-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/andywongpt-my/hermes-skins-engine/actions/workflows/ci.yml)

## Features

- 🎨 **Color-theory palette engine** — generate 29-color palettes from a single base color using HSL harmony (complementary, analogous, triadic, monochrome, split-complementary), with strict hex validation
- 🎭 **8 built-in Evangelion theme templates** — Asuka, Rei, Shinji, Misato, Kaworu, NERV, Berserk, SEELE
- 🎲 **Random skin generator** — deterministic with seed support, or fully random
- 🖥️ **Terminal preview** — colors, spinners, branding, tool icons, and Rich-rendered banner art; `preview` with no argument shows the active skin, `--all` dumps every template; honors `NO_COLOR`
- 📦 **CLI tool** — list (marks the active skin), preview, generate, validate, install, switch, export skins
- ✅ **Schema validation** — catches invalid hex colors (`#ZZZZZZ`, malformed alpha), missing spinner frames; `install` validates before copying
- 🧪 **WCAG 2.1 contrast engine** — derived status-bar and semantic colors are clamped to ≥4.5:1 (dim ≥3.0:1); `hermes-skins validate` re-checks any skin file or your whole installed set
- 🧬 **150-test pytest suite + GitHub Actions CI** across Linux/macOS/Windows, Python 3.10–3.13

## Install

```bash
# From source
git clone https://github.com/andywongpt-my/hermes-skins-engine.git
cd hermes-skins-engine
uv pip install -e .
# or: pip install -e .
```

## Quick Start

```bash
# List built-in templates
hermes-skins templates

# Generate and install Asuka skin
hermes-skins generate asuka --switch

# Preview any template in terminal
hermes-skins preview asuka

# Generate a random skin
hermes-skins random

# Generate a random skin with seed (reproducible)
hermes-skins random "nerv-hq-2026"

# Custom skin from a base color
hermes-skins custom my-theme --color "#FF6D00" --harmony triadic --switch

# List installed skins (← active marks the skin from ~/.hermes/config.yaml)
hermes-skins list

# Validate one file or everything installed (schema + WCAG contrast)
hermes-skins validate ./my-theme.yaml
hermes-skins validate

# Export a skin to a file
hermes-skins export asuka -o ./my-asuka.yaml

# Preview with automatic terminal color-depth detection (truecolor → 256 → 16)
# Override: HERMES_SKINS_COLOR_MODE=truecolor|256|16|none
hermes-skins preview asuka

# Health check: skins dir, active skin, template collisions, terminal color
hermes-skins doctor            # add --json for machine-readable output
hermes-skins doctor --json

# Scriptable JSON output
hermes-skins list-json
hermes-skins validate --json ./my-theme.yaml
hermes-skins wcag --json asuka

# WCAG report: every status-bar color pair graded per role
# hard pairs fail with exit 1 · advisory pairs warn · decorative is informational
hermes-skins wcag asuka
hermes-skins wcag
```

## Built-in Templates

| Template | Description |
|----------|-------------|
| `asuka` | EVA-02 Asuka Langley — tactical red, berserker energy |
| `rei` | EVA-00 Rei Ayanami — ethereal blue, quiet depths |
| `shinji` | EVA-01 Shinji Ikari — introspective blue-violet |
| `misato` | Misato Katsuragi — tactical commander, wine and strategy |
| `kaoru` | Kaworu Nagisa — silver serenity, the final messenger |
| `nerv` | NERV HQ — military green, command center |
| `berserk` | EVA-01 Berserk Mode — feral, eyes glowing red |
| `seele` | SEELE Committee — shadowy monolith, Instrumentality |

## Architecture

```
src/hermes_skins/
├── core.py        # Skin dataclass, schema, YAML load/dump, validation
├── generators.py  # Palette engine (HSL harmony), 8 theme templates, random generator
├── preview.py     # Terminal preview with ANSI 24-bit truecolor
└── cli.py         # Typer-based CLI
```

### Palette Engine

The palette engine takes a single base color and a harmony type, then derives all 29 Hermes-native color slots:

```
base_color (#CC0033) + harmony=complementary
  → accent (opposite hue)
  → dark (lightness - 0.35)
  → dim (saturation × 0.6, lightness - 0.20)
  → bright (lightness + 0.25)
  → text (desaturated, high lightness)
  → semantic: ok/error/warn/bad clamped to ≥4.5:1 on the status-bar bg
  → status_bar (8 slots), voice_status, selection, completion_menu (4 slots)
```

### Schema

A Skin contains:
- **colors** — 29 named hex color slots (`banner_border`, `ui_accent`, `prompt`, `status_bar_*`, `completion_menu_*`, etc.)
- **spinner** — waiting/thinking faces, thinking verbs, wing decorations
- **branding** — agent name, welcome/goodbye text, prompt symbol, response label
- **tool_emojis** — per-tool icon mapping
- **banner_logo / banner_hero** — optional ASCII/braille art

## License

MIT — see [LICENSE](LICENSE)

## Credits

- Evangelion characters © GAINAX / khara
- Built for [Hermes Agent](https://github.com/NousResearch/hermes-agent) by Nous Research