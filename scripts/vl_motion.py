"""Motion core for video-lite: easing, springs, tweens, stagger, path length and stroke reveal.

Everything here is a pure function of time, so any frame can be drawn on its own (no state
between frames): transitions can draw two scenes at once and tests can draw one frame.
"""
import math


def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def lerp(a, b, k):
    return a + (b - a) * k


def mix(c1, c2, k):
    """Blend two RGB tuples (0..1 floats)."""
    return tuple(lerp(a, b, k) for a, b in zip(c1, c2))


# ---------- easing (k in 0..1 -> 0..1) ----------

def linear(k):
    return k


def ease_out_cubic(k):
    return 1 - (1 - k) ** 3


def ease_in_cubic(k):
    return k ** 3


def ease_in_out_cubic(k):
    return 4 * k ** 3 if k < 0.5 else 1 - (-2 * k + 2) ** 3 / 2


def ease_out_quint(k):
    return 1 - (1 - k) ** 5


def ease_out_back(k, s=1.70158):
    k -= 1
    return 1 + (s + 1) * k ** 3 + s * k ** 2


def ease_out_elastic(k, amp=0.45):
    """A light elastic: one or two small wobbles, not a cartoon bounce."""
    if k <= 0:
        return 0.0
    if k >= 1:
        return 1.0
    std = 1 + math.pow(2, -10 * k) * math.sin((k * 10 - 0.75) * (2 * math.pi) / 3)
    return lerp(ease_out_cubic(k), std, amp)


def spring(k, damping=0.55, freq=2.2):
    """Damped spring settling at 1 (critically-ish damped by default)."""
    if k <= 0:
        return 0.0
    if k >= 1:
        return 1.0
    return 1 - math.exp(-damping * 10 * k) * math.cos(freq * 2 * math.pi * k)


EASE = {
    "linear": linear, "out": ease_out_cubic, "in": ease_in_cubic, "inout": ease_in_out_cubic,
    "quint": ease_out_quint, "back": ease_out_back, "elastic": ease_out_elastic, "spring": spring,
}


def prog(t, start, dur):
    """Raw progress 0..1 of a tween that starts at `start` and lasts `dur` seconds."""
    if dur <= 0:
        return 1.0 if t >= start else 0.0
    return clamp((t - start) / dur)


def tween(t, start, dur, ease="out"):
    return EASE[ease](prog(t, start, dur))


def stagger(i, n, span, first=0.0):
    """Start time of item i of n spread over `span` seconds."""
    if n <= 1:
        return first
    return first + span * i / (n - 1)


def pulse(t, period=2.4, lo=0.0, hi=1.0):
    """Smooth 0..1 breathing, for glows and highlights."""
    return lo + (hi - lo) * (0.5 - 0.5 * math.cos(2 * math.pi * t / period))


def hash01(*xs):
    """Deterministic pseudo-random 0..1 from numbers (stable across frames and machines)."""
    h = 0
    for x in xs:
        h = (h * 1000003) ^ int(x * 7919 + 17)
        h &= 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 0x5BD1E995) & 0xFFFFFFFF
    h ^= h >> 15
    return (h & 0xFFFFFF) / float(0xFFFFFF)


# ---------- paths: length + progressive stroke ("draw-on") ----------

def path_length(ctx):
    """Length of the current path in user space (flattened). Call after building the path."""
    total, x0, y0, sx, sy = 0.0, 0.0, 0.0, 0.0, 0.0
    for kind, pts in ctx.copy_path_flat():
        if kind == 0:  # MOVE_TO
            x0, y0 = pts
            sx, sy = pts
        elif kind == 1:  # LINE_TO
            x, y = pts
            total += math.hypot(x - x0, y - y0)
            x0, y0 = x, y
        elif kind == 3:  # CLOSE_PATH
            total += math.hypot(sx - x0, sy - y0)
            x0, y0 = sx, sy
    return total


def stroke_reveal(ctx, length, k):
    """Stroke the current path showing only the first k (0..1) of its length (dash trick)."""
    if k <= 0:
        ctx.new_path()
        return
    if k >= 1:
        ctx.set_dash([])
        ctx.stroke()
        return
    ctx.set_dash([max(0.01, length * k), length + 10])
    ctx.stroke()
    ctx.set_dash([])
