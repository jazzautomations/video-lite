#!/usr/bin/env python3
"""Check what video-lite needs on this machine and say how to fix what is missing.

    doctor.py           check tools, fonts, voice; measures speed once (saved in ~/.cache/video-lite)
    doctor.py --bench   measure speed again (render.py uses it to pick x264 preset / effects)
"""
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vl_common import cache_dir, emoji_font, espeak, family, installed_families, mbrola_voices, run, symbol_families, x264_env  # noqa: E402

ok = True


def line(good, what, fix=""):
    global ok
    ok = ok and good
    print(("ok   " if good else "FALTA ") + what + ("" if good or not fix else "  →  " + fix))


def bench(ff):
    """ms per 720p frame: drawing (a busy scene) and x264 encoding per preset."""
    import cairo
    from vl_common import THEMES
    from vl_draw import Painter
    import vl_scenes
    W, H, N = 1280, 720, 24
    P = Painter(THEMES["mystic"], W, H)
    s = {"kind": "wheel", "idx": 0, "dur": 6.0, "speech": 5.0, "title": "Sete princípios",
         "narration": "Um teste rápido de velocidade com legenda e animação.",
         "nodes": ["Mentalismo", "Correspondência", "Vibração", "Polaridade", "Ritmo", "Causa e Efeito", "Gênero"], "center": "☿"}
    vl_scenes.prepare(P, s)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    frames = []
    t0 = time.time()
    for i in range(N):
        t = 1.0 + i / 24.0
        ctx.set_source_surface(P.bg, 0, 0)
        ctx.paint()
        P.particles(ctx, t)
        vl_scenes.draw(P, ctx, s, t)
        P.caption(ctx, s, t)
        surf.flush()
        frames.append(bytes(surf.get_data()))
    draw_ms = (time.time() - t0) * 1000 / N
    enc = {}
    for preset in ("ultrafast", "superfast", "veryfast"):
        cmd = [ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", "%dx%d" % (W, H), "-r", "24",
               "-i", "-", "-c:v", "libx264", "-preset", preset, "-tune", "animation", "-crf", "20", "-pix_fmt", "yuv420p", "-f", "null", "-"]
        t0 = time.time()
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL, env=x264_env())
        for _ in range(2):
            for f in frames:
                p.stdin.write(f)
        p.stdin.close()
        p.wait()
        enc[preset] = round((time.time() - t0) * 1000 / (2 * N), 1)
    res = {"pixels": W * H, "draw_ms": round(draw_ms, 1), "enc_ms": enc, "when": time.strftime("%Y-%m-%d %H:%M")}
    with open(os.path.join(cache_dir(), "bench.json"), "w") as fh:
        json.dump(res, fh)
    return res


def main():
    line(sys.version_info >= (3, 8), "python3 >= 3.8 (" + sys.version.split()[0] + ")", "instale um python3 mais novo")
    try:
        import cairo
        line(True, "pycairo %s (cairo %s)" % (cairo.version, cairo.cairo_version_string()))
    except Exception:
        line(False, "pycairo", "sudo apt install python3-cairo  (ou: pip3 install --user pycairo)")
    try:
        import PIL
        line(True, "Pillow " + PIL.__version__)
    except Exception:
        print("aviso Pillow ausente: sem emoji colorido nem brilho borrado (pip3 install --user pillow)")
    ff = shutil.which("ffmpeg")
    line(bool(ff), "ffmpeg", "sudo apt install ffmpeg")
    if ff:
        enc = run([ff, "-hide_banner", "-encoders"]).stdout
        line("libx264" in enc, "encoder libx264", "um ffmpeg com libx264 (o do apt tem)")
        if "libx264" in enc:
            r = subprocess.run([ff, "-hide_banner", "-loglevel", "info", "-f", "lavfi", "-i", "color=c=gray:s=64x64:d=0.1", "-frames:v", "1",
                                "-c:v", "libx264", "-f", "null", "-"], capture_output=True, text=True, env=x264_env())
            line("capabilities: none" not in r.stderr, "x264 com SIMD (SSE2/MMX)",
                 "o libx264 deste sistema foi compilado sem asm (3x mais lento): sudo apt install libx264-164 e confira /usr/lib/i386-linux-gnu/i686/sse2")
        line(bool(shutil.which("ffprobe")), "ffprobe", "vem com o ffmpeg")
    es, _ = espeak()
    line(bool(es), "voz espeak-ng" + (" (" + es + ")" if es else ""),
         "bash " + os.path.join(HERE, "setup_voice.sh") + "  (sem root), ou sudo apt install espeak-ng; sem voz use \"voice\": \"none\"")
    if es:
        mb = mbrola_voices()
        print("info vozes MBROLA: " + (", ".join(mb) if mb else "nenhuma (bash setup_voice.sh instala mb-br3 sem root)"))
    have = installed_families()
    for role in ("sans", "serif-display", "mono", "icons"):
        f = family(role)
        good = have is None or f in have
        print(("ok   " if good else "aviso ") + "fonte %s: %s" % (role, f if good else "não achei (" + f + "): sudo apt install fonts-noto-core fonts-font-awesome"))
    print("info símbolos: " + ", ".join(symbol_families()))
    print("info emoji: " + (emoji_font() or "sem fonte de emoji colorido (sudo apt install fonts-noto-color-emoji)"))
    try:
        with open("/proc/meminfo") as fh:
            mem = int(fh.readline().split()[1]) // 1024
        print("info memória: %d MB — %s" % (mem, "use --draft primeiro" if mem < 3000 else "ok"))
    except OSError:
        pass
    path = os.path.join(cache_dir(), "bench.json")
    if ok and ff and ("--bench" in sys.argv or not os.path.exists(path)):
        print("medindo velocidade (uma vez, ~1 min em máquina velha)…", flush=True)
        try:
            r = bench(ff)
            print("info velocidade 720p: desenho %.0f ms/quadro, x264 %s ms/quadro (salvo em %s)" % (
                r["draw_ms"], ", ".join("%s %.0f" % kv for kv in r["enc_ms"].items()), path))
        except Exception as e:  # never block the golden path on the benchmark
            print("aviso: não consegui medir a velocidade (%s); render.py usa o padrão" % e)
    elif os.path.exists(path):
        with open(path) as fh:
            r = json.load(fh)
        print("info velocidade 720p (%s): desenho %.0f ms/quadro, x264 %s" % (
            r.get("when", "?"), r["draw_ms"], ", ".join("%s %.0f" % kv for kv in r["enc_ms"].items())))
    print("tudo pronto" if ok else "corrija o que FALTA e rode de novo")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
