"""Original ANSI art pieces: size, colour, picking, side-by-side, credits."""
import random
import unittest

from courierhst import ansi, art, content

INVENTED = {"hexcraft", "copperwire", "byte witch", "drakon", "starfall", "rotary joe"}


class Pieces(unittest.TestCase):
    def test_required_pieces(self):
        for name, uses in [("skull", "panel"), ("modem", "panel"), ("floppy", "panel"),
                           ("dragon", "door"), ("ship", "door"), ("phone", "bye")]:
            self.assertIn(uses, art.PIECES[name]["uses"])

    def test_size_and_shape(self):
        for name, p in art.PIECES.items():
            with self.subTest(piece=name):
                widths = {ansi.vlen(x) for x in p["lines"]}
                self.assertEqual(len(widths), 1, "rows must have equal width")
                self.assertLessEqual(widths.pop(), 34)
                self.assertLessEqual(len(p["lines"]), 14)
                self.assertGreaterEqual(len(p["lines"]), 8)
                self.assertIn(p["group"], content.ART_GROUPS)

    def test_door_and_panel_limits(self):
        for name, p in art.PIECES.items():
            w, h = ansi.vlen(p["lines"][0]), len(p["lines"])
            if "bye" not in p["uses"]:
                self.assertLessEqual(w, 30, name)
            if "door" in p["uses"]:
                self.assertLessEqual(h, 12, name)

    def test_converts_and_has_colours(self):
        for name, p in art.PIECES.items():
            codes = set()
            for line in p["lines"]:
                ansi.pipe_to_ansi(line)
                codes.update(c for c in __import__("re").findall(r"\|(\d\d)", line))
            with self.subTest(piece=name):
                self.assertGreaterEqual(len(codes), 3)

    def test_piece_is_copy(self):
        a = art.piece("skull")
        a[0] = "x"
        self.assertNotEqual(art.piece("skull")[0], "x")

    def test_pick(self):
        for use in ("panel", "door", "bye"):
            for seed in range(30):
                n = art.pick(random.Random(seed), use)
                self.assertIn(use, art.PIECES[n]["uses"])
                self.assertEqual(n, art.pick(random.Random(seed), use))

    def test_credit(self):
        for name, p in art.PIECES.items():
            c = art.credit(name)
            self.assertLessEqual(ansi.vlen(c), 79)
            self.assertEqual(c, f"|08ansi by {p['artist'].lower()}/{p['group'].lower()}")
            self.assertIn(p["artist"], INVENTED)


class SideBySide(unittest.TestCase):
    def check(self, left, right):
        out = art.side_by_side(left, right)
        self.assertEqual(len(out), max(len(left), len(right)))
        for i, line in enumerate(out):
            self.assertLessEqual(ansi.vlen(line), 79)
            if i < len(left):
                self.assertIn("|07|16", line)
        return out

    def test_left_taller(self):
        out = self.check(art.piece("skull"), ["|15one", "|15two"])
        self.assertTrue(ansi.strip(out[-1]).strip() == ansi.strip(art.piece("skull")[-1]).strip())

    def test_right_taller(self):
        out = self.check(["|12ab", "|12c"], ["r%d" % i for i in range(5)])
        self.assertEqual(len(out), 5)

    def test_reset_between_panes(self):
        line = art.side_by_side(["|12|20x"], ["|10y"])[0]
        self.assertLess(line.index("|12|20x"), line.index("|07|16"))
        self.assertLess(line.index("|07|16"), line.index("|10y"))

    def test_truncated(self):
        out = art.side_by_side(["a" * 30], ["b" * 100])
        self.assertEqual(ansi.vlen(out[0]), 79)

    def test_wrap(self):
        for line in art.wrap("|08" + "word " * 30, 30):
            self.assertLessEqual(ansi.vlen(line), 30)
            self.assertTrue(line.startswith("|08"))


if __name__ == "__main__":
    unittest.main()
