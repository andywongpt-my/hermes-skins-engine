"""
Core skin schema — our own dataclass-based model.

A Skin is a complete theme definition: colors, spinner, branding,
tool icons, and optional banner art.  The schema is designed to be
extensible without breaking existing skins.
"""

from __future__ import annotations

import re
import yaml
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Sub-sections
# ---------------------------------------------------------------------------

@dataclass
class Colors:
    """29 named color slots that map to Hermes TUI elements.

    All Hermes-native color slots are supported so engine-generated skins
    are fully compatible with the Hermes skin loader.
    """
    # Banner / general UI
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

    # Status bar (TUI bottom bar)
    status_bar_bg: str = "#1A1A2E"
    status_bar_text: str = "#C0C0C0"
    status_bar_strong: str = "#FFFFFF"
    status_bar_dim: str = "#8B8682"
    status_bar_good: str = "#8FBC8F"
    status_bar_warn: str = "#FFD700"
    status_bar_bad: str = "#FF8C00"
    status_bar_critical: str = "#FF6B6B"

    # Voice status (TUI voice mode indicator)
    voice_status_bg: str = "#1A1A2E"

    # TUI selection / completion menu
    selection_bg: str = "#333355"
    completion_menu_bg: str = "#1A1A2E"
    completion_menu_current_bg: str = "#333355"
    completion_menu_meta_bg: str = "#1A1A2E"
    completion_menu_meta_current_bg: str = "#333355"

    @classmethod
    def from_dict(cls, d: dict) -> "Colors":
        # YAML "colors: null" parses as None — treat as absent (AGY P2 #3)
        if not isinstance(d, dict):
            d = {}
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in (d or {}).items() if k in known})

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
        # YAML "colors: null" parses as None — treat as absent (AGY P2 #3)
        if not isinstance(d, dict):
            d = {}
        known = {f.name for f in cls.__dataclass_fields__.values()}
        kwargs = {k: v for k, v in (d or {}).items() if k in known}
        # Non-sequence faces (e.g. a bare string) would break len()/iteration
        # downstream (AGY P2 #7) — coerce to defaults.
        for key in ("waiting_faces", "thinking_faces"):
            if key in kwargs and not isinstance(kwargs[key], (list, tuple)):
                kwargs[key] = list(kwargs[key]) if kwargs[key] else None
                if kwargs[key] is None:
                    kwargs.pop(key)
        return cls(**kwargs)

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
        # YAML "colors: null" parses as None — treat as absent (AGY P2 #3)
        if not isinstance(d, dict):
            d = {}
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in (d or {}).items() if k in known})

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Main Skin dataclass
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Schema versioning (audit F12). Bump when the Skin schema gains/changes
# fields in a way skins should be able to declare. Community skins written
# for a NEWER engine carry a higher schema_version and validate() warns.
# ---------------------------------------------------------------------------
SCHEMA_VERSION = 1

_KNOWN_TOP_KEYS = frozenset({
    "name", "description", "schema_version", "author", "tags",
    "colors", "spinner", "branding", "tool_prefix", "tool_emojis",
    "banner_logo", "banner_hero",
})


@dataclass
class Skin:
    name: str
    description: str = ""
    schema_version: int = SCHEMA_VERSION
    author: str = ""
    tags: list[str] = field(default_factory=list)
    colors: Colors = field(default_factory=Colors)
    spinner: Spinner = field(default_factory=Spinner)
    branding: Branding = field(default_factory=Branding)
    tool_prefix: str = "┊"
    tool_emojis: dict[str, str] = field(default_factory=dict)
    banner_logo: Optional[str] = None
    banner_hero: Optional[str] = None
    # Unknown top-level keys from hand-edited / community YAML are preserved
    # here so a load→dump round-trip never silently drops someone's metadata
    # (audit F12). They are re-emitted after the known fields on dump.
    extra: dict = field(default_factory=dict, repr=False, compare=False)

    # ----- I/O -----

    @classmethod
    def from_dict(cls, d: dict) -> "Skin":
        extra = {k: v for k, v in d.items() if k not in _KNOWN_TOP_KEYS}
        return cls(
            name=d.get("name", "unnamed"),
            description=d.get("description", ""),
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            author=d.get("author", ""),
            tags=list(d.get("tags", [])) if isinstance(d.get("tags", []), list) else [],
            # `or {}` guards explicit YAML nulls (colors: null etc. — AGY P2 #3)
            colors=Colors.from_dict(d.get("colors") or {}),
            spinner=Spinner.from_dict(d.get("spinner") or {}),
            branding=Branding.from_dict(d.get("branding") or {}),
            tool_prefix=d.get("tool_prefix", "┊"),
            tool_emojis=d.get("tool_emojis", {}),
            banner_logo=d.get("banner_logo"),
            banner_hero=d.get("banner_hero"),
            extra=extra,
        )

    def to_dict(self) -> dict:
        d: dict = {
            "name": self.name,
            "description": self.description,
            "schema_version": self.schema_version,
        }
        if self.author:
            d["author"] = self.author
        if self.tags:
            d["tags"] = list(self.tags)
        d["colors"] = self.colors.to_dict()
        d["spinner"] = self.spinner.to_dict()
        d["branding"] = self.branding.to_dict()
        d["tool_prefix"] = self.tool_prefix
        d["tool_emojis"] = dict(self.tool_emojis)
        if self.banner_logo:
            d["banner_logo"] = self.banner_logo
        if self.banner_hero:
            d["banner_hero"] = self.banner_hero
        # Unknown keys ride along at the end; known fields always win.
        for k, v in self.extra.items():
            d.setdefault(k, v)
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
        # Schema versioning (F12): skins written for a NEWER engine may use
        # features we don't know; flag it so upgrades aren't silent.
        if not isinstance(self.schema_version, int) or self.schema_version < 1:
            warnings.append(f"schema_version = {self.schema_version!r} is not a positive integer")
        elif self.schema_version > SCHEMA_VERSION:
            warnings.append(
                f"schema_version {self.schema_version} is newer than engine's {SCHEMA_VERSION} — some fields may be ignored"
            )
        # Strict hex: '#' + 6 hex digits, optional 2-digit alpha. Catches
        # "#ZZZZZZ" (wrong chars) that a length-only check would pass.
        hex_re = re.compile(r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")
        for slot, hexval in self.colors.to_dict().items():
            if not (isinstance(hexval, str) and hex_re.match(hexval)):
                warnings.append(f"colors.{slot} = {hexval!r} is not a valid #RRGGBB hex")
        # Type-guard: a malformed skin can carry null/non-sequence faces
        # (AGY P2 #7) — report a warning instead of raising TypeError.
        faces = self.spinner.waiting_faces
        if not isinstance(faces, (list, tuple)) or len(faces) < 2:
            warnings.append("spinner.waiting_faces should have at least 2 entries for animation")
        return warnings

    # ----- Convenience -----

    def palette(self) -> dict[str, str]:
        """Return just the color dict."""
        return self.colors.to_dict()

    def primary(self) -> str:
        """The dominant accent color."""
        return self.colors.ui_accent