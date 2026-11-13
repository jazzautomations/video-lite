"""Scene kinds for video-lite v2. Each kind has prepare(P, s) (layout, once) and draw(P, ctx, s, t).

t is seconds since the scene started; it can go past s["dur"] while the next scene transitions in
(elements then exit). Content must stay inside P.top..P.bottom (captions live below).
"""
import math

import vl_icons
from vl_motion import clamp, ease_out_back, path_length, prog, pulse, stroke_reveal, tween

TAU = 2 * math.pi


def _items(lst, key="text"):
    """Normalize ["a", {"text": "b", "icon": "fa-x"}] -> [(text, icon or None)]."""
    out = []
    for x in lst or []:
        if isinstance(x, dict):
            out.append((str(x.get(key) or x.get("text") or x.get("label") or ""), x.get("icon") or x.get("symbol")))
        else:
            out.append((str(x), None))
    return out


def _speech_span(s, frac=0.85, lo=1.0):
    sp = s.get("speech") or 0
    return max(lo, (sp if sp > 0 else s["dur"] * 0.8) * frac)


def _beats(s, n, defaults, lead=0.12):
    """Reveal times for n items: sentence k reveals item k when the narration has n (or n+1,
    the first being an intro) sentences; otherwise the evenly spread defaults."""
    st = [x[0] for x in s.get("sents", [])]
    if n and len(st) == n:
        return [max(0.1, x - lead) for x in st]
    if n and len(st) == n + 1:
        return [max(0.1, x - lead) for x in st[1:]]
    return defaults


# ---------- shared pieces ----------

def draw_icon(P, ctx, info, cx, cy, box, color, alpha, scale=1.0):
    """Small icon (glyph filled, or emoji bitmap) centered at cx, cy."""
    if alpha <= 0.01 or scale <= 0.01:
        return
    ctx.save()
    ctx.translate(cx, cy)
    ctx.scale(scale, scale)
    if info["kind"] == "emoji":
        surf = P.emoji_surface(info["text"])
        if surf is not None:
            sc = box / max(surf.get_width(), surf.get_height())
            ctx.scale(sc, sc)
            ctx.set_source_surface(surf, -surf.get_width() / 2, -surf.get_height() / 2)
            ctx.paint_with_alpha(alpha)
            ctx.restore()
            return
        info = P.symbol_info("✦")
    size = info.get("isize")
    if not size:
        size = info["isize"] = P.fit_glyph_size(info, box)
    ctx.new_path()
    P.glyph_path(ctx, info, size)
    ctx.set_source_rgba(color[0], color[1], color[2], alpha)
    ctx.fill()
    ctx.restore()


def icon_info(P, spec, where):
    try:
        return P.symbol_info(spec)
    except ValueError as e:
        raise ValueError("%s: %s" % (where, e))


def underline(P, ctx, cx, y, width, k, alpha, align="center"):
    if k <= 0 or alpha <= 0.01:
        return
    u = P.u
    w = width * k
    x0 = cx - w / 2 if align == "center" else cx
    ctx.set_source_rgba(P.ac[0], P.ac[1], P.ac[2], alpha)
    ctx.rectangle(x0, y, w, max(2, 3 * u))
    ctx.fill()
    d = 5 * u * k
    for x in ((x0, x0 + w) if align == "center" else (x0 + w,)):
        ctx.move_to(x, y + 1.5 * u - d)
        ctx.line_to(x + d, y + 1.5 * u)
        ctx.line_to(x, y + 1.5 * u + d)
        ctx.line_to(x - d, y + 1.5 * u)
        ctx.close_path()
    ctx.fill()


def deco_rings(P, ctx, t, cx, cy, r, alpha=0.12):
    k = tween(t, 0.0, 1.8, "inout")
    P.ring(ctx, cx, cy, r, k, P.ac, alpha, ticks=36, rot=t * 0.04)
    P.ring(ctx, cx, cy, r * 0.84, k, P.ac2, alpha * 0.8, rot=-t * 0.03)


# ---------- title / cta ----------

def prep_title(P, s):
    u, W = P.u, P.W
    c = s["_c"]
    c["t"] = P.layout(s.get("title", ""), P.t["font"], 100 * u, W - 2 * P.margin, 3, bold=True, min_size=40 * u)
    c["s"] = P.layout(s.get("subtitle", ""), P.t["body"], 34 * u, W - 2 * P.margin - 80 * u, 2, min_size=22 * u)
    sym = s.get("symbol") or s.get("icon")
    c["box"] = 0
    if sym:
        icon_info(P, sym, "cena %d (symbol)" % s["idx"])
        c["box"] = min(150 * u, (P.bottom - P.top) - c["t"].height - c["s"].height - 80 * u)
    c["h"] = (c["box"] + 30 * u if c["box"] > 40 * u else 0) + c["t"].height + 34 * u + c["s"].height


def draw_title(P, ctx, s, t):
    c, u, W = s["_c"], P.u, P.W
    cy = (P.top + P.bottom) / 2
    deco_rings(P, ctx, t, W / 2, cy, (P.bottom - P.top) * 0.55)
    y = cy - c["h"] / 2
    if c["box"] > 40 * u:
        P.draw_symbol(ctx, s, t, s.get("symbol") or s.get("icon"), W / 2, y + c["box"] / 2, c["box"], start=0.1)
        y += c["box"] + 30 * u
        t_words = 0.6
    else:
        t_words = 0.2
    cta = s["kind"] == "cta"
    lay = c["t"]
    if cta:
        k, a = P.vis(s, t, t_words, 0.7, "back")
        ctx.save()
        ctx.translate(W / 2, y + lay.height / 2)
        sc = 0.6 + 0.4 * k
        ctx.scale(sc, sc)
        ctx.translate(-W / 2, -(y + lay.height / 2))
        P.draw_layout(ctx, lay, W / 2, y, "center", P.fg, a)
        ctx.restore()
    else:
        P.draw_layout(ctx, lay, W / 2, y, "center", P.fg, 1.0, anim=P.word_anim(s, t, t_words, 0.08, 0.6))
    y += lay.height + 12 * u
    n = P.nwords(lay)
    k, a = P.vis(s, t, t_words + 0.08 * n + 0.1, 0.8)
    underline(P, ctx, W / 2, y, min(lay.width * 0.7, 420 * u), k, a)
    y += 22 * u
    sub = c["s"]
    if sub.lines:
        k, a = P.vis(s, t, t_words + 0.08 * n + 0.35, 0.7)
        if cta:
            pad = 18 * u
            bw, bh = sub.width + 2 * pad + 20 * u, sub.height + pad
            x0 = W / 2 - bw / 2
            ctx.new_path()
            P.rounded(ctx, x0, y - pad * 0.3, bw, bh, bh / 2)
            glow = pulse(t, 1.8, 0.25, 0.6) * a
            ctx.set_source_rgba(P.ac[0], P.ac[1], P.ac[2], 0.18 * a)
            ctx.fill_preserve()
            ctx.set_line_width(2.5 * u)
            ctx.set_source_rgba(P.ac[0], P.ac[1], P.ac[2], glow + 0.3 * a)
            L = 2 * (bw + bh)
            stroke_reveal(ctx, L, k)
            P.draw_layout(ctx, sub, W / 2, y, "center", P.fg, a)
        else:
            P.draw_layout(ctx, sub, W / 2, y + (1 - k) * 14 * u, "center", P.ac, a)


