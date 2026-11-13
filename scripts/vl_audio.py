"""Audio for video-lite: per-sentence TTS (cached), expressive MBROLA overlay, SFX, chord pad,
voice chain + sidechain ducking, two-pass EBU R128 loudness. Everything runs outside the frame loop.

Final product: one AAC .m4a that render.py muxes with -c:a copy.
"""
import array
import hashlib
import math
import os
import random
import re
import shutil
import subprocess
import wave

from vl_common import cache_dir, espeak

SR = 22050
GAP_S = 0.25      # silence between sentences of one scene
LEAD_S = 0.15     # silence before the first sentence of a scene
VOICE_RATE = {"mb-br1": 130, "mb-br3": 130, "mb-br4": 130, "pt-br": 160, "pt": 160}
# wider pitch range than the stock MBROLA voices (stock br3: "pitch 80 120", nearly monotone)
EXPRESSIVE = {"mb-br3": ("br3", "male", "76 138"), "mb-br1": ("br1", "male", "76 138"), "mb-br4": ("br4", "female", "140 240")}


def ffmpeg():
    return shutil.which("ffmpeg") or "ffmpeg"


def voice_rate(voice, speed=1.0):
    base = VOICE_RATE.get(voice, 160)
    return int(round(base * max(0.9, min(1.15, float(speed or 1.0)))))


def split_sentences(narration):
    """Narration (string or list) -> list of sentences."""
    if isinstance(narration, list):
        return [str(x).strip() for x in narration if str(x).strip()]
    text = (narration or "").strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?…])\s+", text)
    return [p.strip() for p in parts if p.strip()]


# ---------- expressive voice overlay (no root: symlinks into ~/.cache) ----------

def _data_dir(env):
    cands = []
    if env and env.get("ESPEAK_DATA_PATH"):
        cands.append(os.path.join(env["ESPEAK_DATA_PATH"], "espeak-ng-data"))
    cands += ["/usr/lib/i386-linux-gnu/espeak-ng-data", "/usr/lib/x86_64-linux-gnu/espeak-ng-data",
              "/usr/share/espeak-ng-data", "/usr/local/share/espeak-ng-data", "/opt/homebrew/share/espeak-ng-data"]
    for d in cands:
        if os.path.exists(os.path.join(d, "phontab")):
            return d
    return None


def expressive_voice(voice, env):
    """(voice_arg, env) using a wider-pitch copy of an MBROLA voice; falls back to (voice, env)."""
    if voice not in EXPRESSIVE:
        return voice, env
    src = _data_dir(env)
    if not src:
        return voice, env
    base = os.path.join(cache_dir(), "espeak")
    ov = os.path.join(base, "espeak-ng-data")
    name = voice + "-vl"
    try:
        os.makedirs(os.path.join(ov, "voices", "mb"), exist_ok=True)
        for e in os.listdir(src):
            if e != "voices" and not os.path.lexists(os.path.join(ov, e)):
                os.symlink(os.path.join(src, e), os.path.join(ov, e))
        for e in os.listdir(os.path.join(src, "voices")):
            if e != "mb" and not os.path.lexists(os.path.join(ov, "voices", e)):
                os.symlink(os.path.join(src, "voices", e), os.path.join(ov, "voices", e))
        mbdir = os.path.join(src, "voices", "mb")
        if os.path.isdir(mbdir):
            for e in os.listdir(mbdir):
                if not os.path.lexists(os.path.join(ov, "voices", "mb", e)):
                    os.symlink(os.path.join(mbdir, e), os.path.join(ov, "voices", "mb", e))
        mb, gender, pitch = EXPRESSIVE[voice]
        with open(os.path.join(ov, "voices", "mb", name), "w") as fh:
            fh.write("language pt-br 6\nname vl-%s\ngender %s\npitch %s\ndictrules 2 3 4\nvoicing 120\n\nmbrola %s ptbr_phtrans\n" % (mb, gender, pitch, mb))
    except OSError:
        return voice, env
    env2 = dict(env or os.environ)
    env2["ESPEAK_DATA_PATH"] = base
    return "mb/" + name, env2


# ---------- TTS ----------

class VoiceError(Exception):
    pass


