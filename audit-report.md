# Hermes Skins Engine Audit Report

## Bugs & Defects

### 1. `preview` command dumps all templates when no name is provided
* **Evidence:** `src/hermes_skins/cli.py:92-99`
* **Value:** Fixes a confusing UX mismatch where the help text says "shows the active skin" but the command instead floods the terminal with all templates.
* **Scope:** S
* **Risk:** L
* **Implementation Sketch:** If `name is None`, shell out to `hermes config get display.skin` to find the active skin, or read `~/.hermes/config.yaml` directly, and preview only that skin. If unavailable, instruct the user to provide a name.

### 2. Contrast failure for light base colors in `generate_palette`
* **Evidence:** `src/hermes_skins/generators.py:89` (`text = hsl_to_hex(h, s * 0.15, 0.90)`)
* **Value:** Prevents generated skins from being completely illegible (white-on-white) when users input light hex codes.
* **Scope:** M
* **Risk:** L
* **Implementation Sketch:** Introduce a luminance check for the base color. If lightness `l > 0.6`, derive a dark palette (invert the lightness shifts) so `text` becomes dark (`l = 0.15`), and `status_bar_bg` shifts to a lighter shade, essentially adding light terminal support.

### 3. Hardcoded hex colors in template banner art drift from palette
* **Evidence:** `src/hermes_skins/generators.py:188` (`[bold #C98293] ██████╗...`)
* **Value:** Ensures that if a template's base color is adjusted, the ASCII art colors match the new palette instead of remaining hardcoded to the original hex.
* **Scope:** S
* **Risk:** L
* **Implementation Sketch:** Replace hardcoded hex values in `THEMES` banner strings with placeholders like `[{ui_accent}]` or `[{banner_dim}]`. In `generate_from_template`, substitute these placeholders dynamically using the generated palette colors.

### 4. `status_bar_bad` derived from base hue instead of semantic color
* **Evidence:** `src/hermes_skins/generators.py:103` (`status_bad = hsl_to_hex(h, min(1, s + 0.1), min(0.65, l + 0.10))`)
* **Value:** Ensures warnings in the TUI remain recognizable. If the base color is black/gray, `status_bad` becomes a dark gray, eliminating its semantic meaning.
* **Scope:** S
* **Risk:** L
* **Implementation Sketch:** Hardcode `status_bar_bad` to a distinct semantic color like dark orange (`#FF8C00`), similar to how `status_good` and `status_critical` are assigned fixed semantic colors.

### 5. `hex_to_hsl` silently drops alpha channel for 9-char hex inputs
* **Evidence:** `src/hermes_skins/core.py:181` (validation allows 9 chars) & `src/hermes_skins/generators.py:25` (only parses up to index 6).
* **Value:** Prevents silent data loss where users provide valid `#RRGGBBAA` strings, but generation commands silently strip the alpha channel when converting to HSL.
* **Scope:** S
* **Risk:** L
* **Implementation Sketch:** Update `hex_to_hsl` to extract and return the alpha channel if present (`a = int(hex[6:8], 16)/255`). Update `hsl_to_hex` to accept an optional alpha and format as `#RRGGBBAA`.

### 6. CLI `installed_skins` dictionary uses file stem instead of internal skin name
* **Evidence:** `src/hermes_skins/cli.py:55` (`{f.stem: f for f in d.glob("*.yaml")}`)
* **Value:** Prevents CLI mismatches. If a user renames a file (e.g., `my-skin.yaml` -> `test.yaml`), they must use `hermes-skins preview test`, even though the internal `name` is `my-skin`.
* **Scope:** S
* **Risk:** L
* **Implementation Sketch:** When loading `installed_skins()`, open each YAML file, extract the `name` field, and use that as the dictionary key (falling back to file stem if the field is missing).

---

## Feature Opportunities

### 7. Interactive Terminal Skin Picker
* **Value:** Massive UX improvement. Users shouldn't have to repeatedly type `preview <name>`. An interactive menu would let them arrow-key through all templates/installed skins and instantly see the rendered preview.
* **Scope:** M
* **Risk:** L
* **Implementation Sketch:** Add `hermes-skins picker` using `questionary` or a simple loop that captures keystrokes (`tty` raw mode). As the user presses up/down, clear the screen and call `render_preview()`.

### 8. WCAG Contrast Validation
* **Value:** Improves color-theory quality. Ensures generated or hand-edited skins are accessible and legible.
* **Scope:** M
* **Risk:** L
* **Implementation Sketch:** Implement a WCAG contrast ratio calculator in `core.py`. Update `Skin.validate()` to check ratios between foreground/background pairs (e.g., `status_bar_bg` vs `status_bar_text`, `prompt` vs terminal background) and emit warnings if the ratio falls below 4.5:1.

### 9. Skin Diff Tool
* **Value:** High-value UX win for users customizing skins. Lets them easily see what they've tweaked compared to a base template.
* **Scope:** S
* **Risk:** L
* **Implementation Sketch:** Add `hermes-skins diff <skin_A> <skin_B>`. Load both into dictionaries, compute the delta, and print a color-coded output (using `rich` or standard ANSI) highlighting only the changed slots.

### 10. Robust Configuration Fallback for `switch`
* **Value:** Prevents the `switch` command from completely failing if the `hermes` CLI isn't in the system PATH, bridging ecosystem integration.
* **Scope:** S
* **Risk:** M
* **Implementation Sketch:** If `shutil.which("hermes")` is None in `_do_switch`, fallback to locating `~/.hermes/config.yaml`, safely loading the YAML, modifying `display.skin`, and dumping it back directly.

### 11. Real-time Live Preview (`watch` command)
* **Value:** Huge quality-of-life win for skin developers tweaking a YAML file in their editor.
* **Scope:** M
* **Risk:** L
* **Implementation Sketch:** Add `hermes-skins watch <file.yaml>`. Use a basic polling loop on file modification time (or add `watchdog` as a dependency). When changed, clear the terminal and run `render_preview()`.

### 12. Automated CI/CD and Test Suite
* **Value:** Resolves the complete lack of tests, ensuring robustness against future color engine regressions.
* **Scope:** M
* **Risk:** L
* **Implementation Sketch:** Create a `tests/` directory with `pytest`. Test `generate_palette` logic, YAML round-trip fidelity, and CLI commands using `typer.testing.CliRunner`. Add a `.github/workflows/ci.yml` for automated testing on PRs.

### 13. Dynamic Tool Emoji Assignment for Generators
* **Value:** `generate_custom` and `generate_random` currently rely on `DEFAULT_TOOL_EMOJIS` which is static and boring. Making them dynamic adds flavor.
* **Scope:** S
* **Risk:** L
* **Implementation Sketch:** In `generate_random`, randomly pick symbols from the selected `faces` pool and assign them to various tool emojis instead of hardcoding the defaults.

### 14. Skin Sharing / Fetch Command
* **Value:** Ecosystem growth. Allows users to easily share and download community skins without manually curling files into `~/.hermes/skins/`.
* **Scope:** M
* **Risk:** M
* **Implementation Sketch:** Add `hermes-skins fetch <url>`. Safely fetch the YAML via HTTP, load it to validate schema constraints, and then save it to the installed skins directory.

