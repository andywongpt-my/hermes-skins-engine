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


@pytest.fixture(autouse=True)
def clean_color_env(monkeypatch):
    """Remove NO_COLOR/CLICOLOR so color tests are hermetic (audit 0.2.0 #4).

    autouse: without this, a host shell exporting NO_COLOR=1 makes every
    ANSI assertion fail. Tests that exercise the env vars re-set them
    explicitly via monkeypatch.setenv.

    v0.4.0 (F10): also pin TERM/COLORTERM and force the truecolor mode —
    legacy assertions expect raw 38;2 sequences, and inheriting the host
    terminal's depth (e.g. TERM=xterm-256color) would silently degrade them.
    Tests that exercise depth detection re-set these explicitly.
    """
    for var in ("NO_COLOR", "CLICOLOR", "CLICOLOR_FORCE", "FORCE_COLOR",
                "COLORTERM", "HERMES_SKINS_COLOR_MODE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("TERM", raising=False)  # unset TERM = historical truecolor default
    return monkeypatch
