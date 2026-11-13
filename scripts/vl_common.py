"""Shared helpers for video-lite: tools discovery, themes, fonts."""
import glob
import os
import shutil
import subprocess

HOME_ESPEAK = os.path.expanduser("~/.local/opt/espeak-ng")
HOME_MBROLA = os.path.expanduser("~/.local/opt/mbrola")

# Colors are 0-255 RGB. bg = gradient stops (top-left -> bottom-right). font = display role,
# body = text role. particles: dust | stars | bokeh | code | neon | bubbles | none.
# transitions: cycled scene by scene (fade | slide | zoom | wipe | iris | cut).
THEMES = {
    "terminal-green": {"bg": [(4, 12, 8), (10, 34, 22), (2, 8, 6)], "fg": (220, 255, 230), "accent": (80, 250, 123),
                       "accent2": (40, 200, 255), "dim": (120, 170, 140), "font": "mono", "body": "sans",
                       "particles": "code", "transitions": ["wipe", "slide"], "grain": 0.05, "vignette": 0.65},
    "sunset": {"bg": [(36, 10, 40), (120, 36, 52), (190, 82, 48)], "fg": (255, 244, 230), "accent": (255, 184, 76),
               "accent2": (255, 110, 120), "dim": (235, 190, 170), "font": "sans-display", "body": "sans",
               "particles": "bokeh", "transitions": ["slide", "fade"], "grain": 0.04, "vignette": 0.5},
    "ocean": {"bg": [(4, 18, 40), (10, 56, 96), (8, 90, 120)], "fg": (235, 245, 255), "accent": (90, 210, 250),
              "accent2": (120, 255, 210), "dim": (150, 190, 220), "font": "sans-display", "body": "sans",
              "particles": "bubbles", "transitions": ["fade", "zoom"], "grain": 0.04, "vignette": 0.55},
    "paper": {"bg": [(248, 244, 234), (236, 229, 214), (222, 212, 194)], "fg": (30, 30, 34), "accent": (196, 64, 44),
              "accent2": (40, 90, 140), "dim": (110, 104, 96), "font": "serif-display", "body": "serif",
              "particles": "dust", "transitions": ["slide", "wipe"], "grain": 0.07, "vignette": 0.25},
    "mono": {"bg": [(12, 12, 14), (30, 30, 34), (8, 8, 10)], "fg": (240, 240, 240), "accent": (255, 255, 255),
             "accent2": (160, 160, 170), "dim": (150, 150, 155), "font": "sans-display", "body": "sans",
             "particles": "dust", "transitions": ["fade", "slide"], "grain": 0.06, "vignette": 0.6},
    "mystic": {"bg": [(8, 6, 26), (26, 16, 60), (5, 3, 16)], "fg": (246, 238, 218), "accent": (232, 192, 104),
               "accent2": (150, 120, 235), "dim": (178, 168, 206), "font": "serif-display", "body": "serif",
               "particles": "stars", "transitions": ["fade", "zoom", "iris"], "grain": 0.05, "vignette": 0.75},
    "neon": {"bg": [(6, 4, 18), (22, 6, 44), (4, 2, 12)], "fg": (250, 248, 255), "accent": (255, 64, 200),
             "accent2": (0, 236, 255), "dim": (170, 160, 210), "font": "sans-display", "body": "sans",
             "particles": "neon", "transitions": ["wipe", "slide", "zoom"], "grain": 0.04, "vignette": 0.7},
}

# Font roles -> fontconfig family names, first installed one wins (cairo "toy" faces).
FAMILIES = {
    "sans": ["Noto Sans", "DejaVu Sans", "Liberation Sans", "Helvetica", "Arial"],
    "sans-display": ["Noto Sans Display", "Noto Sans", "DejaVu Sans", "Helvetica Neue", "Helvetica"],
    "serif": ["Noto Serif", "DejaVu Serif", "Liberation Serif", "Times New Roman", "Times"],
    "serif-display": ["Noto Serif Display", "Noto Serif", "DejaVu Serif", "Didot", "Times"],
    "mono": ["JetBrains Mono", "DejaVu Sans Mono", "Liberation Mono", "Menlo", "Courier"],
    "icons": ["FontAwesome"],
}
GENERIC = {"sans": "sans-serif", "sans-display": "sans-serif", "serif": "serif", "serif-display": "serif",
           "mono": "monospace", "icons": "FontAwesome"}
# glyph fallback chain for symbols (alchemy, planets, math, arrows…)
SYMBOL_FAMILIES = ["Noto Sans Symbols", "Noto Sans Symbols2", "Noto Sans Math", "DejaVu Sans", "FreeSerif",
                   "Apple Symbols"]

_families = None


def installed_families():
    """Set of installed font family names (fontconfig); None when fc-list is missing."""
    global _families
    if _families is None:
        fc = shutil.which("fc-list")
        if not fc:
            _families = set()
            return None
        out = run([fc, ":", "family"]).stdout
        _families = set()
        for line in out.splitlines():
            for name in line.split(","):
                if name.strip():
                    _families.add(name.strip())
    return _families or None


