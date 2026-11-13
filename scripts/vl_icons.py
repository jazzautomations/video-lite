"""Symbol names for video-lite: Font Awesome 4 names, named Unicode symbols and emoji.

A "symbol" in a storyboard can be:
  - a literal character:            "☿", "☯", "✡", "∞"
  - a Font Awesome 4 name:           "fa-cogs", "fa-book", "fa-rocket" (see FA below)
  - a named symbol from NAMED below: "mercurio", "caduceu", "yin-yang", "olho"...
  - an emoji:                        "🔥", "🚀", "💡"
resolve() turns it into (kind, text, font-role): kind is "glyph" (drawn as a vector with cairo,
can be stroke-revealed) or "emoji" (color bitmap via Pillow).
"""

# Font Awesome 4.7 (fontawesome-webfont.ttf / FontAwesome.otf), CSS names without "fa-".
FA = {
    "glass": 0xf000, "music": 0xf001, "search": 0xf002, "envelope-o": 0xf003, "heart": 0xf004,
    "star": 0xf005, "star-o": 0xf006, "user": 0xf007, "film": 0xf008, "check": 0xf00c,
    "times": 0xf00d, "close": 0xf00d, "search-plus": 0xf00e, "power-off": 0xf011, "signal": 0xf012,
    "cog": 0xf013, "gear": 0xf013, "trash-o": 0xf014, "home": 0xf015, "file-o": 0xf016,
    "clock-o": 0xf017, "clock": 0xf017, "road": 0xf018, "download": 0xf019, "inbox": 0xf01c,
    "refresh": 0xf021, "lock": 0xf023, "flag": 0xf024, "headphones": 0xf025, "volume-up": 0xf028,
    "qrcode": 0xf029, "tag": 0xf02b, "tags": 0xf02c, "book": 0xf02d, "bookmark": 0xf02e,
    "print": 0xf02f, "camera": 0xf030, "pencil": 0xf040, "map-marker": 0xf041, "adjust": 0xf042,
    "tint": 0xf043, "edit": 0xf044, "play": 0xf04b, "pause": 0xf04c, "stop": 0xf04d,
    "chevron-left": 0xf053, "chevron-right": 0xf054, "plus-circle": 0xf055, "question-circle": 0xf059,
    "info-circle": 0xf05a, "crosshairs": 0xf05b, "check-circle-o": 0xf05d, "ban": 0xf05e,
    "arrow-left": 0xf060, "arrow-right": 0xf061, "arrow-up": 0xf062, "arrow-down": 0xf063,
    "plus": 0xf067, "minus": 0xf068, "asterisk": 0xf069, "exclamation-circle": 0xf06a, "gift": 0xf06b,
    "leaf": 0xf06c, "fire": 0xf06d, "eye": 0xf06e, "eye-slash": 0xf070, "warning": 0xf071,
    "exclamation-triangle": 0xf071, "plane": 0xf072, "calendar": 0xf073, "random": 0xf074,
    "comment": 0xf075, "magnet": 0xf076, "retweet": 0xf079, "shopping-cart": 0xf07a, "folder": 0xf07b,
    "folder-open": 0xf07c, "bar-chart": 0xf080, "camera-retro": 0xf083, "key": 0xf084, "cogs": 0xf085,
    "gears": 0xf085, "comments": 0xf086, "thumbs-o-up": 0xf087, "thumbs-up": 0xf087, "trophy": 0xf091,
    "phone": 0xf095, "twitter": 0xf099, "facebook": 0xf09a, "github": 0xf09b, "unlock": 0xf09c,
    "credit-card": 0xf09d, "rss": 0xf09e, "hdd-o": 0xf0a0, "bullhorn": 0xf0a1, "certificate": 0xf0a3,
    "globe": 0xf0ac, "wrench": 0xf0ad, "tasks": 0xf0ae, "filter": 0xf0b0, "briefcase": 0xf0b1,
    "users": 0xf0c0, "link": 0xf0c1, "cloud": 0xf0c2, "flask": 0xf0c3, "scissors": 0xf0c4,
    "paperclip": 0xf0c6, "floppy-o": 0xf0c7, "save": 0xf0c7, "bars": 0xf0c9, "list-ul": 0xf0ca,
    "list-ol": 0xf0cb, "table": 0xf0ce, "magic": 0xf0d0, "truck": 0xf0d1, "money": 0xf0d6,
    "envelope": 0xf0e0, "undo": 0xf0e2, "gavel": 0xf0e3, "dashboard": 0xf0e4, "tachometer": 0xf0e4,
    "bolt": 0xf0e7, "sitemap": 0xf0e8, "umbrella": 0xf0e9, "lightbulb-o": 0xf0eb, "lightbulb": 0xf0eb,
    "exchange": 0xf0ec, "cloud-download": 0xf0ed, "cloud-upload": 0xf0ee, "user-md": 0xf0f0,
    "stethoscope": 0xf0f1, "suitcase": 0xf0f2, "bell": 0xf0f3, "coffee": 0xf0f4, "cutlery": 0xf0f5,
    "building-o": 0xf0f7, "hospital-o": 0xf0f8, "medkit": 0xf0fa, "desktop": 0xf108, "laptop": 0xf109,
    "tablet": 0xf10a, "mobile": 0xf10b, "circle-o": 0xf10c, "quote-left": 0xf10d, "quote-right": 0xf10e,
    "spinner": 0xf110, "circle": 0xf111, "reply": 0xf112, "smile-o": 0xf118, "frown-o": 0xf119,
    "gamepad": 0xf11b, "keyboard-o": 0xf11c, "flag-checkered": 0xf11e, "terminal": 0xf120, "code": 0xf121,
    "code-fork": 0xf126, "question": 0xf128, "info": 0xf129, "exclamation": 0xf12a,
    "puzzle-piece": 0xf12e, "microphone": 0xf130, "shield": 0xf132, "rocket": 0xf135, "anchor": 0xf13d,
    "bullseye": 0xf140, "ellipsis-h": 0xf141, "compass": 0xf14e, "eur": 0xf153, "usd": 0xf155,
    "btc": 0xf15a, "file": 0xf15b, "file-text": 0xf15c, "youtube-play": 0xf16a, "instagram": 0xf16d,
    "apple": 0xf179, "windows": 0xf17a, "android": 0xf17b, "linux": 0xf17c, "female": 0xf182,
    "male": 0xf183, "sun-o": 0xf185, "sun": 0xf185, "moon-o": 0xf186, "moon": 0xf186, "archive": 0xf187,
    "bug": 0xf188, "university": 0xf19c, "graduation-cap": 0xf19d, "paw": 0xf1b0, "cube": 0xf1b2,
    "cubes": 0xf1b3, "recycle": 0xf1b8, "car": 0xf1b9, "tree": 0xf1bb, "database": 0xf1c0,
    "life-ring": 0xf1cd, "paper-plane": 0xf1d8, "history": 0xf1da, "sliders": 0xf1de,
    "share-alt": 0xf1e0, "bomb": 0xf1e2, "plug": 0xf1e6, "wifi": 0xf1eb, "calculator": 0xf1ec,
    "paint-brush": 0xf1fc, "birthday-cake": 0xf1fd, "area-chart": 0xf1fe, "pie-chart": 0xf200,
    "line-chart": 0xf201, "toggle-on": 0xf205, "diamond": 0xf219, "ship": 0xf21a, "user-secret": 0xf21b,
    "heartbeat": 0xf21e, "venus": 0xf221, "mars": 0xf222, "mercury": 0xf223, "server": 0xf233,
    "user-plus": 0xf234, "whatsapp": 0xf232, "battery-full": 0xf240, "balance-scale": 0xf24e,
    "hourglass": 0xf254, "hand-paper-o": 0xf256, "map": 0xf279, "industry": 0xf275,
    "handshake-o": 0xf2b5, "handshake": 0xf2b5,
}

