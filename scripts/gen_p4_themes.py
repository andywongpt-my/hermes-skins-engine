#!/usr/bin/env python3
"""One-off generator: emit Python source for the 6 P4 theme templates.

Writes /tmp/p4_themes.py which is then spliced into generators.py by hand.
Not part of the package — kept for reproducibility.
"""
from pyfiglet import Figlet

f = Figlet(font='ansi_shadow')
ART = {}
for name in ['MARI', 'RITSUKO', 'GENDO', 'KAJI', 'LILITH', 'MAGI']:
    lines = [l.rstrip() for l in f.renderText(name).splitlines() if l.strip()]
    ART[name] = lines

HERO_TOP = "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣠⣴⣶⣿⣿⣿⣶⣦⣄⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀"
HERO_TOP2 = "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣶⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀"
HERO_MID1 = "⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⡿⠛⠉⠉⠛⢿⣿⣿⣿⣿⣿⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀"
HERO_MID2 = "⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⠋⠀⠀⠀⠀⠀⠀⠀⠙⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀"
HERO_MID3 = "⠀⠀⠀⠀⠀⠀⠀⣸⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀"
HERO_MID4 = "⠀⠀⠀⠀⠀⠀⣸⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢿⣿⣿⣿⡆⠀⠀⠀⠀⠀⠀⠀⠀⠀"
HERO_MID5 = "⠀⠀⠀⠀⠀⢀⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀"
HERO_MID6 = "⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀"
HERO_MID7 = "⠀⠀⠀⠀⠀⢸⣿⣿⣿⣷⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀"
HERO_MID8 = "⠀⠀⠀⠀⠀⠘⣿⣿⣿⣿⣿⣦⣀⠀⠀⠀⠀⠀⠀⣀⣴⣿⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀"
HERO_BOT1 = "⠀⠀⠀⠀⠀⠀⠻⣿⣿⣿⣿⣿⣿⣿⣷⣶⣶⣶⣶⣿⣿⣿⣿⣿⣿⠟⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀"
HERO_BOT2 = "⠀⠀⠀⠀⠀⠀⠀⠉⠛⠻⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠟⠛⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀"


def logo_block(lines, mid, light):
    n = len(lines)
    parts = []
    for i, line in enumerate(lines):
        if i < n - 2:
            parts.append(f'"[bold {mid}]{line}[/]\\n"')
        else:
            parts.append(f'"[{light}]{line}[/]\\n"')
    return "\n            ".join(parts)


def hero_block(dark, mid, light):
    rows = [
        (dark, HERO_TOP), (dark, HERO_TOP2),
        (light, HERO_MID1), (light, HERO_MID2), (light, HERO_MID3), (light, HERO_MID4),
        (mid, HERO_MID5), (mid, HERO_MID6),
        (light, HERO_MID7), (light, HERO_MID8),
        (dark, HERO_BOT1), (mid, HERO_BOT2),
    ]
    body = "\n".join(f'            "[{c}]{r}[/]\\n"' for c, r in rows)
    # first row needs the opening quote
    return body


