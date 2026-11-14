"""Logo engine: several 90s-scene looks for board names and door titles.

Styles (all letterforms here are original designs):

* ``block``   - the 5x5 half-block font from :mod:`courierhst.ansi`
* ``chunky``  - 7-pixel-tall heavy half-block letters with a drop shadow
* ``dither``  - the chunky font, shaded towards the bottom with ░▒▓
* ``lineart`` - thin lettering made of ``/ \\ _ |``, gradient left to right

``render`` returns pipe-coded lines and never raises.
"""

from . import ansi

STYLES = ("block", "chunky", "dither", "lineart")

_SUPPORTED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -!.'")

# --------------------------------------------------------------------------
# Chunky font: 7 pixel rows per glyph, 5-7 wide; '#' = pixel.

_CHUNKY_SRC = {
    "A": ".####. ##..## ##..## ###### ##..## ##..## ##..##",
    "B": "#####. ##..## ##..## #####. ##..## ##..## #####.",
    "C": ".##### ##.... ##.... ##.... ##.... ##.... .#####",
    "D": "#####. ##..## ##..## ##..## ##..## ##..## #####.",
    "E": "###### ##.... ##.... #####. ##.... ##.... ######",
    "F": "###### ##.... ##.... #####. ##.... ##.... ##....",
    "G": ".##### ##.... ##.... ##.### ##..## ##..## .#####",
    "H": "##..## ##..## ##..## ###### ##..## ##..## ##..##",
    "I": "###### ..##.. ..##.. ..##.. ..##.. ..##.. ######",
    "J": "....## ....## ....## ....## ##..## ##..## .####.",
    "K": "##..## ##.##. ####.. ###... ####.. ##.##. ##..##",
    "L": "##.... ##.... ##.... ##.... ##.... ##.... ######",
    "M": "##...## ###.### ####### ##.#.## ##...## ##...## ##...##",
    "N": "##..## ###.## ###### ###### ##.### ##..## ##..##",
    "O": ".####. ##..## ##..## ##..## ##..## ##..## .####.",
    "P": "#####. ##..## ##..## #####. ##.... ##.... ##....",
    "Q": ".####. ##..## ##..## ##..## ##.### ##..## .#####",
    "R": "#####. ##..## ##..## #####. ##.##. ##..## ##..##",
    "S": ".##### ##.... ##.... .####. ....## ....## #####.",
    "T": "###### ..##.. ..##.. ..##.. ..##.. ..##.. ..##..",
    "U": "##..## ##..## ##..## ##..## ##..## ##..## .####.",
    "V": "##..## ##..## ##..## ##..## ##..## .####. ..##..",
    "W": "##...## ##...## ##...## ##.#.## ####### ###.### ##...##",
    "X": "##..## ##..## .####. ..##.. .####. ##..## ##..##",
    "Y": "##..## ##..## .####. ..##.. ..##.. ..##.. ..##..",
    "Z": "###### ....## ...##. ..##.. .##... ##.... ######",
    "0": ".####. ##..## ##.### ###### ###.## ##..## .####.",
    "1": "..##. .###. ..##. ..##. ..##. ..##. .####",
    "2": ".####. ##..## ....## ..###. .##... ##.... ######",
    "3": "#####. ....## ....## .####. ....## ....## #####.",
    "4": "##..## ##..## ##..## ###### ....## ....## ....##",
    "5": "###### ##.... #####. ....## ....## ##..## .####.",
    "6": ".####. ##.... #####. ##..## ##..## ##..## .####.",
    "7": "###### ....## ...##. ..##.. ..##.. ..##.. ..##..",
    "8": ".####. ##..## ##..## .####. ##..## ##..## .####.",
    "9": ".####. ##..## ##..## .##### ....## ....## .####.",
    "-": ".... .... .... #### #### .... ....",
    "!": "## ## ## ## ## .. ##",
    ".": ".. .. .. .. .. ## ##",
    "'": "## ## #. .. .. .. ..",
    " ": "... ... ... ... ... ... ...",
}
_CHUNKY = {k: v.split() for k, v in _CHUNKY_SRC.items()}