def synth(text, voice, rate, expressive=True):
    """Cached 22.05 kHz mono s16 WAV of one sentence -> (path, seconds)."""
    exe, env = espeak()
    if not exe:
        raise VoiceError("sem espeak-ng")
    key = hashlib.sha1(("%s|%s|%s|%s" % (voice, rate, expressive, text)).encode("utf-8")).hexdigest()
    d = os.path.join(cache_dir(), "tts")
    os.makedirs(d, exist_ok=True)
    out = os.path.join(d, key + ".wav")
    if not os.path.exists(out):
        raw = out + ".raw.wav"
        v, e = expressive_voice(voice, env) if expressive else (voice, env)
        r = subprocess.run([exe, "-v", v, "-s", str(rate), "-g", "0", "-w", raw, text], env=e, capture_output=True, text=True)
        if (r.returncode != 0 or not os.path.exists(raw) or os.path.getsize(raw) < 100) and v != voice:
            r = subprocess.run([exe, "-v", voice, "-s", str(rate), "-w", raw, text], env=env, capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(raw) or os.path.getsize(raw) < 100:
            raise VoiceError("espeak-ng falhou na voz %r: %s" % (voice, (r.stderr or "").strip()[:200]))
        c = subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-i", raw, "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", out + ".tmp.wav"],
                           capture_output=True, text=True)
        os.remove(raw)
        if c.returncode != 0:
            raise VoiceError("ffmpeg não converteu a fala: " + c.stderr.strip()[:200])
        os.replace(out + ".tmp.wav", out)
    with wave.open(out) as w:
        return out, w.getnframes() / float(w.getframerate())


def scene_speech(s, voice, rate):
    """Synthesize a scene's sentences; sets s["sents"] = [(start, dur, text, wav)] and s["speech"]."""
    sents = split_sentences(s.get("narration"))
    out, t = [], LEAD_S
    if voice != "none":
        for text in sents:
            path, dur = synth(text, voice, rate)
            out.append((t, dur, text, path))
            t += dur + GAP_S
    s["sents"] = out
    s["speech"] = (out[-1][0] + out[-1][1] - LEAD_S) if out else 0.0


def build_voice(scenes, path):
    """One mono 16-bit track: each scene's sentences at their start times, silence elsewhere."""
    with wave.open(path, "wb") as o:
        o.setnchannels(1)
        o.setsampwidth(2)
        o.setframerate(SR)
        for s in scenes:
            total = int(round(s["dur"] * SR))
            written = 0
            for start, dur, _, wav in s.get("sents", []):
                at = int(round(start * SR))
                if at > written:
                    o.writeframes(b"\x00\x00" * (at - written))
                    written = at
                with wave.open(wav) as w:
                    data = w.readframes(w.getnframes())
                o.writeframes(data)
                written += len(data) // 2
            if total > written:
                o.writeframes(b"\x00\x00" * (total - written))


# ---------- SFX (pure Python, cached) ----------

def _whoosh(dur=0.7, f0=250.0, f1=5000.0, peak=0.6, q=0.7, seed=1):
    rnd = random.Random(seed)
    n = int(dur * SR)
    low = band = 0.0
    b0 = b1 = b2 = 0.0
    damp = 1.0 / q
    out = []
    for i in range(n):
        x = i / float(n)
        u = x / peak if x < peak else 1 - (x - peak) / (1 - peak) * 0.6
        fc = f0 * (f1 / f0) ** u
        F = 2 * math.sin(math.pi * min(fc, SR / 6.0) / SR)
        w = rnd.uniform(-1, 1)
        b0 = 0.99765 * b0 + w * 0.0990460
        b1 = 0.96300 * b1 + w * 0.2965164
        b2 = 0.57000 * b2 + w * 1.0526913
        pink = b0 + b1 + b2 + w * 0.1848
        hp = pink - low - damp * band
        band += F * hp
        low += F * band
        env = (x / peak) ** 2 if x < peak else (1 - (x - peak) / (1 - peak)) ** 1.5
        out.append(band * env)
    return out


def _pop(dur=0.12, fstart=900.0, fend=180.0, k=40.0):
    n = int(dur * SR)
    ph = 0.0
    out = []
    for i in range(n):
        t = i / float(SR)
        f = fend + (fstart - fend) * math.exp(-t * k)
        ph += 2 * math.pi * f / SR
        out.append(math.sin(ph) * math.exp(-t * 30) * min(1, t * SR / 40.0))
    return out