# ---------- bullets ----------

def prep_bullets(P, s):
    u, W = P.u, P.W
    c = s["_c"]
    c["t"] = P.layout(s.get("title", ""), P.t["font"], 58 * u, W - 2 * P.margin, 2, bold=True, min_size=32 * u)
    items = _items(s.get("bullets"))
    icons = s.get("icons") or []
    infos = []
    for i, (txt, ic) in enumerate(items):
        spec = ic or (icons[i] if i < len(icons) else None)
        infos.append(icon_info(P, spec, "cena %d bullet %d" % (s["idx"], i + 1)) if spec else None)
    avail = P.bottom - (P.top + c["t"].height + 46 * u)
    size = 44 * u
    while True:
        box = size * 1.25
        tw = W - 2 * P.margin - box - 28 * u
        lays = [P.layout(txt, P.t["body"], size, tw, 2, min_size=size) for txt, _ in items]
        gap = size * 0.55
        total = sum(max(l.height, box) for l in lays) + gap * max(0, len(lays) - 1)
        if total <= avail or size <= 20 * u:
            break
        size *= 0.92
    c.update(items=lays, infos=infos, box=box, gap=gap, total=total)
    n = max(1, len(items))
    span = clamp((_speech_span(s) - 0.5) / n, 0.35, 1.8)
    c["starts"] = _beats(s, len(items), [0.5 + i * span for i in range(n)])


def draw_bullets(P, ctx, s, t):
    c, u = s["_c"], P.u
    x = P.margin
    y = P.top + 6 * u
    lay = c["t"]
    P.draw_layout(ctx, lay, x, y, "left", P.fg, 1.0, anim=P.word_anim(s, t, 0.05, 0.06, 0.5))
    y += lay.height + 8 * u
    k, a = P.vis(s, t, 0.3, 0.8)
    underline(P, ctx, x, y, min(lay.width, 300 * u), k, a, align="left")
    y += 34 * u
    avail = P.bottom - y
    y += max(0, (avail - c["total"]) / 2) * 0.5
    box = c["box"]
    starts = c["starts"]
    for i, bl in enumerate(c["items"]):
        st = starts[i]
        k, a = P.vis(s, t, st, 0.6, "back", i)
        if a <= 0.01:
            break
        active = i == len(starts) - 1 or t < starts[i + 1]
        dimk = 1.0 if active else 0.72
        h = max(bl.height, box)
        cx, cy = x + box / 2, y + h / 2 if bl.height <= box else y + box / 2
        ctx.new_path()
        ctx.arc(cx, cy, box / 2 * max(0.01, k), 0, TAU)
        ctx.set_source_rgba(P.ac[0], P.ac[1], P.ac[2], (0.22 if active else 0.12) * a)
        ctx.fill_preserve()
        ctx.set_line_width(1.8 * u)
        ctx.set_source_rgba(P.ac[0], P.ac[1], P.ac[2], 0.9 * a * dimk)
        ctx.stroke()
        info = c["infos"][i]
        if info:
            draw_icon(P, ctx, info, cx, cy, box * 0.52, P.ac if not P.light else P.ac, a, k)
        else:
            ctx.arc(cx, cy, box * 0.14 * k, 0, TAU)
            ctx.set_source_rgba(P.ac[0], P.ac[1], P.ac[2], a)
            ctx.fill()
        tx = x + box + 24 * u + (1 - min(1, k)) * 40 * u
        ty = cy - bl.height / 2 if bl.height <= box else y
        P.draw_layout(ctx, bl, tx, ty - bl.size * 0.02, "left", P.fg, a * dimk)
        y += h + c["gap"]


# ---------- terminal ----------

def prep_terminal(P, s):
    u, W = P.u, P.W
    c = s["_c"]
    size = 28 * u
    face = P.fonts.role("mono")
    inner = W - 2 * P.margin - 70 * u
    rows = []
    for line in s.get("lines", []):
        lay = P.layout(line or " ", "mono", size, inner, 99, min_size=size, accents=False)
        segs = [" ".join(w.text for w in ws) for _, ws in lay.lines] or [""]
        for j, seg in enumerate(segs):
            rows.append((seg, line.startswith("$"), j == len(segs) - 1))
    maxrows = int((P.bottom - P.top - 90 * u) / (size * 1.4))
    if len(rows) > maxrows:
        rows = rows[-maxrows:]
    c.update(rows=rows, size=size, face=face, total=sum(len(r[0]) for r in rows) or 1)
    c["h"] = 70 * u + len(rows) * size * 1.4 + 30 * u


def draw_terminal(P, ctx, s, t):
    c, u, W = s["_c"], P.u, P.W
    k, a = P.vis(s, t, 0.05, 0.6, "back")
    if a <= 0.01:
        return
    h = min(P.bottom - P.top, max(c["h"], 220 * u))
    x0, x1 = P.margin, W - P.margin
    y0 = (P.top + P.bottom) / 2 - h / 2
    ctx.save()
    cx, cy = W / 2, y0 + h / 2
    sc = 0.92 + 0.08 * k
    ctx.translate(cx, cy + (1 - k) * 30 * u)
    ctx.scale(sc, sc)
    ctx.translate(-cx, -cy)
    ctx.new_path()
    P.rounded(ctx, x0, y0, x1 - x0, h, 14 * u)
    ctx.set_source_rgba(0.02, 0.03, 0.03, 0.82 * a)
    ctx.fill_preserve()
    ctx.set_line_width(2 * u)
    ctx.set_source_rgba(P.ac[0], P.ac[1], P.ac[2], (0.35 + 0.25 * pulse(t, 2.0)) * a)
    ctx.stroke()
    for i, col in enumerate(((1, 0.37, 0.34), (1, 0.74, 0.18), (0.15, 0.79, 0.25))):
        ctx.arc(x0 + 28 * u + i * 26 * u, y0 + 24 * u, 7 * u, 0, TAU)
        ctx.set_source_rgba(col[0], col[1], col[2], a)
        ctx.fill()
    ctx.set_source_rgba(0.6, 0.6, 0.6, 0.12 * a)
    ctx.rectangle(x0, y0 + 46 * u, x1 - x0, 1.2 * u)
    ctx.fill()
    size = c["size"]
    ctx.set_font_face(c["face"])
    ctx.set_font_size(size)
    shown = int(c["total"] * clamp((t - 0.5) / max(0.8, s["dur"] * 0.65)))
    y = y0 + 70 * u + size
    curx, cury = x0 + 34 * u, y
    for seg, prompt, _ in c["rows"]:
        part = seg[:max(0, shown)]
        shown -= len(seg)
        col = P.ac if prompt else (0.9, 0.9, 0.9)
        ctx.set_source_rgba(col[0], col[1], col[2], a)
        ctx.move_to(x0 + 34 * u, y)
        ctx.show_text(part)
        curx, cury = x0 + 34 * u + ctx.text_extents(part).x_advance, y
        if shown <= 0:
            break
        y += size * 1.4
    if int(t * 2.2) % 2 == 0:
        ctx.set_source_rgba(P.ac[0], P.ac[1], P.ac[2], a)
        ctx.rectangle(curx + 3 * u, cury - size * 0.8, size * 0.5, size * 0.95)
        ctx.fill()
    ctx.restore()


