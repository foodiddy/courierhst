"""Original hand-drawn ANSI art pieces, credited to fictional scene artists.

Every piece is a list of pipe-coded rows (CP437 blocks, shades and colour
gradients).  Shapes are drawn as character grids and coloured with small
painters; all rows are padded with spaces to one visible width.
"""

from . import ansi

W_SKULL = 26


def _runs(cells):
    """cells: list of (ch, fg, bg) -> pipe-coded row, switching colour only on change."""
    out, fg, bg = [], 7, 0
    for ch, f, b in cells:
        if ch == " " and b == 0:
            f = fg
        if ch == "|":
            ch = "||"
        code = ""
        if b != bg:
            code += f"|{16 + b:02d}"
            bg = b
        if f != fg:
            code += f"|{f:02d}"
            fg = f
        out.append(code + ch)
    return "".join(out) + ("|07|16" if (fg, bg) != (7, 0) else "")


def _from_rows(rows, paint, width):
    """Centre or left-pad char rows to `width`, then colour each cell with paint(x, y, ch, row)."""
    out = []
    for y, row in enumerate(rows):
        row = row.ljust(width)[:width]
        cells = []
        for x, ch in enumerate(row):
            c = paint(x, y, ch, row) if ch != " " else None
            fg, bg = c if isinstance(c, tuple) else (c if c is not None else 7, 0)
            cells.append((ch, fg, bg))
        out.append(_runs(cells))
    return out


def _centre(rows, width):
    return [r.center(width) for r in rows]


def _mirror(half):
    """Left half rows (outer edge first) -> full symmetric rows."""
    swap = str.maketrans("▌▐▛▜", "▐▌▜▛")
    return [h + h[::-1].translate(swap) for h in half]


class _Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.c = [[(" ", 7, 0)] * w for _ in range(h)]

    def put(self, x, y, ch, fg=7, bg=0):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.c[y][x] = (ch, fg, bg)

    def rect(self, x0, y0, x1, y1, ch=" ", fg=7, bg=0):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.put(x, y, ch, fg, bg)

    def text(self, x, y, s, fg=7, bg=0):
        for i, ch in enumerate(s):
            self.put(x + i, y, ch, fg, bg)

    def lines(self):
        return [_runs(r) for r in self.c]


# ---------------------------------------------------------------- skull
def _skull():
    rows = _centre([
        "▄▄▄██████▄▄▄",
        "▄██████████████▄",
        "▐████████████████▌",
        "▐█▄▄▄▄██████▄▄▄▄█▌",
        "▐█ ░░ ██████ ░░ █▌",
        "▐█▀▀▀▀██▀▀██▀▀▀▀█▌",
        "▀█████ ▀▀ █████▀",
        "▀███▄▄▄▄▄▄███▀",
        "▐█▌█▌█▌█▌█▌█▌",
        "▀█▀█▀█▀█▀█▀█▀",
        "▒▒▓▓▓▓▓▓▓▓▓▓▓▓▒▒",
    ], W_SKULL)

    def paint(x, y, ch, row):
        if y == 4 and ch == "░":
            return 12
        if y == 10:
            return 12 if abs(x - W_SKULL / 2 + .5) < 4 else 4
        if y in (8, 9):
            return 15 if x % 2 else 7
        a, b = len(row) - len(row.lstrip()), len(row.rstrip())
        t = (x - a) / max(1, b - a - 1)
        if y <= 2 and t < .45:
            return 15
        return 15 if t < .3 else (7 if t < .68 else 8)
    return _from_rows(rows, paint, W_SKULL)


# ---------------------------------------------------------------- modem
def _modem():
    c = _Canvas(30, 10)
    c.text(1, 0, "▄" * 27, 7)
    c.rect(0, 1, 28, 6, " ", 0, 7)
    for y in range(1, 7):
        c.put(0, y, "█", 15, 7)
        c.put(27, y, "▒", 8, 7)
        c.put(28, y, "░", 8, 7)
    c.text(3, 1, "COURiER HST", 4, 7)
    c.text(15, 1, "14.4", 0, 7)
    c.text(21, 1, "V.32bis", 8, 7)
    c.text(2, 2, "▀" * 24, 8, 7)
    c.rect(2, 3, 25, 4, " ", 7, 0)
    labels = ["HS", "AA", "CD", "OH", "RD", "SD", "TR", "MR"]
    lit = [10, 8, 10, 8, 14, 12, 10, 11]
    for i, (lb, col) in enumerate(zip(labels, lit)):
        x = 3 + i * 3
        c.text(x, 3, lb, 8, 0)
        c.put(x, 4, "■", col, 0)
        c.put(x + 1, 4, "▄" if col != 8 else " ", col, 0)
    c.text(2, 5, "▄" * 24, 8, 7)
    c.text(1, 7, "▀" * 27, 8)
    c.text(3, 8, "▀▀", 8)
    c.text(23, 8, "▀▀", 8)
    c.text(5, 9, "░░▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒░░", 8)
    c.text(26, 4, "═", 3, 7)
    c.text(27, 4, "╗", 3, 7)
    return c.lines()