TEMPLATES = [
    dict(
        key="mari", title="MARI",
        base="#E86A9E", harmony="analogous",
        description="Mari Illustrious Makinami — rose-pink, cheerful audacity",
        agent_name="EVA-05 Agent", prompt_symbol="◉ ❯ ", response_label=" ◉ EVA-05 ",
        waiting_faces=["(◉)", "(◎)", "(◠)", "(◡)", "(☀)"],
        thinking_faces=["(◉)", "(◠)", "(◎)", "(◡)", "(☀)"],
        verbs=["calibrating EVA-05", "tuning the goggle HUD", "humming in the entry plug",
               "checking vertical takeoff", "sniffing out an Angel", "sharing the provisions",
               "swinging on the cable", "plotting a cheerful descent"],
        wings=[["⟪◉", "◉⟫"], ["⟪◎", "◎⟫"], ["⟪◠", "◠⟫"], ["⟪◡", "◡⟫"]],
        tool_prefix="╟",
        emojis={"terminal": "◉", "web_search": "◎", "read_file": "◠", "write_file": "❖",
                "search_files": "◡", "execute_code": "⌁", "browser_navigate": "⊕",
                "delegate_task": "▣", "mixture_of_agents": "⚗", "memory": "◐", "clarify": "?",
                "cronjob": "↻", "process": "⚙", "todo": "☐"},
        welcome="Banzai! Type /help for the fun stuff.",
        goodbye="Mission's a hit! See ya next sortie...",
        help_header="(◉) Cheerful Commands",
        sub="EVA-05 · MARI · VERTICAL TAKEOFF",
        quote='\\"Banzai! Chomp, chomp...\\" — MARI',
        dark="#3D1224", mid="#C25E8C", light="#F5C9DC", subc="#7A3B57",
    ),
    dict(
        key="ritsuko", title="RITSUKO",
        base="#C9973A", harmony="complementary",
        description="Ritsuko Akagi — amber laboratory light, Magi caretaker",
        agent_name="Magi Lab", prompt_symbol="▤ ❯ ", response_label=" MAGI LAB ",
        waiting_faces=["(▤)", "(▥)", "(▦)", "(▧)", "(▣)"],
        thinking_faces=["(▤)", "(▩)", "(▦)", "(▣)", "(▥)"],
        verbs=["running the Magi triad", "compiling Casper's verdict", "cross-checking Melchior",
               "auditing Balthasar's node", "feeding the cat, quietly", "filing a redacted report",
               "correlating the dead sea scrolls", "debugging the fifth Angel"],
        wings=[["⟪▤", "▤⟫"], ["⟪▦", "▦⟫"], ["⟪▩", "▩⟫"]],
        tool_prefix="┠",
        emojis={"terminal": "▤", "web_search": "◎", "read_file": "▦", "write_file": "◆",
                "search_files": "▩", "execute_code": "⌁", "browser_navigate": "⊕",
                "delegate_task": "▣", "mixture_of_agents": "⚗", "memory": "◐", "clarify": "?",
                "cronjob": "↻", "process": "⚙", "todo": "☐"},
        welcome="Magi nodes online. Type /help for the analysis.",
        goodbye="Analysis archived. Lab lights off.",
        help_header="(▤) Analysis Commands",
        sub="MAGI LAB · RITSUKO · MELCHIOR-2",
        quote='\\"The truth is always rational.\\" — AKAGI',
        dark="#2E2612", mid="#B98A3E", light="#EAD9B4", subc="#6E5A2E",
    ),
    dict(
        key="gendo", title="GENDO",
        base="#6B4FE0", harmony="monochrome",
        description="Commander Ikari — instrumentality violet, glasses gleam",
        agent_name="Commander", prompt_symbol="◤ ❯ ", response_label=" SCENARIO ",
        waiting_faces=["(▤)", "(◼)", "(▬)", "(▰)", "(▱)"],
        thinking_faces=["(◼)", "(▬)", "(▱)", "(▰)", "(▤)"],
        verbs=["advancing the scenario", "folding the hands", "consulting SEELE's script",
               "weighing the Spear", "watching Yui's window", "silencing the bridge",
               "judging the pilots", "waiting at the altar"],
        wings=[["⟪◼", "◼⟫"], ["⟪▬", "▬⟫"], ["⟪▤", "▤⟫"]],
        tool_prefix="╠",
        emojis={"terminal": "◼", "web_search": "◉", "read_file": "▬", "write_file": "▰",
                "search_files": "▱", "execute_code": "⌁", "browser_navigate": "⊕",
                "delegate_task": "▣", "mixture_of_agents": "⚗", "memory": "◐", "clarify": "?",
                "cronjob": "↻", "process": "⚙", "todo": "☐"},
        welcome="The scenario proceeds. Type /help.",
        goodbye="Everything is proceeding as planned.",
        help_header="(◼) Command Deck",
        sub="COMMAND DECK · GENDO · SCENARIO",
        quote='\\"Everything is proceeding as planned.\\" — IKARI',
        dark="#191233", mid="#6B5CB8", light="#D9D4EE", subc="#3E3568",
    ),
    dict(
        key="kaji", title="KAJI",
        base="#4FA66B", harmony="split_comp",
        description="Ryoji Kaji — watermelon patch green, laid-back truth seeker",
        agent_name="Kaji's Field", prompt_symbol="⊰ ❯ ", response_label=" INSPECTOR ",
        waiting_faces=["(❦)", "(✿)", "(❀)", "(❁)", "(◍)"],
        thinking_faces=["(❦)", "(✿)", "(❁)", "(❀)", "(◍)"],
        verbs=["watering the patch", "peeling the secret file", "dangling the thread",
               "humming by the river", "digging up the truth", "sharpening the crossblade",
               "leaving a voicemail", "watching the sunset"],
        wings=[["⟪✿", "✿⟫"], ["⟪❀", "❀⟫"], ["⟪◍", "◍⟫"]],
        tool_prefix="╾",
        emojis={"terminal": "❦", "web_search": "◎", "read_file": "❧", "write_file": "✾",
                "search_files": "❥", "execute_code": "⌁", "browser_navigate": "⊕",
                "delegate_task": "▣", "mixture_of_agents": "⚗", "memory": "◐", "clarify": "?",
                "cronjob": "↻", "process": "⚙", "todo": "☐"},
        welcome="Patch is watered. Type /help.",
        goodbye="The rest is up to you...",
        help_header="(❦) Field Notes",
        sub="FIELD PATCH · KAJI · WATERMELON",
        quote='\\"The rest is up to you.\\" — KAJI',
        dark="#12271A", mid="#4E9A67", light="#C4E2CF", subc="#2C5A3C",
    ),
    dict(
        key="lilith", title="LILITH",
        base="#9FD8E8", harmony="monochrome",
        description="Lilith — pale first ancestor, silent instrumentality",
        agent_name="First Ancestral", prompt_symbol="◇ ❯ ", response_label=" LILITH ",
        waiting_faces=["(◌)", "(○)", "(◯)", "(◎)", "(⊙)"],
        thinking_faces=["(◌)", "(◯)", "(○)", "(⊙)", "(⊚)"],
        verbs=["seeding the black moon", "bleeding the fruit", "listening to no one",
               "sheltering the souls", "unfolding the wings", "resonating with Adam",
               "weaving the sea of LCL", "waiting at Terminal Dogma"],
        wings=[["⟪◌", "◌⟫"], ["⟪◯", "◯⟫"], ["⟪⊙", "⊙⟫"]],
        tool_prefix="│",
        emojis={"terminal": "◌", "web_search": "○", "read_file": "◍", "write_file": "◎",
                "search_files": "⊙", "execute_code": "⌁", "browser_navigate": "⊕",
                "delegate_task": "▣", "mixture_of_agents": "⚗", "memory": "◐", "clarify": "?",
                "cronjob": "↻", "process": "⚙", "todo": "☐"},
        welcome="The egg is still. Type /help.",
        goodbye="Returning to the sea of LCL...",
        help_header="(◌) Instrumentality",
        sub="TERMINAL DOGMA · LILITH · FIRST ANCESTOR",
        quote='\\"...the first ancestor.\\" — LILITH',
        dark="#16323D", mid="#5F93A4", light="#D6ECF3", subc="#2E4A55",
    ),
    dict(
        key="magi", title="MAGI",
        base="#8A5CF5", harmony="triadic",
        description="The Magi System — Melchior, Balthasar, Casper in conclave",
        agent_name="MAGI CONCLAVE", prompt_symbol="⬢ ❯ ", response_label=" MAGI ",
        waiting_faces=["(⬢)", "(⬡)", "(⬣)", "(△)", "(▽)"],
        thinking_faces=["(⬢)", "(⬣)", "(⬡)", "(△)", "(▽)"],
        verbs=["polling Melchior", "polling Balthasar", "polling Casper",
               "casting the majority", "weighing objection A-801", "simulating the bargain",
               "tallying the three answers", "rendering the verdict"],
        wings=[["⟪⬢", "⬢⟫"], ["⟪⬣", "⬣⟫"], ["⟪△", "△⟫"]],
        tool_prefix="╿",
        emojis={"terminal": "⬢", "web_search": "◎", "read_file": "⬡", "write_file": "⬣",
                "search_files": "△", "execute_code": "⌁", "browser_navigate": "⊕",
                "delegate_task": "▣", "mixture_of_agents": "⚗", "memory": "◐", "clarify": "?",
                "cronjob": "↻", "process": "⚙", "todo": "☐"},
        welcome="Three nodes concur. Type /help.",
        goodbye="Deliberation closed. Answer recorded.",
        help_header="(⬢) Deliberation Commands",
        sub="MAGI · MELCHIOR·BALTHASAR·CASPER",
        quote='\\"Question. Answer. Question.\\" — MAGI',
        dark="#1E1440", mid="#6B4CC4", light="#CFC5F2", subc="#443486",
    ),
]

