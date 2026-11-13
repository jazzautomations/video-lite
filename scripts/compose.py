#!/usr/bin/env python3
"""Write a starting storyboard and show the reference.

    compose.py formats | themes | kinds | symbols
    compose.py new --format F --theme T --out FILE [--voice V]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vl_common import THEMES  # noqa: E402
from vl_icons import FA, NAMED  # noqa: E402

T = "TROQUE: "
FORMATS = {
    "explainer": ("ensinar ou apresentar algo em 4 cenas (simples)", [
        {"kind": "title", "title": T + "nome", "subtitle": T + "o que é, em uma linha", "narration": T + "frase de abertura"},
        {"kind": "bullets", "title": T + "por que importa", "bullets": [T + "ponto 1", T + "ponto 2", T + "ponto 3"], "narration": [T + "frase do ponto 1", T + "frase do ponto 2", T + "frase do ponto 3"]},
        {"kind": "terminal", "lines": [T + "$ comando", T + "saída"], "narration": T + "mostre funcionando"},
        {"kind": "cta", "title": T + "chamada", "subtitle": T + "link ou próximo passo", "narration": T + "frase final"},
    ]),
    "promo": ("anunciar/lançar em 3 cenas rápidas", [
        {"kind": "title", "title": T + "produto", "subtitle": T + "promessa", "narration": T + "gancho"},
        {"kind": "bullets", "title": T + "o que muda", "bullets": [T + "benefício 1", T + "benefício 2"], "narration": [T + "frase do benefício 1", T + "frase do benefício 2"]},
        {"kind": "cta", "title": T + "chamada", "subtitle": T + "link", "narration": T + "convite"},
    ]),
    "demo": ("mostrar um fluxo no terminal", [
        {"kind": "title", "title": T + "o que vamos fazer", "subtitle": T + "contexto", "narration": T + "introdução"},
        {"kind": "terminal", "lines": [T + "$ passo 1", T + "resultado"], "narration": T + "passo 1"},
        {"kind": "terminal", "lines": [T + "$ passo 2", T + "resultado"], "narration": T + "passo 2"},
        {"kind": "quote", "title": T + "resultado em uma frase", "subtitle": "", "narration": T + "fechamento"},
    ]),
    "explainer-motion": ("explicar com animação e ilustrações (6 cenas, ~40 s)", [
        {"kind": "title", "title": T + "tema", "subtitle": T + "o que é, em uma linha", "symbol": T + "símbolo (ex.: fa-lightbulb-o, ☿, 🔥)", "narration": T + "abertura"},
        {"kind": "kinetic", "text": T + "frase de impacto com uma *palavra* destacada", "narration": T + "a mesma frase, falada"},
        {"kind": "split", "title": T + "conceito", "text": T + "explicação curta (1 a 2 frases)", "symbol": T + "símbolo", "narration": T + "explique o conceito"},
        {"kind": "icons", "title": T + "partes", "items": [{"icon": T + "fa-cog", "label": T + "parte 1"}, {"icon": T + "fa-book", "label": T + "parte 2"}, {"icon": T + "fa-globe", "label": T + "parte 3"}], "narration": [T + "frase da parte 1", T + "frase da parte 2", T + "frase da parte 3"]},
        {"kind": "wheel", "title": T + "como se ligam", "nodes": [T + "etapa 1", T + "etapa 2", T + "etapa 3", T + "etapa 4"], "center": T + "centro (palavra ou símbolo)", "narration": [T + "frase da etapa 1", T + "frase da etapa 2", T + "frase da etapa 3", T + "frase da etapa 4"]},
        {"kind": "cta", "title": T + "chamada", "subtitle": T + "link ou próximo passo", "narration": T + "fechamento"},
    ]),
    "story": ("contar uma história/ideia com ritmo (7 cenas, ~60 s)", [
        {"kind": "title", "title": T + "título", "subtitle": T + "subtítulo", "narration": T + "abertura"},
        {"kind": "symbol", "symbol": T + "símbolo do personagem/tema", "title": T + "nome", "subtitle": T + "quem/o que é", "narration": T + "apresente"},
        {"kind": "split", "title": T + "origem", "text": T + "de onde vem (1 a 2 frases)", "shape": "circle", "narration": T + "conte a origem"},
        {"kind": "geometry", "shape": T + "forma (flower, hexagram, spiral, ouroboros, eye, wave…)", "title": T + "a ideia central", "narration": T + "a ideia"},
        {"kind": "kinetic", "text": T + "a virada da história com uma *palavra* forte", "narration": T + "a mesma frase"},
        {"kind": "quote", "title": T + "citação", "subtitle": T + "autor", "narration": T + "leia a citação"},
        {"kind": "cta", "title": T + "fechamento", "subtitle": T + "próximo passo", "narration": T + "frase final"},
    ]),
    "listicle": ("N coisas/princípios: visão geral na roda + uma cena por item (~60 s)", [
        {"kind": "title", "title": T + "os N itens de algo", "subtitle": T + "subtítulo", "narration": T + "abertura"},
        {"kind": "wheel", "title": T + "visão geral", "nodes": [T + "item 1", T + "item 2", T + "item 3", T + "item 4"], "narration": [T + "frase do item 1", T + "frase do item 2", T + "frase do item 3", T + "frase do item 4"]},
        {"kind": "symbol", "symbol": T + "símbolo do item 1", "title": T + "item 1", "subtitle": T + "a ideia em uma linha", "narration": T + "explique o item 1"},
        {"kind": "geometry", "shape": T + "forma do item 2", "title": T + "item 2", "subtitle": T + "a ideia em uma linha", "narration": T + "explique o item 2"},
        {"kind": "split", "title": T + "item 3", "text": T + "explicação curta", "symbol": T + "símbolo", "narration": T + "explique o item 3"},
        {"kind": "wheel", "title": T + "item 4", "nodes": [T + "item 1", T + "item 2", T + "item 3", T + "item 4"], "active": 4, "narration": T + "explique o item 4"},
        {"kind": "cta", "title": T + "chamada", "subtitle": T + "link", "narration": T + "fechamento"},
    ]),
}

KINDS_HELP = [
    ("title", 'título grande palavra por palavra + sublinhado', '{"kind": "title", "title": "O Caibalion", "subtitle": "os 7 princípios", "symbol": "☿"}'),
    ("bullets", 'lista com ícones, um item por vez', '{"kind": "bullets", "title": "Por quê", "bullets": ["roda em PC velho", {"text": "grátis", "icon": "fa-gift"}]}'),
    ("terminal", 'janela de terminal digitando', '{"kind": "terminal", "lines": ["$ jazz -p \\"corrige\\"", "ok: 12 testes"]}'),
    ("quote", 'citação com aspas grandes', '{"kind": "quote", "title": "Como acima, assim abaixo.", "subtitle": "Tábua de Esmeralda"}'),
    ("cta", 'chamada final com botão', '{"kind": "cta", "title": "Experimente", "subtitle": "github.com/x/y"}'),
    ("symbol", 'símbolo enorme desenhado no traço + brilho', '{"kind": "symbol", "symbol": "☯", "title": "Polaridade", "subtitle": "tudo é duplo", "spin": true}'),
    ("geometry", 'geometria desenhada aos poucos', '{"kind": "geometry", "shape": "flower", "title": "Flor da vida"}'),
    ("wheel", 'roda/diagrama: nós em círculo, um por vez; active destaca 1', '{"kind": "wheel", "title": "7 princípios", "nodes": ["Mentalismo", "Ritmo", "Gênero"], "active": 2, "center": "☿"}'),
    ("icons", 'grade de ícones com legenda (1 a 8)', '{"kind": "icons", "title": "Ferramentas", "items": [{"icon": "fa-cogs", "label": "motor"}, {"icon": "🚀", "label": "deploy"}]}'),
    ("kinetic", 'frase grande palavra por palavra, *palavra* = destaque', '{"kind": "kinetic", "text": "O Todo é *Mente*"}'),
    ("split", 'texto de um lado, ilustração (symbol ou shape) do outro', '{"kind": "split", "title": "Corpus Hermeticum", "text": "Textos gregos…", "symbol": "fa-book", "side": "right"}'),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("formats")
    sub.add_parser("themes")
    sub.add_parser("kinds")
    sub.add_parser("symbols")
    n = sub.add_parser("new")
    n.add_argument("--format", choices=sorted(FORMATS), default="explainer-motion")
    n.add_argument("--theme", choices=sorted(THEMES), default="terminal-green")
    n.add_argument("--voice", default="pt-br")
    n.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "formats":
        for k, (why, scenes) in sorted(FORMATS.items()):
            print("%-17s %s\n%-17s   %s" % (k, why, "", " → ".join(s["kind"] for s in scenes)))
        return
    if a.cmd == "themes":
        for k, t in sorted(THEMES.items()):
            print("%-15s fonte %-13s partículas %-8s transições %s" % (k, t["font"], t["particles"], "/".join(t["transitions"])))
        return
    if a.cmd == "kinds":
        for k, why, ex in KINDS_HELP:
            print("%-9s %s\n          %s" % (k, why, ex))
        from vl_scenes import SHAPES
        print("\nshape (geometry/split): " + ", ".join(SHAPES))
        print("todas as cenas aceitam: narration, seconds, transition (fade/slide/zoom/wipe/iris/cut), camera (auto/none)")
        return
    if a.cmd == "symbols":
        print("caractere direto: ☿ ☤ ☉ ☽ ♀ ♂ ☯ ⚖ ⚛ ☥ ✡ ★ ✦ ∞ 🜁 🜂 🜃 🜄 △ ▽ ⊙ ⬡ ⛤ ♪  |  emoji: 🔥 🚀 💡 👁 ✨")
        print("nomes: " + ", ".join(sorted(NAMED)))
        print("Font Awesome 4 (fa-NOME): " + ", ".join(sorted(FA)))
        return
    if os.path.exists(a.out):
        sys.exit("já existe %s: edite esse ou escolha outro --out" % a.out)
    sb = {"theme": a.theme, "voice": a.voice, "scenes": json.loads(json.dumps(FORMATS[a.format][1]))}
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(sb, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print("escrito %s (formato %s, tema %s). Agora troque TODO texto \"TROQUE:\" por conteúdo real." % (a.out, a.format, a.theme))


if __name__ == "__main__":
    main()