# ---------- quote ----------

def prep_quote(P, s):
    u, W = P.u, P.W
    c = s["_c"]
    text = s.get("title") or s.get("text") or ""
    c["q"] = P.layout(text, P.t["body"], 48 * u, W - 2 * P.margin - 140 * u, 4, italic=True, min_size=28 * u)
    author = s.get("subtitle") or s.get("author") or ""
    c["a"] = P.layout(("— " + author) if author and not author.startswith(("—", "-")) else author, P.t["body"], 30 * u, W - 2 * P.margin - 140 * u, 2, bold=True, min_size=20 * u)
    c["h"] = c["q"].height + (c["a"].height + 30 * u if c["a"].lines else 0)


def draw_quote(P, ctx, s, t):
    c, u = s["_c"], P.u
    x = P.margin + 110 * u
    y = (P.top + P.bottom) / 2 - c["h"] / 2
    k, a = P.vis(s, t, 0.05, 0.9, "back")
    ctx.save()
    qx, qy = P.margin + 40 * u, y + 40 * u
    ctx.translate(qx, qy)
    ctx.rotate((1 - k) * -0.4)
    ctx.scale(0.5 + 0.5 * k, 0.5 + 0.5 * k)
    ctx.set_font_face(P.fonts.role(P.t["font"], True))
    ctx.set_font_size(230 * u)
    ctx.set_source_rgba(P.ac[0], P.ac[1], P.ac[2], 0.35 * a)
    ex = ctx.text_extents("“")
    ctx.move_to(-ex.width / 2 - ex.x_bearing, ex.height / 2 + 60 * u)
    ctx.show_text("“")
    ctx.restore()
    kb, ab = P.vis(s, t, 0.3, 1.0, "inout")
    ctx.set_source_rgba(P.ac[0], P.ac[1], P.ac[2], 0.8 * ab)
    ctx.rectangle(x - 26 * u, y, 3 * u, c["h"] * kb)
    ctx.fill()
    n = P.nwords(c["q"])
    step = clamp(_speech_span(s, 0.6) / max(1, n), 0.03, 0.12)
    P.draw_layout(ctx, c["q"], x, y, "left", P.fg, 1.0, anim=P.word_anim(s, t, 0.4, step, 0.6, rise=10 * u, ease="out"))
    if c["a"].lines:
        k2, a2 = P.vis(s, t, 0.4 + n * step + 0.2, 0.7)
        P.draw_layout(ctx, c["a"], x - (1 - k2) * 40 * u, y + c["q"].height + 30 * u, "left", P.ac, a2)


# ---------- symbol ----------

def _sym_block(P, s, box_max):
    u = P.u
    c = s["_c"]
    c["t"] = P.layout(s.get("title", ""), P.t["font"], 60 * u, P.W - 2 * P.margin, 2, bold=True, min_size=30 * u)
    c["s"] = P.layout(s.get("subtitle", ""), P.t["body"], 30 * u, P.W - 2 * P.margin - 60 * u, 2, min_size=20 * u)
    text_h = (c["t"].height + 14 * u if c["t"].lines else 0) + (c["s"].height + 8 * u if c["s"].lines else 0)
    avail = P.bottom - P.top - text_h - 24 * u
    c["box"] = max(60 * u, min(box_max, avail / 1.5))
    c["h"] = c["box"] * 1.5 + 24 * u + text_h


def prep_symbol(P, s):
    if not (s.get("symbol") or s.get("icon")):
        raise ValueError("cena %d (symbol): falta \"symbol\" (ex.: \"☿\", \"fa-book\", \"🔥\")" % s["idx"])
    icon_info(P, s.get("symbol") or s.get("icon"), "cena %d (symbol)" % s["idx"])
    _sym_block(P, s, 250 * P.u)


def _text_below(P, ctx, s, t, y, start):
    c, u, W = s["_c"], P.u, P.W
    if c["t"].lines:
        P.draw_layout(ctx, c["t"], W / 2, y, "center", P.fg, 1.0, anim=P.word_anim(s, t, start, 0.07, 0.6))
        y += c["t"].height + 14 * u
    if c["s"].lines:
        k, a = P.vis(s, t, start + 0.07 * P.nwords(c["t"]) + 0.3, 0.7)
        P.draw_layout(ctx, c["s"], W / 2, y + (1 - k) * 12 * u, "center", P.dim if not P.light else P.ac2, a)


def halo(P, ctx, s, t, cx, cy, r, start=0.0):
    k = tween(t, start, 1.4, "inout")
    _, a = P.vis(s, t, start, 0.4)
    P.ring(ctx, cx, cy, r, k, P.ac, 0.55 * a, ticks=24, rot=t * 0.05)
    P.ring(ctx, cx, cy, r * 1.12, k, P.ac2, 0.22 * a, rot=-t * 0.04)
    ko = prog(t, start + 1.2, 0.6) * a
    if ko > 0:
        for i in range(3):
            ang = t * 0.5 + i * TAU / 3
            P.soft_dot(ctx, cx + math.cos(ang) * r, cy + math.sin(ang) * r, 9 * P.u, P.ac, 0.9 * ko)
            ctx.arc(cx + math.cos(ang) * r, cy + math.sin(ang) * r, 2.6 * P.u, 0, TAU)
            ctx.set_source_rgba(P.fg[0], P.fg[1], P.fg[2], ko)
            ctx.fill()


def draw_symbol(P, ctx, s, t):
    c, u, W = s["_c"], P.u, P.W
    box = c["box"]
    y = (P.top + P.bottom) / 2 - c["h"] / 2
    cy = y + box * 0.75
    halo(P, ctx, s, t, W / 2, cy, box * 0.68)
    P.draw_symbol(ctx, s, t, s.get("symbol") or s.get("icon"), W / 2, cy, box, start=0.25, spin=bool(s.get("spin")))
    _text_below(P, ctx, s, t, y + box * 1.5 + 24 * u, 1.2)


# ---------- geometry ----------

def _poly(n, rot=-math.pi / 2, r=1.0, step=1):
    pts = [(math.cos(rot + TAU * i * step / n) * r, math.sin(rot + TAU * i * step / n) * r) for i in range(n)]

    def b(ctx):
        ctx.move_to(*pts[0])
        for p in pts[1:]:
            ctx.line_to(*p)
        ctx.close_path()
    return b, pts


