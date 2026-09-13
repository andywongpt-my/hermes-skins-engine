"""
Gallery — static HTML gallery generator for all skins (P4, v0.5.0).

Renders every template (and optionally installed skins) to a self-contained
HTML file with inline CSS: one card per skin showing the palette, spinner
faces, branding, and a mock terminal preview. No JavaScript, no external
assets — one file you can open anywhere or attach to a GitHub release page.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path

from .core import Colors, Skin


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _luminance(h: str) -> float:
    r, g, b = _hex_to_rgb(h)
    def chan(c: float) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def contrast(fg: str, bg: str) -> float:
    l1, l2 = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def _grade(ratio: float) -> tuple[str, str]:
    if ratio >= 7.0:
        return "AAA", "#1a7f37"
    if ratio >= 4.5:
        return "AA", "#1a7f37"
    if ratio >= 3.0:
        return "AA-large", "#9a6700"
    return "fail", "#cf222e"


# ---------------------------------------------------------------------------
# Per-skin HTML card
# ---------------------------------------------------------------------------


def _swatches(colors: dict[str, str], status_bg: str) -> str:
    cells = []
    for name, hexv in colors.items():
        ratio = contrast(hexv, status_bg)
        grade, color = _grade(ratio)
        text = "#ffffff" if _luminance(hexv) < 0.4 else "#111111"
        cells.append(
            f'<div class="sw" style="background:{hexv};color:{text}">'
            f'<span class="nm">{html.escape(name)}</span>'
            f'<span class="hx">{hexv}</span>'
            f'<span class="gr" style="color:{text};opacity:.75">{grade}</span></div>'
        )
    return '<div class="swatches">' + "".join(cells) + "</div>"


def _mock_terminal(skin: Skin) -> str:
    """A fake terminal window painted with the skin's own colors."""
    c = skin.colors
    d = c.to_dict()
    sb_bg = c.status_bar_bg
    sb_fg = d.get("status_bar_text", "#ffffff")
    faces = " ".join(skin.spinner.waiting_faces[:3])
    verbs = " · ".join(skin.spinner.thinking_verbs[:3])
    rows = [
        f'<div class="tline"><span style="color:{d.get("prompt", "#fff")}">{html.escape(skin.branding.prompt_symbol)}</span>'
        f'<span style="color:{d.get("banner_text", "#ccc")}"> type a command…</span></div>',
        f'<div class="tline"><span style="color:{d.get("ui_accent", "#fff")}">{html.escape(skin.branding.response_label)}</span>'
        f'<span style="color:{d.get("banner_text", "#ccc")}"> {html.escape(skin.branding.welcome)}</span></div>',
        f'<div class="tline" style="color:{d.get("ui_dim", d.get("banner_dim", "#888"))}">{html.escape(faces)}  {html.escape(verbs)}</div>',
    ]
    tools = "".join(
        f'<span style="color:{d.get("ui_accent", "#fff")}">{html.escape(e)}</span>'
        f'<span style="color:{d.get("banner_text", "#ccc")}"> {html.escape(k)}</span>&nbsp;&nbsp;'
        for k, e in list(skin.tool_emojis.items())[:8]
    )
    rows.append(f'<div class="tline">{tools}</div>')
    statusbar = (
        f'<div class="tstatus" style="background:{sb_bg};color:{sb_fg}">'
        f'{html.escape(skin.branding.agent_name)} · {html.escape(skin.name)} · ✓ WCAG</div>'
    )
    bg = d.get("app_bg", "#16161e")
    return (
        f'<div class="term" style="background:{bg}">'
        + "".join(rows)
        + statusbar
        + "</div>"
    )


def skin_card(skin: Skin) -> str:
    c = skin.colors
    d = c.to_dict()
    sb_bg = c.status_bar_bg
    # overall grade across key text-on-bg pairs
    mock_bg = "#16161e"
    # grade each slot against the surface it actually renders on
    graded = [
        (d.get("status_bar_text", "#fff"), sb_bg),   # status bar text
        (d.get("banner_text", "#e6e6eb"), mock_bg),   # card heading (h2) color
        (d.get("prompt", "#fff"), mock_bg),           # prompt text
    ]
    ratios = [contrast(f, b) for f, b in graded]
    worst = min(ratios)
    grade, gcolor = _grade(worst)
    accent = d.get("ui_accent", "#888")

    h2_color = d.get("banner_text", "#e6e6eb")
    card = f"""
<section class="card" id="{html.escape(skin.name)}">
  <header>
    <h2 style="color:{h2_color};border-left:3px solid {accent};padding-left:8px">{html.escape(skin.branding.agent_name)}</h2>
    <p class="desc">{html.escape(skin.description or "")}</p>
    <p class="meta"><code>{html.escape(skin.name)}</code> · base <code>{d.get('ui_accent','')}</code>
       · worst key pair {worst:.2f}:1
       <span class="grade" style="background:{gcolor}">{grade}</span></p>
  </header>
  {_mock_terminal(skin)}
  {_swatches(d, sb_bg)}
  <footer class="spinfo">
    <span>faces: {html.escape(' '.join(skin.spinner.waiting_faces[:5]))}</span>
    <span>wings: {html.escape(' '.join(skin.spinner.wings[0]))}</span>
  </footer>
</section>"""
    return card


