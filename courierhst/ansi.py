"""ANSI helpers: Renegade-style pipe color codes, block-letter logos, bars.

Authoring format (period-accurate "pipe codes"):
    |00..|15  foreground color (DOS palette order)
    |16..|23  background color
    ||        a literal pipe
Everything else passes through untouched.  Strings are converted to real
ANSI SGR sequences with `pipe_to_ansi`, emitting full ESC[0;1;3x;4xm style
sequences exactly like a DOS BBS would.
"""

import re

ESC = "\x1b"

# DOS color index -> ANSI color number
_DOS_TO_ANSI = [0, 4, 2, 6, 1, 5, 3, 7]

_PIPE_RE = re.compile(r"\|(\||\d\d)")
_RUN_RE = re.compile(r"(?:\|\d\d)+|\|\|")


def sgr(fg, bg=0):
    """Full SGR for a DOS fg (0-15) / bg (0-7) pair."""
    bold = "1;" if fg >= 8 else ""
    return f"{ESC}[0;{bold}3{_DOS_TO_ANSI[fg & 7]};4{_DOS_TO_ANSI[bg & 7]}m"


def pipe_to_ansi(text, state=None):
    """Convert pipe codes to SGR. `state` is a 2-item list [fg, bg] that is
    carried across calls; a run of codes only costs bytes on the wire when it
    actually changes the attribute, like a decent ANSI editor would save."""
    if state is None:
        state = [7, 0]

    def repl(m):
        run = m.group(0)
        if run == "||":
            return "|"
        fg, bg = state
        for i in range(0, len(run), 3):
            n = int(run[i + 1:i + 3])
            if n <= 15:
                fg = n
            elif n <= 23:
                bg = n - 16
        if [fg, bg] == state:
            return ""
        state[0], state[1] = fg, bg
        return sgr(fg, bg)

    return _RUN_RE.sub(repl, text)


def strip(text):
    """Remove pipe codes (for measuring visible width)."""
    return _PIPE_RE.sub(lambda m: "|" if m.group(1) == "|" else "", text)


def truncate(text, width):
    """Cut pipe-coded text to `width` visible characters, keeping codes."""
    if vlen(text) <= width:
        return text
    out, n, i = [], 0, 0
    while i < len(text) and n < width:
        m = _PIPE_RE.match(text, i)
        if m and m.group(1) != "|":
            out.append(m.group(0))
            i = m.end()
            continue
        if m:  # literal pipe
            out.append("||")
            i = m.end()
        else:
            out.append(text[i])
            i += 1
        n += 1
    return "".join(out)


def vlen(text):
    return len(strip(text))


