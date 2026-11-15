"""The README media: renderer smoke tests and the committed files."""
import os
import re
import subprocess
import sys
import tempfile
import unittest

try:
    import pyte  # noqa: F401
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "tools", "render_media.py")
MEDIA = os.path.join(ROOT, "docs", "media")
EXPECTED = ["dialin.gif", "browse.gif", "goodbye.gif", "renegade.png",
            "telegard.png", "mystic.png", "pcboard.png", "logo.png",
            "art.png", "gfiles.png", "statusbar.png",
            "dialer.png", "dialer.gif"]


@unittest.skipIf(Image is None, "Pillow and pyte are needed (pip install '.[media]')")
class RenderMedia(unittest.TestCase):
    def render(self, tmp, only):
        r = subprocess.run([sys.executable, SCRIPT, "--out", tmp, "--only", only],
                           cwd=ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        path = os.path.join(tmp, only + ".png")
        self.assertTrue(os.path.isfile(path), path)
        return Image.open(path)

    def test_render_mystic_and_statusbar(self):
        with tempfile.TemporaryDirectory() as tmp:
            im = self.render(tmp, "mystic")
            im.load()
            self.assertEqual(im.format, "PNG")
            self.assertEqual(im.size, (640, 416))
            bar = self.render(tmp, "statusbar")
            bar.load()
            self.assertEqual(bar.format, "PNG")
            self.assertEqual(bar.width, 640)

    def test_telegard_shot_has_time_left_value(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("render_media_tg", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        needles = mod.TELEGARD_NEEDLES
        chunks = mod.capture(1, "telegard", mod.FAST, stop=mod.has(*needles), idle=None)
        screen = mod.first_match(chunks, needles, mod.TELEGARD_EXTRA)
        self.assertIsNotNone(screen)
        text = "\n".join(screen.display)
        self.assertRegex(text, r"Time Left: +\d+ :")

    def test_committed_files(self):
        for name in EXPECTED:
            self.assertTrue(os.path.isfile(os.path.join(MEDIA, name)), name)
        for name in sorted(os.listdir(MEDIA)):
            path = os.path.join(MEDIA, name)
            with self.subTest(name=name):
                with Image.open(path) as im:
                    if name == "header.jpg":
                        self.assertEqual(im.format, "JPEG")
                        self.assertEqual(im.width, 1280)
                        self.assertLess(os.path.getsize(path), 300 * 1024)
                        continue
                    self.assertEqual(im.width, 640)
                    if name.endswith(".gif"):
                        self.assertLess(os.path.getsize(path), 3 * 1024 * 1024)
                        self.assertTrue(getattr(im, "is_animated", False))
                        self.assertGreater(im.n_frames, 1)
                    else:
                        self.assertEqual(im.format, "PNG")

    def test_readme_references_every_file(self):
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            readme = f.read()
        for name in sorted(os.listdir(MEDIA)):
            self.assertIn("docs/media/" + name, readme)
        self.assertRegex(readme, r"(?m)^## Screenshots$")
        self.assertLess(readme.index("## Screenshots"), readme.index("## Install"))

    def test_font_licence(self):
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "tools", "fonts", "LICENSE.txt")))
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "tools", "fonts",
                                                    "Px437_IBM_VGA_8x16.ttf")))

    def test_app_does_not_import_pillow(self):
        for dirpath, _, files in os.walk(os.path.join(ROOT, "courierhst")):
            for f in files:
                if f.endswith(".py"):
                    with open(os.path.join(dirpath, f), encoding="utf-8") as fh:
                        self.assertIsNone(re.search(r"^\s*(import|from)\s+PIL", fh.read(),
                                                    re.M), f)


if __name__ == "__main__":
    unittest.main()