def _circle(x, y, r):
    def b(ctx):
        ctx.new_sub_path()
        ctx.arc(x, y, r, -math.pi / 2, 1.5 * math.pi)
    return b


def _spiral(ctx):
    phi = (1 + 5 ** 0.5) / 2
    b = math.log(phi) / (math.pi / 2)
    tmax = 5 * math.pi
    for i in range(241):
        th = tmax * i / 240
        r = math.exp(b * (th - tmax))
        x, y = math.cos(th) * r, math.sin(th) * r
        if i == 0:
            ctx.move_to(x, y)
        else:
            ctx.line_to(x, y)


def shape_strokes(name):
    """[(builder, line-width factor)], [vertices] for a static shape in unit space (radius 1)."""
    S = []
    verts = []
    if name == "circle":
        S.append((_circle(0, 0, 1), 1))
    elif name in ("triangle", "triangle-down"):
        b, verts = _poly(3, math.pi / 2 if name == "triangle-down" else -math.pi / 2)
        S += [(_circle(0, 0, 1), 0.5), (b, 1)]
    elif name == "square":
        b, verts = _poly(4, -math.pi / 4)
        S += [(_circle(0, 0, 1), 0.5), (b, 1)]
    elif name == "hexagon":
        b, verts = _poly(6, -math.pi / 2)
        S += [(_circle(0, 0, 1), 0.5), (b, 1)]
    elif name == "hexagram":
        b1, v1 = _poly(3, -math.pi / 2)
        b2, v2 = _poly(3, math.pi / 2)
        S += [(_circle(0, 0, 1), 0.5), (b1, 1), (b2, 1)]
        verts = v1 + v2
    elif name == "pentagram":
        b, verts = _poly(5, -math.pi / 2, step=2)
        S += [(_circle(0, 0, 1), 0.5), (b, 1)]
    elif name in ("flower", "seed"):
        r = 1 / 3.0 if name == "flower" else 0.5
        cs = [(0, 0)] + [(math.cos(TAU * i / 6 - math.pi / 2) * r, math.sin(TAU * i / 6 - math.pi / 2) * r) for i in range(6)]
        if name == "flower":
            cs += [(math.cos(TAU * i / 6 - math.pi / 2) * 2 * r, math.sin(TAU * i / 6 - math.pi / 2) * 2 * r) for i in range(6)]
            cs += [(math.cos(TAU * i / 6) * r * 3 ** 0.5, math.sin(TAU * i / 6) * r * 3 ** 0.5) for i in range(6)]
        S += [(_circle(x, y, r), 0.8) for x, y in cs]
        S.append((_circle(0, 0, 1.0 if name == "flower" else 1.0), 1.2))
    elif name == "vesica":
        S += [(_circle(-0.32, 0, 0.64), 1), (_circle(0.32, 0, 0.64), 1)]
    elif name == "spiral":
        S += [(_circle(0, 0, 1), 0.4), (_spiral, 1.2)]
    elif name == "eye":
        b, verts = _poly(3, -math.pi / 2)

        def lens(ctx):
            ctx.move_to(-0.42, 0.12)
            ctx.curve_to(-0.2, -0.12, 0.2, -0.12, 0.42, 0.12)
            ctx.curve_to(0.2, 0.36, -0.2, 0.36, -0.42, 0.12)
            ctx.close_path()

        def rays(ctx):
            for i in range(16):
                a = TAU * i / 16
                ctx.move_to(math.cos(a) * 1.08, math.sin(a) * 1.08)
                ctx.line_to(math.cos(a) * 1.22, math.sin(a) * 1.22)
        S += [(b, 1.2), (lens, 1), (_circle(0, 0.12, 0.11), 1), (rays, 0.7)]
    elif name == "ouroboros":
        S += [(None, 0)]  # drawn by draw_ouroboros
    else:
        raise ValueError("forma %r não existe (use %s)" % (name, ", ".join(SHAPES)))
    return S, verts


STATIC = ("circle", "triangle", "triangle-down", "square", "hexagon", "hexagram", "pentagram", "flower", "seed",
          "vesica", "spiral", "eye", "ouroboros")
DYNAMIC = ("wave", "pendulum", "arrows")
SHAPES = STATIC + DYNAMIC


def draw_ouroboros(P, ctx, t, k, a, lw):
    """Snake eating its tail: tapered ring + head. k = reveal 0..1. Unit space."""
    if k <= 0:
        return
    a0 = -math.pi / 2 + 0.28
    span = (TAU - 0.42) * k
    r = 0.82
    segs = 40
    for i in range(segs):
        f0, f1 = i / segs, (i + 1) / segs
        if f0 * (TAU - 0.42) > span:
            break
        th0 = a0 + f0 * (TAU - 0.42)
        th1 = a0 + min(f1 * (TAU - 0.42), span)
        wf = 0.35 + 0.65 * min(1, f0 / 0.35) if f0 < 0.35 else 1.0
        ctx.set_line_width(0.13 * wf)
        ctx.set_line_cap(1)
        ctx.new_path()
        ctx.arc(0, 0, r, th0, th1)
        ctx.set_source_rgba(P.ac[0], P.ac[1], P.ac[2], a)
        ctx.stroke()
    # scales: a thin dashed line along the body
    ctx.set_line_cap(0)
    ctx.set_line_width(lw * 0.7)
    ctx.set_dash([0.04, 0.05])
    ctx.new_path()
    ctx.arc(0, 0, r, a0 + 0.3, a0 + max(0.3, span - 0.05))
    bgc = P.t["bg"][1]
    ctx.set_source_rgba(bgc[0] / 255.0, bgc[1] / 255.0, bgc[2] / 255.0, 0.7 * a)
    ctx.stroke()
    ctx.set_dash([])
    if k >= 0.98:
        hk = ease_out_back(prog(k, 0.98, 0.02))
        th = a0 + TAU - 0.42
        hx, hy = math.cos(th) * r, math.sin(th) * r
        ctx.save()
        ctx.translate(hx, hy)
        ctx.rotate(th + math.pi / 2)
        ctx.scale(hk, hk)
        ctx.new_path()
        ctx.move_to(-0.11, -0.04)
        ctx.curve_to(-0.12, 0.12, -0.02, 0.22, 0.03, 0.24)
        ctx.curve_to(0.08, 0.2, 0.12, 0.12, 0.11, -0.04)
        ctx.close_path()
        ctx.set_source_rgba(P.ac[0], P.ac[1], P.ac[2], a)
        ctx.fill()
        ctx.arc(0.045, 0.06, 0.022, 0, TAU)
        ctx.set_source_rgba(bgc[0] / 255.0, bgc[1] / 255.0, bgc[2] / 255.0, a)
        ctx.fill()
        ctx.restore()