def family(role):
    """Installed family name for a font role (sans, serif-display, mono, icons…)."""
    have = installed_families()
    for name in FAMILIES.get(role, FAMILIES["sans"]):
        if have is None or name in have:
            return name
    return GENERIC.get(role, "sans-serif")


def symbol_families():
    have = installed_families()
    return [f for f in SYMBOL_FAMILIES if have is None or f in have] or ["sans-serif"]


def emoji_font():
    """Path of a color emoji font usable by Pillow, or None."""
    for d in FONT_DIRS:
        for name in ("NotoColorEmoji.ttf", "Apple Color Emoji.ttc"):
            hits = glob.glob(os.path.join(d, "**", name), recursive=True)
            if hits:
                return sorted(hits)[0]
    return None


def cache_dir():
    d = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "video-lite")
    os.makedirs(d, exist_ok=True)
    return d


FONT_CANDIDATES = {
    "mono": ["JetBrainsMono-{w}.ttf", "DejaVuSansMono-{w}.ttf", "DejaVuSansMono.ttf", "Menlo.ttc", "LiberationMono-{w}.ttf"],
    "sans": ["NotoSans-{w}.ttf", "DejaVuSans-{w}.ttf", "DejaVuSans.ttf", "LiberationSans-{w}.ttf", "Helvetica.ttc", "Arial.ttf"],
    "serif": ["NotoSerif-{w}.ttf", "DejaVuSerif-{w}.ttf", "DejaVuSerif.ttf", "LiberationSerif-{w}.ttf", "Times.ttc"],
}
FONT_DIRS = ["/usr/share/fonts", "/usr/local/share/fonts", os.path.expanduser("~/.fonts"),
             os.path.expanduser("~/.local/share/fonts"), "/System/Library/Fonts", "/Library/Fonts"]

_font_cache = {}


def find_font(family, bold=False):
    """Path of a TTF for family (mono/sans/serif), bold or regular; None = Pillow default."""
    key = (family, bold)
    if key in _font_cache:
        return _font_cache[key]
    w = "Bold" if bold else "Regular"
    found = None
    for pat in FONT_CANDIDATES.get(family, FONT_CANDIDATES["sans"]):
        name = pat.format(w=w)
        for d in FONT_DIRS:
            hits = glob.glob(os.path.join(d, "**", name), recursive=True)
            if hits:
                found = sorted(hits)[0]
                break
        if found:
            break
    _font_cache[key] = found
    return found


def _with_mbrola(env):
    """Put a user-local mbrola binary on PATH (MBROLA voices: mb-br1/br3/br4…)."""
    mb = os.path.join(HOME_MBROLA, "usr", "bin")
    if os.path.exists(os.path.join(mb, "mbrola")) and not shutil.which("mbrola"):
        env["PATH"] = mb + os.pathsep + env.get("PATH", "")
    return env


def mbrola_voices():
    """MBROLA voices espeak-ng can use here (e.g. ["mb-br3"]); [] = none."""
    exe, env = espeak()
    if not exe:
        return []
    found = []
    roots = ["/usr/share/mbrola", "/usr/local/share/mbrola"]
    if env and env.get("ESPEAK_DATA_PATH"):
        roots.insert(0, os.path.join(env["ESPEAK_DATA_PATH"], "espeak-ng-data", "mbrola"))
    for r in roots:
        for v in ("br1", "br3", "br4", "us1", "us2", "es1"):
            if os.path.exists(os.path.join(r, v)) or os.path.exists(os.path.join(r, v, v)):
                if ("mb-" + v) not in found:
                    found.append("mb-" + v)
    if not (shutil.which("mbrola") or os.path.exists(os.path.join(HOME_MBROLA, "usr", "bin", "mbrola"))):
        return []
    return found


def espeak():
    """(argv0, env) for espeak-ng / espeak, or (None, None)."""
    for name in ("espeak-ng", "espeak"):
        p = shutil.which(name)
        if p:
            return p, _with_mbrola(dict(os.environ))
    local = os.path.join(HOME_ESPEAK, "usr", "bin", "espeak-ng")
    if os.path.exists(local):
        libs = glob.glob(os.path.join(HOME_ESPEAK, "usr", "lib", "*-linux-gnu"))
        env = dict(os.environ)
        if libs:
            env["LD_LIBRARY_PATH"] = libs[0] + (":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
            data = os.path.join(libs[0], "espeak-ng-data")
            if os.path.isdir(data):
                env["ESPEAK_DATA_PATH"] = libs[0]
        return local, _with_mbrola(env)
    return None, None


def run(argv, **kw):
    return subprocess.run(argv, capture_output=True, text=True, **kw)


SSE2_X264 = "/usr/lib/i386-linux-gnu/i686/sse2"


def x264_env():
    """Env for ffmpeg so libx264 uses SSE2 on 32-bit Debian (its default i386 build has asm off: ~3x slower)."""
    env = dict(os.environ)
    try:
        if os.path.exists(os.path.join(SSE2_X264, "libx264.so.164")) and " sse2" in open("/proc/cpuinfo").read():
            env["LD_LIBRARY_PATH"] = SSE2_X264 + (":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
    except OSError:
        pass
    return env
