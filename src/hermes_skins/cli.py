"""
CLI entry point — hermes-skins command.

Usage:
  hermes-skins list                 List installed skins
  hermes-skins templates            List built-in theme templates
  hermes-skins preview [NAME]       Preview a skin (installed or template)
  hermes-skins generate TEMPLATE    Generate from a named template
  hermes-skins random [SEED]        Generate a random skin (optionally seeded)
  hermes-skins custom NAME --color #RRGGBB [--harmony complementary]
  hermes-skins install FILE         Install a skin file to ~/.hermes/skins/
  hermes-skins switch NAME          Set display.skin in Hermes config
  hermes-skins export NAME -o FILE  Export a skin to a YAML file
"""

from __future__ import annotations

import sys
import re
import shutil
import time
import urllib.error
import urllib.request
from enum import Enum
from pathlib import Path

import typer
import yaml

from . import __version__
from .core import Skin
from .generators import (
    generate_from_template,
    generate_random,
    generate_custom,
    list_templates,
    contrast_ratio,
    THEMES,
)
from .preview import render_preview, _color_enabled, strip_ansi

class Harmony(str, Enum):
    complementary = "complementary"
    analogous = "analogous"
    triadic = "triadic"
    monochrome = "monochrome"
    split_comp = "split_comp"
    # Extended harmonies (audit F11)
    tetradic = "tetradic"
    square = "square"
    pastel = "pastel"
    neon = "neon"


class Mode(str, Enum):
    dark = "dark"
    light = "light"