# Named symbols (pt-BR and English) -> character from Noto Sans Symbols / Symbols2 / Math.
NAMED = {
    "mercurio": "☿", "mercury": "☿", "hermes": "☿", "caduceu": "☤", "caduceus": "☤",
    "sol": "☉", "sun-symbol": "☉", "lua": "☽", "moon-symbol": "☽", "venus-symbol": "♀", "feminino": "♀",
    "marte": "♂", "masculino": "♂", "jupiter": "♃", "saturno": "♄", "terra": "♁", "urano": "♅",
    "netuno": "♆", "yin-yang": "☯", "yinyang": "☯", "balanca": "⚖", "scales": "⚖", "atomo": "⚛",
    "atom": "⚛", "ankh": "☥", "hexagrama": "✡", "hexagram": "✡", "estrela": "★", "star-symbol": "★",
    "brilho": "✦", "sparkle": "✦", "infinito": "∞", "infinity": "∞", "olho": "👁", "eye-symbol": "👁",
    "ar": "🜁", "air": "🜁", "fogo": "🜂", "fire-symbol": "🜂", "terra-elemento": "🜃", "earth": "🜃",
    "agua": "🜄", "water": "🜄", "enxofre": "🜍", "sulfur": "🜍", "sal": "🜔", "salt": "🜔",
    "triangulo": "△", "triangle-symbol": "△", "circulo-ponto": "⊙", "circumpunct": "⊙",
    "hexagono": "⬡", "hexagon": "⬡", "nodo": "☊", "pentagrama": "⛤", "pentagram": "⛤",
    "raio": "⚡", "lightning": "⚡", "coracao": "♥", "musica": "♪", "note": "♪",
}


def is_emoji(text):
    """True when text should be drawn as a color emoji (not a vector glyph)."""
    for ch in text:
        o = ord(ch)
        if o == 0xFE0F or (0x1F300 <= o <= 0x1FAFF and not 0x1F700 <= o <= 0x1F7FF):
            return True
        if o in (0x2705, 0x2728, 0x274C, 0x2753, 0x2764, 0x26A1, 0x2B50, 0x231B, 0x23F3):
            return True
    return False


def resolve(spec):
    """(kind, text, role) for a symbol spec; kind is glyph|emoji, role is a font role name.

    Raises ValueError with a helpful message when a name is unknown.
    """
    s = (spec or "").strip()
    if not s:
        raise ValueError("símbolo vazio")
    low = s.lower()
    if low.startswith("fa-") or low.startswith("fa "):
        name = low[3:].strip()
        if name in FA:
            return "glyph", chr(FA[name]), "icons"
        try:
            cp = int(name, 16)
            if 0xF000 <= cp <= 0xF2FF:
                return "glyph", chr(cp), "icons"
        except ValueError:
            pass
        near = [k for k in FA if name[:3] and k.startswith(name[:3])][:6]
        raise ValueError("ícone %r não existe no Font Awesome 4%s" % (s, (" — parecidos: " + ", ".join("fa-" + k for k in near)) if near else ""))
    if low in NAMED:
        s = NAMED[low]
    elif len(s) > 2 and not is_emoji(s):
        if low in FA:
            return "glyph", chr(FA[low]), "icons"
        raise ValueError("símbolo %r: use um caractere (☿ ☯ ✡), um nome fa-... (fa-book) ou um emoji (🔥)" % s)
    if is_emoji(s):
        return "emoji", s, "emoji"
    o = ord(s[0])
    if 0xF000 <= o <= 0xF2FF:
        return "glyph", s, "icons"
    return "glyph", s, "symbols"
