#!/usr/bin/env python3
"""Render a video-lite storyboard to MP4: render.py storyboard.json --out video.mp4 [--draft] [--fast]."""
import argparse
import difflib
import fcntl
import re
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vl_common import THEMES, cache_dir, espeak, mbrola_voices, x264_env  # noqa: E402

try:
    import cairo
except ImportError:
    sys.exit("falta o pycairo (python3-cairo): rode scripts/doctor.py — no Debian/antiX: sudo apt install python3-cairo")

import vl_audio  # noqa: E402
import vl_scenes  # noqa: E402
from vl_draw import Painter  # noqa: E402
from vl_motion import ease_in_out_cubic  # noqa: E402

KINDS = tuple(vl_scenes.KINDS)
TRANSITIONS = ("fade", "slide", "zoom", "wipe", "iris", "cut")
PAD_S = 0.6       # pause after each narration (the next scene's transition plays here)
MIN_S = 2.5       # shortest scene
TRANS_S = 0.6     # scene transition length (overlaps the start of the incoming scene)
FADE_S = 0.4      # fade from/to black at the very start/end
CHARS_PER_S = 14  # narration pace check
BUDGET = 10.0     # target render seconds per video second (90 s video -> 15 min)


def die(msg):
    sys.exit("render: " + msg)


def check(sb):
    if not isinstance(sb.get("scenes"), list) or not sb["scenes"]:
        die("storyboard sem \"scenes\"")
    bad = []

    def walk(v, where):
        if isinstance(v, str) and "TROQUE:" in v:
            bad.append(where)
        elif isinstance(v, list):
            for i, x in enumerate(v):
                walk(x, "%s[%d]" % (where, i))
        elif isinstance(v, dict):
            for k, x in v.items():
                walk(x, where + "." + k)
    walk(sb, "storyboard")
    if bad:
        die("ainda tem texto de modelo (TROQUE:) em: " + ", ".join(bad[:8]) + " — troque por conteúdo real")
    warn = []
    prev = []
    for i, s in enumerate(sb["scenes"]):
        if not isinstance(s, dict) or s.get("kind") not in KINDS:
            k = s.get("kind") if isinstance(s, dict) else s
            near = difflib.get_close_matches(str(k), KINDS, 1)
            die("cena %d: kind %r não existe%s (use %s)" % (i, k, (" — quis dizer %r?" % near[0]) if near else "", ", ".join(KINDS)))
        tr = s.get("transition")
        if tr and tr not in TRANSITIONS:
            die("cena %d: transition %r não existe (use %s)" % (i, tr, ", ".join(TRANSITIONS)))
        for sent in vl_audio.split_sentences(s.get("narration")):
            if URL_RE.search(sent):
                die("cena %d narration: tem link/e-mail/caminho falado (%r) → tire da narração e ponha só na tela (cta subtitle)" % (i, sent[:60]))
            if len(sent) > 160:
                die("cena %d narration: frase de %d caracteres → quebre em frases de até 110" % (i, len(sent)))
            if len(sent) > 110:
                warn.append("cena %d: frase longa (%d caracteres); até 110 soa melhor" % (i, len(sent)))
        prev.append(s["kind"])
        if len(prev) >= 3 and prev[-1] == prev[-2] == prev[-3]:
            warn.append("cenas %d-%d: três %r seguidas; alterne com symbol/geometry/kinetic/wheel" % (i - 2, i, s["kind"]))
    first = vl_audio.split_sentences(sb["scenes"][0].get("narration"))
    if first and re.match(r"(?i)^(ol[aá]|oi|neste v[ií]deo|hoje vamos)", first[0]):
        warn.append("cena 0: abertura fraca (\"%s…\"); comece pelo assunto" % first[0][:20])
    if sb.get("theme", "terminal-green") not in THEMES:
        die("tema %r não existe (compose.py themes)" % sb.get("theme"))
    return warn


URL_RE = re.compile(r"https?://|www\.|\w+\.(com|br|io|dev|org|net)\b|@\w|\w/\w+/")


# ---------- performance ----------