# ---------------------------------------------------------------- floppy
def _floppy():
    c = _Canvas(26, 12)
    c.rect(0, 0, 25, 11, " ", 9, 1)
    c.rect(0, 0, 0, 11, "▌", 9, 1)
    c.rect(25, 0, 25, 11, "▐", 8, 1)
    c.rect(0, 11, 25, 11, "▄", 8, 1)
    c.rect(22, 0, 25, 0, " ", 7, 0)
    c.put(21, 0, "▄", 1, 0)
    c.put(22, 0, "▄", 1, 0)
    c.put(23, 1, "▄", 1, 0)
    c.put(24, 1, " ", 7, 0)
    c.rect(24, 1, 25, 1, " ", 7, 0)
    c.put(23, 1, "▄", 1, 0)
    c.text(2, 1, "HD", 15, 1)
    c.rect(6, 0, 17, 4, " ", 0, 7)
    c.rect(6, 0, 6, 4, "▌", 15, 7)
    c.rect(17, 0, 17, 4, "▐", 8, 7)
    c.rect(11, 1, 15, 3, " ", 7, 0)
    c.rect(11, 1, 15, 1, "▄", 8, 0)
    c.text(8, 2, "▒▒", 8, 7)
    c.rect(3, 6, 22, 11, " ", 0, 7)
    c.rect(3, 6, 22, 6, "▀", 15, 7)
    c.text(5, 7, "-=[ WaReZ DiSK ]=-", 4, 7)
    c.text(5, 8, "NOiR  vol. 07/13", 0, 7)
    c.text(5, 9, "─" * 16, 8, 7)
    c.text(5, 10, "ALL FiLES TESTED", 1, 7)
    c.rect(22, 6, 22, 11, "▒", 8, 7)
    c.rect(3, 11, 22, 11, "▄", 8, 1)
    c.rect(1, 9, 1, 10, "▌", 0, 1)
    return c.lines()


# ---------------------------------------------------------------- dragon
def _dragon():
    half = [
        "▄█▄         ▄▄▄",
        "▀██▄▄▄▄▄▄▄▄█████",
        " ▀██▀▀▀▀▀███████",
        "  ▀█▄▄▄▄▄▄▄▄▄▄██",
        "  ▄██▀▀▀▀▄▄▄█▀▀▀",
        "  ██▌▄▄▄▄▀███▄▄█",
        "  ██▌▐███▀███▀▀▀",
        "  ▀██▄▀▀▄████▄▄▄",
        "   ▀██▄▄▄████▀██",
        "    ▀▀▀▀▀▄▀█▀▀▀▀",
        "         ▀▄█▄▄▄",
    ]
    rows = _mirror(half)
    w = len(rows[0])

    def paint(x, y, ch, row):
        d = min(x, w - 1 - x)
        if y == 4 and ch in "▀▄" and 5 <= d <= 8:
            return 14
        if y == 5 and ch == "▄":
            return 12
        if y == 6 and d >= 12 and ch in "▀":
            return 8
        if y == 7 and d >= 12:
            return 8
        if y == 9:
            return 15
        if y == 10:
            return 12 if d > 12 else 4
        t = d / (w / 2)
        if y == 0:
            return 10
        return 10 if t > .55 else (2 if t > .15 else 8)
    return _from_rows(rows, paint, w)


