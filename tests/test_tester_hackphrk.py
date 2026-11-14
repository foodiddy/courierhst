"""Tester checks for G-Files part 2 (task mwgq5tmx53f6yi): the hackphrk section.

Data-only task: loader pick-up, file format, phone numbers, a content-safety
denylist, a clean-language check and the cookbook parody markers.
"""
import os
import re
import unittest

from courierhst import gfiles

NAMES = sorted(["PHRKHIST.TXT", "BLUEBOX.TXT", "REDBOX.TXT", "BOXCOLRS.TXT",
                "HACKETHC.TXT", "WARDIAL.TXT", "SYSOPWAR.TXT",
                "ANARCK01.TXT", "ANARCK02.TXT"])
FOLDER = os.path.join(gfiles.DATA_DIR, "hackphrk")

DENY = [
    # explosives, precursors
    r"nitroglycerin", r"nitrate", r"ammonium", r"\bTNT\b", r"thermite",
    r"gunpowder", r"potassium chlorate", r"chlorate", r"picric",
    r"acetone peroxide", r"peroxide", r"sulfuric acid", r"sulphuric",
    r"nitric acid", r"napalm", r"black powder", r"detonat",
    r"\bfuse length", r"grams of", r"ounces of",
    # drugs
    r"synthesi", r"precursor", r"pseudoephedrine", r"ephedrine",
    r"methamphetamine", r"reagent", r"\blsd\b",
    # electronics / phreak methods
    r"schematic", r"resistor", r"capacitor", r"\bohms?\b", r"transistor",
    r"solder", r"\d\s*k?hz\b", r"\bdtmf\b", r"\bmf tones?\b", r"tone table",
    r"\b2600\s*(hz|cycle)", r"crystal", r"\bdiode",
]
DENY_RE = [re.compile(p, re.I) for p in DENY]

# Carlin's seven words and variants. Short ones are whole-word only.
SWEAR_SUB = ["shit", "piss", "fuck", "cunt", "cocksuck", "motherfuck"]
SWEAR_WORD = [r"\btits?\b", r"\btitties\b", r"\btitty\b"]
SWEAR_RE = ([re.compile(w, re.I) for w in SWEAR_SUB] +
            [re.compile(w, re.I) for w in SWEAR_WORD])


def section():
    for s in gfiles.load():
        if s["folder"] == "hackphrk":
            return s
    return None


def text_of(path):
    with open(path, "rb") as fh:
        return fh.read().decode("cp437")


def all_paths():
    return [os.path.join(FOLDER, n) for n in NAMES] + [
        os.path.join(FOLDER, "files.bbs")]


class Loads(unittest.TestCase):
    def test_section_present_after_known(self):
        secs = gfiles.load()
        folders = [s["folder"] for s in secs]
        self.assertIn("hackphrk", folders)
        self.assertEqual(folders[:4], ["scene", "bbs", "rants", "misc"])
        self.assertEqual(section()["title"], "Hackphrk")

    def test_lists_every_file_with_desc(self):
        s = section()
        self.assertEqual([f["name"] for f in s["files"]], NAMES)
        for f in s["files"]:
            self.assertTrue(f["desc"], f["name"])
            self.assertLessEqual(len(f["desc"]), 45, f["name"])
        d = {f["name"]: f["desc"] for f in s["files"]}
        self.assertTrue(d["PHRKHIST.TXT"].startswith("History of the Phone Phreaks"))

    def test_desc_comes_from_files_bbs(self):
        bbs = text_of(os.path.join(FOLDER, "files.bbs")).splitlines()
        listed = {ln.split()[0] for ln in bbs if ln.strip() and ln[0] not in " \t"}
        self.assertEqual(listed, set(NAMES))
        for ln in bbs:
            if ln.strip() and ln[0] not in " \t":
                self.assertEqual(ln[:13].rstrip(), ln.split()[0], ln)
                self.assertLessEqual(len(ln[13:].strip()), 45, ln)


class Format(unittest.TestCase):
    def test_each_file(self):
        for f in section()["files"]:
            with self.subTest(f=f["name"]):
                self.assertRegex(f["name"], r"^[A-Z0-9_]{1,8}\.TXT$")
                lines = text_of(f["path"]).splitlines()
                self.assertTrue(25 <= len(lines) <= 80, len(lines))
                for n, ln in enumerate(lines, 1):
                    self.assertLessEqual(len(ln.expandtabs(8)), 79, n)
                    self.assertNotIn("\x1b", ln, n)
                out = gfiles.read(f)
                self.assertEqual(len(out), len(lines))
                self.assertTrue(any(l.strip() for l in out))

    def test_phone_numbers(self):
        for p in all_paths():
            for num in re.findall(r"\d{3}-\d{4}", text_of(p)):
                self.assertRegex(num, r"^555-01\d\d$", os.path.basename(p))


class Safety(unittest.TestCase):
    def test_denylist(self):
        for p in all_paths():
            text = text_of(p)
            for rx in DENY_RE:
                m = rx.search(text)
                self.assertIsNone(m, f"{os.path.basename(p)}: {rx.pattern!r} -> "
                                     f"{m and text[max(0, m.start()-30):m.end()+30]!r}")

    def test_denylist_self_check(self):
        """The denylist must not trip on innocent words, and must catch bad ones."""
        clean = "confused fusebox d00d Fusebox 2400 baud modem 1985 class title"
        for rx in DENY_RE:
            self.assertIsNone(rx.search(clean), rx.pattern)
        for bad in ["2600 Hz", "2600Hz", "1.7 kHz", "a 10 ohm part", "DTMF pad",
                    "detonator", "3 grams of", "fuse length"]:
            self.assertTrue(any(rx.search(bad) for rx in DENY_RE), bad)

    def test_clean_language(self):
        for p in all_paths():
            text = text_of(p)
            for rx in SWEAR_RE:
                self.assertIsNone(rx.search(text), f"{os.path.basename(p)}: {rx.pattern}")

    def test_clean_language_self_check(self):
        for rx in SWEAR_RE:
            self.assertIsNone(rx.search("class pass title bass stitch petite"), rx.pattern)


class Parody(unittest.TestCase):
    def test_cookbook_markers(self):
        a = text_of(os.path.join(FOLDER, "ANARCK01.TXT"))
        b = text_of(os.path.join(FOLDER, "ANARCK02.TXT"))
        both = a + b
        for marker in ["[-- LINE NOISE --]", "[TEXT CORRUPTED]", "2400 baud modem"]:
            self.assertIn(marker, both)
        self.assertIn("how to annoy your sysop", a.lower())
        self.assertRegex(both.lower(), r"parody|joke|disclaimer")


if __name__ == "__main__":
    unittest.main()
