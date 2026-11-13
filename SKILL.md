---
name: video-lite
description: "Make short narrated videos with real motion graphics (animated titles, kinetic text, symbols drawn on, sacred geometry, diagrams, icon grids, transitions, particles) using Python + pycairo + ffmpeg + espeak-ng — no Node, no browser, no GPU. Built for old 32-bit machines (i686, 2 GB RAM). Use for an explainer, story, list, promo or demo MP4 with voice, music bed and sound effects."
license: MIT
---

# Video Lite v2

A finished MP4 from a small storyboard JSON. Every frame is vector art drawn with cairo
(antialiased text, symbols, geometry, glows, particles, camera moves, scene transitions) and
encoded with ffmpeg; the voice is espeak-ng/MBROLA (pt-BR and English) over a soft procedural
music bed that ducks under the voice, with whoosh/pop sound effects on cuts and reveals. Runs on
an old Pentium M: ~90 s of 720p video in about 7–8 min (draft 480p: ~4 min). No Node, Chromium, GPU, models or network.

`<skill-dir>` below is the folder of this SKILL.md. Run every command from the user's
project folder; outputs go there.

## Golden path — do exactly this, in order

```bash
# 1. Check the machine ONCE (also measures its speed, ~1 min). It says what is missing and how to fix it.
python3 <skill-dir>/scripts/doctor.py
#    No voice? On Debian/Ubuntu/antiX this installs espeak-ng + MBROLA pt-BR in ~/.local, without root:
bash <skill-dir>/scripts/setup_voice.sh

# 2. Start from a FORMAT (the job) and a THEME (the feel):
python3 <skill-dir>/scripts/compose.py formats   # explainer-motion / story / listicle / explainer / promo / demo
python3 <skill-dir>/scripts/compose.py themes    # mystic, neon, terminal-green, sunset, ocean, paper, mono
python3 <skill-dir>/scripts/compose.py new --format explainer-motion --theme neon --out storyboard.json
#    Then edit storyboard.json: EVERY "TROQUE:" placeholder must become real content for THIS
#    video (render refuses leftovers). You may add, remove or reorder scenes freely.
#    Narration pace: about 14 characters per second. One idea per scene, 1–2 sentences.

# 3. Render. Blocks until the MP4 is written. --draft = 480p, faster: use it first on old machines.
python3 <skill-dir>/scripts/render.py storyboard.json --out video.mp4 --draft
python3 <skill-dir>/scripts/render.py storyboard.json --out video.mp4
#    Optional: look at ONE frame before a long render (writes video.png):
python3 <skill-dir>/scripts/render.py storyboard.json --out video.mp4 --still 12.5

# 4. Verify the real file (duration, video+audio streams) and LOOK at the contact sheet PNG.
python3 <skill-dir>/scripts/verify.py video.mp4 --require-audio
```

Do NOT hand-write ffmpeg pipelines or draw frames yourself: render.py owns layout, text fit,
animation, timing and sync. If a step fails, read its message — it says what to change.
Slow machine and in a hurry? `render.py ... --fast` (fewer particles, no camera move).

## Storyboard

```json
{
  "theme": "mystic",
  "voice": "mb-br3",
  "scenes": [
    {"kind": "title", "title": "O Caibalion", "subtitle": "os sete princípios herméticos", "symbol": "☿",
     "narration": "Conheça o Caibalion e seus sete princípios."},
    {"kind": "kinetic", "text": "O Todo é *Mente*",
     "narration": "O primeiro princípio diz: o Todo é mente."},
    {"kind": "bullets", "title": "Na prática", "bullets": ["observe seus pensamentos", "mude o foco", "repita"],
     "narration": ["Observe seus pensamentos.", "Mude o foco.", "E repita todo dia."]},
    {"kind": "wheel", "title": "Os sete princípios", "center": "☿",
     "nodes": ["Mentalismo", "Correspondência", "Vibração", "Polaridade", "Ritmo", "Causa e Efeito", "Gênero"],
     "narration": "Mentalismo, correspondência, vibração, polaridade, ritmo, causa e efeito e gênero."},
    {"kind": "cta", "title": "Leia o livro", "subtitle": "domínio público desde 1908",
     "narration": "Leia e tire suas conclusões."}
  ]
}
```

Top level: `theme`, `voice` (`pt-br`, `en-us`, `es`… or MBROLA `mb-br3` / `mb-br1` / `mb-br4`, far
less robotic; with `pt-br`, `mb-br3` is used when installed; `"none"` = silent). The speaking rate is
set by render.py (~14 characters/s); `"speed": 0.9`–`1.15` nudges it (`rate` from v1 is ignored).
Optional: `transition` for every scene, `"music": false` (no soft chord bed under the voice),
`"sfx": false` (no whoosh/pop/riser), `"captions": true` (show the narration as subtitles; off by
default — the screen shows the key words, the voice tells the rest).

