"""G-Files: loader, shipped data, scene chatter, and the screens via a pty."""
from concurrent.futures import ThreadPoolExecutor
import os
import random
import re
import shutil
import tempfile
import unittest

from courierhst import ansi, content, gfiles
from tests.test_session_pty import BBS_COLS, geometry, pyte, run_session


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="latin-1") as fh:
        fh.write(text)


class Loader(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_shipped_sections(self):
        secs = gfiles.load()
        self.assertEqual([s["folder"] for s in secs],
                         ["scene", "bbs", "rants", "misc", "hackphrk"])
        self.assertEqual([s["title"] for s in secs],
                         ["Scene & NFOs", "BBS Lists & Ads",
                          "Rants & Editorials", "Humor & Misc", "Hackphrk"])
        for s in secs:
            self.assertGreaterEqual(len(s["files"]), 3, s["folder"])
            for f in s["files"]:
                self.assertEqual(set(f), {"name", "size", "date", "desc", "path"})
                self.assertTrue(f["desc"])
                self.assertLessEqual(len(f["desc"]), 45)
                self.assertRegex(f["date"], r"^\d\d-\d\d-9[0-3]$")
                self.assertEqual(f["size"], os.path.getsize(f["path"]))

    def test_new_section_and_file_picked_up(self):
        write(os.path.join(self.tmp, "scene", "A.TXT"), "first\n")
        write(os.path.join(self.tmp, "cookbook_x", "NEW.txt"), "\n\n  hello there\n")
        secs = gfiles.load(self.tmp)
        self.assertEqual([s["folder"] for s in secs], ["scene", "cookbook_x"])
        self.assertEqual(secs[1]["title"], "Cookbook X")
        self.assertEqual(secs[1]["files"][0]["desc"], "hello there")
        write(os.path.join(self.tmp, "scene", "B.TXT"), "second\n")
        self.assertEqual([f["name"] for f in gfiles.load(self.tmp)[0]["files"]],
                         ["A.TXT", "B.TXT"])

    def test_missing_root(self):
        self.assertEqual(gfiles.load(os.path.join(self.tmp, "nope")), [])

    def test_empty_section_skipped(self):
        os.makedirs(os.path.join(self.tmp, "misc"))
        write(os.path.join(self.tmp, "rants", "readme.dat"), "x")
        self.assertEqual(gfiles.load(self.tmp), [])

    def test_files_bbs_descriptions(self):
        d = os.path.join(self.tmp, "misc")
        write(os.path.join(d, "ONE.TXT"), "line one of the file\n")
        write(os.path.join(d, "TWO.TXT"), "line one of two\n")
        write(os.path.join(d, "files.bbs"),
              "ONE.TXT       Indexed description\n"
              "              continued here\n")
        files = {f["name"]: f for f in gfiles.load(self.tmp)[0]["files"]}
        self.assertEqual(files["ONE.TXT"]["desc"], "Indexed description")
        self.assertEqual(files["TWO.TXT"]["desc"], "line one of two")

    def test_desc_truncated_to_45(self):
        write(os.path.join(self.tmp, "misc", "L.TXT"), "x" * 100 + "\n")
        self.assertEqual(len(gfiles.load(self.tmp)[0]["files"][0]["desc"]), 45)

    def test_date_deterministic(self):
        self.assertEqual(gfiles.fake_date("RATIOS.TXT"), gfiles.fake_date("RATIOS.TXT"))

    def test_unreadable_file_does_not_raise(self):
        write(os.path.join(self.tmp, "misc", "A.TXT"), "hi\n")
        entry = gfiles.load(self.tmp)[0]["files"][0]
        os.remove(entry["path"])
        self.assertEqual(gfiles.read(entry), [])

    def test_read_width_and_tabs(self):
        write(os.path.join(self.tmp, "misc", "W.TXT"), "a\tb\n" + "y" * 200 + "\n")
        lines = gfiles.read(gfiles.load(self.tmp)[0]["files"][0])
        self.assertEqual(lines[0], "a       b")
        self.assertEqual(len(lines[1]), 79)

    def test_read_shipped_files(self):
        for s in gfiles.load():
            for f in s["files"]:
                lines = gfiles.read(f)
                self.assertTrue(25 <= len(lines) <= 80, f["name"])
                self.assertTrue(all(len(x) <= 79 for x in lines))


class ShippedData(unittest.TestCase):
    def test_width_and_phone_numbers(self):
        for s in gfiles.load():
            for f in s["files"]:
                with open(f["path"], "rb") as fh:
                    text = fh.read().decode("latin-1")
                for n, line in enumerate(text.splitlines(), 1):
                    self.assertLessEqual(len(line.expandtabs(8)), 79,
                                         f"{f['name']}:{n}")
                for num in re.findall(r"\d{3}-\d{4}", text):
                    self.assertRegex(num, r"^555-01\d\d$", f["name"])

    def test_index_lines(self):
        for s in gfiles.load():
            idx = os.path.join(os.path.dirname(s["files"][0]["path"]), "files.bbs")
            self.assertTrue(os.path.isfile(idx), s["folder"])


class SceneChatter(unittest.TestCase):
    def test_base_listed(self):
        self.assertIn("Scene Chatter", content.MSG_BASES)

    def test_template_count(self):
        self.assertGreaterEqual(len(content._SCENE_TEMPLATES), 10)

    def test_shape_and_width(self):
        want = set(content.message(random.Random(1), "X"))
        rng = random.Random(7)
        for _ in range(1500):
            m = content.scene_message(rng, content.bbs_name(rng))
            self.assertEqual(set(m), want)
            for line in m["body"] + [m["subj"], m["from"], m["to"]]:
                self.assertLessEqual(ansi.vlen(line), 79, line)
                self.assertNotIn("{", line)
                self.assertNotIn("|", line)
            for num in re.findall(r"\d{3}-\d{4}", " ".join(m["body"])):
                self.assertRegex(num, r"^555-01\d\d$")


SEEDS = (3, 5)
STYLES = ["renegade", "telegard", "mystic", "pcboard"]


@unittest.skipIf(pyte is None, "pyte not installed (pip install '.[test]')")
class GFilesPty(unittest.TestCase):
    def one(self, style, seed):
        cols, rows = 80, 26
        left, top, bottom, status = geometry(cols, rows)
        seen = {"sections": False, "listing": False, "page": False,
                "menu": False}

        def check(screen):
            lines = ["".join(screen.buffer[y][x].data for x in range(cols))
                     for y in range(rows)]
            for y, line in enumerate(lines):
                for x in range(cols):
                    if line[x].strip() == "":
                        continue
                    if y == status - 1:
                        continue
                    if not (top - 1 <= y <= bottom - 1
                            and left <= x < left + BBS_COLS):
                        raise AssertionError(
                            f"glyph outside window x={x} y={y}: {line[x]!r}")
            text = "\n".join(lines)
            if "Scene & NFOs" in text and "Humor & Misc" in text:
                seen["sections"] = True
            if "=" * 70 in text and ".TXT" in text:
                seen["listing"] = True
            if re.search(r"Page \d of \d", text):
                seen["page"] = True
            if "G-Files" in text and ("Goodbye" in text):
                seen["menu"] = True

        code, text = run_session(seed, cols, rows, check,
                                 extra=("--board-style", style))
        if "Traceback" in text:
            raise AssertionError("traceback:\n" + text[-1500:])
        if code != 0:
            raise AssertionError(f"exit code {code}\n{text[-800:]}")
        return seen

    def test_matrix(self):
        cases = [(st, s) for st in STYLES for s in SEEDS]
        with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 4)) as ex:
            futs = [(c, ex.submit(self.one, *c)) for c in cases]
        for case, f in futs:
            with self.subTest(style=case[0], seed=case[1]):
                seen = f.result()
                for k, v in seen.items():
                    self.assertTrue(v, f"{k} never shown")


if __name__ == "__main__":
    unittest.main()