def _riser(dur=2.0, seed=3):
    rnd = random.Random(seed)
    n = int(dur * SR)
    out = []
    ph = 0.0
    hp = 0.0
    prev = 0.0
    for i in range(n):
        x = i / float(n)
        f = 200 + 800 * x
        ph += 2 * math.pi * f / SR
        w = rnd.uniform(-1, 1)
        hp = 0.9 * (hp + w - prev)
        prev = w
        env = x ** 3 if x < 0.97 else (1 - x) / 0.03
        out.append((0.5 * math.sin(ph) + 0.5 * hp) * env)
    return out


def _norm(xs, peak=0.7):
    m = max(1e-9, max(abs(v) for v in xs))
    g = peak / m
    return [v * g for v in xs]


def sfx_bank():
    """{'whoosh': [...], 'pop': [...], 'riser': [...]} float samples at SR, cached on disk."""
    d = os.path.join(cache_dir(), "sfx")
    os.makedirs(d, exist_ok=True)
    bank = {}
    for name, fn in (("whoosh", _whoosh), ("pop", _pop), ("riser", _riser)):
        p = os.path.join(d, name + "-v1.raw")
        if os.path.exists(p):
            a = array.array("f")
            with open(p, "rb") as fh:
                a.frombytes(fh.read())
            bank[name] = a
        else:
            a = array.array("f", _norm(fn()))
            with open(p, "wb") as fh:
                fh.write(a.tobytes())
            bank[name] = a
    return bank


def build_sfx(events, total, path, gain=0.5):
    """events: [(time_s, name, gain)]. Writes a mono WAV of the SFX alone. Max one event per 0.35 s."""
    bank = sfx_bank()
    n = int(total * SR) + 1
    buf = array.array("f", bytes(4 * n))
    last = -9.0
    for t, name, g in sorted(events):
        if name != "riser" and t - last < 0.35:
            continue
        if name != "riser":
            last = t
        src = bank[name]
        at = int(max(0.0, t) * SR)
        k = gain * g
        for i in range(min(len(src), n - at)):
            buf[at + i] += src[i] * k
    pcm = array.array("h", (int(max(-1.0, min(1.0, v)) * 32767) for v in buf))
    with wave.open(path, "wb") as o:
        o.setnchannels(1)
        o.setsampwidth(2)
        o.setframerate(SR)
        o.writeframes(pcm.tobytes())


# ---------- music bed ----------

PROGRESSIONS = {
    # vi-IV-I-V voicings (Hz), from the audio research note
    "warm": [[110.00, 164.81, 261.63, 329.63, 493.88], [87.31, 130.81, 220.00, 329.63, 392.00],
             [130.81, 196.00, 261.63, 329.63, 392.00], [98.00, 146.83, 246.94, 293.66, 440.00]],
}
THEME_MOOD = {"mystic": 0.944, "neon": 1.122, "terminal-green": 1.0, "sunset": 1.059, "ocean": 0.891, "paper": 1.0, "mono": 0.944}


def build_pad(path, total, theme="mono"):
    """Seamless 16 s chord loop (sine sources, ffmpeg) stretched to `total` seconds."""
    seg, x = 4.0, 1.5
    ratio = THEME_MOOD.get(theme, 1.0)
    chords = PROGRESSIONS["warm"]
    cyc = len(chords) * seg
    total = max(total, 4.0)
    g, cl = [], []
    for k, notes in enumerate(chords):
        lab = []
        for j, f in enumerate(notes):
            for i, det in enumerate((0.0, 0.25 + 0.1 * j)):
                L = "s%d%d%d" % (k, j, i)
                g.append("sine=f=%.2f:r=%d:d=%.1f,volume=%.2f[%s]" % (f * ratio + det, SR, seg + x, 0.9 / (1 + j * 0.35), L))
                lab.append("[%s]" % L)
        g.append("".join(lab) + "amix=inputs=%d:normalize=0,afade=t=in:d=%.1f:curve=qsin,afade=t=out:st=%.1f:d=%.1f:curve=qsin,adelay=%d:all=1,apad=whole_dur=%.1f[c%d]"
                 % (len(lab), x, seg, x, int(k * seg * 1000), cyc + x, k))
        cl.append("[c%d]" % k)
    g.append("".join(cl) + "amix=inputs=%d:normalize=0,asplit[a][b]" % len(cl))
    g.append("[a]atrim=0:%.1f[h];[b]atrim=%.1f:%.1f,asetpts=PTS-STARTPTS[t]" % (cyc, cyc, cyc + x))
    g.append("[h][t]amix=inputs=2:normalize=0:duration=first,aloop=loop=-1:size=%d,atrim=duration=%.2f,"
             "lowpass=f=1400,tremolo=f=0.15:d=0.25,aecho=0.8:0.6:120|250|430:0.3|0.2|0.12,volume=1.2,"
             "afade=t=in:d=2,afade=t=out:st=%.2f:d=3" % (int(cyc * SR), total, max(0.0, total - 3)))
    r = subprocess.run([ffmpeg(), "-v", "error", "-y", "-filter_complex", ";".join(g), "-ac", "1", "-t", "%.2f" % total, path],
                       capture_output=True, text=True)
    return r.returncode == 0 and os.path.exists(path)