def draw_dynamic(P, ctx, s, name, t, start, a, lw):
    """Animated shapes in unit space: wave (vibração), pendulum (ritmo), arrows (causa→efeito)."""
    ac, ac2, fg = P.ac, P.ac2, P.fg
    k = tween(t, start, 1.2, "out")
    if name == "wave":
        for i in range(4):
            rr = ((t * 0.35 + i / 4.0) % 1.0) * 1.15
            ctx.new_path()
            ctx.arc(0, 0, max(0.01, rr), 0, TAU)
            ctx.set_line_width(lw * 0.6)
            ctx.set_source_rgba(ac2[0], ac2[1], ac2[2], a * 0.35 * (1 - rr / 1.15) * k)
            ctx.stroke()
        for j, (fr, amp, col, al) in enumerate(((2, 0.32, ac, 1.0), (3, 0.22, ac2, 0.7), (5, 0.12, fg, 0.45))):
            ctx.new_path()
            for i in range(97):
                x = -1.3 + 2.6 * i / 96
                env = math.sin(math.pi * i / 96)
                y = math.sin(x * fr * 2 + t * (2.2 + j)) * amp * env * k
                if i == 0:
                    ctx.move_to(x, y)
                else:
                    ctx.line_to(x, y)
            ctx.set_line_width(lw * (1.3 - 0.3 * j))
            ctx.set_source_rgba(col[0], col[1], col[2], a * al)
            stroke_reveal(ctx, 4.0, tween(t, start + 0.2 * j, 1.0, "inout"))
    elif name == "pendulum":
        amp = 0.6 * k
        th = amp * math.sin(TAU * (t - start) / 2.4)
        px, py, L = 0, -0.95, 1.55
        ctx.new_path()
        ctx.arc(px, py, L, math.pi / 2 - 0.6, math.pi / 2 + 0.6)
        ctx.set_line_width(lw * 0.6)
        ctx.set_dash([0.03, 0.05])
        ctx.set_source_rgba(ac2[0], ac2[1], ac2[2], a * 0.5)
        ctx.stroke()
        ctx.set_dash([])
        for side in (-1, 1):
            gx, gy = px + math.sin(side * 0.6) * L, py + math.cos(side * 0.6) * L
            ctx.arc(gx, gy, 0.07, 0, TAU)
            ctx.set_source_rgba(fg[0], fg[1], fg[2], a * 0.15)
            ctx.fill()
        bx, by = px + math.sin(th) * L, py + math.cos(th) * L
        ctx.move_to(px, py)
        ctx.line_to(bx, by)
        ctx.set_line_width(lw)
        ctx.set_source_rgba(fg[0], fg[1], fg[2], a * 0.9)
        ctx.stroke()
        ctx.arc(px, py, 0.04, 0, TAU)
        ctx.fill()
        P.soft_dot(ctx, bx, by, 0.3, ac, a * 0.45)
        ctx.arc(bx, by, 0.11, 0, TAU)
        ctx.set_source_rgba(ac[0], ac[1], ac[2], a)
        ctx.fill()
    elif name == "arrows":
        xs = (-1.05, 0.0, 1.05)
        for i, x in enumerate(xs):
            ki = tween(t, start + i * 0.5, 0.6, "back")
            ctx.new_path()
            ctx.arc(x, 0, 0.2 * max(0.01, ki), 0, TAU)
            ctx.set_source_rgba(ac[0], ac[1], ac[2], a * 0.18)
            ctx.fill_preserve()
            ctx.set_line_width(lw)
            ctx.set_source_rgba(ac[0], ac[1], ac[2], a * min(1, ki))
            ctx.stroke()
            if i < 2:
                ka = tween(t, start + i * 0.5 + 0.3, 0.5, "out")
                x0, x1 = x + 0.25, xs[i + 1] - 0.25
                ctx.new_path()
                ctx.move_to(x0, 0)
                ctx.line_to(x0 + (x1 - x0) * ka, 0)
                ctx.set_source_rgba(fg[0], fg[1], fg[2], a * 0.8)
                ctx.stroke()
                if ka >= 1:
                    ctx.move_to(x1, 0)
                    ctx.line_to(x1 - 0.08, -0.06)
                    ctx.line_to(x1 - 0.08, 0.06)
                    ctx.close_path()
                    ctx.fill()
                    f = ((t - start) * 0.8 + i * 0.5) % 1.0
                    P.soft_dot(ctx, x0 + (x1 - x0) * f, 0, 0.09, ac, a * 0.9)


def prep_geometry(P, s):
    shapes = s.get("shape") or s.get("shapes") or "flower"
    if isinstance(shapes, str):
        shapes = [shapes]
    shapes = [str(x).strip().lower() for x in shapes]
    for n in shapes:
        if n not in SHAPES:
            raise ValueError("cena %d (geometry): forma %r não existe (use %s)" % (s["idx"], n, ", ".join(SHAPES)))
    c = s["_c"]
    c["shapes"] = shapes
    strokes = []
    for n in shapes:
        if n in STATIC and n != "ouroboros":
            st, verts = shape_strokes(n)
            strokes += [(b, w) for b, w in st]
            c.setdefault("verts", []).extend(verts)
    lens = []
    m = P.mctx
    for b, w in strokes:
        m.new_path()
        b(m)
        lens.append(path_length(m))
        m.new_path()
    c["strokes"] = list(zip(strokes, lens))
    _sym_block(P, s, 240 * P.u)
    c["labels"] = [P.layout(x, P.t["body"], 24 * P.u, 200 * P.u, 2, min_size=16 * P.u) for x in (s.get("labels") or [])[:3]]


def draw_shape_art(P, ctx, s, t, cx, cy, R, start=0.15):
    c, u = s["_c"], P.u
    _, a = P.vis(s, t, start, 0.4)
    if a <= 0.01:
        return
    strokes = c["strokes"]
    n = len(strokes)
    span = clamp(_speech_span(s, 0.45), 1.4, 3.2)
    lw = 2.2 * u / R
    done = start + span + 0.3
    static = [x for x in c["shapes"] if x in STATIC]
    rot = 0.0
    if static and not any(x in ("eye", "ouroboros") for x in static):
        rot = max(0.0, t - start) * 0.05
    # glow behind the finished drawing (cached blurred mask)
    if n:
        def fill_strokes(g):
            g.scale(R, R)
            g.set_line_width(lw * 2.2)
            for (b, w), _ in strokes:
                g.new_path()
                b(g)
                g.stroke()
        mask = P.glow_mask(("geo", tuple(c["shapes"]), int(R)), 2.6 * R, fill_strokes, max(4, R * 0.05))
        kg = prog(t, done - 0.3, 0.8)
        ctx.save()
        ctx.translate(cx, cy)
        ctx.rotate(rot)
        P.paint_glow(ctx, mask, 0, 0, P.ac, 0.65 * kg * a * pulse(t, 3.0, 0.6, 1.0))
        ctx.restore()
    ctx.save()
    ctx.translate(cx, cy)
    ctx.rotate(rot)
    ctx.scale(R, R)
    ctx.set_line_join(1)
    for j, ((b, w), L) in enumerate(strokes):
        st = start + span * j / (n + 1)
        k = tween(t, st, 2.0 * span / (n + 1), "inout")
        if k <= 0:
            continue
        ctx.new_path()
        b(ctx)
        ctx.set_line_width(lw * w)
        col = P.ac if w >= 1 else P.ac2
        ctx.set_source_rgba(col[0], col[1], col[2], a * (0.95 if w >= 1 else 0.6))
        stroke_reveal(ctx, L, k)
    kv = prog(t, done - 0.2, 0.5) * a
    if kv > 0:
        for (x, y) in c.get("verts", []):
            ctx.arc(x, y, 0.035, 0, TAU)
            ctx.set_source_rgba(P.fg[0], P.fg[1], P.fg[2], kv)
            ctx.fill()
    if "ouroboros" in c["shapes"]:
        draw_ouroboros(P, ctx, t, tween(t, start, span, "inout"), a, lw)
    for name in c["shapes"]:
        if name in DYNAMIC:
            draw_dynamic(P, ctx, s, name, t, start, a, lw)
    ctx.restore()
    if "arrows" in c["shapes"] and c["labels"]:
        for i, lay in enumerate(c["labels"]):
            k2, a2 = P.vis(s, t, start + i * 0.5 + 0.3, 0.6)
            P.draw_layout(ctx, lay, cx + (-1.05 + 1.05 * i) * R, cy + 0.3 * R + 10 * u, "center", P.fg, a2 * a)


