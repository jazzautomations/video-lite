#!/usr/bin/env python3
"""Self-test: render every scene kind for ~1.5 s in draft and check the MP4 with ffprobe.

    python3 selftest.py [--keep DIR] [--theme mystic] [--voice]

Without --voice the test is silent (fast, no espeak needed). Exit code 0 = all good.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vl_common import THEMES  # noqa: E402

SCENES = [
    {"kind": "title", "title": "Teste de *título*", "subtitle": "subtítulo com acento: ação, coração", "symbol": "☿"},
    {"kind": "bullets", "title": "Lista", "bullets": [{"text": "primeiro ponto", "icon": "fa-rocket"}, "segundo ponto bem mais longo para quebrar linha", {"text": "terceiro", "icon": "🔥"}]},
    {"kind": "terminal", "lines": ["$ jazz -p \"teste\"", "ok: 12 testes passando"]},
    {"kind": "quote", "title": "O lábio da sabedoria está fechado, exceto aos ouvidos do entendimento.", "subtitle": "O Caibalion"},
    {"kind": "cta", "title": "Experimente", "subtitle": "github.com/exemplo"},
    {"kind": "symbol", "symbol": "☯", "title": "Polaridade", "subtitle": "tudo é duplo", "spin": True},
    {"kind": "symbol", "symbol": "💡", "title": "Emoji"},
    {"kind": "geometry", "shape": "flower", "title": "Flor da vida"},
    {"kind": "geometry", "shape": ["circle", "hexagram"], "title": "Hexagrama"},
    {"kind": "geometry", "shape": "ouroboros", "title": "Ouroboros"},
    {"kind": "geometry", "shape": "wave", "title": "Vibração"},
    {"kind": "geometry", "shape": "pendulum", "title": "Ritmo"},
    {"kind": "geometry", "shape": "arrows", "labels": ["causa", "efeito", "causa"], "title": "Causa e efeito"},
    {"kind": "geometry", "shape": "spiral"},
    {"kind": "geometry", "shape": "eye", "title": "Mente"},
    {"kind": "wheel", "title": "Sete princípios", "nodes": ["Mentalismo", "Correspondência", "Vibração", "Polaridade", "Ritmo", "Causa e Efeito", "Gênero"], "active": 3, "center": "☿"},
    {"kind": "wheel", "nodes": [{"label": "um", "icon": "fa-cog"}, {"label": "dois", "icon": "fa-book"}, "três"], "center": "Centro"},
    {"kind": "icons", "title": "Ícones", "items": [{"icon": "fa-cogs", "label": "engrenagens"}, {"icon": "fa-book", "label": "livro"}, {"icon": "☿", "label": "mercúrio"}, {"icon": "🚀", "label": "foguete"}, {"icon": "fa-globe", "label": "mundo"}]},
    {"kind": "kinetic", "text": "O Todo é *Mente* e o universo é mental"},
    {"kind": "split", "title": "Corpus Hermeticum", "text": "Textos gregos dos séculos II e III atribuídos a Hermes Trismegisto.", "symbol": "fa-book"},
    {"kind": "split", "title": "Correspondência", "bullets": ["como acima", "assim abaixo"], "shape": "hexagram", "side": "left"},
]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keep", help="pasta para guardar o MP4 e quadros (padrão: temporária, apagada)")
    ap.add_argument("--theme", default="mystic", choices=sorted(THEMES))
    ap.add_argument("--voice", action="store_true", help="narra cada cena (testa espeak + legendas)")
    ap.add_argument("--full", action="store_true", help="720p em vez de --draft")
    a = ap.parse_args()
    work = a.keep or tempfile.mkdtemp(prefix="vl-selftest-")
    os.makedirs(work, exist_ok=True)
    scenes = []
    for i, s in enumerate(SCENES):
        s = dict(s, seconds=1.6)
        if a.voice:
            s["narration"] = "Cena %d." % (i + 1)
        scenes.append(s)
    sb = {"theme": a.theme, "voice": "pt-br" if a.voice else "none", "scenes": scenes}
    path = os.path.join(work, "selftest.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(sb, fh, ensure_ascii=False, indent=1)
    out = os.path.join(work, "selftest.mp4")
    t0 = time.time()
    cmd = [sys.executable, os.path.join(HERE, "render.py"), path, "--out", out] + ([] if a.full else ["--draft"])
    r = subprocess.run(cmd, capture_output=True, text=True)
    el = time.time() - t0
    fails = []
    if r.returncode != 0:
        fails.append("render falhou: " + (r.stderr or r.stdout).strip()[-600:])
    else:
        probe = shutil.which("ffprobe")
        q = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height", "-of", "json", out],
                           capture_output=True, text=True)
        info = json.loads(q.stdout or "{}")
        dur = float(info.get("format", {}).get("duration", 0))
        want = sum(max(2.5, s["seconds"]) for s in scenes)
        v = [x for x in info.get("streams", []) if x.get("codec_type") == "video"]
        if not v:
            fails.append("sem vídeo")
        if abs(dur - want) > 1.0:
            fails.append("duração %.1fs, esperado ~%.1fs" % (dur, want))
        print("render: %.0fs para %.1fs de vídeo (%d cenas, todos os kinds) — %s" % (el, dur, len(scenes), out))
    if a.keep and not fails:
        print("quadros:  ffmpeg -i %s -vf fps=1/2.5,scale=320:-1,tile=5x5 -frames:v 1 %s" % (out, os.path.join(work, "sheet.png")))
    if not a.keep:
        shutil.rmtree(work, ignore_errors=True)
    if fails:
        print("FALHOU: " + "; ".join(fails))
        sys.exit(1)
    print("ok: selftest passou")


if __name__ == "__main__":
    main()