def mean_db(path):
    r = subprocess.run([ffmpeg(), "-nostats", "-i", path, "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", r.stderr)
    return float(m.group(1)) if m else None


def integrated_lufs(path):
    r = subprocess.run([ffmpeg(), "-nostats", "-i", path, "-af", "ebur128=framelog=quiet", "-f", "null", "-"], capture_output=True, text=True)
    vals = re.findall(r"^\s+I:\s+(-?[\d.]+) LUFS", r.stderr, re.M)
    return float(vals[-1]) if vals else None


def mix(voice_wav, total, tmp, theme, music=True, sfx_events=None, has_voice=True):
    """Voice chain + ducked pad + SFX -> loudness-normalized AAC (.m4a). Returns its path."""
    ff = ffmpeg()
    inputs = []
    chains = []
    labels = []
    if has_voice:
        inputs += ["-i", voice_wav]
        chains.append("[0:a]aresample=44100,highpass=f=90,equalizer=f=250:t=q:w=1.2:g=-2,equalizer=f=3200:t=q:w=1:g=3,"
                      "acompressor=threshold=0.125:ratio=3:attack=5:release=80:makeup=2,aecho=0.9:0.9:22|37:0.12|0.08,asplit=2[vo][sc]")
        labels.append("[vo]")
    idx = 1 if has_voice else 0
    if music:
        pad = os.path.join(tmp, "pad.wav")
        if build_pad(pad, total, theme):
            vm = mean_db(voice_wav) if has_voice else -20.0
            pm = mean_db(pad)
            # voice mean includes silences; the bed sits ~14 dB under the speech level
            g = ((vm if vm is not None else -24.0) + 6.0 - 14.0) - (pm if pm is not None else -20.0)
            inputs += ["-i", pad]
            chains.append("[%d:a]aresample=44100,volume=%.1fdB[mus]" % (idx, g))
            if has_voice:
                chains.append("[mus][sc]sidechaincompress=threshold=0.03:ratio=6:attack=30:release=600:makeup=1:knee=4[duck]")
                labels.append("[duck]")
            else:
                labels.append("[mus]")
            idx += 1
    if sfx_events:
        sf = os.path.join(tmp, "sfx.wav")
        build_sfx(sfx_events, total, sf)
        inputs += ["-i", sf]
        chains.append("[%d:a]aresample=44100,volume=-9dB[fx]" % idx)
        labels.append("[fx]")
        idx += 1
    if has_voice and len(labels) == 1:
        chains[0] = chains[0].replace(",asplit=2[vo][sc]", "[vo]")
    if not labels:
        return None
    premix = os.path.join(tmp, "premix.wav")
    graph = ";".join(chains) + ";" + "".join(labels) + "amix=inputs=%d:normalize=0:duration=longest,atrim=duration=%.3f[out]" % (len(labels), total)
    r = subprocess.run([ff, "-y", "-loglevel", "error"] + inputs + ["-filter_complex", graph, "-map", "[out]", "-ac", "2", premix],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise VoiceError("mixagem falhou: " + r.stderr.strip()[-300:])
    lufs = integrated_lufs(premix)
    gain = -16.0 - lufs if lufs is not None and lufs > -70 else 0.0
    out = os.path.join(tmp, "audio.m4a")
    r = subprocess.run([ff, "-y", "-loglevel", "error", "-i", premix, "-af", "volume=%.2fdB,alimiter=limit=0.79:attack=5:release=50:level=disabled" % gain,
                        "-c:a", "aac", "-b:a", "128k", out], capture_output=True, text=True)
    if r.returncode != 0:
        raise VoiceError("codificação do áudio falhou: " + r.stderr.strip()[-300:])
    return out
