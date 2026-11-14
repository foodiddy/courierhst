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

# DOS color index -> ANSI color number. DOS counts blue=1, green=2, red=4;
# ANSI counts red=1, green=2, blue=4, so the bits come out swapped.
_DOS_TO_ANSI = [0, 4, 2, 6, 1, 5, 3, 7]

_PIPE_RE = re.compile(r"\|(\||\d\d)")
_RUN_RE = re.compile(r"(?:\|\d\d)+|\|\|")


def sgr(fg, bg=0):
    """Full SGR for a DOS fg (0-15) / bg (0-7) pair."""
    bold = "1;" if fg >= 8 else ""  # DOS "high intensity" maps to bold
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
            return ""  # no change, so no bytes
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
    """Left-pad pipe-coded text to centre it in `width` columns."""
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
    "toxic":   [15, 10, 10, 2, 2, 2, 2],
    "violet":  [15, 13, 13, 5, 5, 1, 1],
    "ice":     [15, 15, 11, 11, 9, 9, 1],
    "blood":   [12, 12, 4, 4, 4, 4, 4],
    "gold":    [15, 14, 14, 6, 6, 4, 4],
    "steel":   [15, 7, 7, 3, 3, 3, 3],
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
    # Two pixels per cell: ▀ puts the top in the foreground, the background
    # takes the bottom. Backgrounds stop at 7 (the bright bit means blink), so
    # a bright bottom pixel has to become the foreground of a ▄ instead.
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


