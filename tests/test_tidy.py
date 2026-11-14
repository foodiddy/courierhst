"""Credit width, dither compact layout, wide logos, palettes and --help text."""
import contextlib
import io
import random
import unittest
from unittest import mock

from courierhst import ansi, bbs, content, logos
from courierhst.__main__ import main


def credit(artist, group, width=79):
    s = bbs.Session.__new__(bbs.Session)
    s.b = mock.Mock(art_by=(artist, group))
    return s._ansi_credit(width)


class Credit(unittest.TestCase):
    def test_always_fits(self):
        for artist in ("hexcraft", "a very long artist handle indeed " * 3, "x"):
            for group in ("noir", "g" * 60, "g" * 70, "g" * 200):
                for width in (79, 60, 40, 20):
                    with self.subTest(artist=artist[:12], group=len(group), w=width):
                        out = credit(artist, group, width)
                        self.assertLessEqual(len(out), width)
                        self.assertTrue(out.endswith(out.rstrip()))
                        body = out.strip()
                        self.assertTrue(body.startswith("ansi by "))
                        a, g = body[len("ansi by "):].split("/")
                        self.assertGreaterEqual(len(a), 1)
                        self.assertGreaterEqual(len(g), 1)

    def test_short_credit_unchanged(self):
        self.assertEqual(credit("HexCraft", "NOiR"),
                         " " * (79 - 21) + "ansi by hexcraft/noir")

    def test_long_group_is_cut(self):
        out = credit("hexcraft", "G" * 100)
        self.assertEqual(len(out), 79)
        self.assertEqual(out.strip(), "ansi by h/" + "g" * 69)


class DitherCompact(unittest.TestCase):
    def test_three_lines_fit_in_twelve_rows(self):
        out = logos.render("THE ELITE CONNECTION HQ", "fire", "dither", max_rows=12)
        self.assertEqual(len(out), 12)
        self.assertNotEqual(out, logos.render("THE ELITE CONNECTION HQ", "fire",
                                              "block", max_rows=12))
        text = "".join(ansi.strip(ln) for ln in out)
        for shade in "░▒":
            self.assertIn(shade, text)

    def test_fallback_share_under_two_percent(self):
        total = fell = 0
        for seed in range(3000):
            b = bbs.Board(random.Random(seed), "u")
            if b.logo_style != "dither":
                continue
            for name in (b.name.upper(), b.name[4:].upper()
                         if b.name.startswith("The ") else b.name.upper()):
                total += 1
                if b.logo(name, max_rows=12) == logos.render(
                        name, b.palette, "block", 78, 12):
                    fell += 1
        self.assertGreater(total, 300)
        self.assertLess(fell / total, 0.02)


class WideLogos(unittest.TestCase):
    def test_every_path_fits_79(self):
        texts = ("", "A", "THE ELITE CONNECTION", "X" * 100,
                 "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z")
        for width in (79, 80, 120, 200):
            for style in logos.STYLES:
                for text in texts:
                    for rows in (1, 4, 12):
                        with self.subTest(w=width, style=style, t=text[:8], r=rows):
                            out = logos.render(text, "cyan", style, width, rows)
                            self.assertTrue(out)
                            self.assertLessEqual(len(out), rows)
                            for ln in out:
                                self.assertLessEqual(ansi.vlen(ln), 79)


class Palettes(unittest.TestCase):
    def test_last_colour_contrasts_with_shadow(self):
        for name, pal in ansi.PALETTES.items():
            self.assertNotIn(pal[-1], (0, 8), name)


class Help(unittest.TestCase):
    def help_text(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), self.assertRaises(SystemExit):
            main(["--help"])
        return " ".join(buf.getvalue().split())

    def test_defaults_shown(self):
        text = self.help_text()
        self.assertIn("default 0.0007", text)
        self.assertIn("default 40", text)
        self.assertIn("default 0 = forever", text)
        self.assertEqual(text.count("default 14400"), 1)
        self.assertEqual(text.count("default 5"), 1)

    def test_description(self):
        self.assertIn("Screensaver: dial up early-90s warez BBSes on a 14.4 USR "
                      "Courier HST. Any key exits.", self.help_text())


if __name__ == "__main__":
    unittest.main()
