# hermes-skins-engine

**Independent skin engine and generator for [Hermes Agent](https://github.com/NousResearch/hermes-agent) CLI** — own schema, own color-theory engine, zero dependencies beyond `pyyaml` + `typer`.

[![CI](https://github.com/andywongpt-my/hermes-skins-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/andywongpt-my/hermes-skins-engine/actions/workflows/ci.yml)
![tests](https://img.shields.io/badge/tests-353%20passing-brightgreen)
![WCAG](https://img.shields.io/badge/WCAG-2.1%20AA%2B-blue)
![python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)

**14 Evangelion theme templates · 9 harmony types · WCAG-AA enforced palettes · full-screen TUI browser · one-file HTML gallery**

---

## Why

Hermes Agent's TUI is skinnable, but hand-tuning 29 interdependent color slots is miserable — change one and three others break. This engine does it with color theory instead: pick one base color, pick a harmony, get a complete 29-slot palette where every text-on-background pair meets WCAG contrast. Or don't pick anything — roll the dice.

## Install

```bash
git clone https://github.com/andywongpt-my/hermes-skins-engine.git
cd hermes-skins-engine
uv pip install -e .        # or: pip install -e .
```

## The flagship: `hermes-skins browse`

```bash
hermes-skins browse
```

Full-screen three-pane browser. Left: every installed skin and template. Center: a live preview that repaints as you move. Right: the full palette with contrast grades. Keys:

| Key | Action |
|-----|--------|
| `↑`/`↓` or `j`/`k` | move |
| `Enter` | install + switch |
| `r` | roll a random skin (seedless) |
| `d` | toggle dark / light mode |
| `/` | filter by name |
| `q` | quit |

Adaptive layout degrades three-pane → two-pane → list-only on narrow terminals. No curses, no Rich — pure termios.

## Everything else

```bash
hermes-skins list                    # installed skins (← active from config.yaml)
hermes-skins templates               # all 14 built-in templates
hermes-skins preview asuka           # single-skin terminal preview
hermes-skins preview --all           # dump every template

hermes-skins generate asuka --switch # generate + install + activate
hermes-skins random "my-seed"        # deterministic random skin
hermes-skins custom mine --color "#FF6D00" --harmony triadic --switch

hermes-skins gallery                 # standalone HTML gallery → hermes-skins-gallery.html
hermes-skins picker                  # lightweight list-based picker (F3)
hermes-skins watch my-skin.yaml      # live preview while editing

hermes-skins validate                # schema + WCAG for everything installed
hermes-skins wcag asuka              # per-slot contrast report
hermes-skins doctor                  # environment health check
hermes-skins diff asuka rei          # 29-slot side-by-side
hermes-skins export asuka -o a.yaml  # shareable YAML
hermes-skins install-url URL         # fetch + validate + install
hermes-skins clone / rename / uninstall
hermes-skins list-json               # scriptable JSON
```

## Built-in Templates — 14

**Pilots (v0.1–0.4)**

| Template | Description |
|----------|-------------|
| `asuka` | EVA-02 Asuka Langley — tactical red, berserker energy |
| `rei` | EVA-00 Rei Ayanami — ethereal blue, quiet depths |
| `shinji` | EVA-01 Shinji Ikari — introspective blue-violet |
| `misato` | Misato Katsuragi — tactical commander, wine and strategy |
| `kaoru` | Kaworu Nagisa — silver serenity, the final messenger |
| `nerv` | NERV HQ — military green, command center, Magi systems |
| `berserk` | EVA-01 Berserk Mode — feral, eyes glowing red |
| `seele` | SEELE Committee — shadowy monolith, Instrumentality |

**Supporting cast & systems (P4, v0.5.0)**

| Template | Description |
|----------|-------------|
| `mari` | Mari Illustrious Makinami — rose-pink, cheerful audacity |
| `ritsuko` | Ritsuko Akagi — amber laboratory light, Magi caretaker |
| `gendo` | Commander Ikari — instrumentality violet, glasses gleam |
| `kaji` | Ryoji Kaji — watermelon-patch green, laid-back truth seeker |
| `lilith` | Lilith — pale first ancestor, silent instrumentality |
| `magi` | The Magi System — Melchior, Balthasar, Casper in conclave |

Every template ships in **dark and light mode**, passes **WCAG AA** on its status bar (most hit AAA), and re-colors its banner art to the generated palette.

See them all without installing: **[assets/gallery.html](assets/gallery.html)** — or run `hermes-skins gallery` and open the file.

## Palette engine

One base color + one harmony → all 29 Hermes-native slots:

```
#CC0033 + complementary
  → accent, dark, dim, bright, text
  → semantic ok/error/warn/bad  (clamped ≥4.5:1 on the status bar)
  → status_bar (8 slots), voice_status, selection, completion_menu (4 slots)
```

Harmonies: `complementary` · `analogous` · `triadic` · `monochrome` · `split_comp` · `tetradic` · `square` · `pastel` · `neon`

The contrast engine (`ensure_contrast`) clamps derived colors to meet targets — random and custom skins are AA-safe by construction, not by luck.

## Architecture

```
src/hermes_skins/
├── core.py        # Skin dataclass, 29-slot schema, YAML round-trip, validation
├── generators.py  # HSL harmony engine, 14 templates, seeded random generator
├── preview.py     # ANSI renderer with truecolor → 256 → 16 → none degradation
├── browser.py     # full-screen three-pane TUI browser (termios, zero deps)
├── gallery.py     # standalone HTML gallery generator
└── cli.py         # Typer CLI — 20+ commands
```

- **Color-depth aware**: truecolor, 256, 16, or NO_COLOR — auto-detected, override with `HERMES_SKINS_COLOR_MODE`
- **353-test pytest suite** + GitHub Actions CI: Linux/macOS/Windows × Python 3.10–3.13
- `hermes-skins doctor --json` / `validate --json` / `list-json` for scripting
- `schema_version` + unknown-key preservation — community skins survive round-trips

## Install for Hermes

```bash
cd hermes-skins-engine
uv pip install -e .
hermes-skins generate asuka --switch   # writes ~/.hermes/skins/ + sets config
hermes-skins browse                    # find your favorite
```

## License

MIT — see [LICENSE](LICENSE).

## Credits

- Evangelion characters © GAINAX / khara — this project is a fan work, not affiliated
- Built for [Hermes Agent](https://github.com/NousResearch/hermes-agent) by Nous Research
