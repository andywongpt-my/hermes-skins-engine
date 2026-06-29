"""
Core skin schema — our own dataclass-based model.

A Skin is a complete theme definition: colors, spinner, branding,
tool icons, and optional banner art.  The schema is designed to be
extensible without breaking existing skins.
"""

from __future__ import annotations

import yaml
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Sub-sections
# ---------------------------------------------------------------------------

@dataclass
class Colors:
    """16 named color slots that map to TUI elements."""
    banner_border: str = "#333333"
    banner_title: str = "#FFFFFF"
    banner_accent: str = "#888888"
    banner_dim: str = "#555555"
    banner_text: str = "#CCCCCC"
    ui_accent: str = "#666666"
    ui_label: str = "#999999"
    ui_ok: str = "#00AA00"
    ui_error: str = "#AA0000"
    ui_warn: str = "#AA8800"
    prompt: str = "#CCCCCC"
    input_rule: str = "#444444"
    response_border: str = "#666666"
    session_label: str = "#999999"
    session_border: str = "#333333"

    @classmethod
    def from_dict(cls, d: dict) -> "Colors":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known})

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Spinner:
    waiting_faces: list[str] = field(default_factory=lambda: ["(·)", "(◦)", "(•)"])
    thinking_faces: list[str] = field(default_factory=lambda: ["(·)", "(•)", "(◦)"])
    thinking_verbs: list[str] = field(default_factory=lambda: ["thinking"])
    wings: list[list[str]] = field(default_factory=lambda: [["⟪·", "·⟫"]])

    @classmethod
    def from_dict(cls, d: dict) -> "Spinner":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known})

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Branding:
    agent_name: str = "Agent"
    welcome: str = "Ready."
    goodbye: str = "Goodbye."
    response_label: str = " Agent "
    prompt_symbol: str = "❯ "
    help_header: str = "Available Commands"

    @classmethod
    def from_dict(cls, d: dict) -> "Branding":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known})

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Main Skin dataclass
# ---------------------------------------------------------------------------

@dataclass
class Skin:
    name: str
    description: str = ""
    colors: Colors = field(default_factory=Colors)
    spinner: Spinner = field(default_factory=Spinner)
    branding: Branding = field(default_factory=Branding)
    tool_prefix: str = "┊"
    tool_emojis: dict[str, str] = field(default_factory=dict)
    banner_logo: Optional[str] = None
    banner_hero: Optional[str] = None

    # ----- I/O -----

    @classmethod
    def from_dict(cls, d: dict) -> "Skin":
        return cls(
            name=d.get("name", "unnamed"),
            description=d.get("description", ""),
            colors=Colors.from_dict(d.get("colors", {})),
            spinner=Spinner.from_dict(d.get("spinner", {})),
            branding=Branding.from_dict(d.get("branding", {})),
            tool_prefix=d.get("tool_prefix", "┊"),
            tool_emojis=d.get("tool_emojis", {}),
            banner_logo=d.get("banner_logo"),
            banner_hero=d.get("banner_hero"),
        )

    def to_dict(self) -> dict:
        d: dict = {
            "name": self.name,
            "description": self.description,
            "colors": self.colors.to_dict(),
            "spinner": self.spinner.to_dict(),
            "branding": self.branding.to_dict(),
            "tool_prefix": self.tool_prefix,
            "tool_emojis": dict(self.tool_emojis),
        }
        if self.banner_logo:
            d["banner_logo"] = self.banner_logo
        if self.banner_hero:
            d["banner_hero"] = self.banner_hero
        return d

    @classmethod
    def load(cls, path: str | Path) -> "Skin":
        """Load a skin from a YAML file."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Skin file not found: {p}")
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"Invalid skin file (expected mapping, got {type(raw)}): {p}")
        return cls.from_dict(raw)

    def dump(self, path: str | Path) -> Path:
        """Write skin to a YAML file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(yaml.dump(self.to_dict(), sort_keys=False, allow_unicode=True), encoding="utf-8")
        return p

    # ----- Validation -----

    def validate(self) -> list[str]:
        """Return a list of validation warnings (empty = OK)."""
        warnings: list[str] = []
        if not self.name:
            warnings.append("name is empty")
        for slot, hexval in self.colors.to_dict().items():
            if not (isinstance(hexval, str) and hexval.startswith("#") and len(hexval) in (7, 9)):
                warnings.append(f"colors.{slot} = {hexval!r} is not a valid #RRGGBB hex")
        if len(self.spinner.waiting_faces) < 2:
            warnings.append("spinner.waiting_faces should have at least 2 entries for animation")
        return warnings

    # ----- Convenience -----

    def palette(self) -> dict[str, str]:
        """Return just the color dict."""
        return self.colors.to_dict()

    def primary(self) -> str:
        """The dominant accent color."""
        return self.colors.ui_accent