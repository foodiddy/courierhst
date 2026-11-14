import inspect
import re
import unittest
from pathlib import Path

from courierhst.modem import Line

ROOT = Path(__file__).resolve().parent.parent


class NoiseDefaultTests(unittest.TestCase):
    def test_line_default(self):
        default = inspect.signature(Line.__init__).parameters["noise"].default
        self.assertEqual(default, 0.0007)

    def test_cli_default(self):
        # The parser is built inside main(), so check the source.
        src = (ROOT / "courierhst" / "__main__.py").read_text()
        m = re.search(r'"--noise"[^)]*?default=([0-9.]+)', src, re.S)
        self.assertIsNotNone(m)
        self.assertEqual(float(m.group(1)), 0.0007)

    def test_readme(self):
        text = (ROOT / "README.md").read_text()
        self.assertIn("default 0.0007", text)
        self.assertNotIn("0.0015", text)


if __name__ == "__main__":
    unittest.main()