# ---------------------------------------------------------------------------
# Page assembly
# ---------------------------------------------------------------------------

_PAGE_CSS = """
:root { --bg:#0d0e12; --panel:#16171d; --fg:#e6e6eb; --dim:#8b8b96;
        --line:#2a2b33; --accent:#7aa2f7; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
       font:14px/1.5 -apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
       -webkit-font-smoothing:antialiased; }
header.top { padding:28px 24px 8px; max-width:1240px; margin:0 auto; }
header.top h1 { margin:0 0 4px; font-size:22px; letter-spacing:.3px; }
header.top p { margin:0; color:var(--dim); font-size:13px; }
nav.toc { max-width:1240px; margin:10px auto; padding:0 24px; display:flex;
          flex-wrap:wrap; gap:8px; }
nav.toc a { color:var(--accent); text-decoration:none; font-size:12.5px;
            background:var(--panel); border:1px solid var(--line);
            padding:3px 10px; border-radius:999px; }
nav.toc a:hover { border-color:var(--accent); }
main { max-width:1240px; margin:0 auto; padding:12px 24px 48px;
       display:grid; grid-template-columns:repeat(auto-fill,minmax(380px,1fr));
       gap:18px; }
.card { background:var(--panel); border:1px solid var(--line);
        border-radius:12px; padding:16px; scroll-margin-top:12px; }
.card h2 { margin:0 0 2px; font-size:16px; }
.desc { margin:0 0 6px; color:var(--dim); font-size:13px; }
.meta { margin:0 0 12px; font-size:12px; color:var(--dim); }
.meta code { background:var(--line); padding:1px 6px; border-radius:4px; }
.grade { color:#fff; font-size:11px; padding:1px 7px; border-radius:999px;
         margin-left:6px; }
.term { border-radius:8px; padding:12px 12px 0; font:12.5px/1.7 ui-monospace,
        SFMono-Regular,Menlo,Consolas,monospace; overflow:hidden; }
.tline { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.tstatus { margin:10px -12px 0; padding:4px 12px; font-weight:600;
           font-size:12px; }
.swatches { display:grid; grid-template-columns:repeat(3,1fr); gap:5px;
            margin-top:12px; }
.sw { border-radius:6px; padding:6px 8px; font:11px/1.4 ui-monospace,monospace;
      display:flex; flex-direction:column; min-width:0; }
.sw .nm { overflow:hidden; text-overflow:ellipsis; }
.sw .gr { font-size:9.5px; }
.spinfo { display:flex; gap:14px; margin-top:10px; color:var(--dim);
          font-size:12px; flex-wrap:wrap; }
footer.page { text-align:center; color:var(--dim); font-size:12px;
              padding:0 0 32px; }
"""


def render_gallery(skins: list[Skin], title: str = "hermes-skins gallery") -> str:
    """Render the full standalone HTML page."""
    toc = "".join(
        f'<a href="#{html.escape(s.name)}">{html.escape(s.name)}</a>' for s in skins
    )
    cards = "".join(skin_card(s) for s in skins)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<style>{_PAGE_CSS}</style>
</head>
<body>
<header class="top">
  <h1>{html.escape(title)}</h1>
  <p>{len(skins)} skins · WCAG grade per skin is the worst of its key text pairs · generated by hermes-skins-engine</p>
</header>
<nav class="toc">{toc}</nav>
<main>{cards}</main>
<footer class="footer page">hermes-skins-engine · MIT</footer>
</body>
</html>"""


def collect_gallery_skins(include_installed: bool = True,
                          include_templates: bool = True) -> list[Skin]:
    """Templates + installed skins, deduped by name, sorted."""
    from .cli import installed_skins
    from .generators import THEMES, generate_from_template

    skins: dict[str, Skin] = {}
    if include_templates:
        for name in sorted(THEMES):
            try:
                skins[name] = generate_from_template(name)
            except Exception:
                pass
    if include_installed:
        for name, path in sorted(installed_skins().items()):
            if name not in skins:
                try:
                    skins[name] = Skin.load(path)
                except Exception:
                    pass
    return [skins[k] for k in sorted(skins)]


def render_gallery_file(out: Path, include_installed: bool = True,
                        include_templates: bool = True) -> Path:
    skins = collect_gallery_skins(include_installed, include_templates)
    page = render_gallery(skins)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out