def center(text, width=79):
    pad = max(0, (width - vlen(text)) // 2)
    return " " * pad + text


def rpad(text, width):
    return text + " " * max(0, width - vlen(text))


# --------------------------------------------------------------------------
# Block font (5x5 pixels per glyph, rendered with half blocks)
# --------------------------------------------------------------------------

_FONT_SRC = {
    "A": ".###. #...# ##### #...# #...#",
    "B": "####. #...# ####. #...# ####.",
    "C": ".#### #.... #.... #.... .####",
    "D": "####. #...# #...# #...# ####.",
    "E": "##### #.... ####. #.... #####",
    "F": "##### #.... ####. #.... #....",
    "G": ".#### #.... #..## #...# .###.",
    "H": "#...# #...# ##### #...# #...#",
    "I": "##### ..#.. ..#.. ..#.. #####",
    "J": "..### ...#. ...#. #..#. .##..",
    "K": "#...# #..#. ###.. #..#. #...#",
    "L": "#.... #.... #.... #.... #####",
    "M": "#...# ##.## #.#.# #...# #...#",
    "N": "#...# ##..# #.#.# #..## #...#",
    "O": ".###. #...# #...# #...# .###.",
    "P": "####. #...# ####. #.... #....",
    "Q": ".###. #...# #.#.# #..#. .##.#",
    "R": "####. #...# ####. #..#. #...#",
    "S": ".#### #.... .###. ....# ####.",
    "T": "##### ..#.. ..#.. ..#.. ..#..",
    "U": "#...# #...# #...# #...# .###.",
    "V": "#...# #...# #...# .#.#. ..#..",
    "W": "#...# #...# #.#.# ##.## #...#",
    "X": "#...# .#.#. ..#.. .#.#. #...#",
    "Y": "#...# .#.#. ..#.. ..#.. ..#..",
    "Z": "##### ...#. ..#.. .#... #####",
    "0": ".###. #..## #.#.# ##..# .###.",
    "1": "..#.. .##.. ..#.. ..#.. .###.",
    "2": ".###. #...# ..##. .#... #####",
    "3": "####. ....# .###. ....# ####.",
    "4": "#..#. #..#. ##### ...#. ...#.",
    "5": "##### #.... ####. ....# ####.",
    "6": ".###. #.... ####. #...# .###.",
    "7": "##### ....# ...#. ..#.. ..#..",
    "8": ".###. #...# .###. #...# .###.",
    "9": ".###. #...# .#### ....# .###.",
    "-": "... ... ### ... ...",
    "!": "# # # . #",
    ".": ". . . . #",
    "'": "# # . . .",
    " ": "... ... ... ... ...",
}
FONT = {k: [r for r in v.split()] for k, v in _FONT_SRC.items()}

# Gradient palettes, top pixel row -> bottom pixel row.
PALETTES = {
    "cyan":    [15, 11, 11, 3, 3, 9, 1],
    "fire":    [15, 14, 14, 12, 12, 4, 4],
    "toxic":   [15, 10, 10, 2, 2, 8, 8],
    "violet":  [15, 13, 13, 5, 5, 1, 1],
    "ice":     [15, 15, 11, 11, 9, 9, 1],
    "blood":   [12, 12, 4, 4, 4, 8, 8],
    "gold":    [15, 14, 14, 6, 6, 4, 4],
    "steel":   [15, 7, 7, 8, 8, 8, 8],
}

# Accent colors (bright, dim) that pair with each palette for menus.
ACCENTS = {
    "cyan": (11, 3), "fire": (14, 4), "toxic": (10, 2), "violet": (13, 5),
    "ice": (15, 9), "blood": (12, 4), "gold": (14, 6), "steel": (15, 8),
}


def _glyph_pixels(text, sx, sy):
    """Return a 2D list of bools for `text` scaled by sx, sy."""
    rows = [[] for _ in range(5 * sy)]
    for i, ch in enumerate(text.upper()):
        g = FONT.get(ch, FONT[" "])
        w = len(g[0])
        for gy in range(5):
            for yy in range(sy):
                row = rows[gy * sy + yy]
                for gx in range(w):
                    row.extend([g[gy][gx] == "#"] * sx)
                if i != len(text) - 1:
                    row.extend([False] * sx)
    return rows


def _text_width(text, sx):
    return sum((len(FONT.get(c, FONT[" "])[0]) + 1) * sx for c in text.upper()) - sx


def _cell(ct, cb):
    """Render one character cell from top/bottom pixel colors (None=empty)."""
    if ct is None and cb is None:
        return "|07|16 "
    if cb is None:
        return f"|{ct:02d}|16▀"
    if ct is None:
        return f"|{cb:02d}|16▄"
    if ct == cb:
        return f"|{ct:02d}|16█"
    if cb < 8:
        return f"|{ct:02d}|{16 + cb}▀"
    if ct < 8:
        return f"|{cb:02d}|{16 + ct}▄"
    return f"|{ct:02d}|{16 + (cb & 7)}▀"


def block_text(text, palette="cyan", sx=1, sy=1, shadow=True):
    """Render text in the block font. Returns list of pipe-coded lines."""
    px = _glyph_pixels(text, sx, sy)
    h = len(px)
    w = len(px[0]) + (1 if shadow else 0)
    hh = h + (1 if shadow else 0)
    if hh % 2:
        hh += 1
    pal = PALETTES[palette]
    grid = [[None] * w for _ in range(hh)]
    for y in range(h):
        c = pal[min(len(pal) - 1, y * len(pal) // h)]
        for x, on in enumerate(px[y]):
            if on:
                grid[y][x] = c
    if shadow:
        for y in range(hh - 1, 0, -1):
            for x in range(w - 1, 0, -1):
                if grid[y][x] is None and y - 1 < h and x - 1 < len(px[0]) \
                        and px[y - 1][x - 1]:
                    grid[y][x] = 8
    lines = []
    for y in range(0, hh, 2):
        lines.append("".join(_cell(grid[y][x], grid[y + 1][x]) for x in range(w))
                     + "|07|16")
    return lines


def logo(text, palette="cyan", width=78):
    """Pick the biggest scale at which every word-wrapped line fits."""
    words = text.split()
    for sx, sy in ((2, 2), (1, 2), (1, 1)):
        lines, cur = [], ""
        ok = True
        for w in words:
            trial = (cur + " " + w).strip()
            if _text_width(trial, sx) + 1 <= width:
                cur = trial
            else:
                if _text_width(w, sx) + 1 > width:
                    ok = False
                    break
                lines.append(cur)
                cur = w
        if not ok:
            continue
        lines.append(cur)
        if sx == 2 and len(lines) > 2:
            continue
        out = []
        for ln in lines:
            for row in block_text(ln, palette, sx, sy):
                out.append(center(row, width + 1))
        return out
    return [center(text, width)]


# --------------------------------------------------------------------------
# Decorations
# --------------------------------------------------------------------------

def fade_bar(width=78, colors=(8, 7, 15, 7, 8)):
    """A ░▒▓█▓▒░ horizontal fade bar."""
    chars = "░▒▓█▓▒░"
    out = []
    for i in range(width):
        t = i / max(1, width - 1)
        ci = min(len(chars) - 1, int(t * len(chars)))
        col = colors[min(len(colors) - 1, int(t * len(colors)))]
        out.append(f"|{col:02d}{chars[ci]}")
    return "".join(out) + "|07"


def gradient_rule(width=78, palette="cyan", char="─"):
    pal = PALETTES[palette]
    seq = list(reversed(pal[1:])) + pal
    out = []
    for i in range(width):
        c = seq[min(len(seq) - 1, i * len(seq) // width)]
        out.append(f"|{c:02d}{char}")
    return "".join(out) + "|07"


def box(lines, width=78, fg=9, title=None, title_color=15, double=False):
    """Box a list of pipe-coded lines."""
    if double:
        tl, tr, bl, br, hz, vt = "╔╗╚╝═║"
    else:
        tl, tr, bl, br, hz, vt = "┌┐└┘─│"
    inner = width - 2
    c = f"|{fg:02d}"
    if title:
        t = f" {title} "
        left = (inner - vlen(t)) // 2
        top = c + tl + hz * left + f"|{title_color:02d}" + t + c + \
            hz * (inner - left - vlen(t)) + tr
    else:
        top = c + tl + hz * inner + tr
    out = [top]
    for ln in lines:
        out.append(c + vt + "|07" + rpad(ln, inner) + c + vt + "|07")
    out.append(c + bl + hz * inner + br + "|07")
    return out


def elite(text):
    """Scene caps: everything upper case except a lowercase i (ELiTE)."""
    return "".join("i" if c in "iI" else c.upper() for c in text)