def load_bench():
    try:
        with open(os.path.join(cache_dir(), "bench.json")) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def choose_speed(W, H, fps, fast):
    """(x264 preset, quality 0..1) to keep render time near BUDGET x the video length."""
    if fast:
        return "ultrafast", 0.5
    b = load_bench()
    if not b:
        return ("veryfast" if (os.cpu_count() or 1) >= 2 else "superfast"), 1.0
    px = (W * H) / float(b.get("pixels", 1280 * 720))
    per_frame = 1000.0 * BUDGET / fps
    draw = b.get("draw_ms", 60) * px * 1.15
    for preset in ("veryfast", "superfast", "ultrafast"):
        enc = b.get("enc_ms", {}).get(preset)
        if enc is not None and draw + enc * px <= per_frame:
            return preset, 1.0
    enc = b.get("enc_ms", {}).get("ultrafast", 100) * px
    return "ultrafast", (1.0 if draw * 0.8 + enc <= per_frame else 0.5)


# ---------- compositing ----------

def scene_transition(sb, theme, s):
    if s["idx"] == 0:
        return "cut"
    tr = s.get("transition") or sb.get("transition")
    if tr:
        return tr
    lst = theme.get("transitions") or ["fade"]
    return lst[(s["idx"] - 1) % len(lst)]


def compose_frame(P, ctx, g, A, tA, B, tB, kind, p):
    """One frame: background, particles, content (A alone, or A->B transition), captions."""
    W, H = P.W, P.H
    ctx.set_source_surface(P.bg, 0, 0)
    ctx.paint()
    P.particles(ctx, g)
    if B is None:
        vl_scenes.draw(P, ctx, A, tA)
        P.caption(ctx, A, tA)
        return
    e = ease_in_out_cubic(p)
    if kind == "slide":
        ctx.save()
        ctx.translate(-e * W * 0.6, 0)
        ctx.push_group()
        vl_scenes.draw(P, ctx, A, tA)
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(1 - e)
        ctx.restore()
        ctx.save()
        ctx.translate((1 - e) * W * 0.6, 0)
        ctx.push_group()
        vl_scenes.draw(P, ctx, B, tB)
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(e)
        ctx.restore()
    elif kind == "zoom":
        for S, ts, z, a in ((A, tA, 1 + 0.25 * e, 1 - e), (B, tB, 0.85 + 0.15 * e, e)):
            if a <= 0.01:
                continue
            ctx.save()
            ctx.translate(W / 2, H / 2)
            ctx.scale(z, z)
            ctx.translate(-W / 2, -H / 2)
            ctx.push_group()
            vl_scenes.draw(P, ctx, S, ts)
            ctx.pop_group_to_source()
            ctx.paint_with_alpha(a)
            ctx.restore()
    elif kind in ("wipe", "iris"):
        vl_scenes.draw(P, ctx, A, tA)
        ctx.save()
        ctx.new_path()
        if kind == "wipe":
            x = e * (W + 80 * P.u)
            ctx.rectangle(0, 0, x, H)
        else:
            ctx.arc(W / 2, H / 2, max(1, e * (W * 0.62)), 0, 6.2832)
        ctx.clip()
        ctx.set_source_surface(P.bg, 0, 0)
        ctx.paint()
        P.particles(ctx, g)
        vl_scenes.draw(P, ctx, B, tB)
        ctx.restore()
        ctx.set_line_width(3 * P.u)
        ctx.set_source_rgba(P.ac[0], P.ac[1], P.ac[2], 0.9 * (1 - abs(2 * p - 1)))
        ctx.new_path()
        if kind == "wipe":
            ctx.move_to(x, 0)
            ctx.line_to(x, H)
        else:
            ctx.arc(W / 2, H / 2, max(1, e * (W * 0.62)), 0, 6.2832)
        ctx.stroke()
    else:  # fade
        for S, ts, a in ((A, tA, 1 - e), (B, tB, e)):
            if a <= 0.01:
                continue
            ctx.push_group()
            vl_scenes.draw(P, ctx, S, ts)
            ctx.pop_group_to_source()
            ctx.paint_with_alpha(a)
    P.caption(ctx, B, tB)


