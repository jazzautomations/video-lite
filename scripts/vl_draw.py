"""Cairo painter for video-lite v2: layered compositor, text layout, symbols, geometry, scenes.

Layers per frame (back to front):
  1. background  — gradient + accent glows + vignette + grain, drawn ONCE per theme (cached surface)
  2. particles   — screen-space, a pure function of global time (dust, stars, bokeh, code, neon…)
  3. content     — the scene (vector, under a slow camera transform); two scenes blend in transitions
  4. captions    — the narration in sync with the speech, current word highlighted
Expensive things are cached: background, blurred glows (A8 masks), emoji bitmaps, text layouts,
path lengths. Vector strokes/text are cheap in cairo and are redrawn every frame.
"""
import math

import cairo

import vl_common as C
import vl_icons
from vl_motion import clamp, ease_in_out_cubic, hash01, path_length, prog, pulse, stroke_reveal, tween

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont
except ImportError:  # Pillow is optional: no emoji bitmaps, cheaper glows
    Image = None

TAU = 2 * math.pi
EXIT_S = 0.35


def rgb(c):
    return (c[0] / 255.0, c[1] / 255.0, c[2] / 255.0)


# ---------- text layout ----------

class Word:
    __slots__ = ("text", "x", "w", "runs", "accent")

    def __init__(self, text, x, w, runs, accent=False):
        self.text, self.x, self.w, self.runs, self.accent = text, x, w, runs, accent


class Layout:
    """Wrapped text: lines of words with x offsets; size/line_h in px."""

    def __init__(self, size, line_h, lines, face_key):
        self.size, self.line_h, self.lines, self.face_key = size, line_h, lines, face_key

    @property
    def height(self):
        return self.line_h * len(self.lines)

    @property
    def width(self):
        return max([w for w, _ in self.lines] or [0])

    def words(self):
        for li, (lw, words) in enumerate(self.lines):
            for w in words:
                yield li, lw, w


