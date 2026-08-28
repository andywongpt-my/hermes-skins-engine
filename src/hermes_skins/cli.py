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
import shutil
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
    THEMES,
)
from .preview import render_preview

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
    (audit B9).
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
    typer.echo(f"Installed skins ({len(skins)}):")
    for name, path in sorted(skins.items()):
        try:
            skin = Skin.load(path)
            desc = skin.description or "(no description)"
        except Exception:
            desc = "(failed to load)"
        typer.echo(f"  {name:20s}  {desc}")


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


def _fg_dim(text: str) -> str:
    return f"\033[2m{text}\033[0m"


@app.command()
def generate(
    template: str = typer.Argument(..., help="Template name (see 'hermes-skins templates')"),
    output: str = typer.Option(None, "--output", "-o", help="Output file path. If omitted, installs to ~/.hermes/skins/"),
    switch: bool = typer.Option(False, "--switch", help="Switch Hermes to this skin after generating"),
):
    """Generate a skin from a built-in template."""
    try:
        skin = generate_from_template(template)
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
):
    """Generate a completely random skin."""
    skin = generate_random(seed)
    if output:
        path = skin.dump(output)
    else:
        path = hermes_skins_dir() / f"{skin.name}.yaml"
        skin.dump(path)
    typer.echo(f"✓ Generated random skin '{skin.name}' → {path}")
    typer.echo(f"  Harmony: {skin.description}")
    if switch:
        _do_switch(skin.name)


class Harmony(str, Enum):
    complementary = "complementary"
    analogous = "analogous"
    triadic = "triadic"
    monochrome = "monochrome"
    split_comp = "split_comp"


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
):
    """Generate a custom skin from a base color and harmony."""
    if not color.startswith("#") or len(color) not in (7, 9):
        typer.echo(f"Invalid color: {color!r}. Expected #RRGGBB format.", err=True)
        raise typer.Exit(1)

    skin = generate_custom(
        name=name,
        base_color=color,
        harmony=harmony.value,
        agent_name=agent_name,
        prompt_symbol=prompt,
        description=description,
    )

    if output:
        path = skin.dump(output)
    else:
        path = hermes_skins_dir() / f"{skin.name}.yaml"
        skin.dump(path)
    typer.echo(f"✓ Generated custom skin '{skin.name}' → {path}")
    typer.echo(f"  Base: {color}  Harmony: {harmony}")
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
    dst = hermes_skins_dir() / f"{skin.name}.yaml"
    shutil.copy2(src, dst)
    typer.echo(f"✓ Installed {src.name} → {dst}")
    if skin.name != src.stem:
        typer.echo(f"  (saved as '{skin.name}.yaml' to match the skin's internal name)")
    typer.echo(f"  Activate: hermes config set display.skin {skin.name}")


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

    out_path = output or f"{skin.name}.yaml"
    skin.dump(out_path)
    typer.echo(f"✓ Exported '{skin.name}' → {out_path}")


@app.command()
def version():
    """Show version."""
    typer.echo(f"hermes-skins v{__version__}")


if __name__ == "__main__":
    app()