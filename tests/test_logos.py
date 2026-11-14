import unittest

from courierhst import ansi, logos

ALL_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -!.'"
TEXTS = ["", "A", ALL_CHARS, "THE ELITE CONNECTION",
         "ABCDEFGHIJKLMNOPQRSTUVWXY", "LaTer"]
HALF = set("▀▄█")


class Render(unittest.TestCase):
    def cases(self):
        for style in logos.STYLES:
            for pal in ansi.PALETTES:
                for text in TEXTS:
                    for rows in (12, 4):
                        yield style, pal, text, rows

    def test_every_case_is_sane(self):
        for style, pal, text, rows in self.cases():
            with self.subTest(style=style, palette=pal, text=text, rows=rows):
                out = logos.render(text, pal, style, max_rows=rows)
                self.assertIsInstance(out, list)
                self.assertTrue(out)
                self.assertLessEqual(len(out), rows)
                for ln in out:
                    self.assertLessEqual(ansi.vlen(ln), 79)
                    ansi.pipe_to_ansi(ln)

    def test_block_is_ansi_logo(self):
        for pal in ansi.PALETTES:
            for text in ("A", "THE ELITE CONNECTION", "LaTer", "SHADOWMIRE"):
                self.assertEqual(logos.render(text, pal, "block"),
                                 ansi.logo(text, pal, 78))

    def test_lineart_has_pipes(self):
        out = logos.render("HI", "cyan", "lineart")
        self.assertTrue(any("|" in ansi.strip(ln) for ln in out))
        # literal pipes are doubled so they survive pipe_to_ansi
        self.assertTrue(any("||" in ln for ln in out))
        for ln in out:
            self.assertEqual(ansi.pipe_to_ansi(ln).count("|"),
                             ansi.strip(ln).count("|"))
        text = "".join(ansi.strip(ln) for ln in out)
        self.assertTrue(set(text) <= set(" /\\_|-.'`"))

    def test_lineart_gradient_varies_across_width(self):
        out = logos.render("SHADOWMIRE", "fire", "lineart")
        codes = set()
        for ln in out:
            codes.update(c for c in ansi.pipe_to_ansi(ln).split("\x1b[") if c)
        self.assertGreater(len(codes), 2)

    def test_chunky_and_dither_blocks(self):
        for style in ("chunky", "dither"):
            text = "".join(ansi.strip(ln) for ln in logos.render("ELITE", "cyan", style))
            self.assertTrue(HALF & set(text), style)
        d = "".join(ansi.strip(ln) for ln in logos.render("ELITE", "cyan", "dither"))
        self.assertTrue(set("░▒▓") & set(d))

    def test_chunky_is_four_rows_per_line(self):
        self.assertEqual(len(logos.render("ELITE", "cyan", "chunky")), 4)
        self.assertEqual(len(logos.render("THE ELITE CONNECTION", "cyan", "chunky")), 8)

    def test_styles_differ(self):
        outs = {s: logos.render("SHADOWMIRE", "toxic", s) for s in logos.STYLES}
        self.assertEqual(len({tuple(v) for v in outs.values()}), len(logos.STYLES))

    def test_unsupported_text(self):
        for style in logos.STYLES:
            out = logos.render("@#", "cyan", style)
            self.assertTrue(out)
            for ln in out:
                self.assertLessEqual(ansi.vlen(ln), 79)
        logos.render("a|b\x1b[0m☃", "ice", "lineart")

    def test_bad_arguments_do_not_raise(self):
        self.assertTrue(logos.render("X", "nope", "nope", width=500, max_rows=0))

    def test_too_long_falls_back(self):
        out = logos.render("X" * 200, "cyan", "chunky", max_rows=4)
        self.assertLessEqual(len(out), 4)
        for ln in out:
            self.assertLessEqual(ansi.vlen(ln), 79)


class BoardLogo(unittest.TestCase):
    def test_style_is_drawn_last(self):
        import random
        from courierhst import bbs
        board = bbs.Board(random.Random(5), "x")
        self.assertEqual(board.logo_style, bbs.Board(random.Random(5), "x").logo_style)
        self.assertIn(board.logo_style, logos.STYLES)
        self.assertEqual(board.logo("HI"),
                         logos.render("HI", board.palette, board.logo_style))


if __name__ == "__main__":
    unittest.main()
