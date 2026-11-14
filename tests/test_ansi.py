import re
import unittest

from courierhst import ansi


class PipeCodes(unittest.TestCase):
    def test_fg_bg(self):
        self.assertEqual(ansi.pipe_to_ansi("|12x", [7, 0]), ansi.sgr(12, 0) + "x")
        self.assertEqual(ansi.pipe_to_ansi("|17x", [7, 0]), ansi.sgr(7, 1) + "x")

    def test_literal_pipe(self):
        self.assertEqual(ansi.pipe_to_ansi("a||b", [7, 0]), "a|b")
        self.assertEqual(ansi.strip("a||b"), "a|b")
        self.assertEqual(ansi.vlen("||||"), 2)

    def test_redundant_sgr_skipped(self):
        st = [7, 0]
        self.assertEqual(ansi.pipe_to_ansi("|07|16hi", st), "hi")
        out = ansi.pipe_to_ansi("|15a|15b", st)
        self.assertEqual(out.count("\x1b["), 1)
        # state carries across calls
        self.assertEqual(ansi.pipe_to_ansi("|15c", st), "c")

    def test_run_collapses_to_one_sgr(self):
        out = ansi.pipe_to_ansi("|09|17|12x", [7, 0])
        self.assertEqual(out.count("\x1b["), 1)

    def test_strip_and_vlen(self):
        self.assertEqual(ansi.strip("|15he|07llo"), "hello")
        self.assertEqual(ansi.vlen("|15he|07llo"), 5)


class Widths(unittest.TestCase):
    def test_truncate_invariants(self):
        s = "|15hello |09wor|07ld ||pipe"
        for w in range(0, ansi.vlen(s) + 3):
            t = ansi.truncate(s, w)
            self.assertLessEqual(ansi.vlen(t), w)
            if w >= ansi.vlen(s):
                self.assertEqual(t, s)
            else:
                self.assertEqual(ansi.vlen(t), w)

    def test_rpad_center(self):
        self.assertEqual(ansi.vlen(ansi.rpad("|15ab", 10)), 10)
        self.assertLessEqual(ansi.vlen(ansi.center("|15ab")), 79)

    def test_block_text_and_logo_fit(self):
        names = ["NEON ABYSS", "THE TWILIGHT FORGE", "FORGOTTEN CATACOMBS",
                 "LATER", "FILES"]
        for pal in ansi.PALETTES:
            for n in names:
                for fn in (ansi.block_text, ansi.logo):
                    lines = fn(n, pal)
                    self.assertTrue(lines)
                    for ln in lines:
                        self.assertLessEqual(
                            ansi.vlen(ln), 79, f"{fn.__name__} {pal} {n!r}")
                        self.assertNotIn("\n", ln)
                for ln in ansi.logo(ansi.elite(n), pal):
                    self.assertLessEqual(ansi.vlen(ln), 79)


if __name__ == "__main__":
    unittest.main()
