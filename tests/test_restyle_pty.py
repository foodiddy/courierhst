"""Scene restyle: every board style through a pty + pyte, two terminal sizes."""
from concurrent.futures import ThreadPoolExecutor
import os
import unittest

from tests.test_session_pty import (BBS_COLS, geometry, pyte, run_session)

STYLES = ["renegade", "telegard", "mystic", "pcboard"]
SIZES = [(80, 26), (120, 40)]
SEEDS = range(1, 6)
FRAME_CHARS = set("┌┐└┘─│├┤┬┴┼")


@unittest.skipIf(pyte is None, "pyte not installed (pip install '.[test]')")
class RestylePty(unittest.TestCase):
    def one(self, style, seed, cols, rows):
        left, top, bottom, status = geometry(cols, rows)
        width = min(80, cols) - 1
        seen = {"frame": False, "colons": False, "arrows": False, "bar": False}

        def check(screen):
            for y in range(rows):
                line = screen.buffer[y]
                for x in range(cols):
                    if line[x].data.strip() == "":
                        continue
                    in_window = (top - 1 <= y <= bottom - 1
                                 and left <= x < left + BBS_COLS)
                    in_status = y == status - 1 and left <= x < left + width
                    if not (in_window or in_status):
                        raise AssertionError(
                            f"glyph outside window at x={x} y={y}: {line[x].data!r}")
            # status row: blue background across the whole bar once drawn
            srow = screen.buffer[status - 1]
            text = "".join(srow[x].data for x in range(cols))
            if "ALT-Z for menu" in text:
                seen["bar"] = True
                for x in range(left, left + width):
                    if srow[x].bg != "blue":
                        raise AssertionError(f"status cell {x} not blue: {srow[x].bg}")
            rows_txt = ["".join(screen.buffer[y][x].data for x in range(cols))
                        for y in range(top - 1, bottom)]
            for t in rows_txt:
                if "filename" in t:
                    i = rows_txt.index(t)
                    near = "".join(rows_txt[max(0, i - 1):i + 3])
                    if "┌" in near and "│" in near and "├" in near:
                        seen["frame"] = True
                if ":::" in t:
                    seen["colons"] = True
                if ">>" in t:
                    seen["arrows"] = True

        code, text = run_session(seed, cols, rows, check,
                                 extra=("--board-style", style))
        if "Traceback" in text:
            raise AssertionError("traceback:\n" + text[-1500:])
        if code != 0:
            raise AssertionError(f"exit code {code}\n{text[-800:]}")
        if not seen["bar"]:
            raise AssertionError("status bar never seen")
        return seen

    def test_matrix(self):
        cases = [(st, s, c, r) for st in STYLES for c, r in SIZES for s in SEEDS]
        with ThreadPoolExecutor(max_workers=min(16, os.cpu_count() or 4)) as ex:
            futs = [(case, ex.submit(self.one, *case)) for case in cases]
        for case, f in futs:
            with self.subTest(style=case[0], seed=case[1], size=f"{case[2]}x{case[3]}"):
                seen = f.result()
                if case[0] in ("renegade", "telegard"):
                    # every seed visits a file area (the planner guarantees it)
                    self.assertTrue(seen["frame"], "file listing not framed")
                if case[0] == "mystic":
                    self.assertTrue(seen["colons"], "no ::: prompt")
                    self.assertTrue(seen["arrows"], "no >> info line")


if __name__ == "__main__":
    unittest.main()
