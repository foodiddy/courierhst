"""Project rule: none of the seven dirty words may appear in anything the app shows.

The word list lives only in this file.
"""
import ast
import glob
import os
import random
import re
import unittest

from courierhst import art, content, logos

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_STEMS = {
    "shit": ["shit", "shits", "shitty", "shitting", "shitter", "shitters",
             "shitted", "shithead", "shitheads", "shitload", "shitfaced"],
    "piss": ["piss", "pisses", "pissed", "pissing", "pisser", "pissers",
             "pissy", "pisshead"],
    "fuck": ["fuck", "fucks", "fucked", "fucking", "fucker", "fuckers",
             "fuckin", "fuckup", "fuckface", "fuckhead", "phuck", "phucking"],
    "cunt": ["cunt", "cunts", "cunty"],
    "cocksucker": ["cocksucker", "cocksuckers", "cocksucking"],
    "motherfucker": ["motherfucker", "motherfuckers", "motherfucking",
                     "motherfucked"],
    "tits": ["tits", "titty", "titties"],
}
_PREFIXES = ["bull", "horse", "dip", "dumb", "apple", "bat", "jack", "wise",
             "chicken", "ape", "batshit", "mother", "un"]

_WORDS = sorted({w for forms in _STEMS.values() for w in forms},
                key=len, reverse=True)
_PATTERN = re.compile(
    r"(?<![a-z])(?:%s)?(?:%s)(?![a-z])"
    % ("|".join(_PREFIXES), "|".join(_WORDS)), re.I)


def offences(text):
    return [m.group(0) for m in _PATTERN.finditer(text)]


def strip_codes(text):
    return re.sub(r"\|\d\d", "", text.replace("||", "|"))


class FilterSelfTest(unittest.TestCase):
    def test_matches_variants_and_compounds(self):
        for stem, forms in _STEMS.items():
            for w in forms:
                for text in (w, w.upper(), f"what the {w.title()}!", f"a_{w}_b"):
                    with self.subTest(text=text):
                        self.assertTrue(offences(text))
        for text in ("bullshit", "Horseshit", "dipshit", "dumbfuck"):
            self.assertTrue(offences(text), text)

    def test_innocent_words_pass(self):
        for text in ("Scunthorpe", "Essex", "assassin", "pissarro", "title",
                     "titles", "titan", "cocktail", "mother", "motherboard",
                     "shitake", "Fukuoka", "passion", "cocker spaniel"):
            with self.subTest(text=text):
                self.assertEqual(offences(text), [])


class Scan(unittest.TestCase):
    def check(self, label, text):
        hits = offences(strip_codes(text))
        self.assertEqual(hits, [], f"{label}: {text[:80]!r}")

    def test_gfiles(self):
        files = glob.glob(os.path.join(ROOT, "courierhst", "data", "gfiles",
                                       "**", "*"), recursive=True)
        files = [f for f in files if os.path.isfile(f)]
        self.assertGreaterEqual(len(files), 12)
        for path in files:
            with open(path, encoding="latin-1") as fh:
                self.check(os.path.relpath(path, ROOT), fh.read())

    def test_art_pieces(self):
        for name, piece in art.PIECES.items():
            for ln in piece["lines"]:
                self.check(f"art {name}", ln)

    def test_logos(self):
        names = [n for n, _ in content.DOORS] + [g for g in content.GROUPS]
        rng = random.Random(7)
        names += [content.bbs_name(rng) for _ in range(300)]
        for name in names:
            for style in logos.STYLES:
                for ln in logos.render(name.upper(), "cyan", style):
                    self.check(f"logo {name}", ln)
            self.check("name", name)

    def test_generated_posts(self):
        for i in range(500):
            rng = random.Random(i)
            for fn in (content.message, content.scene_message):
                post = fn(rng, content.bbs_name(rng))
                parts = [post["from"], str(post["to"]), post["subj"],
                         *post["body"], post.get("tag") or ""]
                for p in parts:
                    self.check(f"{fn.__name__} seed {i}", p)

    def test_string_literals_in_source(self):
        files = sorted(glob.glob(os.path.join(ROOT, "courierhst", "*.py")))
        self.assertTrue(files)
        for path in files:
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    self.check(f"{os.path.relpath(path, ROOT)}:{node.lineno}",
                               strip_codes(node.value))


if __name__ == "__main__":
    unittest.main()