def draw_geometry(P, ctx, s, t):
    c, u, W = s["_c"], P.u, P.W
    box = c["box"]
    y = (P.top + P.bottom) / 2 - c["h"] / 2
    cy = y + box * 0.75
    R = box * 0.68
    if "arrows" in c["shapes"]:
        R = min(R, (W - 2 * P.margin) / 2.8)
    draw_shape_art(P, ctx, s, t, W / 2, cy, R)
    _text_below(P, ctx, s, t, y + box * 1.5 + 24 * u, 1.0)


# ---------- wheel / diagram ----------

def prep_wheel(P, s):
    u, W = P.u, P.W
    c = s["_c"]
    nodes = _items(s.get("nodes"), "label")
    if not 2 <= len(nodes) <= 12:
        raise ValueError("cena %d (wheel): \"nodes\" precisa de 2 a 12 itens" % s["idx"])
    c["t"] = P.layout(s.get("title", ""), P.t["font"], 54 * u, W - 2 * P.margin, 1, bold=True, min_size=30 * u)
    top = P.top + (c["t"].height + 18 * u if c["t"].lines else 0)
    avail = P.bottom - top
    R = min(avail * 0.36, W * 0.2)
    c["R"], c["cy"] = R, top + avail / 2 + 4 * u
    lw = W / 2 - R - 30 * u - P.margin
    size = 26 * u if len(nodes) <= 8 else 21 * u
    c["labels"] = [P.layout(txt, P.t["body"], size, max(120 * u, lw), 2, min_size=15 * u) for txt, _ in nodes]
    c["icons"] = [icon_info(P, ic, "cena %d nó %d" % (s["idx"], i + 1)) if ic else None for i, (_, ic) in enumerate(nodes)]
    act = s.get("active")
    c["active"] = int(act) - 1 if isinstance(act, (int, float)) and 1 <= int(act) <= len(nodes) else None
    n = len(nodes)
    if c["active"] is not None:
        c["starts"] = [0.3 + 0.12 * i for i in range(n)]
    else:
        span = clamp((_speech_span(s) - 0.6) / n, 0.3, 2.0)
        c["starts"] = _beats(s, n, [0.6 + span * i for i in range(n)])
    center = s.get("center")
    c["center_sym"] = None
    c["center_txt"] = None
    if center:
        try:
            c["center_sym"] = P.symbol_info(center) if len(center) <= 2 or center.startswith("fa-") or center.lower() in vl_icons.NAMED else None
        except ValueError:
            c["center_sym"] = None
        if c["center_sym"] is None:
            c["center_txt"] = P.layout(center, P.t["font"], 26 * u, R * 1.1, 2, bold=True, min_size=14 * u)
    c["num"] = P.fonts.role(P.t["font"], True)


def draw_wheel(P, ctx, s, t):
    c, u, W = s["_c"], P.u, P.W
    if c["t"].lines:
        P.draw_layout(ctx, c["t"], W / 2, P.top, "center", P.fg, 1.0, anim=P.word_anim(s, t, 0.05, 0.06, 0.5))
    cx, cy, R = W / 2, c["cy"], c["R"]
    n = len(c["labels"])
    kr = tween(t, 0.1, 1.0, "inout")
    _, a0 = P.vis(s, t, 0.1, 0.4)
    P.ring(ctx, cx, cy, R, kr, P.ac, 0.45 * a0)
    P.ring(ctx, cx, cy, R * 1.28, kr, P.ac2, 0.15 * a0, ticks=48, rot=t * 0.03)
    starts = c["starts"]
    act = c["active"]
    if act is None:
        cur = max([i for i in range(n) if t >= starts[i]] or [-1])
    else:
        cur = act if t >= starts[-1] + 0.3 else -1
    pos = [(cx + math.cos(-math.pi / 2 + TAU * i / n) * R, cy + math.sin(-math.pi / 2 + TAU * i / n) * R) for i in range(n)]
    # spokes and chords
    ctx.set_line_width(1.3 * u)
    for i in range(n):
        k = tween(t, starts[i], 0.5, "out")
        _, a = P.vis(s, t, starts[i], 0.5, i=i)
        if k <= 0:
            continue
        x, y = pos[i]
        hl = i == cur
        ctx.new_path()
        ctx.move_to(cx, cy)
        ctx.line_to(cx + (x - cx) * k, cy + (y - cy) * k)
        ctx.set_source_rgba(P.ac[0], P.ac[1], P.ac[2], a * (0.75 if hl else 0.22))
        ctx.stroke()
        if hl:
            f = (t * 0.7) % 1.0
            P.soft_dot(ctx, cx + (x - cx) * f, cy + (y - cy) * f, 8 * u, P.ac, a * 0.9)
    # center
    _, ac_ = P.vis(s, t, 0.2, 0.6)
    P.soft_dot(ctx, cx, cy, R * 0.55, P.ac, 0.18 * ac_ * pulse(t, 3.0, 0.6, 1.0))
    ctx.new_path()
    ctx.arc(cx, cy, R * 0.32, 0, TAU)
    bg = P.t["bg"][1]
    ctx.set_source_rgba(bg[0] / 255.0, bg[1] / 255.0, bg[2] / 255.0, 0.85 * ac_)
    ctx.fill_preserve()
    ctx.set_line_width(1.6 * u)
    ctx.set_source_rgba(P.ac[0], P.ac[1], P.ac[2], 0.7 * ac_)
    ctx.stroke()
    if c["center_sym"]:
        draw_icon(P, ctx, c["center_sym"], cx, cy, R * 0.36, P.ac, ac_)
    elif c["center_txt"]:
        lay = c["center_txt"]
        P.draw_layout(ctx, lay, cx, cy - lay.height / 2, "center", P.fg, ac_)
    # nodes + labels
    rn = max(16 * u, min(30 * u, R * 0.17))
    for i in range(n):
        k, a = P.vis(s, t, starts[i], 0.6, "back", i)
        if a <= 0.01:
            continue
        x, y = pos[i]
        hl = i == cur
        dimk = 1.0 if (hl or cur < 0) else 0.55
        r = rn * max(0.01, k) * (1.22 if hl else 1.0)
        if hl:
            P.soft_dot(ctx, x, y, r * 2.6, P.ac, 0.55 * a * pulse(t, 1.6, 0.6, 1.0))
        ctx.new_path()
        ctx.arc(x, y, r, 0, TAU)
        if hl:
            ctx.set_source_rgba(P.ac[0], P.ac[1], P.ac[2], a)
        else:
            ctx.set_source_rgba(bg[0] / 255.0, bg[1] / 255.0, bg[2] / 255.0, 0.95 * a)
        ctx.fill_preserve()
        ctx.set_line_width(2 * u)
        ctx.set_source_rgba(P.ac[0], P.ac[1], P.ac[2], a * dimk)
        ctx.stroke()
        inner = (bg[0] / 255.0, bg[1] / 255.0, bg[2] / 255.0) if hl else P.ac
        if c["icons"][i]:
            draw_icon(P, ctx, c["icons"][i], x, y, r * 1.05, inner, a * dimk)
        else:
            ctx.set_font_face(c["num"])
            ctx.set_font_size(r * 1.0)
            txt = str(i + 1)
            ex = ctx.text_extents(txt)
            ctx.move_to(x - ex.x_bearing - ex.width / 2, y - ex.y_bearing - ex.height / 2)
            ctx.set_source_rgba(inner[0], inner[1], inner[2], a * dimk)
            ctx.show_text(txt)
        lay = c["labels"][i]
        ang = -math.pi / 2 + TAU * i / n
        ca, sa = math.cos(ang), math.sin(ang)
        d = rn * 1.25 + 14 * u
        lx, ly = x + ca * d, y + sa * d
        if abs(ca) < 0.3:
            align, tx = "center", lx
            ty = ly - lay.height if sa < 0 else ly
        else:
            align, tx = ("left" if ca > 0 else "right"), lx
            ty = ly - lay.height / 2
        col = P.ac if hl else P.fg
        P.draw_layout(ctx, lay, tx + (1 - min(1, k)) * ca * -20 * u, ty, align, col, a * (1.0 if hl or cur < 0 else 0.7))