# ---------------------------------------------------------------- ship
def _ship():
    rows = [
        "  ∙              ∙      ",
        "           ▄▄▄▄          ∙",
        "   ▄▄     ▄█████▄▄",
        "▒░▄██▄▄▄▄████████████▄▄▄",
        "▓▒▓███████▀▀▀▀▀██████████▄▄",
        "▒▓██████████████████████████▀",
        "░▒▀██▀▀▀▀▀▀▀▀▀▀████████▀▀▀▀▀",
        "   ▀▀     ▀█████▀▀",
        "  ∙        ▀▀▀▀      ∙",
    ]

    def paint(x, y, ch, row):
        if ch == "∙":
            return 8
        if x < 3 and ch in "░▒▓":
            return (4, 12, 14)[x]
        if y == 4 and ch == "▀":
            return 11
        if x < 5 and y in (3, 4, 5, 6):
            return 12
        if y == 5 and x >= 26:
            return 15
        return 15 if y <= 3 else (7 if y == 4 else (8 if y >= 6 else 7))
    return _from_rows(rows, paint, 30)


# ---------------------------------------------------------------- phone
def _phone():
    import math
    c = _Canvas(34, 11)
    c.text(5, 0, "▄" * 24, 12)
    c.rect(3, 1, 30, 1, "█", 12)
    c.text(6, 1, "▀" * 8, 15)
    c.rect(3, 2, 8, 2, "█", 12)
    c.rect(25, 2, 30, 2, "█", 12)
    c.text(9, 2, "▀" * 16, 4)
    c.text(3, 3, "▀" * 6, 4)
    c.text(25, 3, "▀" * 6, 4)
    c.text(10, 3, "▐▌", 8)
    c.text(22, 3, "▐▌", 8)
    c.text(6, 4, "▄" * 22, 12)
    c.rect(3, 5, 30, 9, "█", 12)
    c.rect(3, 5, 3, 9, "▌", 15)
    c.rect(28, 5, 30, 9, "▓", 4)
    c.rect(3, 9, 30, 9, "▄", 4)
    c.text(5, 10, "▀" * 24, 4)
    c.text(7, 10, "░░", 8)
    for y, hw in enumerate([6, 9, 10, 9, 6]):
        c.rect(16 - hw + 1, 5 + y, 16 + hw - 1, 5 + y, " ", 0, 7)
    for k in range(10):
        t = math.radians(35 + k * 30)
        c.put(round(16.5 + 7.6 * math.cos(t)), round(7 - 1.8 * math.sin(t)), "○", 0, 7)
    c.put(16, 7, "◙", 8, 7)
    c.put(17, 7, "◙", 8, 7)
    return c.lines()


_META = {
    "skull": ("hexcraft", "NOiR", ("panel",), _skull),
    "modem": ("copperwire", "PRiZM", ("panel",), _modem),
    "floppy": ("byte witch", "SPECTRA", ("panel",), _floppy),
    "dragon": ("drakon", "CHROMA", ("door",), _dragon),
    "ship": ("starfall", "HUE", ("door",), _ship),
    "phone": ("rotary joe", "iNK", ("bye",), _phone),
}


def _pad(rows):
    w = max(ansi.vlen(x) for x in rows)
    return [x + " " * (w - ansi.vlen(x)) for x in rows]


PIECES = {
    name: {"lines": _pad(draw()), "artist": artist, "group": group, "uses": uses}
    for name, (artist, group, uses, draw) in _META.items()
}


def piece(name):
    return list(PIECES[name]["lines"])


def pick(rng, use):
    names = sorted(n for n, p in PIECES.items() if use in p["uses"])
    return rng.choice(names)


def credit(name):
    p = PIECES[name]
    return f"|08ansi by {p['artist'].lower()}/{p['group'].lower()}"


def side_by_side(left, right, gap=2, width=79):
    lw = max((ansi.vlen(x) for x in left), default=0)
    out = []
    for i in range(max(len(left), len(right))):
        a = left[i] if i < len(left) else ""
        b = right[i] if i < len(right) else ""
        pad = " " * (lw - ansi.vlen(a))
        out.append(ansi.truncate(f"{a}{pad}|07|16{' ' * gap}{b}", width))
    return out


def wrap(text, width):
    """Wrap pipe-coded `text` to `width` visible columns, repeating its
    opening colour code at the start of each continuation line."""
    lead = ""
    i = 0
    while text[i:i + 1] == "|" and text[i + 1:i + 3].isdigit():
        lead += text[i:i + 3]
        i += 3
    lines, cur = [], ""
    for word in text.split(" "):
        trial = f"{cur} {word}" if cur else word
        if cur and ansi.vlen(trial) > width:
            lines.append(cur)
            cur = lead + word
        else:
            cur = trial
    lines.append(cur)
    return [ansi.truncate(x, width) for x in lines]