Every scene: `kind` (below), `narration`, optional `seconds` (default: the narration + a short
pause; can only make a scene longer), optional `transition` (`fade` | `slide` | `zoom` | `wipe` |
`iris` | `cut`; default: the theme's own rotation), optional `camera` (`auto` slow zoom/pan, or `none`).

**Sync items to the voice:** `narration` can be a list of sentences. When a `bullets`, `wheel`,
`icons` or `split` scene has N items and the narration has N sentences (or N+1: an intro first),
item k appears exactly when sentence k starts:

```json
{"kind": "bullets", "title": "Por quê", "bullets": ["roda em PC velho", "modelos grátis", "testa tudo"],
 "narration": ["Três motivos.", "Roda em computador velho.", "Usa modelos grátis.", "E testa antes de dizer pronto."]}
```

Do not put links, e-mails or file paths in `narration` (render refuses): show them on screen
(`cta` subtitle). Keep each sentence under ~110 characters.

### Scene kinds (`compose.py kinds` prints this list)

| kind | what you see | fields |
|---|---|---|
| `title` | big title word by word, drawn underline, optional symbol on top | `title`, `subtitle`, `symbol` (opt.) |
| `bullets` | title + items one by one, each with an icon | `title`, `bullets`: `["text", {"text": "…", "icon": "fa-rocket"}]` |
| `terminal` | terminal window typing | `lines`: `["$ comando", "saída"]` |
| `quote` | big quote mark, words fade in, author slides in | `title` (the quote), `subtitle` (author) |
| `cta` | closing call: title pops, subtitle in a glowing button | `title`, `subtitle`, `symbol` (opt.) |
| `symbol` | ONE huge symbol drawn stroke by stroke, then filled + glow, halo ring | `symbol`, `title`, `subtitle`, `spin` (true/false) |
| `geometry` | sacred geometry drawn progressively, then glows | `shape` (one name or a list), `title`, `subtitle`, `labels` (only for `arrows`) |
| `wheel` | N nodes (2–12) on a circle revealed one by one with lines to the center; the current one glows | `title`, `nodes`: `["a", {"label": "b", "icon": "fa-cog"}]`, `center` (word or symbol), `active` (1..N: highlight that node) |
| `icons` | grid of 1–8 icons with labels popping in | `title`, `items`: `[{"icon": "fa-cogs", "label": "motor"}]` |
| `kinetic` | big words appear in sync with the voice; `*word*` = accent color + glow | `text` |
| `split` | text column + illustration on the other side | `title`, `text` or `bullets`, and `symbol` OR `shape`, `side` (`right`/`left`: where the art goes) |

`shape` names: `circle`, `triangle`, `triangle-down`, `square`, `hexagon`, `hexagram`, `pentagram`,
`flower` (flower of life), `seed` (seed of life), `vesica`, `spiral` (golden), `eye` (eye in the
triangle), `ouroboros`, `wave` (vibration), `pendulum` (rhythm), `arrows` (cause → effect; use
`"labels": ["causa", "efeito", "causa"]`). Combine: `"shape": ["circle", "hexagram"]`.

`symbol` / `icon` / `center` accept (`compose.py symbols` lists all names):
- a character: `"☿"`, `"☤"`, `"☯"`, `"✡"`, `"⚖"`, `"∞"`, `"🜂"` (alchemy), `"♀"`, `"☉"`, `"☽"`…
- a Font Awesome 4 name: `"fa-cogs"`, `"fa-book"`, `"fa-rocket"`, `"fa-lightbulb-o"`, `"fa-globe"`, `"fa-terminal"`…
- a named symbol: `"mercurio"`, `"caduceu"`, `"yin-yang"`, `"balanca"`, `"fogo"`, `"agua"`, `"olho"`…
- an emoji: `"🔥"`, `"🚀"`, `"💡"` (color; shown with a pop, not drawn stroke by stroke).

A complete ~90 s example (hermetism, theme mystic, every illustration kind): `<skill-dir>/examples/caibalion.json`.

### Good taste, quickly
- Vary kinds: never 3 scenes of the same kind in a row; alternate text-heavy (`bullets`, `split`)
  with visual (`symbol`, `geometry`, `kinetic`, `wheel`).
- Titles short (≤ 5 words), subtitles ≤ 10 words, bullets ≤ 6 words each, at most 5 bullets.
- A list of N things: one `wheel` overview, then one scene per item (`symbol`/`geometry`), or
  `wheel` again with `"active": k`.
- Themes: `mystic` (indigo/gold, serif, stars), `neon` (magenta/cyan, synth grid), `terminal-green`
  (code), `sunset`, `ocean`, `paper` (light, serif), `mono`.

## Tests

`python3 <skill-dir>/scripts/selftest.py` renders every kind for a moment in draft and checks the
MP4 with ffprobe (exit 0 = ok). `--voice` also tests espeak + captions.