# ---------- icons grid ----------

def prep_icons(P, s):
    u, W = P.u, P.W
    c = s["_c"]
    items = _items(s.get("items"), "label")
    if not 1 <= len(items) <= 8:
        raise ValueError("cena %d (icons): \"items\" precisa de 1 a 8 itens {\"icon\": ..., \"label\": ...}" % s["idx"])
    for i, (_, ic) in enumerate(items):
        if not ic:
            raise ValueError("cena %d (icons): item %d sem \"icon\"" % (s["idx"], i + 1))
    c["t"] = P.layout(s.get("title", ""), P.t["font"], 54 * u, W - 2 * P.margin, 2, bold=True, min_size=30 * u)
    n = len(items)
    cols = n if n <= 4 else (n + 1) // 2
    rows = (n + cols - 1) // cols
    top = P.top + (c["t"].height + 30 * u if c["t"].lines else 0)
    avail_h = P.bottom - top
    cw = (W - 2 * P.margin) / cols
    ch = avail_h / rows
    r = min(cw * 0.26, ch * 0.24, 62 * u)
    c.update(cols=cols, rows=rows, cw=cw, ch=ch, r=r, top=top)
    c["infos"] = [icon_info(P, ic, "cena %d item %d" % (s["idx"], i + 1)) for i, (_, ic) in enumerate(items)]
    c["labels"] = [P.layout(txt, P.t["body"], 26 * u, cw - 20 * u, 2, min_size=16 * u) for txt, _ in items]
    span = clamp((_speech_span(s, 0.7) - 0.3) / n, 0.18, 1.2)
    c["starts"] = _beats(s, n, [0.4 + span * i for i in range(n)])


def draw_icons(P, ctx, s, t):
    c, u, W = s["_c"], P.u, P.W
    if c["t"].lines:
        P.draw_layout(ctx, c["t"], W / 2, P.top, "center", P.fg, 1.0, anim=P.word_anim(s, t, 0.05, 0.06, 0.5))
    n = len(c["infos"])
    r = c["r"]
    for i in range(n):
        row, col = divmod(i, c["cols"])
        in_row = min(c["cols"], n - row * c["cols"])
        x0 = (W - in_row * c["cw"]) / 2
        cx = x0 + c["cw"] * (col + 0.5)
        lab = c["labels"][i]
        block = 2 * r + 14 * u + lab.height
        cy = c["top"] + c["ch"] * row + (c["ch"] - block) / 2 + r
        k, a = P.vis(s, t, c["starts"][i], 0.7, "back", i)
        if a <= 0.01:
            continue
        P.soft_dot(ctx, cx, cy, r * 1.7, P.ac, 0.22 * a * pulse(t + i, 3.0, 0.5, 1.0))
        ctx.new_path()
        ctx.arc(cx, cy, r * max(0.01, k), 0, TAU)
        ctx.set_source_rgba(P.ac[0], P.ac[1], P.ac[2], 0.14 * a)
        ctx.fill_preserve()
        ctx.set_line_width(2 * u)
        ctx.set_source_rgba(P.ac[0], P.ac[1], P.ac[2], 0.85 * a)
        ctx.stroke()
        draw_icon(P, ctx, c["infos"][i], cx, cy, r * 1.0, P.fg if not P.light else P.ac, a, k)
        _, a2 = P.vis(s, t, c["starts"][i] + 0.2, 0.5, i=i)
        P.draw_layout(ctx, lab, cx, cy + r + 14 * u, "center", P.fg, a2)


# ---------- kinetic typography ----------

def prep_kinetic(P, s):
    u, W = P.u, P.W
    c = s["_c"]
    text = s.get("text") or s.get("title") or ""
    words = text.split()
    if not words:
        raise ValueError("cena %d (kinetic): falta \"text\"" % s["idx"])
    maxw = W - 2 * P.margin
    pages = []
    lay = P.layout(text, P.t["font"], 92 * u, maxw, 3, bold=True, min_size=58 * u)
    if len(lay.lines) <= 3:
        pages = [lay]
    else:
        per = 6
        for i in range(0, len(words), per):
            pages.append(P.layout(" ".join(words[i:i + per]), P.t["font"], 86 * u, maxw, 3, bold=True, min_size=46 * u))
    c["pages"] = pages
    total = sum(len(w.text) + 1 for p in pages for _, _, w in p.words()) or 1
    sp = s.get("speech") or 0
    window = sp * 0.92 if sp > 0 else s["dur"] * 0.7
    times, acc = [], 0
    for p in pages:
        tt = []
        for _, _, w in p.words():
            tt.append(0.15 + window * acc / total)
            acc += len(w.text) + 1
        times.append(tt)
    if len(pages) > 1 and len(s.get("sents", [])) == len(pages):
        # one sentence per page: start each page with its sentence
        for pi, tt in enumerate(times):
            st, du = s["sents"][pi][0], s["sents"][pi][1]
            base = tt[0]
            span = (tt[-1] - base) or 1.0
            times[pi] = [st + (x - base) / span * du * 0.85 for x in tt]
    c["times"] = times


