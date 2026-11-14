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
        self.assertIn("Offline", "".join(line._buf))


class StatusBarStyle(unittest.TestCase):
    def draw(self, cols=100, **kw):
        line = make()
        line.cols, line.rows, line.left, line.status_row = cols, 40, 0, 30
        for k, v in kw.items():
            setattr(line, k, v)
        line._buf.clear()
        line._draw_status(force=True)
        raw = "".join(line._buf)
        m = re.search(r"\x1b\[30;1H\x1b\[0m\x1b\[2K\x1b\[30;1H(.*)\x1b\[0m\x1b8", raw, re.S)
        self.assertTrue(m, raw)
        return m.group(1)

    def test_online(self):
        body = self.draw(online_since=time.monotonic() - 21, status_name="The Black Inferno")
        plain = re.sub(r"\x1b\[[0-9;]*m", "", body)
        self.assertEqual(plain, (" The Black Inferno | 14400/ARQ/HST | Connected: 00:00:21"
                                 " | ALT-Z for menu").ljust(99 if False else 79))
        self.assertIn("44m", body)  # blue background, whole bar in one SGR
        self.assertLessEqual(body.count("\x1b["), 2)

    def test_dialing_and_offline(self):
        plain = lambda b: re.sub(r"\x1b\[[0-9;]*m", "", b).rstrip()
        self.assertEqual(plain(self.draw(dialing=True, status_name="Foo BBS")),
                         " Dialing Foo BBS... | ALT-Z for menu")
        self.assertEqual(plain(self.draw()), " Offline | ALT-Z for menu")

    def test_long_name_keeps_tail(self):
        for cols in (60, 80, 120):
            body = self.draw(cols, online_since=time.monotonic(), status_name="X" * 90)
            plain = re.sub(r"\x1b\[[0-9;]*m", "", body)
            self.assertLessEqual(len(plain), min(80, cols) - 1)
            self.assertIn("14400", plain)
            self.assertIn("Connected:", plain)
            self.assertIn("ALT-Z for menu", plain)


if __name__ == "__main__":
    unittest.main()