def block_text(text, palette="cyan", sx=1, sy=1, shadow=True, maxw=79):
    """Render text in the block font. Returns list of pipe-coded lines.
    Text too wide for `maxw` columns is word-wrapped into stacked blocks."""
    if _text_width(text, sx) + (1 if shadow else 0) > maxw and " " in text:
        words, parts, cur = text.split(), [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if cur and _text_width(trial, sx) + 1 > maxw:
                parts.append(cur)
                cur = w
            else:
                cur = trial
        parts.append(cur)
        out = []
        for part in parts:
            out += block_text(part, palette, sx, sy, shadow, maxw)
        return out
    px = _glyph_pixels(text, sx, sy)
    h = len(px)
    w = len(px[0]) + (1 if shadow else 0)
    hh = h + (1 if shadow else 0)
    if hh % 2:  # two pixel rows per text row
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
    """A horizontal rule fading through the palette and back."""
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


# --------------------------------------------------------------------------
# Scene-style screen chrome (framed lists, numbered menus, hints, DIZ, NFO)
#
# Every helper returns a list of pipe-coded lines, none wider than MAXW (79)
# visible columns, so the 80-column window never wraps.
# --------------------------------------------------------------------------

MAXW = 79
FRAME = 9          # bright blue frames (|01 is the dim variant)


def _fit(text, width):
    """Truncate to `width` visible columns and right-pad with spaces."""
    return rpad(truncate(text, width), width)


def frame_table(columns, rows, frame=FRAME, header=True, indent=1,
                hdr_color=15, maxw=78):
    """A box-drawing framed table.

    columns: list of (title, width, color) tuples.  `title` is shown in
        `hdr_color` (lowercase by convention), `width` is the cell width in
        visible columns and `color` is the pipe colour number applied to
        every cell of that column (cells may carry their own pipe codes).
    rows: list of rows; each cell is a string or a list of strings (a
        multi-line cell).  Shorter cells are padded with blank lines.
    header: draw the title row and the ``─`` rule under it.
    indent: blank columns left of the frame.
    maxw: the frame is never wider than this; if the columns would be wider,
        the last column is narrowed.

    Returns pipe-coded lines (top edge, header, rule, body, bottom edge).
    """
    widths = [c[1] for c in columns]
    total = indent + 1 + sum(w + 3 for w in widths)
    if total > maxw:
        widths[-1] = max(1, widths[-1] - (total - maxw))
    fc = f"|{frame:02d}"
    pad = " " * indent

    def edge(left, mid, right):
        return pad + fc + left + mid.join("─" * (w + 2) for w in widths) + right

    def line(cells, colors):
        parts = []
        for cell, w, col in zip(cells, widths, colors):
            parts.append(f" {_fit(f'|{col:02d}' + cell, w)} ")
        return pad + fc + "│" + (fc + "│").join(parts) + fc + "│|07"

    out = [edge("┌", "┬", "┐") + "|07"]
    if header:
        out.append(line([c[0] for c in columns], [hdr_color] * len(columns)))
        out.append(edge("├", "┼", "┤") + "|07")
    colors = [c[2] for c in columns]
    for row in rows:
        cells = [[c] if isinstance(c, str) else list(c) for c in row]
        cells += [[""]] * (len(columns) - len(cells))
        height = max(len(c) for c in cells)
        for i in range(height):
            out.append(line([c[i] if i < len(c) else "" for c in cells], colors))
    out.append(edge("└", "┴", "┘") + "|07")
    return out


def numbered_item(n, name, desc="", name_color=15, desc_color=10, width=78):
    """One menu item: ``( 01 ) Name ........ description``.

    Brackets are orange (|06), digits yellow (|14), the name white (or
    `name_color`), and the description green, right-aligned so the line ends
    exactly at column `width` (78).  Returns a single pipe-coded string
    (also a list-of-one-line helper: use ``[numbered_item(...)]``).
    """
    head = f" |06( |14{n:02d} |06) |{name_color:02d}"
    room = width - vlen(head)
    desc = truncate(desc, max(0, room - 2))
    name = truncate(name, max(0, room - vlen(desc) - (2 if desc else 0)))
    gap = width - vlen(head) - vlen(name) - vlen(desc)
    return head + name + " " * gap + (f"|{desc_color:02d}" + desc if desc else "")


def section_header(title, indent=1):
    """``:: ORIGINAL GAMES ::`` with magenta colons and a white title."""
    return " " * indent + f"|13:: |15{truncate(title, 60)} |13::"


def key_hints(pairs, width=78):
    """``(N) Next  (F) Flag`` line: keys and brackets red, labels green.

    pairs: list of (key, label).  Items that would pass `width` are dropped.
    """
    out, used = [], 1
    for key, label in pairs:
        item = f"|12({key}) |10{label}"
        w = vlen(item) + (2 if out else 0)
        if used + w > width:
            break
        out.append(item)
        used += w
    return " " + "  ".join(out) + "|07"


def corner_info(left_lines, right_lines, width=78):
    """Splash info blocks: `left_lines` stacked in the top-left corner and
    `right_lines` right-aligned in the top-right.  One output line per row.
    """
    out = []
    for i in range(max(len(left_lines), len(right_lines))):
        left = left_lines[i] if i < len(left_lines) else ""
        right = right_lines[i] if i < len(right_lines) else ""
        right = truncate(right, width // 2)
        left = truncate(left, max(0, width - vlen(right) - 1))
        gap = max(0, width - vlen(left) - vlen(right))
        out.append(left + " " * gap + right + "|07")
    return out


def diz_block(group, title, publisher, part, parts, kind, supplier, cracker,
              protect, width=45, short=False):
    """FILE_ID.DIZ-style description, every line <= `width` (<= 45) columns:

        ─┤ CRiMSON TiDE ├────────────
        Title (c) Publisher
        [01/05]  VGA Strategy
        Supplied by X · Cracked by Y
        Doc check removed

    The supplier/cracker line is split in two when it would not fit.
    `short=True` keeps only the first three lines (for disks 2..n of a set).
    """
    width = min(width, 45)
    group = truncate(group, width - 6)
    top = f"|09─┤ |14{group} |09├" + "─" * max(0, width - vlen(group) - 5)
    body = [
        f"|15{title} |07(c) {publisher}",
        f"|08[|15{int(part):02d}|08/|15{int(parts):02d}|08]  |11{kind}",
    ]
    if not short:
        credit = f"|07Supplied by |13{supplier}|07 · Cracked by |13{cracker}"
        if vlen(credit) <= width:
            body.append(credit)
        else:
            body += [f"|07Supplied by |13{supplier}", f"|07Cracked by |13{cracker}"]
        body.append(f"|10{protect}")
    return [top] + [truncate(ln, width) for ln in body]


def updated_banner(date, width=78):
    """Framed ``UPDATED> mm/dd/yy`` banner (red frame, yellow text), one row
    centred in `width`.  `date` is any short string, normally mm/dd/yy."""
    text = f"|12╞═╡ |14UPDATED> |15{date} |12╞═╡"
    return [center(text, width)]


def nfo_page(group, fields, greets, width=78):
    """NFO-style release page: a framed ``field | value`` table titled with
    the group, then a greets line.

    fields: list of (label, value) such as Release, Supplier, Cracker,
    Protection, Disks, Date.  greets: list of group names.
    """
    lw = max(len(f[0]) for f in fields)
    vw = width - 2 - (lw + 3) - 3 - 1
    rows = [[f"{k.lower()}", v] for k, v in fields]
    out = [center(f"|09─┤ |14{truncate(group, 40)} |09├─", width)]
    out += frame_table([("field", lw, 14), ("release info", vw, 15)], rows,
                       maxw=width)
    g = truncate(", ".join(greets), width - 12)
    out.append(f" |13greets|08: |10{g}")
    return out


def art_tag(handle, group=""):
    """A small lowercase artist tag (2-4 chars, e.g. ``sk`` or ``mt67``)
    derived deterministically from the artist's handle/group, dark grey."""
    import zlib
    src = "".join(c for c in handle.lower() if c.isalpha()) or "x"
    h = zlib.crc32((handle + group).encode())
    a = src[0]
    b = src[1:][h % len(src[1:])] if len(src) > 1 else "x"
    tag = a + b
    if (h >> 8) % 3 == 0:
        tag += f"{(h >> 4) % 90 + 10}"
    return f"|08{tag}"