def draw_kinetic(P, ctx, s, t):
    c, u, W = s["_c"], P.u, P.W
    pages, times = c["pages"], c["times"]
    pi = 0
    for i in range(len(pages)):
        if t >= times[i][0] - 0.05:
            pi = i
    lay = pages[pi]
    tt = times[pi]
    nxt = times[pi + 1][0] if pi + 1 < len(pages) else None
    y = (P.top + P.bottom) / 2 - lay.height / 2

    def anim(i):
        st = tt[i]
        k, a = P.vis(s, t, st, 0.45, "back", i)
        if nxt is not None:
            a *= 1 - tween(t, nxt - 0.25, 0.22, "in")
        sc = 1.35 - 0.35 * k
        return a, 0.0, (1 - min(1, k)) * 26 * u, sc
    # glow under accent words
    i = 0
    for li, (lw, words) in enumerate(lay.lines):
        for w in words:
            if w.accent:
                a, _, _, _ = anim(i)
                if a > 0.02:
                    x = W / 2 - lw / 2 + w.x + w.w / 2
                    yy = y + li * lay.line_h + lay.size * 0.55
                    P.soft_dot(ctx, x, yy, w.w * 0.7, P.ac, 0.22 * a)
            i += 1
    P.draw_layout(ctx, lay, W / 2, y, "center", P.fg, 1.0, anim=anim)


# ---------- split: text + illustration ----------

def prep_split(P, s):
    u, W = P.u, P.W
    c = s["_c"]
    colw = (W - 2 * P.margin) * 0.54
    c["colw"] = colw
    c["t"] = P.layout(s.get("title", ""), P.t["font"], 54 * u, colw, 2, bold=True, min_size=30 * u)
    body = s.get("text") or ""
    c["b"] = P.layout(body, P.t["body"], 32 * u, colw, 7, min_size=20 * u) if body else None
    items = _items(s.get("bullets"))
    c["bul"] = [P.layout(x, P.t["body"], 30 * u, colw - 40 * u, 2, min_size=18 * u) for x, _ in items]
    if s.get("shape") or s.get("shapes"):
        prep_geometry(P, s)
        c["t"] = P.layout(s.get("title", ""), P.t["font"], 54 * u, colw, 2, bold=True, min_size=30 * u)
        c["art"] = "shape"
    elif s.get("symbol") or s.get("icon"):
        icon_info(P, s.get("symbol") or s.get("icon"), "cena %d (split)" % s["idx"])
        c["art"] = "symbol"
    else:
        raise ValueError("cena %d (split): falta a ilustração: \"symbol\" ou \"shape\"" % s["idx"])
    h = c["t"].height + 24 * u
    if c["b"]:
        h += c["b"].height
    h += sum(b.height + 14 * u for b in c["bul"])
    c["h"] = h
    nb = max(1, len(c["bul"]))
    span = clamp((_speech_span(s) - 0.6) / nb, 0.3, 1.6)
    c["bstarts"] = _beats(s, len(c["bul"]), [0.6 + i * span for i in range(nb)])


def draw_split(P, ctx, s, t):
    c, u, W = s["_c"], P.u, P.W
    left_art = (s.get("side") or "right") == "left"
    colw = c["colw"]
    tx = P.margin + ((W - 2 * P.margin) - colw if left_art else 0)
    ax = P.margin + ((W - 2 * P.margin - colw) / 2 if left_art else colw + (W - 2 * P.margin - colw) / 2)
    cy = (P.top + P.bottom) / 2
    box = min((W - 2 * P.margin - colw) * 0.62, (P.bottom - P.top) * 0.5)
    if c["art"] == "symbol":
        halo(P, ctx, s, t, ax, cy, box * 0.7)
        P.draw_symbol(ctx, s, t, s.get("symbol") or s.get("icon"), ax, cy, box, start=0.25, spin=bool(s.get("spin")))
    else:
        R = box * 0.7
        if "arrows" in c["shapes"]:
            R = min(R, (W - 2 * P.margin - colw) / 3.0)
        draw_shape_art(P, ctx, s, t, ax, cy, R)
    y = cy - c["h"] / 2
    P.draw_layout(ctx, c["t"], tx, y, "left", P.fg, 1.0, anim=P.word_anim(s, t, 0.1, 0.06, 0.5))
    y += c["t"].height + 6 * u
    k, a = P.vis(s, t, 0.4, 0.7)
    underline(P, ctx, tx, y, min(c["t"].width, 220 * u), k, a, align="left")
    y += 18 * u
    if c["b"]:
        n = P.nwords(c["b"])
        step = clamp(_speech_span(s, 0.6) / max(1, n), 0.02, 0.1)
        P.draw_layout(ctx, c["b"], tx, y, "left", P.fg, 0.92, anim=P.word_anim(s, t, 0.6, step, 0.5, rise=8 * u, ease="out"))
        y += c["b"].height + 10 * u
    for i, b in enumerate(c["bul"]):
        k, a = P.vis(s, t, c["bstarts"][i], 0.5, "back", i)
        ctx.arc(tx + 8 * u, y + b.size * 0.62, 5 * u * max(0.01, k), 0, TAU)
        ctx.set_source_rgba(P.ac[0], P.ac[1], P.ac[2], a)
        ctx.fill()
        P.draw_layout(ctx, b, tx + 30 * u + (1 - min(1, k)) * 20 * u, y, "left", P.fg, a)
        y += b.height + 14 * u


KINDS = {
    "title": (prep_title, draw_title), "cta": (prep_title, draw_title), "bullets": (prep_bullets, draw_bullets),
    "terminal": (prep_terminal, draw_terminal), "quote": (prep_quote, draw_quote),
    "symbol": (prep_symbol, draw_symbol), "geometry": (prep_geometry, draw_geometry),
    "wheel": (prep_wheel, draw_wheel), "diagram": (prep_wheel, draw_wheel), "icons": (prep_icons, draw_icons),
    "kinetic": (prep_kinetic, draw_kinetic), "split": (prep_split, draw_split),
}


def prepare(P, s):
    s["_c"] = {}
    KINDS[s["kind"]][0](P, s)
    s["_c"]["cap"] = P.caption_prepare(s)


def draw(P, ctx, s, t):
    """Scene content (no background/captions) under the scene camera."""
    ctx.save()
    P.camera(ctx, s, t)
    KINDS[s["kind"]][1](P, ctx, s, t)
    ctx.restore()