app = typer.Typer(
    name="hermes-skins",
    help="Independent skin engine and generator for Hermes Agent.",
    no_args_is_help=True,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def hermes_skins_dir() -> Path:
    """Default Hermes skins directory."""
    return Path.home() / ".hermes" / "skins"


def installed_skins() -> dict[str, Path]:
    """Return {name: path} for all installed skin YAML files.

    Keyed by the skin's internal `name` field (falling back to the file
    stem), so renaming a file doesn't break preview/switch/export lookups
    (audit B9). The key is always sanitized via Path().name — an internal
    name like "../../tmp/escaped" must never become a lookup key (audit
    0.2.0 #11); users find skins by their filename, and install() only
    ever writes sanitized basenames anyway.
    """
    d = hermes_skins_dir()
    if not d.exists():
        return {}
    result: dict[str, Path] = {}
    for f in d.glob("*.yaml"):
        try:
            key = Skin.load(f).name or f.stem
        except Exception:
            key = f.stem
        key = Path(key).name or f.stem
        result[key] = f
    return result


def active_skin_name() -> str | None:
    """Read display.skin from ~/.hermes/config.yaml (audit B6).

    Returns None if the config is missing/unreadable or the key is absent.
    Read-only: this function never writes Hermes config.
    """
    cfg = Path.home() / ".hermes" / "config.yaml"
    try:
        raw = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    node = raw
    for part in ("display", "skin"):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node if isinstance(node, str) and node else None


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.command()
def list():
    """List all installed skins."""
    skins = installed_skins()
    if not skins:
        typer.echo("No skins installed in ~/.hermes/skins/")
        typer.echo("Use 'hermes-skins generate' or 'hermes-skins install' to add one.")
        return
    active = active_skin_name()
    typer.echo(f"Installed skins ({len(skins)}):")
    for name, path in sorted(skins.items()):
        try:
            skin = Skin.load(path)
            desc = skin.description or "(no description)"
        except Exception:
            desc = "(failed to load)"
        marker = " ← active" if name == active else ""
        typer.echo(f"  {name:20s}  {desc}{marker}")
    if active and active not in skins:
        typer.echo(f"\n  note: active skin '{active}' (from config.yaml) is not installed here.")


def _fg_dim(text: str) -> str:
    if not _color_enabled():
        return text
    return f"\033[2m{text}\033[0m"


@app.command()
def validate(
    file: str = typer.Argument(None, help="Path to a skin YAML file. If omitted, validates all installed skins."),
    contrast: bool = typer.Option(True, "--contrast/--no-contrast", help="Also check WCAG AA contrast on status-bar pairs."),
    min_ratio: float = typer.Option(4.5, "--min-ratio", help="Minimum WCAG ratio for text pairs (dim pairs use 3.0)."),
):
    """Validate a skin file (or all installed skins): schema + WCAG contrast.

    Exit code 0 = all valid, 1 = any errors. Warnings don't affect the exit
    code; errors are missing name, invalid hex, or unreadable status bar.
    """
    from .generators import contrast_ratio

    targets: list[tuple[str, Path, Skin | None, str | None]] = []
    if file:
        p = Path(file)
        if not p.exists():
            typer.echo(f"File not found: {p}", err=True)
            raise typer.Exit(1)
        try:
            targets.append((p.name, p, Skin.load(p), None))
        except Exception as e:
            typer.echo(f"✗ {p.name}: invalid skin file: {e}", err=True)
            raise typer.Exit(1)
    else:
        skins = installed_skins()
        if not skins:
            typer.echo("No skins installed in ~/.hermes/skins/ (nothing to validate).")
            return
        for name, p in sorted(skins.items()):
            try:
                targets.append((name, p, Skin.load(p), None))
            except Exception as e:
                targets.append((name, p, None, str(e)))

    had_error = False
    for label, path, skin, load_err in targets:
        if load_err is not None:
            typer.echo(f"✗ {label}: {load_err}", err=True)
            had_error = True
            continue
        warnings = skin.validate()
        # Schema errors vs warnings (audit 0.2.0 #1): a missing name or an
        # invalid hex value makes the skin unusable — treat those as errors,
        # not advisory warnings, so validate exits non-zero.
        error_prefixes = ("name is empty", "is not a valid #RRGGBB hex")
        schema_errors = [w for w in warnings if any(w.startswith(p) or p in w for p in error_prefixes)]
        schema_warnings = [w for w in warnings if w not in schema_errors]
        had_error = had_error or bool(schema_errors)
        # WCAG check on the pairs that actually render as text-on-background
        contrast_errors: list[str] = []
        if contrast:
            pairs = [
                ("status_bar_text", skin.colors.status_bar_bg, min_ratio),
                ("status_bar_strong", skin.colors.status_bar_bg, min_ratio),
                ("status_bar_dim", skin.colors.status_bar_bg, 3.0),
                ("status_bar_good", skin.colors.status_bar_bg, min_ratio),
                ("status_bar_warn", skin.colors.status_bar_bg, min_ratio),
                ("status_bar_bad", skin.colors.status_bar_bg, min_ratio),
                ("status_bar_critical", skin.colors.status_bar_bg, min_ratio),
            ]
            for slot, bg, need in pairs:
                fg = getattr(skin.colors, slot)
                try:
                    ratio = contrast_ratio(fg, bg)
                except (ValueError, AttributeError):
                    continue  # invalid hex already reported as a schema error
                if ratio < need:
                    contrast_errors.append(
                        f"colors.{slot} on {bg}: {ratio:.2f}:1 < {need}:1"
                    )
            had_error = had_error or bool(contrast_errors)
        if not schema_errors and not schema_warnings and not contrast_errors:
            ok_msg = f"✓ {label}: valid (29 colors"
            ok_msg += f", status bar ≥ {min_ratio}:1)" if contrast else ")"
            typer.echo(ok_msg)
            continue
        if schema_errors:
            typer.echo(f"✗ {label}: {len(schema_errors)} schema error(s):", err=True)
            for e in schema_errors:
                typer.echo(f"  · {e}", err=True)
        if schema_warnings:
            typer.echo(f"⚠ {label}: {len(schema_warnings)} warning(s):")
            for w in schema_warnings:
                typer.echo(f"  · {w}")
        if contrast_errors:
            typer.echo(f"✗ {label}: {len(contrast_errors)} contrast error(s):", err=True)
            for e in contrast_errors:
                typer.echo(f"  · {e}", err=True)

    if had_error:
        raise typer.Exit(1)


@app.command()
def templates():
    """List built-in theme templates."""
    tmpl = list_templates()
    typer.echo(f"Built-in templates ({len(tmpl)}):")
    for name, desc in sorted(tmpl.items()):
        typer.echo(f"  {name:20s}  {desc}")


@app.command()
def preview(
    name: str = typer.Argument(None, help="Skin name (installed or template). If omitted, shows the active skin from ~/.hermes/config.yaml."),
    all: bool = typer.Option(False, "--all", "-a", help="Show ALL templates (old no-arg behavior)."),
):
    """Preview a skin in the terminal."""
    if all:
        for tname in THEMES:
            skin = generate_from_template(tname)
            typer.echo(render_preview(skin))
            typer.echo("\n")
        return

    if name is None:
        # Show the active skin from Hermes config (matches help text; audit B6)
        active = active_skin_name()
        if not active:
            typer.echo("No active skin found in ~/.hermes/config.yaml (display.skin).", err=True)
            typer.echo("Preview a specific skin:  hermes-skins preview <name>", err=True)
            typer.echo("Dump all templates:       hermes-skins preview --all", err=True)
            raise typer.Exit(1)
        typer.echo(_fg_dim(f"Active skin (from ~/.hermes/config.yaml): {active}"))
        name = active

    # Try installed first, then template
    skins = installed_skins()
    if name in skins:
        skin = Skin.load(skins[name])
    elif name in THEMES:
        skin = generate_from_template(name)
    else:
        typer.echo(f"Skin '{name}' not found.", err=True)
        typer.echo(f"Installed: {', '.join(sorted(skins)) or '(none)'}", err=True)
        typer.echo(f"Templates: {', '.join(sorted(THEMES))}", err=True)
        raise typer.Exit(1)

    typer.echo(render_preview(skin))


@app.command()
def generate(
    template: str = typer.Argument(..., help="Template name (see 'hermes-skins templates')"),
    output: str = typer.Option(None, "--output", "-o", help="Output file path. If omitted, installs to ~/.hermes/skins/"),
    switch: bool = typer.Option(False, "--switch", help="Switch Hermes to this skin after generating"),
    mode: Mode = typer.Option(Mode.dark, "--mode", "-m", help="Color mode: dark surfaces (default) or light surfaces (audit F2)."),
):
    """Generate a skin from a built-in template."""
    try:
        skin = generate_from_template(template, mode=mode.value)
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    if output:
        path = skin.dump(output)
        typer.echo(f"✓ Generated '{skin.name}' → {path}")
    else:
        path = hermes_skins_dir() / f"{skin.name}.yaml"
        skin.dump(path)
        typer.echo(f"✓ Generated and installed '{skin.name}' → {path}")

    if switch:
        _do_switch(skin.name)

    typer.echo(f"  Preview: hermes-skins preview {skin.name}")
    typer.echo(f"  Activate: hermes config set display.skin {skin.name}")


@app.command()
def random(
    seed: str = typer.Argument(None, help="Random seed (string or number). Same seed = same skin."),
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
    switch: bool = typer.Option(False, "--switch", help="Switch Hermes to this skin after generating"),
    mode: Mode = typer.Option(Mode.dark, "--mode", "-m", help="Color mode: dark surfaces (default) or light surfaces."),
):
    """Generate a completely random skin."""
    skin = generate_random(seed, mode=mode.value)
    if output:
        path = skin.dump(output)
    else:
        path = hermes_skins_dir() / f"{skin.name}.yaml"
        skin.dump(path)
    typer.echo(f"✓ Generated random skin '{skin.name}' → {path}")
    typer.echo(f"  Harmony: {skin.description}")
    if switch:
        _do_switch(skin.name)


@app.command()
def custom(
    name: str = typer.Argument(..., help="Skin name"),
    color: str = typer.Option(..., "--color", "-c", help="Base color in #RRGGBB format"),
    harmony: Harmony = typer.Option(Harmony.complementary, "--harmony", "-H", help="Color harmony"),
    agent_name: str = typer.Option(None, "--agent-name", help="Custom agent display name"),
    prompt: str = typer.Option(None, "--prompt", help="Custom prompt symbol"),
    description: str = typer.Option("", "--description", "-d", help="Skin description"),
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
    switch: bool = typer.Option(False, "--switch", help="Switch Hermes to this skin after generating"),
    mode: Mode = typer.Option(Mode.dark, "--mode", "-m", help="Color mode: dark surfaces (default) or light surfaces."),
):
    """Generate a custom skin from a base color and harmony."""
    color = color.strip()
    if not re.fullmatch(r"#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?", color):
        typer.echo(f"Invalid color: {color!r}. Expected #RRGGBB (optional #RRGGBBAA).", err=True)
        raise typer.Exit(1)

    skin = generate_custom(
        name=name,
        base_color=color,
        harmony=harmony.value,
        agent_name=agent_name,
        prompt_symbol=prompt,
        description=description,
        mode=mode.value,
    )

    # skin.name flows from user input; a traversal-ish name must never become
    # a filesystem path (audit 0.2.0 #2). Explicit --output paths are honored
    # as given; only the derived default is sanitized.
    safe_name = Path(skin.name).name or "custom"
    if output:
        path = skin.dump(output)
    else:
        path = hermes_skins_dir() / f"{safe_name}.yaml"
        skin.dump(path)
    typer.echo(f"✓ Generated custom skin '{skin.name}' → {path}")
    typer.echo(f"  Base: {color}  Harmony: {harmony.value}")
    if switch:
        _do_switch(skin.name)


@app.command()
def install(file: str = typer.Argument(..., help="Path to a skin YAML file")):
    """Validate and install a skin file to ~/.hermes/skins/.

    The file is parsed and validated before landing in the skins directory,
    and is saved under the skin's internal name so lookups stay consistent
    (audit B9).
    """
    src = Path(file)
    if not src.exists():
        typer.echo(f"File not found: {src}", err=True)
        raise typer.Exit(1)
    try:
        skin = Skin.load(src)
    except Exception as e:
        typer.echo(f"✗ Not a valid skin file ({src.name}): {e}", err=True)
        raise typer.Exit(1)
    if skin.name == "unnamed":
        # YAML like "::: garbage" can parse into a mapping and silently load
        # as an all-defaults skin. A real skin always declares `name:`.
        typer.echo(f"✗ {src.name} has no 'name:' field — refusing to install a non-skin file.", err=True)
        raise typer.Exit(1)

    warnings = skin.validate()
    if warnings:
        typer.echo("⚠ Skin has validation warnings:", err=True)
        for w in warnings:
            typer.echo(f"  · {w}", err=True)
        typer.echo("Install anyway? [y/N]: ", err=True, nl=False)
        if sys.stdin.isatty():
            answer = input().strip().lower()
        else:
            answer = "y"  # non-interactive: proceed with warnings on record
        if answer not in ("y", "yes"):
            typer.echo("Aborted.", err=True)
            raise typer.Exit(1)

    hermes_skins_dir().mkdir(parents=True, exist_ok=True)
    # Sanitize the destination: skin.name comes from untrusted YAML, so a
    # name like "../../tmp/evil" or "sub/x" must never escape the skins dir.
    safe_name = Path(skin.name).name
    if safe_name in ("", ".", ".."):
        typer.echo(f"✗ Invalid skin name: {skin.name!r}", err=True)
        raise typer.Exit(1)
    dst = hermes_skins_dir() / f"{safe_name}.yaml"
    if dst.exists() and src.resolve() == dst.resolve():
        typer.echo(f"✓ {src.name} is already installed as '{safe_name}.yaml'. Nothing to do.")
        return
    shutil.copy2(src, dst)
    typer.echo(f"✓ Installed {src.name} → {dst}")
    if safe_name != src.stem:
        typer.echo(f"  (saved as '{safe_name}.yaml' to match the skin's internal name)")
    typer.echo(f"  Activate: hermes config set display.skin {safe_name}")


@app.command()
def switch(name: str = typer.Argument(..., help="Skin name to activate")):
    """Set display.skin in Hermes config."""
    _do_switch(name)


def _do_switch(name: str):
    """Internal: run hermes config set display.skin NAME."""
    result = shutil.which("hermes")
    if not result:
        typer.echo("⚠ 'hermes' CLI not found — cannot switch automatically.", err=True)
        typer.echo(f"  Run manually: hermes config set display.skin {name}")
        return
    import subprocess
    proc = subprocess.run(["hermes", "config", "set", "display.skin", name],
                          capture_output=True, text=True)
    if proc.returncode == 0:
        typer.echo(f"✓ Switched Hermes skin to '{name}'")
    else:
        typer.echo(f"⚠ Failed to switch: {proc.stderr.strip()}", err=True)


@app.command()
def export(
    name: str = typer.Argument(..., help="Skin name (installed or template)"),
    output: str = typer.Option(None, "--output", "-o", help="Output file path (default: ./<name>.yaml)"),
):
    """Export a skin to a standalone YAML file."""
    # Try installed first, then template
    skins = installed_skins()
    if name in skins:
        skin = Skin.load(skins[name])
    elif name in THEMES:
        skin = generate_from_template(name)
    else:
        typer.echo(f"Skin '{name}' not found.", err=True)
        raise typer.Exit(1)

    # skin.name comes from untrusted YAML — never let it become a traversal
    # path when deriving the default output name (audit 0.2.0 #2).
    safe_name = Path(skin.name).name or "skin"
    out_path = output or f"{safe_name}.yaml"
    skin.dump(out_path)
    typer.echo(f"✓ Exported '{skin.name}' → {out_path}")


# ---------------------------------------------------------------------------
# CRUD lifecycle (audit F7)
# ---------------------------------------------------------------------------

def _resolve_skin_path(name: str) -> Path | None:
    """Find an installed skin file by lookup name (internal name or stem)."""
    skins = installed_skins()
    if name in skins:
        return skins[name]
    return None


@app.command()
def uninstall(
    name: str = typer.Argument(..., help="Installed skin name to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Remove even if it is the active skin"),
):
    """Remove an installed skin from ~/.hermes/skins/."""
    path = _resolve_skin_path(name)
    if path is None:
        typer.echo(f"Skin '{name}' is not installed.", err=True)
        typer.echo(f"Installed: {', '.join(sorted(installed_skins())) or '(none)'}", err=True)
        raise typer.Exit(1)
    active = active_skin_name()
    if name == active and not force:
        typer.echo(f"⚠ '{name}' is the ACTIVE skin. Use --force to remove it anyway.", err=True)
        raise typer.Exit(1)
    path.unlink()
    typer.echo(f"✓ Uninstalled '{name}' ({path.name})")
    if name == active:
        typer.echo("  note: it was active — set a new skin with: hermes-skins switch <name>")


@app.command()
def rename(
    old: str = typer.Argument(..., help="Installed skin name"),
    new: str = typer.Argument(..., help="New name"),
):
    """Rename an installed skin: updates the file AND the internal name field.

    Fixes the audit B9 dual-track (file stem vs internal name) for existing
    installs: after rename, both agree.
    """
    path = _resolve_skin_path(old)
    if path is None:
        typer.echo(f"Skin '{old}' is not installed.", err=True)
        raise typer.Exit(1)
    safe_new = Path(new).name
    if safe_new in ("", ".", ".."):
        typer.echo(f"✗ Invalid new name: {new!r}", err=True)
        raise typer.Exit(1)
    if safe_new in installed_skins() and safe_new != old:
        typer.echo(f"✗ A skin named '{safe_new}' already exists.", err=True)
        raise typer.Exit(1)
    try:
        skin = Skin.load(path)
    except Exception as e:
        typer.echo(f"✗ Cannot load '{old}': {e}", err=True)
        raise typer.Exit(1)
    skin.name = safe_new
    dst = hermes_skins_dir() / f"{safe_new}.yaml"
    skin.dump(dst)
    if dst.resolve() != path.resolve():
        path.unlink(missing_ok=True)
    typer.echo(f"✓ Renamed '{old}' → '{safe_new}'")
    if active_skin_name() == old:
        typer.echo(f"  note: '{old}' was the active skin — re-activate with: hermes-skins switch {safe_new}")


@app.command()
def clone(
    name: str = typer.Argument(..., help="Installed skin or template name"),
    new: str = typer.Argument(..., help="Name for the copy"),
):
    """Clone an installed skin or template under a new name."""
    skins = installed_skins()
    if name in skins:
        skin = Skin.load(skins[name])
    elif name in THEMES:
        skin = generate_from_template(name)
    else:
        typer.echo(f"Skin '{name}' not found (installed or template).", err=True)
        raise typer.Exit(1)
    safe_new = Path(new).name
    if safe_new in ("", ".", ".."):
        typer.echo(f"✗ Invalid new name: {new!r}", err=True)
        raise typer.Exit(1)
    if safe_new in installed_skins():
        typer.echo(f"✗ A skin named '{safe_new}' already exists.", err=True)
        raise typer.Exit(1)
    skin.name = safe_new
    hermes_skins_dir().mkdir(parents=True, exist_ok=True)
    dst = hermes_skins_dir() / f"{safe_new}.yaml"
    skin.dump(dst)
    typer.echo(f"✓ Cloned '{name}' → '{safe_new}' ({dst})")
    typer.echo(f"  Activate: hermes-skins switch {safe_new}")


# ---------------------------------------------------------------------------
# Diff (audit F5)
# ---------------------------------------------------------------------------

@app.command()
def diff(
    a: str = typer.Argument(..., help="First skin (installed or template)"),
    b: str = typer.Argument(..., help="Second skin (installed or template)"),
    min_delta: float = typer.Option(
        4.0, "--min-delta", "-t",
        help="Highlight changed slots when any color channel shifts by this much (0-255).",
    ),
):
    """Compare two skins: 29 color slots side by side + branding/spinner deltas."""
    def _load(name: str) -> Skin:
        skins = installed_skins()
        if name in skins:
            return Skin.load(skins[name])
        if name in THEMES:
            return generate_from_template(name)
        typer.echo(f"Skin '{name}' not found.", err=True)
        raise typer.Exit(1)

    skin_a, skin_b = _load(a), _load(b)
    ca, cb = skin_a.colors.to_dict(), skin_b.colors.to_dict()

    def _channels(hx: str) -> tuple[int, int, int] | None:
        if not isinstance(hx, str) or len(hx) < 7 or not hx.startswith("#"):
            return None
        try:
            return int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)
        except ValueError:
            return None

    def _swatch(hx: str) -> str:
        if not _color_enabled():
            return "        "
        rgb = _channels(hx)
        if rgb is None:
            return "????????"
        return f"\033[48;2;{rgb[0]};{rgb[1]};{rgb[2]}m  \033[0m"

    typer.echo(f"diff {a} → {b}:")
    typer.echo(f"  {'slot':22s} {'A':10s} {'B':10s}  change")
    changed = 0
    for slot in ca:
        va, vb = ca[slot], cb.get(slot, "?")
        cha, chb = _channels(va), _channels(vb)
        differs = va != vb
        big = False
        if cha and chb:
            delta = max(abs(x - y) for x, y in zip(cha, chb))
            big = delta >= min_delta
        elif va != vb:
            big = True
        if differs:
            changed += 1
        if big:
            mark = _fg_dim(" ●") if _color_enabled() else " *"
            typer.echo(f"  {slot:22s} {_swatch(va)} {va:9s} {_swatch(vb)} {vb:9s}{mark}")
        elif differs:
            typer.echo(f"  {slot:22s} {_swatch(va)} {va:9s} {_swatch(vb)} {vb:9s}")
    if changed == 0:
        typer.echo("  (all 29 color slots identical)")
    else:
        typer.echo(f"  {changed}/29 slots differ; ● marks visually significant shifts (Δchannel ≥ {min_delta:g})")
    # Branding / spinner summary
    ba, bb = skin_a.branding, skin_b.branding
    brand_diffs = [f"{f} ({getattr(ba, f)!r} → {getattr(bb, f)!r})"
                   for f in ("agent_name", "prompt_symbol", "welcome", "goodbye", "response_label", "help_header")
                   if getattr(ba, f) != getattr(bb, f)]
    if brand_diffs:
        typer.echo("  branding:")
        for d in brand_diffs:
            typer.echo(f"    · {d}")
    if skin_a.spinner.waiting_faces != skin_b.spinner.waiting_faces:
        typer.echo(f"  spinner faces: {skin_a.spinner.waiting_faces} → {skin_b.spinner.waiting_faces}")


