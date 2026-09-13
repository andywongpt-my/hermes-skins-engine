"""P4 (v0.5.0) — HTML gallery generator tests."""

import re

import pytest

from hermes_skins.gallery import (
    collect_gallery_skins,
    contrast,
    render_gallery,
    render_gallery_file,
)


def test_collect_returns_all_14():
    skins = collect_gallery_skins(include_installed=False)
    assert len(skins) == 14
    names = {s.name for s in skins}
    assert {"asuka", "mari", "magi"} <= names


def test_render_gallery_counts_and_links():
    skins = collect_gallery_skins(include_installed=False)
    page = render_gallery(skins)
    assert page.count('<section class="card"') == 14
    for name in ("asuka", "mari", "ritsuko", "magi"):
        assert f'id="{name}"' in page


def test_gallery_is_self_contained():
    skins = collect_gallery_skins(include_installed=False)
    page = render_gallery(skins)
    assert "<script" not in page
    assert "http://" not in page and "https://" not in page  # no CDN calls
    assert "font-family" in page or "font:" in page  # inline CSS present


def test_gallery_escapes_branding():
    from hermes_skins.core import Branding, Colors, Skin, Spinner

    skin = Skin(
        name="xss-probe",
        description="probe <b>bold</b> & 'quotes'",
        colors=Colors(),
        spinner=Spinner(waiting_faces=["(<script>)"], thinking_faces=["(x)"],
                        thinking_verbs=["<img src=x>"], wings=[["⟪a", "a⟫"]]),
        branding=__import__("hermes_skins.core", fromlist=["Branding"]).Branding(
            agent_name="<script>alert(1)</script>",
            welcome="w", goodbye="g", response_label=" r ",
            prompt_symbol="❯ ", help_header="h"),
    )
    page = render_gallery([skin])
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


def test_contrast_grades():
    assert contrast("#000000", "#ffffff") > 15
    g, _ = __import__("hermes_skins.gallery", fromlist=["_grade"])._grade(4.6)
    assert g == "AA"
    g2, _ = __import__("hermes_skins.gallery", fromlist=["_grade"])._grade(2.9)
    assert g2 == "fail"


def test_render_gallery_file_writes(tmp_path):
    out = tmp_path / "sub" / "g.html"
    render_gallery_file(out, include_installed=False)
    assert out.exists() and out.stat().st_size > 50_000
