import io
import re
import time
import unittest

from courierhst import ansi
from courierhst.modem import Line


class FakeOut(io.StringIO):
    def fileno(self):
        raise OSError("not a tty")


def make(**kw):
    kw.setdefault("noise", 0)
    kw.setdefault("out", FakeOut())
    return Line(**kw)


class Metering(unittest.TestCase):
    def test_14400_is_1440_cps(self):
        line = make(bps=14400, warp=1)
        line._layout()
        text = "a" * 1440
        t0 = time.monotonic()
        line.send(text)
        dt = time.monotonic() - t0
        self.assertAlmostEqual(dt, 1.0, delta=0.1)
        self.assertIn(text, line.out.getvalue())

    def test_warp_scales(self):
        line = make(bps=14400, warp=4)
        t0 = time.monotonic()
        line.send("a" * 1440)
        self.assertAlmostEqual(time.monotonic() - t0, 0.25, delta=0.1)


class StatusBar(unittest.TestCase):
    def bar_width(self, cols, name):
        line = make()
        line.cols, line.rows = cols, 40
        line.left, line.status_row = 0, 30
        line.online_since = time.monotonic() - 3725
        line.status_name = name
        line.connect_speed = "CONNECT 14400/ARQ/V32/LAPM/V42BIS"
        line.out.truncate(0)
        line._buf.clear()
        line._draw_status(force=True)
        raw = "".join(line._buf)
        m = re.search(r"\x1b\[30;1H\x1b\[0m\x1b\[2K\x1b\[30;1H(.*)\x1b8", raw, re.S)
        self.assertTrue(m, raw)
        return len(re.sub(r"\x1b\[[0-9;]*m", "", m.group(1)))

    def test_width_limits(self):
        for cols in (20, 40, 79, 80, 120):
            for name in ("", "Short", "The Extremely Long Board Name Of Doom " * 4):
                self.assertLessEqual(self.bar_width(cols, name),
                                     min(80, cols) - 1, (cols, name))

    def test_offline(self):
        line = make()
        line.cols, line.rows, line.left, line.status_row = 80, 30, 0, 27
        line._draw_status(force=True)
        self.assertIn("OFFLINE", "".join(line._buf))


if __name__ == "__main__":
    unittest.main()
