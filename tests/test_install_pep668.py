import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "install.sh")


def run_install(env, *args):
    return subprocess.run(["/bin/sh", SCRIPT] + list(args), env=env, cwd=ROOT,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True)


class Pep668(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bin = os.path.join(self.tmp.name, "bin")
        self.stdlib = os.path.join(self.tmp.name, "stdlib")
        self.home = os.path.join(self.tmp.name, "home")
        for d in (self.bin, self.stdlib, self.home):
            os.mkdir(d)
        self.log = os.path.join(self.tmp.name, "calls.log")
        shim = os.path.join(self.bin, "python3")
        with open(shim, "w") as f:
            f.write('#!/bin/sh\necho "$*" >> "%s"\ncase "$1" in\n'
                    '  -m) case "$2" in pip) [ "$3" = install ] && '
                    'echo "error: externally-managed-environment" >&2 && exit 1; exit 0;; '
                    'site) echo "%s/.local"; exit 0;; esac;;\n'
                    'esac\nexec "%s" "$@"\n' % (self.log, self.home, sys.executable))
        os.chmod(shim, 0o755)
        for tool in ("grep", "cat", "dirname"):
            path = shutil.which(tool)
            if path:
                os.symlink(path, os.path.join(self.bin, tool))

    def env(self, marker):
        if marker:
            open(os.path.join(self.stdlib, "EXTERNALLY-MANAGED"), "w").close()
        return {"PATH": self.bin, "HOME": self.home, "COURIERHST_STDLIB_DIR": self.stdlib}

    def calls(self):
        if not os.path.exists(self.log):
            return ""
        with open(self.log) as f:
            return f.read()

    def check_hint(self, *args):
        r = run_install(self.env(True), *args)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("externally managed", r.stderr)
        self.assertIn("sudo apt install pipx", r.stderr)
        self.assertNotIn("pip install", self.calls())
        self.assertNotIn("would run: python3 -m pip install", r.stdout)
        self.assertEqual(os.listdir(self.home), [])

    def test_marker_real(self):
        self.check_hint()

    def test_marker_dry_run(self):
        self.check_hint("--dry-run")

    def test_pip_output_detected_after_the_fact(self):
        r = run_install(dict(self.env(False), COURIERHST_STDLIB_DIR=self.stdlib))
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("sudo apt install pipx", r.stderr)
        self.assertNotIn("error: externally-managed-environment", r.stdout + r.stderr)

    def test_no_marker_dry_run_unchanged(self):
        r = run_install(self.env(False), "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("would run: python3 -m pip install --user .", r.stdout)
        self.assertEqual(os.listdir(self.home), [])
        self.assertNotIn("pip install", self.calls())

    def test_syntax(self):
        self.assertEqual(subprocess.run(["sh", "-n", SCRIPT]).returncode, 0)


class Banner(unittest.TestCase):
    def test_header_jpg(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow needed")
        path = os.path.join(ROOT, "docs", "media", "header.jpg")
        self.assertLess(os.path.getsize(path), 300 * 1024)
        with Image.open(path) as im:
            self.assertEqual(im.format, "JPEG")
            self.assertEqual(im.width, 1280)
            self.assertEqual(im.mode, "RGB")
            self.assertFalse(im.info.get("exif"))

    def test_readme(self):
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            text = f.read()
        first = [ln for ln in text.splitlines() if ln.strip()][0]
        self.assertEqual(first, "![courierhst: a 14.4k modem dreaming of BBSes]"
                                "(docs/media/header.jpg)")
        install = text[text.index("## Install"):]
        self.assertIn("sudo apt install pipx", install)


if __name__ == "__main__":
    unittest.main()
