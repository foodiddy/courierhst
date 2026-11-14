"""ANSI art screens through a pty + pyte: file areas, goodbye, both doors."""
from concurrent.futures import ThreadPoolExecutor
import os
import unittest

from tests.test_session_pty import BBS_COLS, geometry, pyte, run_session

BLOCKS = set("█▀▄▌▐░▒▓■")
COLS, ROWS = 80, 26
STYLES = ["renegade", "telegard", "mystic"]
SEEDS = range(1, 9)


def window(screen, left, top, bottom):
    return ["".join(screen.buffer[y][x].data for x in range(left, left + BBS_COLS))
            for y in range(top - 1, bottom)]


def art_in_left(row, n=34):
    return any(c in BLOCKS for c in row[:n])


@unittest.skipIf(pyte is None, "pyte not installed (pip install '.[test]')")
class ArtPty(unittest.TestCase):
    def one(self, style, seed):
        left, top, bottom, status = geometry(COLS, ROWS)
        seen = set()

        def check(screen):
            for y in range(ROWS):
                for x in range(COLS):
                    if screen.buffer[y][x].data.strip() and not (
                            (top - 1 <= y <= bottom - 1 and left <= x < left + BBS_COLS)
                            or (y == status - 1 and left <= x < left + BBS_COLS - 1)):
                        raise AssertionError(f"glyph outside window x={x} y={y}")
            rows = window(screen, left, top, bottom)
            joined = "\n".join(rows)
            if "FILE AREAS" in joined and "( 08 )" in joined and "ansi by" in joined:
                hy = next(i for i, t in enumerate(rows) if "FILE AREAS" in t)
                items = rows[hy + 4:hy + 12]
                for k, t in enumerate(items, 1):
                    if f"( {k:02d} )" not in t:
                        raise AssertionError(f"file area {k} not on its row (wrapped?):\n{joined}")
                if sum(art_in_left(t) for t in items) < 5:
                    raise AssertionError("no art beside the file list:\n" + joined)
                seen.add("files")
            if "GOOD BYE FRIEND!" in joined and "ansi by" in joined:
                r = next(t for t in rows if "GOOD BYE FRIEND!" in t)
                if not art_in_left(r.split("GOOD BYE")[0]) and not any(
                        art_in_left(t) for t in rows[rows.index(r) - 2:rows.index(r) + 3]):
                    raise AssertionError("no art beside GOOD BYE:\n" + joined)
                if "ansi by" not in joined:
                    raise AssertionError("no credit on bye screen")
                seen.add("bye")
                if "NO CARRIER" in joined:
                    seen.add("bye+nocarrier")
            if "The Swamp Kingdom" in joined and "forest fights left" in joined:
                i = next(i for i, t in enumerate(rows) if "The Swamp Kingdom" in t)
                if sum(art_in_left(t) for t in rows[i:i + 6]) < 4:
                    raise AssertionError("no dragon beside the tagline:\n" + joined)
                seen.add("shadowmire")
            if "M E R C H A N T" in joined and "turns remaining" in joined:
                i = next(i for i, t in enumerate(rows) if "M E R C H A N T" in t)
                if sum(art_in_left(t) for t in rows[i:i + 6]) < 4:
                    raise AssertionError("no ship beside the tagline:\n" + joined)
                seen.add("starlane")

        code, text = run_session(seed, COLS, ROWS, check, extra=("--board-style", style))
        if "Traceback" in text:
            raise AssertionError("traceback:\n" + text[-1500:])
        if code != 0:
            raise AssertionError(f"exit code {code}")
        return seen

    def test_screens(self):
        cases = [(st, s) for st in STYLES for s in SEEDS]
        with ThreadPoolExecutor(max_workers=min(16, os.cpu_count() or 4)) as ex:
            futs = [(c, ex.submit(self.one, *c)) for c in cases]
        total = set()
        per_style = {st: set() for st in STYLES}
        for case, f in futs:
            with self.subTest(style=case[0], seed=case[1]):
                got = f.result()
                total |= got
                per_style[case[0]] |= got
        for st in STYLES:
            self.assertIn("files", per_style[st], st)
        for key in ("bye", "bye+nocarrier", "shadowmire", "starlane"):
            self.assertIn(key, total)


if __name__ == "__main__":
    unittest.main()