HEADER = """    # --- P4 (v0.5.0) original templates — Mari, Ritsuko, Gendo, Kaji, Lilith, Magi ---
"""

out = [HEADER]
for t in TEMPLATES:
    title = t["title"]
    lines = ART[title]
    d = t
    e = ",\n".join(f'            "{k}": "{v}"' for k, v in d["emojis"].items())
    verbs = "\n".join(f'            "{v}",' for v in d["verbs"])
    q = d["quote"]
    block = "}},\n" + "    \"" + d['key'] + "\": {\n" + (
        "        \"base_color\": \"" + d['base'] + "\",\n"
        "        \"harmony\": \"" + d['harmony'] + "\",\n"
        "        \"description\": \"" + d['description'] + "\",\n"
        "        \"agent_name\": \"" + d['agent_name'] + "\",\n"
        "        \"prompt_symbol\": \"" + d['prompt_symbol'] + "\",\n"
        "        \"response_label\": \"" + d['response_label'] + "\",\n"
        "        \"waiting_faces\": " + str(d['waiting_faces']) + ",\n"
        "        \"thinking_faces\": " + str(d['thinking_faces']) + ",\n"
        "        \"thinking_verbs\": [\n" + verbs + "\n        ],\n"
        "        \"wings\": " + str(d['wings']) + ",\n"
        "        \"tool_prefix\": \"" + d['tool_prefix'] + "\",\n"
        "        \"tool_emojis\": {\n" + e + ",\n        },\n"
        "        \"welcome\": \"" + d['welcome'] + "\",\n"
        "        \"goodbye\": \"" + d['goodbye'] + "\",\n"
        "        \"help_header\": \"" + d['help_header'] + "\",\n"
        "        \"banner_logo\": (\n"
        "            " + logo_block(lines, d['mid'], d['light']) + "\n"
        "            \"[" + d['subc'] + "]              " + d['sub'] + "[/]\\n\"\n"
        "            \"[" + d['subc'] + "]              " + q + "[/]\"\n"
        "        ),\n"
        "        \"banner_hero\": (\n"
    )
    out.append(block)
    rows = [(d['dark'], HERO_TOP), (d['dark'], HERO_TOP2),
            (d['light'], HERO_MID1), (d['light'], HERO_MID2),
            (d['light'], HERO_MID3), (d['light'], HERO_MID4),
            (d['mid'], HERO_MID5), (d['mid'], HERO_MID6),
            (d['light'], HERO_MID7), (d['light'], HERO_MID8),
            (d['dark'], HERO_BOT1), (d['mid'], HERO_BOT2)]
    for c, r in rows:
        out.append(f'            "[{c}]{r}[/]\\n"')
    # strip trailing \n on last row
    out[-1] = out[-1].replace("\\n\"", "\"")
    out.append('        ),')

text = "\n".join(out)
# The first line of the first block begins with "},\n" — replace with "\n" marker
text = text.replace(HEADER + "},\n", "___FIRST___", 1)
# Actually easier: cut the leading junk up to the first template key
idx = text.find('    "mari": {')
text = text[idx:]

with open("/tmp/p4_themes.py", "w") as fh:
    fh.write(text)
print("written /tmp/p4_themes.py,", len(text.splitlines()), "lines")
