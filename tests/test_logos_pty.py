"""Splash screens in every logo style, through a pty + pyte."""
from concurrent.futures import ThreadPoolExecutor
import random
import unittest

from courierhst import ansi, bbs, content, logos
from tests.test_session_pty import geometry, pyte, run_session

COLS, ROWS = 80, 26


def board_for(seed):
    """The first board a ``--seed`` run dials (mirrors __main__)."""
    rng = random.Random(seed)
    user = content.handle(rng)
    return bbs.Board(rng, user)


def seeds_by_style():
    found = {}
    for seed in range(1, 500):
        found.setdefault(board_for(seed).logo_style, seed)
        if len(found) == len(logos.STYLES):
            break
    return found


@unittest.skipIf(pyte is None, "pyte not installed (pip install '.[test]')")
class SplashPty(unittest.TestCase):
    def one(self, seed):
        b = board_for(seed)
        _, top, bottom, _ = geometry(COLS, ROWS)
        names = {b.name.upper()}
        if b.name.startswith("The "):
            names.add(b.name[4:].upper())
        wanted = [[ansi.strip(r).strip() for r in b.logo(n)] for n in names]
        seen = {}

        def check(screen):
            if seen:
                return
            rows = ["".join(screen.buffer[y][x].data for x in range(COLS))
                    for y in range(top - 1, bottom)]
            hit = [i for i, t in enumerate(rows) if f"Sysop {b.sysop}" in t]
            if not hit:
                return
            seen["row"] = hit[0]
            seen["first"] = rows[0]
            texts = {t.strip() for t in rows}
            seen["logo"] = any(all(r in texts for r in w if r) for w in wanted)

        code, text = run_session(seed, COLS, ROWS, check, extra=("--calls", "1"))
        self.assertNotIn("Traceback", text)
        self.assertEqual(code, 0)
        self.assertTrue(seen, "splash never showed the sysop line")
        # not scrolled: the fade bar is still on the window's top row
        self.assertTrue(set("░▒▓█") & set(seen["first"]), "splash scrolled")
        self.assertTrue(seen["logo"], "logo rows not all visible")
        return seen

    def test_each_style(self):
        found = seeds_by_style()
        self.assertEqual(set(found), set(logos.STYLES))
        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = {st: ex.submit(self.one, sd) for st, sd in found.items()}
        for st, f in futs.items():
            with self.subTest(style=st, seed=found[st]):
                f.result()


if __name__ == "__main__":
    unittest.main()
