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


class SceneChrome(unittest.TestCase):
    LONG = "Extremely Long Name With Many Words " * 6

    def wide(self, lines):
        for ln in lines:
            self.assertLessEqual(ansi.vlen(ln), 79, ansi.strip(ln))

    def test_frame_table(self):
        cols = [("one", 30, 13), ("two", 30, 15), ("three", 30, 10)]
        out = ansi.frame_table(cols, [[self.LONG, self.LONG, [self.LONG, "x"]]])
        self.wide(out)
        plain = [ansi.strip(x) for x in out]
        self.assertTrue(plain[0].lstrip().startswith("┌"))
        self.assertIn("│ one", plain[1])
        self.assertIn("┼", plain[2])
        self.assertTrue(plain[-1].lstrip().startswith("└"))
        self.assertEqual(len(out), 6)  # edge, header, rule, 2 body lines, edge

    def test_numbered_item_right_aligned(self):
        for desc in ("short", "x" * 200, ""):
            it = ansi.numbered_item(7, self.LONG, desc)
            self.assertEqual(ansi.vlen(it), 78)
        it = ansi.numbered_item(7, "Door", "forest RPG")
        self.assertTrue(ansi.strip(it).endswith("forest RPG"))
        self.assertIn("( 07 )", ansi.strip(it))
        self.assertIn("|06( |1407 |06)", it)

    def test_section_header_and_hints(self):
        self.assertEqual(ansi.strip(ansi.section_header("ORIGINAL GAMES")).strip(),
                         ":: ORIGINAL GAMES ::")
        self.wide([ansi.section_header(self.LONG)])
        h = ansi.key_hints([("N", "Next"), ("F", "Flag")] * 20)
        self.wide([h])
        self.assertIn("(N) Next  (F) Flag", ansi.strip(h))
        self.assertIn("|12(N) |10Next", h)

    def test_corner_info(self):
        out = ansi.corner_info([self.LONG, "b", "c"], [self.LONG, "r"])
        self.wide(out)
        self.assertEqual(len(out), 3)
        self.assertTrue(ansi.strip(out[1]).rstrip().endswith("r"))

    def test_diz_block(self):
        out = ansi.diz_block(self.LONG, self.LONG, self.LONG, 1, 5, self.LONG,
                             self.LONG, self.LONG, self.LONG)
        for ln in out:
            self.assertLessEqual(ansi.vlen(ln), 45)
        out = ansi.diz_block("CRiMSON TiDE", "Title", "Pub", 1, 5, "VGA Strategy",
                             "X", "Y", "Doc check removed")
        plain = [ansi.strip(x) for x in out]
        self.assertTrue(plain[0].startswith("─┤ CRiMSON TiDE ├"))
        self.assertEqual(plain[1], "Title (c) Pub")
        self.assertEqual(plain[2], "[01/05]  VGA Strategy")

    def test_updated_and_nfo(self):
        out = ansi.updated_banner("11/02/93")
        self.wide(out)
        self.assertIn("UPDATED> 11/02/93", ansi.strip(out[0]))
        nfo = ansi.nfo_page(self.LONG, [("Release", self.LONG), ("Supplier", "a"),
                                        ("Cracker", "b"), ("Protection", "c"),
                                        ("Disks", "d"), ("Date", "e")],
                            ["A" * 30] * 8)
        self.wide(nfo)
        self.assertIn("greets", ansi.strip(nfo[-1]))

    def test_art_tag(self):
        for h in ("Doc Holiday", "X", "Null Pointer", "Sector 7"):
            t = ansi.strip(ansi.art_tag(h, "NOiR"))
            self.assertTrue(2 <= len(t) <= 4, t)
            self.assertEqual(t, t.lower())
        self.assertTrue(ansi.art_tag("Zero", "HUE").startswith("|08"))


if __name__ == "__main__":
    unittest.main()