# --------------------------------------------------------------------------
# Line-art font: 4 text rows per glyph, rows joined by ','.

_LINE_SRC = {
    "A": r"  _  , / \ ,|___|,|   |",
    "B": r"___  ,|__\ ,|__ \,|___/",
    "C": r" ___ ,/    ,\    ,\___ ",
    "D": r"___  ,|   \,|   /,|__/ ",
    "E": r" ___ ,|___ ,|    ,|___ ",
    "F": r" ___ ,|___ ,|    ,|    ",
    "G": r" ___ ,/    ,| __ ,\___/",
    "H": r"|   |,|___|,|   |,|   |",
    "I": r" ___ ,  |  ,  |  , _|_ ",
    "J": r"  ___,    |,    |,\__/ ",
    "K": r"|  / ,| /  ,| \  ,|  \ ",
    "L": r"|    ,|    ,|    ,|___ ",
    "M": r"|\ /|,| ' |,|   |,|   |",
    "N": r"|\  |,| \ |,|  \|,|   |",
    "O": r" ___ ,/   \,|   |,\___/",
    "P": r"___  ,|__\ ,|    ,|    ",
    "Q": r" ___ ,/   \,|   |,\___\,",
    "R": r"___  ,|__\ ,| \  ,|  \ ",
    "S": r" ___ ,/    ,\___ ,___/ ",
    "T": r"_____,  |  ,  |  ,  |  ",
    "U": r"|   |,|   |,|   |,\___/",
    "V": r"\   /,|   |, \ / ,  '  ",
    "W": r"|   |,| | |,| | |, \_/ ",
    "X": r"\   /, \_/ , / \ ,/   \,",
    "Y": r"\   /, \_/ ,  |  ,  |  ",
    "Z": r"_____,   / ,  /  ,/____",
    "0": r" ___ ,|  /|,| / |,|/__|",
    "1": r"  /| , / | ,   | ,  _|_",
    "2": r" ___ ,/   \,  _/ , /___",
    "3": r" ___ ,  _/ ,   \ ,\__/ ",
    "4": r"  /| , / | ,/__|_,   | ",
    "5": r" ____,|___ ,    \,\___/",
    "6": r" ___ ,/    ,|___ ,\___/",
    "7": r"_____,    /,   / ,  /  ",
    "8": r" ___ ,/___\,/   \,\___/",
    "9": r" ___ ,/   \,\___|,  __/",
    "-": r"   ,___,   ,   ",
    "!": r"|,|, ,.",
    ".": r" , , ,.",
    "'": r"', , , ",
    " ": r"   ,   ,   ,   ",
}
_LINE = {k: v.split(",")[:4] for k, v in _LINE_SRC.items()}


# --------------------------------------------------------------------------
# Shared helpers

def _clean(text):
    """Upper-case; anything unsupported becomes a space."""
    return "".join(c if c in _SUPPORTED else " " for c in str(text).upper())


def _wrap(words, measure, width):
    """Greedy word wrap. Returns a list of lines, or None if a word is too wide."""
    lines, cur = [], ""
    for w in words:
        if measure(w) > width:
            return None
        trial = (cur + " " + w) if cur else w
        if measure(trial) <= width:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _palette(palette):
    return ansi.PALETTES.get(palette) or ansi.PALETTES["cyan"]


def _chunky_pixels(line):
    """7 rows of booleans for `line` (one blank column between glyphs)."""
    rows = [[] for _ in range(7)]
    for i, ch in enumerate(line):
        g = _CHUNKY[ch]
        for y in range(7):
            if i:
                rows[y].append(False)
            rows[y].extend(c == "#" for c in g[y])
    return rows


def _chunky_width(line):
    return sum(len(_CHUNKY[c][0]) for c in line) + len(line) - 1 + 1  # + shadow


