# Post-Dev Audit Report: `hermes-skins-engine` P2 Cycle (`f83bc5c`)

**Audited Commit Range:** [`10e2bdc` → `f83bc5c`](file:///home/meow/hermes-skins-engine) (+1065 / -61 lines)  
**Audited Files:**
- [`src/hermes_skins/cli.py`](file:///home/meow/hermes-skins-engine/src/hermes_skins/cli.py)
- [`src/hermes_skins/core.py`](file:///home/meow/hermes-skins-engine/src/hermes_skins/core.py)
- [`src/hermes_skins/generators.py`](file:///home/meow/hermes-skins-engine/src/hermes_skins/generators.py)
- [`tests/test_p2_features.py`](file:///home/meow/hermes-skins-engine/tests/test_p2_features.py)

---

## Executive Summary

The P2 feature cycle introduces major extensions across color derivation (F2 Light Mode, F11 Extended Harmonies), TUI interaction (F3 Interactive Picker, F4 Live Watch, F5 29-slot Diff), CLI skin lifecycle management (F7 CRUD, F8 URL/Gist Install), banner synchronization (F9 Banner Art Palette Sync), schema evolution (F12 Schema Versioning & Extra Keys), and dynamic aesthetics (F15 Face-Derived Tool Emojis).

Test suite verification (`211 passed`) and bytecode compilation (`py_compile`) passed cleanly. However, rigorous code-level audit revealed **9 defect findings**:
- **2 High severity findings**: The interactive `picker` displays preview screens in monochrome due to an unintended `strip_ansi()` call, and `install-url` ignores its `--force` parameter while `install()` unconditionally overwrites existing skins.
- **1 High severity crash path**: `Skin.from_dict` crashes with `AttributeError` when YAML mappings contain explicit `null` fields.
- **3 Medium severity issues**: Light-mode contrast degradation for `session_label` and extended harmonies (`pastel`/`neon`), a duplicate harmony implementation where `tetradic` is identical to `square`, and filename overwrite vulnerabilities in `rename`/`clone`.
- **2 Low / 1 Nit findings**: Validator crashes on `null` spinner faces, gist regex case sensitivity, and dead test conditionals.

---

## Specific Review Questions

### 1. F2 Light Branch Coherence
**Status: ISSUES IDENTIFIED (Low contrast on `session_label`, `banner_accent`, and extended harmonies)**
- **Surfaces**: `status_bar_bg`, `voice_status_bg`, `selection_bg`, `completion_menu_bg`, and `completion_menu_meta_bg` are consistently light ($L=0.92$, $L=0.88$).
- **Inks**: `banner_border`, `input_rule`, `session_border`, `prompt`, `banner_text` correctly map to dark ink ($L \in [0.10, 0.22]$). `response_border` maps to `accent` ($L \le 0.45$), clamped against light surfaces ($\ge 4.5:1$).
- **`ui_label`**: `adjust_lightness(label_hue, -0.10)` darkens the accent further on classic harmonies ($L \approx 0.35$), providing solid contrast.
- **Defects in Light Mode**:
  1. `bright` in light mode is hardcoded to $L=0.55$ ([`generators.py:211`](file:///home/meow/hermes-skins-engine/src/hermes_skins/generators.py#L211)). For high-luminance hues (yellows/greens, e.g. base `#FFCC00` or `#2B7A2B`), `banner_accent` and `session_label` drop to **$1.45:1$** contrast against the light background.
  2. Extended harmonies (`pastel`, `neon`) calculate `secondary` and `tertiary` before the `if mode == "light"` block, yielding lightness up to $0.85$. These flow into `ui_label` and `session_label` without contrast clamping, dropping contrast to **$1.16:1$ – $1.72:1$** on light surfaces.

### 2. F12 Extra Keys & Shadowing
**Status: VERIFIED (Safe against shadowing; Null-value crash identified)**
- **Shadowing**: `_KNOWN_TOP_KEYS` ([`core.py:119-123`](file:///home/meow/hermes-skins-engine/src/hermes_skins/core.py#L119-L123)) covers all 12 dataclass fields. `extra` only captures unknown keys (`k not in _KNOWN_TOP_KEYS`). In `to_dict()`, known fields are inserted first and `extra` is appended via `d.setdefault(k, v)`, preventing key shadowing or elevation.
- **Duplicate Keys**: Handled by YAML parser (`yaml.safe_load`) prior to dataclass conversion.
- **Defect Found**: `from_dict` uses `d.get("colors", {})`. If a key exists with value `None` (YAML `colors: null`), `d.get(...)` returns `None`, causing `Colors.from_dict(None)` to crash with `AttributeError` on `.items()`.

### 3. F7 Rename Idempotency & Edge Cases
**Status: VERIFIED WITH CAVEAT (Idempotent; Mismatched filename collision risk)**
- **Same-Name Rename**: `rename("asuka", "asuka")` evaluates `dst.resolve() != path.resolve()` as `False` ([`cli.py:549`](file:///home/meow/hermes-skins-engine/src/hermes_skins/cli.py#L549)), preserving the file and updating internal metadata without unlinking.
- **Dual-Track Reconciliation**: Renaming `foo.yaml` (with `name: asuka`) to `asuka` creates `asuka.yaml` and unlinks `foo.yaml`, aligning file stem and internal name.
- **Collision Risk**: `safe_new in installed_skins()` only checks internal names. If `~/.hermes/skins/<safe_new>.yaml` already exists on disk with a *different* internal name, `rename` silently overwrites it.

### 4. F7 Uninstall `--force`
**Status: VERIFIED**
- `uninstall` checks `name == active_skin_name()` ([`cli.py:511`](file:///home/meow/hermes-skins-engine/src/hermes_skins/cli.py#L511)). Without `--force`, it aborts with exit code `1`. With `--force`, it unlinks the file and prints a notification. Unlink permission errors fail noisily as expected.

### 5. F9 Banner Sync Regex & Equal Lightness
**Status: VERIFIED**
- **Whitespace**: `\[(bold\s+)?(#[0-9a-fA-F]{6})\]` captures `bold  ` and `_sub` applies `bold.strip() + ' '`, correctly normalizing multiple spaces.
- **8-digit Hex**: `(#[0-9a-fA-F]{6})\]` strictly matches 6-digit hexes. 8-digit `#RRGGBBAA` hexes in banner art are ignored and left unchanged.
- **Equal Lightness**: Python's `sorted()` is stable; colors with identical lightness preserve document appearance order. The first mapped is `banner_border` and the last is `banner_text`. No crashes or exceptions occur.

### 6. F5 Diff Robustness & Branding Dataclass
**Status: VERIFIED**
- `_channels(hx)` ([`cli.py:611-618`](file:///home/meow/hermes-skins-engine/src/hermes_skins/cli.py#L611-L618)) validates strings, length $\ge 7$, and `#` prefix. For `#RRGGBBAA` (length 9), it parses RGB and ignores alpha. Non-hex characters are caught by `ValueError`.
- `_swatch` returns `"????????"` for unparseable hexes.
- All 6 queried `Branding` attributes (`agent_name`, `prompt_symbol`, `welcome`, `goodbye`, `response_label`, `help_header`) exist on the `Branding` dataclass.

### 7. CLI Enum Definition Placement
**Status: VERIFIED**
- `Harmony` and `Mode` are standard `(str, Enum)` subclasses placed before `app = typer.Typer(...)` ([`cli.py:42-59`](file:///home/meow/hermes-skins-engine/src/hermes_skins/cli.py#L42-L59)). All type annotations resolve cleanly with zero circular imports or runtime evaluation errors.

### 8. Picker Terminal Restoration & Key Handling
**Status: ISSUES IDENTIFIED (ANSI Stripping Bug; Escape blocking)**
- `_read_key` restores `termios.tcsetattr` in a `finally:` block ([`cli.py:762`](file:///home/meow/hermes-skins-engine/src/hermes_skins/cli.py#L762)). Ctrl-C (`\x03`) returns `"quit"` and exits cleanly.
- **Major Bug**: `_render_picker_screen` calls `strip_ansi(render_preview(skin))` ([`cli.py:727`](file:///home/meow/hermes-skins-engine/src/hermes_skins/cli.py#L727)), which strips all color escape codes, rendering the picker preview completely monochrome.
- **Edge Case**: A standalone `ESC` press blocks `sys.stdin.read(1)` synchronously waiting for a following character because non-blocking I/O or `select` timeout is not used.

### 9. Watch Loop Polling & CPU Usage
**Status: VERIFIED**
- `time.sleep(interval)` with `min=0.1` ensures negligible CPU consumption ($<0.1\%$).
- When a watched file is deleted, `p.stat()` raises `FileNotFoundError`, caught at line 841. The loop writes `(file deleted; waiting…)`, sleeps, and automatically resumes live rendering once the file is recreated.

### 10. Remote URL Install & Non-Interactive Safety
**Status: ISSUES IDENTIFIED (Dead `--force` flag; Unconditional overwrite)**
- In non-interactive contexts, `sys.stdin.isatty()` is `False`, auto-selecting `answer = "y"` ([`cli.py:418`](file:///home/meow/hermes-skins-engine/src/hermes_skins/cli.py#L418)) and preventing stdin hangs.
- **Bug**: `install_url` defines `force: bool = typer.Option(...)` ([`cli.py:688`](file:///home/meow/hermes-skins-engine/src/hermes_skins/cli.py#L688)) but never passes or checks it. `install()` unconditionally overwrites destination files regardless of whether `--force` was passed.

### 11. Test Suite Stability & Flakiness
**Status: VERIFIED (Minor test code cleanup needed)**
- Tests use set subsets, deterministic RNG seeds (SHA-256 hashed), and explicit `encoding="utf-8"`.
- `tests/test_p2_features.py:242` contains a dead conditional expression: `assert sync_banner_art("", None) == "" if False else ...`.
- `test_gist_url_resolves_to_raw` tests a local regex variable rather than `cli._fetch_url`.

### 12. EVA Templates Output vs 0.2.0
**Status: VERIFIED**
- All 8 EVA templates (`asuka`, `rei`, `misato`, `shinji`, `kaoru`, `nerv`, `berserk`, `seele`) use classic harmonies and generate byte-identical 29-slot color palettes in dark mode.
- Banner art is synced via `sync_banner_art()` as designed; template tool emoji sets and branding remain unchanged.

---

## Detailed Findings & Defect Catalog

### [HIGH] Finding 1: Interactive Picker Strips ANSI Truecolor Escape Codes
- **File:Line:** [`src/hermes_skins/cli.py:727`](file:///home/meow/hermes-skins-engine/src/hermes_skins/cli.py#L727)
- **Evidence:**
  ```python
  kind, name, src = entries[sel]
  try:
      skin = Skin.load(src) if kind == "installed" else generate_from_template(name)
      lines.append("")
      lines.append(strip_ansi(render_preview(skin)))
  except Exception as e:
      lines.append(f"  (preview failed: {e})")
  ```
- **Description:** The full-screen interactive `picker` (F3) is intended to let users browse and visually evaluate themes in the terminal. However, line 727 passes `render_preview(skin)` through `strip_ansi()`, stripping all foreground and background ANSI escape sequences. The preview displays in plain monochrome.
- **Fix Suggestion:** Append `render_preview(skin)` directly:
  ```python
  lines.append(render_preview(skin))
  ```

---

### [HIGH] Finding 2: `install-url` Ignores `--force` and `install()` Overwrites Silently
- **File:Line:** [`src/hermes_skins/cli.py:688, 703`](file:///home/meow/hermes-skins-engine/src/hermes_skins/cli.py#L688), [`src/hermes_skins/cli.py:430-435`](file:///home/meow/hermes-skins-engine/src/hermes_skins/cli.py#L430-L435)
- **Evidence:**
  ```python
  @app.command(name="install-url")
  def install_url(
      url: str = typer.Argument(..., help="http(s) URL or gist.github.com link pointing to a skin YAML"),
      force: bool = typer.Option(False, "--force", "-f", help="Overwrite an existing skin with the same name"),
  ):
      ...
      try:
          # Reuse the install command's validation and path handling
          install(file=str(tmp))
      finally:
          tmp.unlink(missing_ok=True)
  ```
  And in `install()`:
  ```python
  dst = hermes_skins_dir() / f"{safe_name}.yaml"
  if dst.exists() and src.resolve() == dst.resolve():
      typer.echo(f"✓ {src.name} is already installed as '{safe_name}.yaml'. Nothing to do.")
      return
  shutil.copy2(src, dst)
  ```
- **Description:** 
  1. `install_url` declares `--force` as a CLI parameter, but `force` is never passed to `install()`.
  2. `install(file: str)` does not accept a `force` argument and unconditionally calls `shutil.copy2(src, dst)`, silently overwriting existing skins with the same name even when `--force` was not supplied.
- **Fix Suggestion:** Add `force: bool = typer.Option(False, ...)` to `install()`. When `dst.exists()` and `not force`, abort with an error (or prompt in interactive mode). Pass `force=force` from `install_url`.

---

### [HIGH] Finding 3: `Skin.from_dict` Crashes on Explicit `null` YAML Fields
- **File:Line:** [`src/hermes_skins/core.py:68, 83, 101, 156-160`](file:///home/meow/hermes-skins-engine/src/hermes_skins/core.py#L68)
- **Evidence:**
  ```python
  colors=Colors.from_dict(d.get("colors", {})),
  spinner=Spinner.from_dict(d.get("spinner", {})),
  branding=Branding.from_dict(d.get("branding", {})),
  ```
  ```python
  @classmethod
  def from_dict(cls, d: dict) -> "Colors":
      known = {f.name for f in cls.__dataclass_fields__.values()}
      return cls(**{k: v for k, v in d.items() if k in known})
  ```
- **Description:** In YAML, a key defined as `colors: null` or `branding: null` loads into Python as `{"colors": None}`. Calling `d.get("colors", {})` returns `None` (because the key exists). `Colors.from_dict(None)` executes `None.items()`, crashing with `AttributeError: 'NoneType' object has no attribute 'items'`.
- **Fix Suggestion:** Use `d.get("colors") or {}` or guard inside `from_dict`:
  ```python
  @classmethod
  def from_dict(cls, d: dict | None) -> "Colors":
      d = d or {}
      known = {f.name for f in cls.__dataclass_fields__.values()}
      return cls(**{k: v for k, v in d.items() if k in known})
  ```

---

### [MEDIUM] Finding 4: Insufficient WCAG Contrast in Light Mode for Labels and Extended Harmonies
- **File:Line:** [`src/hermes_skins/generators.py:176-193, 211, 277-279`](file:///home/meow/hermes-skins-engine/src/hermes_skins/generators.py#L176-L193)
- **Evidence:**
  ```python
  elif harmony == "pastel":
      second_h, third_h = (h + 30) % 360, (h - 30) % 360
      second_s_l, third_s_l = (s * 0.45, min(0.85, max(l, 0.70))), (s * 0.45, min(0.85, max(l, 0.70)))
  elif harmony == "neon":
      second_h, third_h = (h + 120) % 360, (h + 240) % 360
      second_s_l, third_s_l = (1.0, 0.60), (1.0, 0.60)
  ```
- **Description:**
  - In light mode, terminal surfaces are near-white ($L \approx 0.95$). `pastel` and `neon` secondary/tertiary colors are lifted in lightness ($L=0.60-0.85$).
  - For extended harmonies, `label_hue = secondary` and `session_hue = tertiary`. In light mode, these are assigned directly to `ui_label` and `session_label` without being clamped via `ensure_contrast()`.
  - For example, generating `generate_palette("#3B7EC4", "neon", mode="light")` produces `session_label = "#97FF33"` with a contrast ratio of **$1.16:1$** against the surface, making text invisible.
  - Additionally, `bright = hsl_to_hex(h, s * 0.9, 0.55)` in light mode yields **$1.45:1$** contrast for yellow base colors (`#FFCC00`).
- **Fix Suggestion:** In `generate_palette(mode="light")`, apply `ensure_contrast(..., status_bg, 4.5)` to `bright`, `secondary`, and `tertiary` (or clamp lightness to $L \le 0.40$).

---

### [MEDIUM] Finding 5: `tetradic` Harmony is Byte-Identical to `square`
- **File:Line:** [`src/hermes_skins/generators.py:153-157, 176-181`](file:///home/meow/hermes-skins-engine/src/hermes_skins/generators.py#L153-L157)
- **Evidence:**
  ```python
  elif harmony == "tetradic":
      accent_h = (h + 90) % 360
      accent_s, accent_l = s, l
  elif harmony == "square":
      accent_h = (h + 90) % 360
      accent_s, accent_l = s, l
  ```
  ```python
  if harmony == "tetradic":
      second_h, third_h = (h + 180) % 360, (h + 270) % 360
      second_s_l, third_s_l = (s, l), (s, l)
  elif harmony == "square":
      second_h, third_h = (h + 180) % 360, (h + 270) % 360
      second_s_l, third_s_l = (s, l), (s, l)
  ```
- **Description:** In color theory, *square* harmony uses equal 90° intervals ($0^\circ, 90^\circ, 180^\circ, 270^\circ$). *Tetradic* (rectangular) harmony uses two complementary pairs forming a rectangle with unequal angles (e.g. $0^\circ, 60^\circ, 180^\circ, 240^\circ$ or $0^\circ, 30^\circ, 180^\circ, 210^\circ$). The current implementation uses $90^\circ, 180^\circ, 270^\circ$ for both, making `tetradic` a redundant alias of `square`.
- **Fix Suggestion:** Update `tetradic` to rectangular angles:
  ```python
  elif harmony == "tetradic":
      accent_h = (h + 60) % 360
      accent_s, accent_l = s, l
  ```
  And `second_h, third_h = (h + 180) % 360, (h + 240) % 360`.

---

### [MEDIUM] Finding 6: Silent File Overwrite on Existing Disk Filenames in `rename` and `clone`
- **File:Line:** [`src/hermes_skins/cli.py:538, 548-550`](file:///home/meow/hermes-skins-engine/src/hermes_skins/cli.py#L538), [`src/hermes_skins/cli.py:574, 579-580`](file:///home/meow/hermes-skins-engine/src/hermes_skins/cli.py#L574)
- **Evidence:**
  ```python
  if safe_new in installed_skins() and safe_new != old:
      typer.echo(f"✗ A skin named '{safe_new}' already exists.", err=True)
      raise typer.Exit(1)
  ...
  dst = hermes_skins_dir() / f"{safe_new}.yaml"
  skin.dump(dst)
  ```
- **Description:** `installed_skins()` maps internal skin `name` attributes to paths. If a file `~/.hermes/skins/<safe_new>.yaml` exists on disk but has a different internal `name:`, `safe_new in installed_skins()` evaluates to `False`. Executing `hermes-skins rename` or `hermes-skins clone` will silently overwrite the existing file on disk.
- **Fix Suggestion:** Check both the internal name registry and the physical file destination:
  ```python
  if dst.exists() and (dst.resolve() != path.resolve()):
      typer.echo(f"✗ Destination file '{dst.name}' already exists.", err=True)
      raise typer.Exit(1)
  ```

---

### [LOW] Finding 7: `Skin.validate()` Unhandled Exception on Non-Sequence `waiting_faces`
- **File:Line:** [`src/hermes_skins/core.py:229`](file:///home/meow/hermes-skins-engine/src/hermes_skins/core.py#L229)
- **Evidence:**
  ```python
  if len(self.spinner.waiting_faces) < 2:
      warnings.append("spinner.waiting_faces should have at least 2 entries for animation")
  ```
- **Description:** If loaded from a malformed skin where `spinner.waiting_faces` is `null` or a non-sequence, `len(self.spinner.waiting_faces)` raises `TypeError: object of type 'NoneType' has no len()`, aborting validation instead of returning a warning.
- **Fix Suggestion:** Type-guard the check:
  ```python
  if not isinstance(self.spinner.waiting_faces, (list, tuple)) or len(self.spinner.waiting_faces) < 2:
      warnings.append("spinner.waiting_faces should have at least 2 entries for animation")
  ```

---

### [LOW] Finding 8: Gist URL Regex in `_fetch_url` Rejects Uppercase Hex IDs
- **File:Line:** [`src/hermes_skins/cli.py:674`](file:///home/meow/hermes-skins-engine/src/hermes_skins/cli.py#L674)
- **Evidence:**
  ```python
  m = re.match(r"https://gist\.github\.com/([^/]+)/([0-9a-f]+)$", url.rstrip("/"))
  ```
- **Description:** The regex character class `[0-9a-f]+` only matches lowercase hex. URLs with uppercase hex characters (e.g. `https://gist.github.com/user/A1B2C3D4`) fail to match and are not resolved to raw URLs.
- **Fix Suggestion:** Update regex to support alphanumeric/case-insensitive IDs:
  ```python
  m = re.match(r"https://gist\.github\.com/([^/]+)/([0-9a-zA-Z]+)$", url.rstrip("/"))
  ```

---

### [NIT] Finding 9: Dead Conditional Expression in `test_sync_empty_art_passthrough`
- **File:Line:** [`tests/test_p2_features.py:242`](file:///home/meow/hermes-skins-engine/tests/test_p2_features.py#L242)
- **Evidence:**
  ```python
  def test_sync_empty_art_passthrough(self):
      assert sync_banner_art("", None) == "" if False else sync_banner_art("", generate_from_template("rei").colors) == ""
  ```
- **Description:** The expression `... if False else ...` dead-codes the test against `sync_banner_art("", None)`.
- **Fix Suggestion:** Separate into clear assertions:
  ```python
  assert sync_banner_art("", None) == ""
  assert sync_banner_art("", generate_from_template("rei").colors) == ""
  ```

---

## Verdict

**VERDICT: PASS-WITH-FINDINGS**

The P2 feature cycle delivers significant functional expansions with high test coverage and solid core architecture. The color derivation maintains regression compatibility for all 8 EVA templates in dark mode, and the CLI surface integrates cleanly. However, deployment to production should address the High severity findings—specifically re-enabling ANSI color rendering in the `picker`, fixing the unhandled `NoneType` crashes in `Skin.from_dict`/`validate`, wiring the `--force` flag in `install-url`, and clamping light-mode contrast on extended harmony slots.