class Fonts:
    def __init__(self):
        self._faces = {}
        self._cover = {}
        self._probe = cairo.Context(cairo.ImageSurface(cairo.FORMAT_A8, 4, 4))
        self.symbols = C.symbol_families()

    def face(self, family, bold=False, italic=False):
        key = (family, bold, italic)
        f = self._faces.get(key)
        if f is None:
            f = cairo.ToyFontFace(family, cairo.FONT_SLANT_ITALIC if italic else cairo.FONT_SLANT_NORMAL,
                                  cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
            self._faces[key] = f
        return f

    def role(self, role, bold=False, italic=False):
        return self.face(C.family(role), bold, italic)

    def covers(self, face, ch):
        key = (id(face), ch)
        v = self._cover.get(key)
        if v is None:
            p = self._probe
            p.set_font_face(face)
            p.set_font_size(20)
            try:
                g = p.get_scaled_font().text_to_glyphs(0, 0, ch, False)
                v = bool(g) and all(x.index != 0 for x in g)
            except Exception:
                v = True
            self._cover[key] = v
        return v

    def face_for(self, ch, primary):
        """primary when it has ch, else the first symbol font that has it."""
        if ord(ch) < 0x2000 or self.covers(primary, ch):
            return primary
        for fam in self.symbols:
            f = self.face(fam)
            if self.covers(f, ch):
                return f
        return primary

    def runs(self, text, primary):
        out, cur, buf = [], None, ""
        for ch in text:
            f = self.face_for(ch, primary)
            if f is not cur and buf:
                out.append((cur, buf))
                buf = ""
            cur = f
            buf += ch
        if buf:
            out.append((cur, buf))
        return out


class Painter:
    def __init__(self, theme, W, H, quality=1.0, captions=True):
        self.t, self.W, self.H, self.q = theme, W, H, quality
        self.u = H / 720.0
        self.fg, self.ac, self.ac2, self.dim = rgb(theme["fg"]), rgb(theme["accent"]), rgb(theme.get("accent2", theme["accent"])), rgb(theme["dim"])
        self.light = sum(theme["bg"][0]) > 380  # paper-like theme: dark text, darker shadows
        self.fonts = Fonts()
        self.captions = captions
        self.mctx = cairo.Context(cairo.ImageSurface(cairo.FORMAT_A8, 4, 4))
        self.margin = 80 * self.u
        self.top = 50 * self.u
        self.bottom = H - (150 * self.u if captions else 50 * self.u)
        self._glow = {}
        self._emoji = {}
        self.bg = self._background()
        self.emoji_path = C.emoji_font()

    # ----- layer 1: background -----
    def _background(self):
        W, H, t = self.W, self.H, self.t
        s = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
        c = cairo.Context(s)
        stops = t["bg"]
        g = cairo.LinearGradient(0, 0, W * 0.35, H)
        for i, col in enumerate(stops):
            g.add_color_stop_rgb(i / max(1, len(stops) - 1), *rgb(col))
        c.set_source(g)
        c.paint()
        for (x, y, r, col, a) in ((0.82, 0.18, 0.55, self.ac, 0.13), (0.12, 0.88, 0.5, self.ac2, 0.10)):
            rg = cairo.RadialGradient(W * x, H * y, 0, W * x, H * y, H * r)
            rg.add_color_stop_rgba(0, col[0], col[1], col[2], a * (0.6 if self.light else 1))
            rg.add_color_stop_rgba(1, col[0], col[1], col[2], 0)
            c.set_source(rg)
            c.paint()
        v = t.get("vignette", 0.5)
        if v > 0:
            rg = cairo.RadialGradient(W / 2, H / 2, H * 0.35, W / 2, H / 2, math.hypot(W, H) * 0.62)
            rg.add_color_stop_rgba(0, 0, 0, 0, 0)
            rg.add_color_stop_rgba(1, 0, 0, 0, v * (0.45 if self.light else 1))
            c.set_source(rg)
            c.paint()
        gr = t.get("grain", 0.0)
        if gr > 0 and Image is not None:
            tile = 256
            noise = Image.effect_noise((tile, tile), 64).point(lambda x: max(0, min(255, (x - 128) * 2 + 128)))
            for invert, col in ((False, 1.0), (True, 0.0)):
                n = ImageChops.invert(noise) if invert else noise
                n = n.point(lambda x: max(0, x - 128) * 2)
                m = cairo.ImageSurface.create_for_data(bytearray(n.tobytes()), cairo.FORMAT_A8, tile, tile, tile)
                pat = cairo.SurfacePattern(m)
                pat.set_extend(cairo.EXTEND_REPEAT)
                c.set_source_rgba(col, col, col, gr)
                c.mask(pat)
        s.flush()
        return s

    # ----- text -----
    def layout(self, text, role, size, max_w, max_lines=2, bold=False, italic=False, min_size=16, accents=True):
        """Wrap text (shrinking the font) to fit max_w x max_lines. *word* marks an accent word."""
        f = self.fonts.role(role, bold, italic)
        size = max(min_size, size)
        raw = (text or "").split()
        while True:
            lay = self._wrap(raw, f, size, max_w, accents)
            if len(lay.lines) <= max_lines or size <= min_size:
                return lay
            size = max(min_size, size * 0.9)

    def _wrap(self, raw, face, size, max_w, accents):
        m = self.mctx
        space = self._adv(face, " ", size)
        lines, cur, x = [], [], 0.0
        in_acc = False
        for token in raw:
            t = token
            acc = in_acc
            if accents and t.startswith("*") and len(t) > 1:
                t = t[1:]
                acc = in_acc = True
            core = t.rstrip(".,;:!?)")
            if accents and acc and core.endswith("*"):
                t = core[:-1] + t[len(core):]
                in_acc = False
            if not t:
                continue
            runs = []
            w = 0.0
            for f, chunk in self.fonts.runs(t, face):
                runs.append((f, chunk, w))
                w += self._adv(f, chunk, size)
            if cur and x + space + w > max_w:
                lines.append((x, cur))
                cur, x = [], 0.0
            if cur:
                x += space
            cur.append(Word(t, x, w, runs, acc))
            x += w
        if cur:
            lines.append((x, cur))
        del m
        return Layout(size, size * 1.22, lines, face)

    def _adv(self, face, text, size):
        m = self.mctx
        m.set_font_face(face)
        m.set_font_size(size)
        return m.text_extents(text).x_advance

    def draw_layout(self, ctx, lay, x, y, align="center", color=None, alpha=1.0, anim=None, accent=None, box_w=None):
        """Draw a layout with its top-left at (x, y) (or centered on x for align=center).

        anim(i) -> (alpha, dx, dy, scale) per word, i = word index in reading order.
        """
        color = color or self.fg
        accent = accent or self.ac
        i = 0
        asc = lay.size * 0.95
        for li, (lw, words) in enumerate(lay.lines):
            if align == "center":
                lx = x - lw / 2
            elif align == "right":
                lx = x - lw
            else:
                lx = x
            by = y + li * lay.line_h + asc
            for w in words:
                a, dx, dy, sc = (1.0, 0.0, 0.0, 1.0) if anim is None else anim(i)
                i += 1
                a *= alpha
                if a <= 0.01:
                    continue
                col = accent if w.accent else color
                wx = lx + w.x + dx
                if sc != 1.0:
                    ctx.save()
                    cx, cy = wx + w.w / 2, by + dy - lay.size * 0.35
                    ctx.translate(cx, cy)
                    ctx.scale(sc, sc)
                    ctx.translate(-cx, -cy)
                ctx.set_source_rgba(col[0], col[1], col[2], a)
                ctx.set_font_size(lay.size)
                for f, chunk, off in w.runs:
                    ctx.set_font_face(f)
                    ctx.move_to(wx + off, by + dy)
                    ctx.show_text(chunk)
                if w.accent:
                    ctx.rectangle(wx, by + dy + lay.size * 0.14, w.w, max(2, lay.size * 0.06))
                    ctx.set_source_rgba(accent[0], accent[1], accent[2], a * 0.8)
                    ctx.fill()
                if sc != 1.0:
                    ctx.restore()
        return i

    def nwords(self, lay):
        return sum(len(ws) for _, ws in lay.lines)

    # ----- element visibility (enter + exit) -----
    def vis(self, s, t, start, dur=0.6, ease="out", i=0):
        """(eased enter progress, alpha) of an element; it exits after the scene ends (transitions)."""
        k = tween(t, start, dur, ease)
        a = prog(t, start, dur * 0.8)
        if t > s["dur"] - 0.05:
            a *= 1 - tween(t, s["dur"] - 0.05 + 0.04 * i, EXIT_S, "in")
        return k, a

    def word_anim(self, s, t, start, step=0.06, dur=0.55, rise=None, ease="back"):
        rise = 22 * self.u if rise is None else rise

        def f(i):
            k, a = self.vis(s, t, start + i * step, dur, ease, i)
            return a, 0.0, (1 - k) * rise, 1.0
        return f

    # ----- glow / symbols -----
    def _a8_from_pil(self, img):
        w, h = img.size
        stride = cairo.ImageSurface.format_stride_for_width(cairo.FORMAT_A8, w)
        data = bytearray(stride * h)
        raw = img.tobytes()
        for y in range(h):
            data[y * stride:y * stride + w] = raw[y * w:(y + 1) * w]
        return cairo.ImageSurface.create_for_data(data, cairo.FORMAT_A8, w, h, stride)

    def glow_mask(self, key, size, draw_fn, blur):
        """Cached blurred A8 mask (size x size) of whatever draw_fn(ctx) fills; centered."""
        k = (key, int(size), int(blur))
        m = self._glow.get(k)
        if m is not None:
            return m
        n = int(size) + 4 * int(blur) + 8
        n += (-n) % 4
        surf = cairo.ImageSurface(cairo.FORMAT_A8, n, n)
        c = cairo.Context(surf)
        c.translate(n / 2, n / 2)
        draw_fn(c)
        surf.flush()
        if Image is not None and blur > 0:
            stride = surf.get_stride()
            buf = bytes(surf.get_data())
            img = Image.frombuffer("L", (n, n), buf, "raw", "L", stride, 1).copy()
            img = img.filter(ImageFilter.GaussianBlur(blur))
            surf = self._a8_from_pil(img)
        self._glow[k] = surf
        return surf

    def paint_glow(self, ctx, mask, cx, cy, color, alpha, scale=1.0):
        if alpha <= 0.01:
            return
        w, h = mask.get_width(), mask.get_height()
        ctx.save()
        ctx.translate(cx, cy)
        if scale != 1.0:
            ctx.scale(scale, scale)
        ctx.set_source_rgba(color[0], color[1], color[2], alpha)
        ctx.mask_surface(mask, -w / 2, -h / 2)
        ctx.restore()

    def soft_dot(self, ctx, cx, cy, r, color, alpha):
        """Cheap radial glow (no blur)."""
        if alpha <= 0.01 or r <= 0:
            return
        g = cairo.RadialGradient(cx, cy, 0, cx, cy, r)
        g.add_color_stop_rgba(0, color[0], color[1], color[2], alpha)
        g.add_color_stop_rgba(1, color[0], color[1], color[2], 0)
        ctx.set_source(g)
        ctx.arc(cx, cy, r, 0, TAU)
        ctx.fill()

    def symbol_info(self, spec):
        kind, text, role = vl_icons.resolve(spec)
        if kind == "glyph":
            if role == "icons":
                face = self.fonts.role("icons")
            else:
                face = self.fonts.face_for(text[0], self.fonts.face(self.fonts.symbols[0]))
            return {"kind": "glyph", "text": text, "face": face}
        return {"kind": "emoji", "text": text}

    def emoji_surface(self, text):
        """Color emoji as a cairo ARGB32 surface (Pillow + NotoColorEmoji), cached; None if impossible."""
        if text in self._emoji:
            return self._emoji[text]
        surf = None
        if Image is not None and self.emoji_path:
            for size in (109, 96, 160, 64):
                try:
                    f = ImageFont.truetype(self.emoji_path, size)
                    break
                except OSError:
                    f = None
            if f is not None:
                im = Image.new("RGBA", (int(f.size * 1.5), int(f.size * 1.5)), (0, 0, 0, 0))
                try:
                    ImageDraw.Draw(im).text((f.size * 0.2, f.size * 0.1), text, font=f, embedded_color=True)
                    bb = im.getbbox()
                except Exception:
                    bb = None
                if bb:
                    im = im.crop(bb)
                    w, h = im.size
                    r, g, b, a = im.split()
                    r, g, b = (ImageChops.multiply(ch, a) for ch in (r, g, b))
                    data = bytearray(Image.merge("RGBA", (b, g, r, a)).tobytes())
                    surf = cairo.ImageSurface.create_for_data(data, cairo.FORMAT_ARGB32, w, h, w * 4)
        self._emoji[text] = surf
        return surf

    def glyph_path(self, ctx, info, size):
        """Build the glyph outline centered on (0,0); returns its ink extents (w, h)."""
        ctx.set_font_face(info["face"])
        ctx.set_font_size(size)
        ex = ctx.text_extents(info["text"])
        ctx.move_to(-ex.x_bearing - ex.width / 2, -ex.y_bearing - ex.height / 2)
        ctx.text_path(info["text"])
        return ex.width, ex.height

    def fit_glyph_size(self, info, box):
        """Font size so the glyph ink fits a box x box square."""
        m = self.mctx
        m.set_font_face(info["face"])
        m.set_font_size(100)
        ex = m.text_extents(info["text"])
        big = max(ex.width, ex.height, 1)
        return 100 * box / big

    def draw_symbol(self, ctx, s, t, spec, cx, cy, box, start=0.2, key="sym", spin=False, color=None, reveal=True):
        """Big symbol with stroke reveal (glyph) or pop (emoji), glow and gentle float."""
        c = s["_c"]
        if key not in c:
            info = self.symbol_info(spec)
            if info["kind"] == "glyph":
                info["size"] = self.fit_glyph_size(info, box)
                self.mctx.new_path()
                self.glyph_path(self.mctx, info, info["size"])
                info["len"] = path_length(self.mctx)
                self.mctx.new_path()
            c[key] = info
        info = c[key]
        color = color or self.ac
        u = self.u
        float_y = math.sin(t * 1.3) * 4 * u
        k_draw = tween(t, start, 1.4, "inout") if reveal else 1.0
        _, a_all = self.vis(s, t, start, 0.3)
        if a_all <= 0.01:
            return
        ctx.save()
        ctx.translate(cx, cy + float_y)
        if spin:
            ctx.rotate(t * 0.35)
        if info["kind"] == "emoji":
            surf = self.emoji_surface(info["text"])
            k = tween(t, start, 0.9, "back")
            a = a_all
            if surf is None:
                info = dict(info, kind="glyph", face=self.fonts.face(self.fonts.symbols[0]))
            else:
                sc = box / max(surf.get_width(), surf.get_height()) * max(0.01, k)
                mask = self.glow_mask(("emoji", info["text"]), box, lambda g: (g.arc(0, 0, box * 0.38, 0, TAU), g.fill()), box * 0.12)
                self.paint_glow(ctx, mask, 0, 0, color, 0.35 * a * pulse(t, 3.0, 0.6, 1.0))
                ctx.rotate((1 - k) * -0.6)
                ctx.scale(sc, sc)
                ctx.set_source_surface(surf, -surf.get_width() / 2, -surf.get_height() / 2)
                ctx.paint_with_alpha(a)
                ctx.restore()
                return
        size = info.get("size") or self.fit_glyph_size(info, box)
        k_fill = tween(t, start + (1.0 if reveal else 0.0), 0.8, "out")
        mask = self.glow_mask(("g", info["text"], id(info["face"])), box,
                              lambda g: (self.glyph_path(g, info, size), g.fill()), max(4, box * 0.05))
        self.paint_glow(ctx, mask, 0, 0, color, 0.75 * k_fill * a_all * pulse(t, 3.2, 0.55, 1.0))
        ctx.new_path()
        self.glyph_path(ctx, info, size)
        if k_fill > 0:
            ctx.set_source_rgba(color[0], color[1], color[2], k_fill * a_all)
            if k_draw < 1:
                ctx.fill_preserve()
            else:
                ctx.fill()
        if k_draw < 1:
            ctx.set_source_rgba(color[0], color[1], color[2], a_all)
            ctx.set_line_width(max(1.5, 2.2 * u))
            stroke_reveal(ctx, info.get("len", 1000), k_draw)
        ctx.new_path()
        ctx.restore()

    def ring(self, ctx, cx, cy, r, k, color, alpha, width=None, ticks=0, rot=0.0):
        """A circle drawn on progressively (k 0..1) with optional tick marks."""
        if k <= 0 or alpha <= 0.01:
            return
        ctx.set_line_width(width or max(1.0, 1.6 * self.u))
        ctx.set_source_rgba(color[0], color[1], color[2], alpha)
        ctx.new_path()
        ctx.arc(cx, cy, r, rot - math.pi / 2, rot - math.pi / 2 + TAU * k)
        ctx.stroke()
        if ticks:
            for i in range(int(ticks * k)):
                a = rot + TAU * i / ticks
                ctx.move_to(cx + math.cos(a) * r * 0.94, cy + math.sin(a) * r * 0.94)
                ctx.line_to(cx + math.cos(a) * r * 1.0, cy + math.sin(a) * r * 1.0)
            ctx.stroke()

    # ----- layer 2: particles -----
    def particles(self, ctx, g):
        style = self.t.get("particles", "dust")
        if style == "none" or self.q <= 0:
            return
        W, H, u = self.W, self.H, self.u
        n = max(6, int({"dust": 40, "stars": 60, "bokeh": 14, "code": 26, "neon": 18, "bubbles": 24}.get(style, 30) * self.q))
        ac, fg = self.ac, self.fg
        if style == "neon":
            self._neon_grid(ctx, g)
        if style == "code":
            ctx.set_font_face(self.fonts.role("mono"))
            ctx.set_font_size(16 * u)
        buckets = {}
        for i in range(n):
            r1, r2, r3, r4 = hash01(i, 1), hash01(i, 2), hash01(i, 3), hash01(i, 4)
            if style in ("dust", "bubbles", "bokeh", "neon"):
                speed = (8 + 22 * r3) * u * (2.2 if style == "bubbles" else 1)
                x = (r1 * W + math.sin(g * 0.4 + i) * 18 * u) % W
                y = (r2 * (H + 60 * u) - g * speed) % (H + 60 * u) - 30 * u
            elif style == "code":
                x = r1 * W
                y = (r2 * H + g * (20 + 30 * r3) * u) % (H + 40 * u) - 20 * u
            else:  # stars
                x = (r1 * W + g * (2 + 4 * r3) * u) % W
                y = r2 * H
            if style == "dust":
                r = (1.0 + 2.2 * r4) * u
                a = 0.10 + 0.25 * r3
                buckets.setdefault(round(a, 1), []).append((x, y, r))
            elif style == "bubbles":
                ctx.set_source_rgba(fg[0], fg[1], fg[2], 0.10 + 0.12 * r4)
                ctx.set_line_width(1.2 * u)
                ctx.new_path()
                ctx.arc(x, y, (3 + 7 * r4) * u, 0, TAU)
                ctx.stroke()
            elif style == "bokeh":
                col = ac if i % 2 else self.ac2
                ctx.set_source_rgba(col[0], col[1], col[2], 0.05 + 0.05 * r4)
                ctx.arc(x, y, (14 + 36 * r4) * u, 0, TAU)
                ctx.fill()
            elif style == "code":
                ctx.set_source_rgba(ac[0], ac[1], ac[2], 0.08 + 0.14 * r4)
                ctx.move_to(x, y)
                ctx.show_text("01{}<>/$#"[i % 9])
            elif style == "neon":
                col = ac if i % 2 else self.ac2
                ctx.set_source_rgba(col[0], col[1], col[2], 0.25 + 0.35 * r4)
                ctx.arc(x, y, (1.0 + 1.6 * r4) * u, 0, TAU)
                ctx.fill()
            else:  # stars: tiny points that twinkle, a few 4-point sparkles
                tw = pulse(g + r4 * 7, 2.5 + 3 * r3, 0.15, 1.0)
                if i % 9 == 0:
                    self._sparkle(ctx, x, y, (5 + 6 * r4) * u * (0.6 + 0.4 * tw), ac, 0.55 * tw)
                else:
                    buckets.setdefault(round(0.25 + 0.6 * tw * r1, 1), []).append((x, y, (0.7 + 1.3 * r4) * u))
        col = self.fg if style == "stars" else (self.dim if not self.light else (0.3, 0.25, 0.2))
        for a, pts in buckets.items():
            ctx.new_path()
            for x, y, r in pts:
                ctx.new_sub_path()
                ctx.arc(x, y, r, 0, TAU)
            ctx.set_source_rgba(col[0], col[1], col[2], a)
            ctx.fill()

    def _sparkle(self, ctx, x, y, r, col, a):
        ctx.new_path()
        ctx.move_to(x, y - r)
        ctx.curve_to(x, y, x, y, x + r, y)
        ctx.curve_to(x, y, x, y, x, y + r)
        ctx.curve_to(x, y, x, y, x - r, y)
        ctx.curve_to(x, y, x, y, x, y - r)
        ctx.set_source_rgba(col[0], col[1], col[2], a)
        ctx.fill()

    def _neon_grid(self, ctx, g):
        W, H, u = self.W, self.H, self.u
        hz = H * 0.66
        ctx.set_line_width(1.2 * u)
        c = self.ac2
        for i in range(1, 9):
            z = ((i + (g * 0.6) % 1.0) / 9.0)
            y = hz + (H - hz) * z * z
            ctx.set_source_rgba(c[0], c[1], c[2], 0.05 + 0.20 * z)
            ctx.move_to(0, y)
            ctx.line_to(W, y)
            ctx.stroke()
        ctx.set_source_rgba(c[0], c[1], c[2], 0.12)
        for i in range(-8, 9):
            ctx.move_to(W / 2 + i * W * 0.02, hz)
            ctx.line_to(W / 2 + i * W * 0.16, H)
        ctx.stroke()

    # ----- layer 4: captions -----
    def caption_prepare(self, s):
        cap = s.get("narration", "")
        if isinstance(cap, list):
            cap = " ".join(str(x) for x in cap)
        if not cap or not self.captions or s.get("speech", 0) <= 0:
            return None
        u = self.u
        maxw = self.W - 2 * self.margin - 40 * u
        lay = self.layout(cap, "sans", 28 * u, maxw, max_lines=99, bold=True, min_size=28 * u, accents=False)
        groups = []
        for i in range(0, len(lay.lines), 2):
            g = lay.lines[i:i + 2]
            groups.append(Layout(lay.size, lay.line_h, g, lay.face_key))
        words = [w for gl in groups for _, ws in gl.lines for w in ws]
        times = []
        sents = s.get("sents") or []
        if sents and sum(len(x[2].split()) for x in sents) == len(words):
            for st, du, text, _ in sents:
                ws = text.split()
                tot = sum(len(w) + 1 for w in ws) or 1
                acc = 0
                for w in ws:
                    times.append(st + du * acc / tot)
                    acc += len(w) + 1
        else:
            total = sum(len(w.text) + 1 for w in words) or 1
            acc = 0
            for w in words:
                times.append(0.15 + s["speech"] * acc / total)
                acc += len(w.text) + 1
        return {"groups": groups, "times": times}

    def caption(self, ctx, s, t):
        cp = s["_c"].get("cap")
        if not cp or t > 0.15 + s["speech"] + 0.4:
            return
        times = cp["times"]
        wi = max(0, sum(1 for x in times if x <= t) - 1)
        gi, n = 0, 0
        for gi, gl in enumerate(cp["groups"]):
            cnt = sum(len(ws) for _, ws in gl.lines)
            if wi < n + cnt:
                break
            n += cnt
        lay = cp["groups"][gi]
        u, W, H = self.u, self.W, self.H
        pad = 16 * u
        bw, bh = lay.width + 2 * pad, lay.height + pad
        x0, y0 = (W - bw) / 2, H - 34 * u - bh
        a = min(1.0, t / 0.25) * (1 - prog(t, 0.15 + s["speech"] + 0.15, 0.25))
        ctx.new_path()
        self.rounded(ctx, x0, y0, bw, bh, 12 * u)
        ctx.set_source_rgba(0, 0, 0, 0.55 * a)
        ctx.fill()
        local = wi - n

        def anim(i):
            return (0.0 if i == local else 1.0 if i < local else 0.8), 0, 0, 1.0
        ctx.save()
        self.draw_layout(ctx, lay, W / 2, y0 + pad * 0.45, "center", (1, 1, 1), a, anim=anim)
        # current word in accent
        k = 0
        for li, (lw, ws) in enumerate(lay.lines):
            for w in ws:
                if k == local:
                    ctx.set_source_rgba(self.ac[0], self.ac[1], self.ac[2], a)
                    ctx.set_font_size(lay.size)
                    for f, chunk, off in w.runs:
                        ctx.set_font_face(f)
                        ctx.move_to(W / 2 - lw / 2 + w.x + off, y0 + pad * 0.45 + li * lay.line_h + lay.size * 0.95)
                        ctx.show_text(chunk)
                k += 1
        ctx.restore()

    def rounded(self, ctx, x, y, w, h, r):
        r = min(r, w / 2, h / 2)
        ctx.new_sub_path()
        ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        ctx.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
        ctx.close_path()

    # ----- camera -----
    def camera(self, ctx, s, t):
        mode = s.get("camera", "auto")
        if mode == "none" or self.q < 0.5:
            return
        k = ease_in_out_cubic(clamp(t / max(1.0, s["dur"] + 0.6)))
        z = 1.0 + 0.045 * k if (s["idx"] % 3 != 2 and mode != "out") else 1.045 - 0.045 * k
        d = 1 if s["idx"] % 2 == 0 else -1
        px = d * 14 * self.u * (k - 0.5)
        py = -6 * self.u * (k - 0.5)
        ctx.translate(self.W / 2 + px, self.H / 2 + py)
        ctx.scale(z, z)
        ctx.translate(-self.W / 2, -self.H / 2)
