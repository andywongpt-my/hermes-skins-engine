# AGY Post-Dev Audit Brief — hermes-skins-engine P2 cycle (f83bc5c)

## Your role
Independent auditor. You did NOT write this code. Find real bugs, security issues, and logic errors. Do NOT propose new features. Verify claims by reading the actual code, not the brief.

## What changed (10e2bdc → f83bc5c, +1065/-61)
4 files: `src/hermes_skins/cli.py` (+410), `src/hermes_skins/core.py` (+52), `src/hermes_skins/generators.py` (+263 net), `tests/test_p2_features.py` (new, 401).

New features:
1. **F2 light mode**: `generate_palette(mode="dark|light")` — light branch inverts derivation (surfaces L 0.92-0.97, ink L 0.10-0.22). CLI `--mode` on generate/random/custom. Random names get `-light` suffix.
2. **F3 picker**: `hermes-skins picker` — raw-termios full-screen browser. TTY-guarded, win32-rejected.
3. **F4 watch**: `hermes-skins watch FILE` — mtime polling loop, invalid-YAML resilience (keeps running, shows error).
4. **F5 diff**: 29-slot side-by-side with ANSI bg swatches, Δchannel significance marks, branding/spinner deltas.
5. **F7 CRUD**: `uninstall` (guards active skin unless --force), `rename` (rewrites file + internal name, sanitizes traversal), `clone` (installed or template).
6. **F8 install-url**: urllib fetch, gist→raw regex resolution, 1MB cap, https-only (regex-enforced), delegates to existing `install()` for validation. NOTE: URL scheme is enforced INSIDE `_fetch_url` via `^https?://` — http is allowed by design (local testing).
7. **F9 banner sync**: `sync_banner_art()` — template banner art hexes re-mapped by lightness rank: darkest→banner_border, lightest→banner_text, middles→banner_accent. Only applied during template generation; dumped skins keep concrete hexes.
8. **F11 extended harmonies**: tetradic/square/pastel/neon; secondary hues → ui_label/session_label when extended; classic five keep byte-identical outputs (regression test exists).
9. **F12 schema versioning**: `schema_version/author/tags` fields + unknown-key preservation via `Skin.extra`; `validate()` warns on newer/bad schema_version.
10. **F15 dynamic emoji**: random skins derive tool emojis from spinner faces; semantic icons (clarify/cronjob/process/todo/mixture_of_agents) stable.

## Known accepted limitations (do NOT report as findings)
- picker is POSIX-only (win32 rejected with clear error) — documented behavior.
- install-url allows http:// (not just https) — intentional for local testing; 1MB cap and urllib (no redirects-to-file risk) apply.
- watch/picker are interactive TTY loops — smoke-tested via non-TTY error paths only.
- `_fetch_url` reads max 1MB and decodes with errors="replace".
- Colors dataclass is frozen-in-shape (29 slots); F11 routes hues into EXISTING slots (ui_label/session_label), no new slots.

## Specific review questions
1. **F2 light branch**: are all 29 slots coherent in light mode? Any slot that still gets a DARK surface or LIGHT ink (would be invisible)? Check `ui_label` (adjust_lightness on light-mode accent), `banner_border`, `input_rule`, `response_border`.
2. **F12 extra keys**: can `extra` be abused? (e.g. a YAML with key `colors` appearing twice, or extra keys that shadow dataclass fields on re-parse?) Check `from_dict`/`to_dict` round-trip logic for key collisions.
3. **F7 rename**: `skin.dump(dst)` then `path.unlink()` — same-file edge cases? What if old path == dst path (rename to sanitized same name)? Idempotency?
4. **F7 uninstall --force**: any path where `path.unlink()` fails noisily (permission)? Acceptable.
5. **F9 sync_banner_art**: regex `[(bold\s+)?(#[0-9a-fA-F]{6})]` — does it handle `[bold #X]` with TWO spaces, or 8-digit hexes in art? Does the mapping break when art has 2+ distinct hexes with EQUAL lightness?
6. **F5 diff**: `_channels()` on 8-digit hex values or non-string — crash paths? `getattr(skin.branding, f)` on Branding dataclass — all six fields exist?
7. **CLI enum move**: Harmony/Mode Enums moved above `app = typer.Typer(...)` — any forward-ref or import-order issue at module load?
8. **picker `_read_key`**: raw mode + Ctrl-C path (`\x03` returns "quit") — is termios always restored via finally? What about exceptions mid-read?
9. **watch loop**: `time.sleep(interval)` with interval option min=0.1 — CPU burn? Missing-file loop behavior?
10. **install-url → install(file=tmp)**: install's non-interactive branch auto-answers "y" to warnings — confirm fetched-skin warnings path can't hang waiting for stdin in a CLI context.
11. **test suite**: any test that asserts on UNSTABLE ordering or that would flake on Windows (paths, encoding)?
12. **Anything in the diff that breaks the 8 EVA templates' output** vs 0.2.0 (byte-identity of colors for classic harmonies is regression-tested; banner art hexes now CHANGE by design — is anything else silently different?)

## Verification you can run
- `cd /home/meow/hermes-skins-engine && .venv/bin/python -m pytest tests/ -q` (expect 211 pass)
- `python3 -m py_compile src/hermes_skins/*.py`
- Read the diff: `git diff 10e2bdc..f83bc5c`

## Output format
Write findings to `audit-brain/p2-findings.md` with severity (CRITICAL/HIGH/MEDIUM/LOW/NIT), file:line, evidence (code snippet), and a concrete fix suggestion for each. End with a verdict line: `VERDICT: <PASS|PASS-WITH-FINDINGS|FAIL>` + one-paragraph summary.