# ---------------------------------------------------------------------------
# Remote install (audit F8)
# ---------------------------------------------------------------------------

def _fetch_url(url: str, timeout: float = 15.0) -> str:
    """Fetch a skin YAML over http(s). urllib only — no new dependencies.

    Gist URLs (gist.github.com/<user>/<id>) are auto-resolved to the raw URL.
    """
    # Gist convenience: resolve to raw
    m = re.match(r"https://gist\.github\.com/([^/]+)/([0-9a-f]+)$", url.rstrip("/"))
    if m:
        url = f"https://gist.githubusercontent.com/{m.group(1)}/{m.group(2)}/raw"
    if not re.match(r"^https?://", url):
        raise ValueError(f"Only http(s) URLs are supported, got: {url!r}")
    req = urllib.request.Request(url, headers={"User-Agent": "hermes-skins-engine"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (https-only enforced above)
        data = resp.read(1024 * 1024)  # 1 MB cap — skins are small
    return data.decode("utf-8", errors="replace")


@app.command(name="install-url")
def install_url(
    url: str = typer.Argument(..., help="http(s) URL or gist.github.com link pointing to a skin YAML"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite an existing skin with the same name"),
):
    """Download, validate, and install a skin from a URL (audit F8)."""
    typer.echo(f"Fetching {url} ...")
    try:
        text = _fetch_url(url)
    except (urllib.error.URLError, ValueError, TimeoutError, OSError) as e:
        typer.echo(f"✗ Download failed: {e}", err=True)
        raise typer.Exit(1)
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as tf:
        tf.write(text)
        tmp = Path(tf.name)
    try:
        # Reuse the install command's validation and path handling
        install(file=str(tmp))
    finally:
        tmp.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Interactive picker (audit F3) — raw-mode TUI, zero dependencies
# ---------------------------------------------------------------------------

def _render_picker_screen(skins: dict[str, Path], themes: list[str], active: str | None,
                          sel: int, entries: list[tuple[str, str, object]]) -> str:
    """One frame of the picker: numbered list + preview of the selected entry."""
    lines = ["", "  ┌─ hermes-skins picker ─────────────────────────────┐"]
    for i, (kind, name, _src) in enumerate(entries):
        cursor = "▸" if i == sel else " "
        active_mark = " ← active" if (kind == "installed" and name == active) else ""
        lines.append(f"  │ {cursor} {i + 1:2d}. [{kind:9s}] {name:16s}{active_mark}")
    lines.append("  │")
    lines.append("  │  ↑/↓ or j/k: move   Enter: switch+install   q: quit")
    lines.append("  └───────────────────────────────────────────────────┘")
    kind, name, src = entries[sel]
    try:
        skin = Skin.load(src) if kind == "installed" else generate_from_template(name)
        lines.append("")
        lines.append(strip_ansi(render_preview(skin)))
    except Exception as e:
        lines.append(f"  (preview failed: {e})")
    return "\n".join(lines)


def _read_key() -> str:
    """Read one keypress in raw mode. Returns 'up'/'down'/'enter'/'quit'/other."""
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
            return "quit"
        if ch in ("\r", "\n"):
            return "enter"
        if ch in ("q", "\x03"):  # q or Ctrl-C
            return "quit"
        if ch == "k":
            return "up"
        if ch == "j":
            return "down"
        return "other"
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


@app.command()
def picker():
    """Interactively browse and preview skins with ↑/↓, Enter to switch (F3).

    Pure-termios raw mode — no curses, no extra dependencies. Requires a TTY;
    on non-Windows systems only.
    """
    if not sys.stdin.isatty() or sys.platform == "win32":
        typer.echo("picker needs an interactive terminal (TTY). Use 'hermes-skins preview --all' instead.", err=True)
        raise typer.Exit(1)

    entries: list[tuple[str, str, object]] = []
    for name, path in sorted(installed_skins().items()):
        entries.append(("installed", name, path))
    for tname in sorted(THEMES):
        entries.append(("template", tname, tname))

    active = active_skin_name()
    sel = 0
    # Start on the active skin if present
    for i, (kind, name, _p) in enumerate(entries):
        if kind == "installed" and name == active:
            sel = i
            break

    import contextlib
    import io

    while True:
        frame = _render_picker_screen(installed_skins(), sorted(THEMES), active, sel, entries)
        # Clear screen + home cursor, then draw one frame
        sys.stdout.write("\033[2J\033[H" + frame + "\n")
        sys.stdout.flush()
        key = _read_key()
        if key == "up":
            sel = (sel - 1) % len(entries)
        elif key == "down":
            sel = (sel + 1) % len(entries)
        elif key == "enter":
            kind, name, _src = entries[sel]
            if kind == "template":
                skin = generate_from_template(name)
                hermes_skins_dir().mkdir(parents=True, exist_ok=True)
                dst = hermes_skins_dir() / f"{skin.name}.yaml"
                if not dst.exists():
                    skin.dump(dst)
                name = skin.name
            _do_switch(name)
            sys.stdout.write(f"\n  ✓ Switched to '{name}'. Opening Hermes with it next time.\n")
            return
        elif key == "quit":
            sys.stdout.write("\n  (picker closed)\n")
            return


# ---------------------------------------------------------------------------
# Watch (audit F4) — live preview while editing a skin YAML
# ---------------------------------------------------------------------------

@app.command()
def watch(
    file: str = typer.Argument(..., help="Path to a skin YAML file to watch"),
    interval: float = typer.Option(0.5, "--interval", "-i", min=0.1, help="Poll interval in seconds"),
):
    """Live-preview a skin YAML as you edit it (mtime polling; F4)."""
    p = Path(file).expanduser()
    if not p.exists():
        typer.echo(f"File not found: {p}", err=True)
        raise typer.Exit(1)
    last_mtime: float | None = None
    last_render: str = ""
    typer.echo(f"Watching {p} — edit the file and the preview refreshes. Ctrl-C to stop.")
    try:
        while True:
            try:
                mtime = p.stat().st_mtime
            except FileNotFoundError:
                sys.stdout.write("\033[2J\033[H(file deleted; waiting…)\n")
                sys.stdout.flush()
                time.sleep(interval)
                continue
            if mtime != last_mtime:
                last_mtime = mtime
                try:
                    skin = Skin.load(p)
                    last_render = render_preview(skin)
                except Exception as e:
                    last_render = f"(invalid YAML — showing last good preview when you fix it)\n✗ {e}"
                sys.stdout.write("\033[2J\033[H" + last_render + "\n")
                sys.stdout.flush()
            time.sleep(interval)
    except KeyboardInterrupt:
        typer.echo("\n(watch stopped)")

@app.command()
def version():
    """Show version."""
    typer.echo(f"hermes-skins v{__version__}")


if __name__ == "__main__":
    app()