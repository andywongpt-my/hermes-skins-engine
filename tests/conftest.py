"""Shared fixtures for the hermes-skins test suite.

Tests never touch the real ~/.hermes: `isolated_home` redirects Path.home()
to a tmp directory for the duration of each test.
"""
from __future__ import annotations

import pytest
from typer.testing import CliRunner

from hermes_skins.cli import app


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def cli_app():
    return app


@pytest.fixture()
def isolated_home(tmp_path, monkeypatch):
    """Redirect Path.home() to a fresh tmp dir (so ~/.hermes/skins and
    ~/.hermes/config.yaml writes are sandboxed)."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: home)
    return home


@pytest.fixture()
def clean_color_env(monkeypatch):
    """Remove NO_COLOR/CLICOLOR so color tests are hermetic."""
    for var in ("NO_COLOR", "CLICOLOR", "CLICOLOR_FORCE", "FORCE_COLOR"):
        monkeypatch.delenv(var, raising=False)
    return monkeypatch