def render_frames(P, scenes, sb, theme, fps, write, frames=None, progress=None):
    """Draw every frame (or only the frame numbers in `frames`) and pass the surface to write()."""
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, P.W, P.H)
    ctx = cairo.Context(surf)
    total = sum(s["dur"] for s in scenes)
    nframes = int(round(total * fps))
    starts, acc = [], 0.0
    for s in scenes:
        starts.append(acc)
        acc += s["dur"]
    kinds = [scene_transition(sb, theme, s) for s in scenes]
    si = 0
    for n in range(nframes) if frames is None else frames:
        g = n / float(fps)
        while si + 1 < len(scenes) and g >= starts[si + 1]:
            si += 1
        while si > 0 and g < starts[si]:
            si -= 1
        S = scenes[si]
        t = g - starts[si]
        tr = kinds[si]
        if si > 0 and tr != "cut" and t < TRANS_S:
            A = scenes[si - 1]
            compose_frame(P, ctx, g, A, A["dur"] + t, S, t, tr, t / TRANS_S)
        else:
            compose_frame(P, ctx, g, S, t, None, 0, None, 0)
        fade = min(1.0, g / FADE_S, (total - g) / FADE_S)
        if fade < 1:
            ctx.set_source_rgba(0, 0, 0, 1 - max(0.0, fade))
            ctx.paint()
        surf.flush()
        write(n, surf)
        if progress:
            progress(n, nframes)
    return nframes


def prepare_scenes(sb, voice, rate, tmp, theme, W, H, quality):
    """TTS per sentence (cached), durations, layouts. Returns (painter, scenes, warnings)."""
    scenes, warn = [], []
    for i, s in enumerate(sb["scenes"]):
        s = dict(s, idx=i)
        try:
            vl_audio.scene_speech(s, voice, rate)
        except vl_audio.VoiceError as e:
            die(str(e))
        sp = s["speech"]
        want = float(s.get("seconds") or 0)
        s["dur"] = max(MIN_S, vl_audio.LEAD_S + sp + PAD_S, want)
        if want and vl_audio.LEAD_S + sp > want:
            warn.append("cena %d: a fala (%.1fs) não cabe nos %ss pedidos — estiquei para %.1fs" % (i, sp, s.get("seconds"), s["dur"]))
        if sp > 12:
            warn.append("cena %d: %.0fs de fala numa cena só; divida em duas cenas" % (i, sp))
        scenes.append(s)
    P = Painter(theme, W, H, quality=quality, captions=sb.get("captions", False) is True)
    for s in scenes:
        try:
            vl_scenes.prepare(P, s)
        except ValueError as e:
            die(str(e))
        except KeyError as e:
            die("cena %d (%s): campo faltando %s" % (s["idx"], s["kind"], e))
    return P, scenes, warn


def sfx_events(sb, theme, scenes):
    """Whoosh on transitions, pop on reveals, riser into the closing cta."""
    if sb.get("sfx", True) is False:
        return []
    ev, start = [], 0.0
    for s in scenes:
        if s["idx"] > 0 and scene_transition(sb, theme, s) != "cut":
            ev.append((start - 0.2, "whoosh", 0.8))
        c = s.get("_c", {})
        for st in (c.get("starts") or [])[:8]:
            ev.append((start + st, "pop", 0.6))
        if s["kind"] in ("symbol", "title") and (s.get("symbol") or s.get("icon")):
            ev.append((start + 0.25, "pop", 0.5))
        if s["kind"] == "cta" and s["idx"] == len(scenes) - 1 and start > 2.5:
            ev.append((start - 1.6, "riser", 0.6))
        start += s["dur"]
    return [e for e in ev if e[0] >= 0]


def pick_voice(sb):
    voice = sb.get("voice", "pt-br")
    exe, _ = espeak()
    if voice in ("pt-br", "pt") and "mb-br3" in mbrola_voices():
        voice = "mb-br3"  # the MBROLA Brazilian voice sounds far less robotic
    if voice.startswith("mb-") and voice not in mbrola_voices():
        print("aviso: voz %s não instalada aqui (bash scripts/setup_voice.sh); usando pt-br" % voice)
        voice = "pt-br"
    if voice != "none" and not exe:
        die("sem voz: rode bash scripts/setup_voice.sh (sem root) ou use \"voice\": \"none\" no storyboard")
    # speaking rate is set here (~14 chars/s); the storyboard only nudges it with "speed" 0.9-1.15
    rate = vl_audio.voice_rate(voice, sb.get("speed", 1.0))
    return voice, rate, exe


