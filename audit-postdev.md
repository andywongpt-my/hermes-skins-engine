# Post-Dev Diff Audit Report: `hermes-skins` (Commit `d81c37e`)

**Audited Commit:** [`d81c37e`](file:///home/meow/tmp/hermes-skins-audit) (*fix: audit P0 batch — correct HSL channel swap, strict validation, readable palettes*)  
**Audited Scope:** [`src/hermes_skins/`](file:///home/meow/tmp/hermes-skins-audit/src/hermes_skins/) (`__init__.py`, `core.py`, `generators.py`, `preview.py`, `cli.py`)

---

## Executive Summary

| Verification Target | Status | Summary |
| :--- | :---: | :--- |
| **(1) `hex_to_hsl` Unpack Fix** | **VERIFIED** | Correctly maps `colorsys.rgb_to_hls` `(h, l, s)` to `(h, s, l)`. Preserves intended saturation and lightness across all 5 harmonies. |
| **(2) `ensure_contrast()` Correctness** | **VERIFIED** | WCAG 2.1 relative luminance math is correct. Dual-direction step search successfully resolves mid-gray and boundary extremes. 65,536 grayscale pairs pass AA with 0 failures. |
| **(3) New Bugs in Commit** | **ISSUES FOUND** | Typer Enum representation leakage in CLI output, unhandled `ValueError` on bad hex in `custom`, path traversal risk in `install`, and non-string type crash in `_rgb()`. |
| **(4) Rich-to-ANSI Converter** | **VERIFIED WITH CAVEATS** | Correctly parses target `[bold #HEX]` and `[#HEX]` single/multi-line tags. Unhandled edge cases for nested tags and standard named Rich tags. |

---

## Detailed Audit Findings

### 1. `hex_to_hsl` Unpack Fix & Color Harmonies

#### Verification Analysis
In [`src/hermes_skins/generators.py:37-38`](file:///home/meow/tmp/hermes-skins-audit/src/hermes_skins/generators.py#L37-L38):
```python
hh, ll, ss = colorsys.rgb_to_hls(r, g, b)  # contract: (h, l, s) — do not reorder
return hh * 360, ss, ll
```
- `colorsys.rgb_to_hls` returns `(h, l, s)` in the `[0, 1]` range.
- Unpacking into `hh, ll, ss` and returning `(hh * 360, ss, ll)` correctly delivers `(h: 0..360, s: 0..1, l: 0..1)`.
- All callers unpacking `h, s, l = hex_to_hsl(...)` now receive true saturation in `s` and true lightness in `l`.

#### Harmony Behavior Verification ([`src/hermes_skins/generators.py:120-143`](file:///home/meow/tmp/hermes-skins-audit/src/hermes_skins/generators.py#L120-L143))
1. **`complementary`** (`accent_h = (h + 180) % 360`, `accent_s = s`, `accent_l = l`):  
   Base `#CC0033` (`asuka`, $H=345^\circ, S=1.0, L=0.4$) now produces `#00CC99` (teal, $H=165^\circ, S=1.0, L=0.4$) with preserved saturation and luminance, fixing the collapse to near-white (`#FFFEFE`).
2. **`analogous`** (`accent_h = (h + 30) % 360`, `accent_s = s`, `accent_l = l`):  
   Base `#4A6FA5` (`shinji`) produces `#524AA4` (blue-violet), preserving the analogous color relationship.
3. **`triadic`** (`accent_h = (h + 120) % 360`, `accent_s = s`, `accent_l = l`):  
   Base `#CC0033` produces `#32CC00` (lime green).
4. **`monochrome`** (`accent_h = h`, `accent_s = s`, `accent_l = min(1, l + 0.15)`):  
   `berserk` (`#FF0000` $\to$ `#FE4C4C`), `seele` (`#1A1A2E` $\to$ `#35355E`), `rei` (`#3B7EC4` $\to$ `#75A4D5`), and `kaoru` (`#C0C0C0` $\to$ `#E6E6E6`) properly scale luminance without washing out or distorting saturation.
5. **`split_comp`** (`accent_h = (h + 150) % 360`, `accent_s = s`, `accent_l = l`):  
   `misato` (`#8B4C6F`) produces `#4F8A4C` (tactical green).

---

### 2. `ensure_contrast()` Correctness & Edge Cases

#### Mathematical & Boundary Verification ([`src/hermes_skins/generators.py:59-103`](file:///home/meow/tmp/hermes-skins-audit/src/hermes_skins/generators.py#L59-L103))
- **WCAG 2.1 Luminance**: [`_relative_luminance`](file:///home/meow/tmp/hermes-skins-audit/src/hermes_skins/generators.py#L59-L63) and [`contrast_ratio`](file:///home/meow/tmp/hermes-skins-audit/src/hermes_skins/generators.py#L66-L70) adhere strictly to the W3C WCAG 2.1 specification: $L = 0.2126R + 0.7152G + 0.0722B$ on linearized sRGB values, and $(L_1 + 0.05) / (L_2 + 0.05)$.
- **Achromatic Foreground ($S = 0$)**: When $S = 0$ (e.g. `#808080`, `#C0C0C0`), modifying `cur_l` in steps of `0.04` transitions through pure grayscale values without hue distortion. Exhaustive testing of all $256 \times 256 = 65,536$ grayscale foreground/background combinations resulted in **0 failures** for both 4.5:1 (text/strong) and 3.0:1 (dim) thresholds.
- **Boundary Clamping ($L \in [0.0, 1.0]$)**: `new_l = max(0.0, min(1.0, cur_l + direction * 0.04))` strictly clamps lightness. The termination condition `if new_l == cur_l: break` terminates after evaluating the extreme boundary values (`0.0` for pure black, `1.0` for pure white).
- **Mid-Gray Backgrounds ($L_{bg} \approx 0.18 - 0.22$)**: Against mid-gray (e.g. `#737373` in `kaoru` status bar, or `#808080`), pure white achieves a maximum ratio of $\sim 3.95:1$. The bidirectional search `for direction in (-1, 1)` allows the search to evaluate the darker direction ($L \to 0$), reaching pure black ($> 5.3:1$), and selects the minimal adjustment `abs(cur_l - l)`.
- **Global Guarantee**: Across any background luminance in $[0.0, 1.0]$, $\max(\text{contrast}(0, L_{bg}), \text{contrast}(1, L_{bg})) \ge \sqrt{21} \approx 4.582:1$. Therefore, for `min_ratio = 4.5` and `min_ratio = 3.0`, a valid candidate is mathematically guaranteed to exist.

---

### 3. Defect Findings & Severity Classification

#### [HIGH] [`src/hermes_skins/cli.py:253`](file:///home/meow/tmp/hermes-skins-audit/src/hermes_skins/cli.py#L253) — Leaked Enum Class Name in `custom` Command Output
- **Description:** In the `custom` CLI command, the confirmation output formats the Enum instance directly:
  ```python
  typer.echo(f"  Base: {color}  Harmony: {harmony}")
  ```
  In Python 3.11, `str(Harmony.complementary)` produces `"Harmony.complementary"`. When the user runs `hermes-skins custom test --color #112233 --harmony complementary`, the CLI prints:
  ```
  ✓ Generated custom skin 'test' → ~/.hermes/skins/test.yaml
    Base: #112233  Harmony: Harmony.complementary
  ```
- **Impact:** CLI UX bug leaking internal Python class name to users.
- **Remediation:** Change to `harmony.value` or `harmony.name`.

---

#### [HIGH] [`src/hermes_skins/cli.py:234-236`](file:///home/meow/tmp/hermes-skins-audit/src/hermes_skins/cli.py#L234-L236) — Incomplete Hex Validation & Unhandled `ValueError` in `custom`
- **Description:** In `cli.py`, `custom()` only checks:
  ```python
  if not color.startswith("#") or len(color) not in (7, 9):
      typer.echo(f"Invalid color: {color!r}. Expected #RRGGBB format.", err=True)
      raise typer.Exit(1)
  ```
  If a user passes non-hex characters (e.g. `--color #ZZZZZZ`), this check passes. `generate_custom` then calls `hex_to_hsl()`, which raises `ValueError: Invalid color '#ZZZZZZ'`. Unlike [`generate()`](file:///home/meow/tmp/hermes-skins-audit/src/hermes_skins/cli.py#L174-L178), `custom()` has no `try...except ValueError` block, causing an unhandled Python traceback.
- **Impact:** Unhandled CLI crash with traceback on invalid user input.
- **Remediation:** Wrap `generate_custom()` in `try...except ValueError` (or validate using the strict regex from `core.py:183`).

---

#### [MEDIUM] [`src/hermes_skins/preview.py:19-25`](file:///home/meow/tmp/hermes-skins-audit/src/hermes_skins/preview.py#L19-L25) — `_rgb()` Crashes on Non-String Color Types
- **Description:** Audit fix B2 intended to allow malformed skins to preview with validation warnings instead of crashing. However, `_rgb(hex_color)` directly invokes `hex_color.strip()`. If a corrupted skin file defines a color slot as an integer, list, or null (e.g., `banner_title: 123456` or `banner_border: null`), `render_preview()` raises an unhandled `AttributeError: 'int' object has no attribute 'strip'` before [`skin.validate()`](file:///home/meow/tmp/hermes-skins-audit/src/hermes_skins/preview.py#L141) is reached.
- **Impact:** Crashes `preview` and `list` commands on skins with non-string YAML values.
- **Remediation:** Add `if not isinstance(hex_color, str): return None` at the start of `_rgb()`.

---

#### [MEDIUM] [`src/hermes_skins/cli.py:296-297`](file:///home/meow/tmp/hermes-skins-audit/src/hermes_skins/cli.py#L296-L297) — Path Traversal in `install` Destination Path
- **Description:** In `install()`:
  ```python
  dst = hermes_skins_dir() / f"{skin.name}.yaml"
  shutil.copy2(src, dst)
  ```
  [`Skin.validate()`](file:///home/meow/tmp/hermes-skins-audit/src/hermes_skins/core.py#L176-L189) only verifies `if not self.name:`. If a skin defines `name: "../../tmp/evil"` or `name: "subdir/custom"`, `dst` resolves outside `~/.hermes/skins/`, allowing arbitrary file write during installation.
- **Impact:** Security risk allowing path traversal when installing untrusted skin YAML files.
- **Remediation:** Sanitize `skin.name` using `Path(skin.name).name` or reject names containing `/`, `\`, or `..`.

---

#### [LOW] [`src/hermes_skins/cli.py:297`](file:///home/meow/tmp/hermes-skins-audit/src/hermes_skins/cli.py#L297) — Unhandled `SameFileError` in `install`
- **Description:** Running `hermes-skins install ~/.hermes/skins/asuka.yaml` causes `shutil.copy2(src, dst)` where `src == dst`, raising an unhandled `shutil.SameFileError` exception.
- **Impact:** CLI crash when attempting to install a file that is already located in the target directory.
- **Remediation:** Check `if src.resolve() != dst.resolve(): shutil.copy2(src, dst)`.

---

#### [LOW] [`src/hermes_skins/generators.py:43-44`](file:///home/meow/tmp/hermes-skins-audit/src/hermes_skins/generators.py#L43-L44) — Float Truncation in `hsl_to_hex`
- **Description:** `hsl_to_hex` formats hex components using `int(r * 255)` rather than `round(r * 255)`. Floating point inaccuracies (e.g. `50.99999999999996`) truncate down to `50` (`0x32`) instead of `51` (`0x33`), causing 1-bit off-by-one roundtrip drifts (e.g., `#CC0033` $\to$ `#CC0032`).
- **Impact:** Minor 1-bit color drift during HSL round-trip conversion.
- **Remediation:** Use `f"#{round(r * 255):02X}{round(g * 255):02X}{round(b * 255):02X}"`.

---

### 4. `preview.py` Rich-to-ANSI Converter Verification

#### Converter Evaluation ([`src/hermes_skins/preview.py:47-57`](file:///home/meow/tmp/hermes-skins-audit/src/hermes_skins/preview.py#L47-L57))
```python
_RICH_TAG = re.compile(r"\[(bold\s+)?(#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?)\](.*?)\[/\]", re.DOTALL)
```
- **Target Tag Coverage:** Correctly converts `[bold #RRGGBB]...[/]` and `[#RRGGBB]...[/]` into 24-bit ANSI truecolor escape sequences (`\033[1;38;2;R;G;Bm` / `\033[38;2;R;G;Bm` and `\033[0m`).
- **Alpha Hex Handling:** Correctly matches 8-digit `#RRGGBBAA` hex tags without regex failure; `_rgb()` parses the first 6 digits and ignores the alpha channel.
- **Multi-line Support:** `re.DOTALL` ensures multiline ASCII banner art blocks convert accurately.

#### Edge Cases Identified:
1. **Nested Tags:** Because the regex uses non-greedy matching `(.*?)\[/\]`, nested tags (e.g. `[bold #111111]Outer [#222222]Inner[/] End[/]`) match up to the first `[/]`, leaving orphaned trailing `[/]` closing tags in output. (Note: Built-in theme banner art is non-nested).
2. **Named & Standard Rich Tags:** Standard Rich tags like `[bold]`, `[dim]`, `[red]`, `[italic]`, or explicit closing tags like `[/bold]` are not matched by `_RICH_TAG` and will leak as raw text if present in custom skins.
3. **Style Reset:** `\033[0m` resets all terminal styles, which strips any surrounding styles outside the matched tag.

---

## Audit Verification Summary

| Check | Verdict |
| :--- | :---: |
| **(1) `hex_to_hsl` unpack contract** | **PASS** |
| **(1) All 5 harmonies verified** | **PASS** |
| **(2) `ensure_contrast()` algorithm** | **PASS** |
| **(2) Achromatic & boundary edge cases** | **PASS** |
| **(2) Mid-gray background resolution** | **PASS** |
| **(3) CLI flag & typer Enum handling** | **FAIL (2 issues: Enum repr leak, unhandled `ValueError`)** |
| **(3) Error handling & security boundaries** | **FAIL (2 issues: Path traversal in `install`, `_rgb` type error)** |
| **(4) Rich-to-ANSI banner conversion** | **PASS (with documented nesting limitation)** |