def _chunky_rows(line, pal):
    px = _chunky_pixels(line)
    w = len(px[0]) + 1
    grid = [[None] * w for _ in range(8)]
    for y in range(7):
        col = pal[y * len(pal) // 7]
        for x, on in enumerate(px[y]):
            if on:
                grid[y][x] = col
    for y in range(7):
        for x in range(w - 1):
            if px[y][x] and grid[y + 1][x + 1] is None:
                grid[y + 1][x + 1] = 8
    return ["".join(ansi._cell(grid[y][x], grid[y + 1][x]) for x in range(w))
            + "|07|16" for y in range(0, 8, 2)]


_SHADES = "▓▒░"


def _dither_width(line):
    return _chunky_width(line)


def _dither_rows(line, pal):
    px = _chunky_pixels(line)
    w = len(px[0]) + 1
    cells = [[None] * w for _ in range(6)]
    for x in range(w - 1):
        for r in (0, 1):
            ct = pal[(2 * r) * len(pal) // 7] if px[2 * r][x] else None
            cb = pal[(2 * r + 1) * len(pal) // 7] if px[2 * r + 1][x] else None
            if ct is not None or cb is not None:
                cells[r][x] = ansi._cell(ct, cb)
        for k in range(3):
            if px[4 + k][x]:
                col = pal[(4 + k) * len(pal) // 7]
                cells[2 + k][x] = f"|{col:02d}|16{_SHADES[k]}"
    solid = [row[:] for row in cells]
    for r in range(1, 6):
        for x in range(1, w):
            if cells[r][x] is None and solid[r - 1][x - 1] is not None:
                cells[r][x] = "|08|16░"
    return ["".join(c or "|07|16 " for c in row) + "|07|16" for row in cells]


def _line_width(line):
    return sum(len(_LINE[c][0]) for c in line) + len(line) - 1


def _line_rows(line, pal):
    rows = [" ".join(_LINE[c][y] for c in line) for y in range(4)]
    w = len(rows[0])
    last = len(pal) - 1
    out = []
    for row in rows:
        s, cur = [], None
        for x, ch in enumerate(row):
            if ch == " ":
                s.append(" ")
                continue
            t = x / (w - 1) if w > 1 else 0.0
            col = pal[round((1 - abs(2 * t - 1)) * last)]
            if col != cur:
                s.append(f"|{col:02d}")
                cur = col
            s.append("||" if ch == "|" else ch)
        out.append("".join(s) + "|07")
    return out


# style -> (width measure, row renderer, rows per text line)
_ENGINES = {
    "chunky": (_chunky_width, _chunky_rows, 4),
    "dither": (_dither_width, _dither_rows, 6),
    "lineart": (_line_width, _line_rows, 4),
}


def _try_style(style, text, pal, width, max_rows):
    measure, draw, height = _ENGINES[style]
    words = text.split()
    if not words:
        return None
    lines = _wrap(words, measure, width)
    if not lines or len(lines) * height > max_rows:
        return None
    out = []
    for ln in lines:
        for row in draw(ln, pal):
            out.append(ansi.center(row, width + 1))
    return out


def _block(text, palette, width, max_rows):
    """The 5x5 font via ansi.logo; cut to size as a last resort."""
    out = ansi.logo(text, palette, width)
    out = [ansi.truncate(ln, 79) for ln in out]
    return out[:max(1, max_rows)]


def render(text, palette="cyan", style="block", width=78, max_rows=12):
    """Return pipe-coded logo lines for `text`; never raises."""
    if palette not in ansi.PALETTES:
        palette = "cyan"
    width = max(1, min(int(width), 78))
    max_rows = max(1, int(max_rows))
    text = _clean(text)
    if style in _ENGINES:
        out = _try_style(style, text, _palette(palette), width, max_rows)
        if out:
            return out
    return _block(text, palette, width, max_rows)