def load_storyboard(path):
    try:
        with open(path, encoding="utf-8") as fh:
            sb = json.load(fh)
    except (OSError, ValueError) as e:
        die("não consegui ler %s: %s" % (path, e))
    if not isinstance(sb, dict):
        die("o storyboard precisa ser um objeto JSON com \"scenes\"")
    return sb, check(sb)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("storyboard")
    ap.add_argument("--out", required=True)
    ap.add_argument("--draft", action="store_true", help="480p, 20 fps, mais rápido")
    ap.add_argument("--fast", action="store_true", help="menos partículas, sem câmera, x264 ultrafast (máquina lenta)")
    ap.add_argument("--preset", help=argparse.SUPPRESS)
    ap.add_argument("--still", type=float, help="só um PNG do quadro nesse segundo (para conferir o visual)")
    a = ap.parse_args()
    ff = shutil.which("ffmpeg")
    if not ff:
        die("falta o ffmpeg: rode scripts/doctor.py")
    sb, warn0 = load_storyboard(a.storyboard)
    theme_name = sb.get("theme", "terminal-green")
    theme = THEMES[theme_name]
    W, H, fps = (854, 480, 20) if a.draft else (1280, 720, 24)
    preset, quality = choose_speed(W, H, fps, a.fast)
    if a.draft:
        preset = "ultrafast"
    if a.preset:
        preset = a.preset
    voice, rate, exe = pick_voice(sb)
    lock = open(os.path.join(tempfile.gettempdir(), "video-lite.lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("aguardando outro render.py terminar (dois ao mesmo tempo ficam 3-5x mais lentos)…", flush=True)
        fcntl.flock(lock, fcntl.LOCK_EX)
    tmp = tempfile.mkdtemp(prefix="video-lite-")
    t0 = time.time()
    try:
        P, scenes, warn = prepare_scenes(sb, voice, rate, tmp, theme, W, H, quality)
        warn = warn0 + warn
        total = sum(s["dur"] for s in scenes)
        if a.still is not None:
            out = a.out if a.out.endswith(".png") else os.path.splitext(a.out)[0] + ".png"
            n = min(int(round(total * fps)) - 1, int(a.still * fps))
            render_frames(P, scenes, sb, theme, fps, lambda i, surf: surf.write_to_png(out), frames=[n])
            print("ok: quadro %.1fs de %.1fs -> %s" % (a.still, total, out))
            return
        if total > 180:
            warn.append("vídeo de %.0fs: acima de 3 min fica cansativo para esse formato" % total)
        has_voice = any(s.get("sents") for s in scenes)
        track = os.path.join(tmp, "voice.wav")
        vl_audio.build_voice(scenes, track)
        try:
            audio = vl_audio.mix(track, total, tmp, theme_name, music=sb.get("music", True) is not False,
                                 sfx_events=sfx_events(sb, theme, scenes), has_voice=has_voice)
        except vl_audio.VoiceError as e:
            print("aviso: %s — sigo só com a voz" % e)
            audio = None
        t_audio = time.time() - t0
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        cmd = [ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", "%dx%d" % (W, H), "-r", str(fps), "-i", "-"]
        if audio:
            cmd += ["-i", audio]
        elif has_voice:
            cmd += ["-i", track]
        cmd += ["-c:v", "libx264", "-preset", preset, "-tune", "animation", "-crf", "20" if not a.draft else "23", "-pix_fmt", "yuv420p"]
        if audio:
            cmd += ["-c:a", "copy", "-shortest"]
        elif has_voice:
            cmd += ["-c:a", "aac", "-b:a", "128k", "-shortest"]
        cmd += ["-movflags", "+faststart", a.out]
        enc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, env=x264_env())
        print("renderizando %.1fs, %dx%d %d fps, x264 %s, qualidade %.1f (áudio pronto em %.0fs)" % (total, W, H, fps, preset, quality, t_audio), flush=True)

        def write(n, surf):
            try:
                enc.stdin.write(surf.get_data())
            except BrokenPipeError:
                die("ffmpeg parou: " + enc.stderr.read().decode(errors="replace").strip()[:400])

        def progress(n, nframes):
            if n and n % (fps * 10) == 0:
                el = time.time() - t0 - t_audio
                print("  %d/%d quadros (%.0fs, faltam ~%.0fs)" % (n, nframes, el, el / n * (nframes - n)), flush=True)
        render_frames(P, scenes, sb, theme, fps, write, progress=progress)
        enc.stdin.close()
        err = enc.stderr.read().decode(errors="replace")
        if enc.wait() != 0:
            die("ffmpeg falhou: " + err.strip()[:400])
        for w in warn:
            print("aviso: " + w)
        print("ok: %s — %.1fs, %dx%d, %d fps, %d cenas, voz %s, render em %.0fs" % (a.out, total, W, H, fps, len(scenes), voice if exe and voice != "none" else "nenhuma", time.time() - t0))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        lock.close()


if __name__ == "__main__":
    main()
