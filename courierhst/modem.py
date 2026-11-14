"""The 'line': a terminal wrapper that throttles output to modem speed.

Everything the remote BBS sends goes through `Line.send`, which meters bytes
out at bps/10 characters per second (8N1 framing: start + 8 data + stop).
Escape sequences cost bytes too, just like they did on the wire.

The 80x25 BBS screen is centered in larger terminals by tracking a left/top
offset; the BBS content only ever uses newlines and clear-screen, which this
layer translates, so arbitrary terminal sizes work.
"""

import os
import random
import re
import select
import signal
import sys
import termios
import time
import tty

from . import ansi

BBS_COLS = 80
BBS_ROWS = 25

_TOKEN_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x0c|\n|.", re.S)
NOISE_CHARS = "}{~`#$@^&*![]|\\°ñæ«»▓∙"


class KeyPressed(Exception):
    """Raised when the viewer touches the keyboard: screensaver over."""


class Line:
    def __init__(self, bps=14400, center=True, status=True, noise=0.002,
                 exit_on_key=True, out=None, warp=1.0):
        self.bps = bps
        self.warp = warp
        self.cps = bps / 10.0 * warp
        self.center = center
        self.status_enabled = status
        self.noise = noise
        self.exit_on_key = exit_on_key
        self.out = out or sys.stdout
        self.fd_in = sys.stdin.fileno() if sys.stdin.isatty() else None
        self._old_tc = None
        self._old_winch = None
        self._buf = []
        self._t = time.monotonic()
        self._state = [7, 0]
        self._resized = True
        self._last_status = 0.0
        # Status bar fields
        self.online_since = None
        self.status_name = ""
        self.connect_speed = ""
        self.offline_msg = "OFFLINE"
        self.dialing = False

    # ------------------------------------------------------------------ setup
    def __enter__(self):
        try:
            return self._enter()
        except BaseException:
            self.__exit__()
            raise

    def _enter(self):
        if self.fd_in is not None:
            self._old_tc = termios.tcgetattr(self.fd_in)
            tty.setcbreak(self.fd_in)
            new = termios.tcgetattr(self.fd_in)
            new[3] &= ~termios.ECHO
            termios.tcsetattr(self.fd_in, termios.TCSANOW, new)
        self._old_winch = signal.signal(signal.SIGWINCH, self._on_winch)
        self._raw("\x1b[?25h\x1b[0m\x1b[2J")
        self._layout()
        return self

    def __exit__(self, *exc):
        try:
            self._buf.clear()
            self._raw("\x1b[r\x1b[0m\x1b[2J\x1b[H\x1b[?25h")
            self._flush()
        except (OSError, ValueError):
            pass
        finally:
            signal.signal(signal.SIGWINCH, self._old_winch or signal.SIG_DFL)
            if self._old_tc is not None:
                try:
                    termios.tcsetattr(self.fd_in, termios.TCSADRAIN, self._old_tc)
                    # swallow the key that woke us up
                    termios.tcflush(self.fd_in, termios.TCIFLUSH)
                except termios.error:
                    pass
        return False

    def _on_winch(self, *_):
        self._resized = True

    def _layout(self):
        self._resized = False
        try:
            cols, rows = os.get_terminal_size(self.out.fileno())
        except OSError:
            cols, rows = BBS_COLS, BBS_ROWS
        self.cols, self.rows = cols, rows
        want = BBS_ROWS + (1 if self.status_enabled else 0)
        self.left = max(0, (cols - BBS_COLS) // 2) if self.center else 0
        self.top = max(0, (rows - want) // 2) + 1 if self.center else 1
        avail = rows - self.top + 1 - (1 if self.status_enabled else 0)
        self.height = max(3, min(BBS_ROWS, avail))
        self.bottom = self.top + self.height - 1
        self.status_row = self.bottom + 1
        self._raw(f"\x1b7\x1b[{self.top};{self.bottom}r\x1b8")
        self._draw_status(force=True)

    # ------------------------------------------------------------------ output
    def _raw(self, s):
        self._buf.append(s)

    def _flush(self):
        if self._buf:
            self.out.write("".join(self._buf))
            self._buf.clear()
            self.out.flush()

    def _home(self):
        return f"\x1b[{self.top};{self.left + 1}H"

    def _newline(self):
        return "\r\n" + (f"\x1b[{self.left}C" if self.left else "")

    def cls_local(self):
        """Clear the BBS window without metering (local terminal action)."""
        self._raw("\x1b[0m\x1b[2J" + self._home())
        self._draw_status(force=True)
        self._flush()

    def send(self, text, cps=None):
        """Send pipe-coded text from the remote side at line speed."""
        self._meter(ansi.pipe_to_ansi(text, self._state), cps or self.cps)

    def sendln(self, text="", cps=None):
        self.send(text + "\n", cps)

    def local(self, text):
        """Draw something instantly (the local terminal program's own UI)."""
        for tok in _TOKEN_RE.findall(ansi.pipe_to_ansi(text, self._state)):
            self._raw(self._translate(tok))
        self._flush()

    def _translate(self, tok):
        if tok == "\n":
            return self._newline()
        if tok == "\x0c":
            return "\x1b[0m\x1b[2J" + self._home() + ansi.sgr(*self._state)
        if tok == "\r" and self.left:
            return f"\r\x1b[{self.left}C"
        return tok

    def _meter(self, data, cps):
        now = time.monotonic()
        if self._t < now - 0.05:
            self._t = now  # line was idle; don't burst to catch up
        per = 1.0 / cps
        for tok in _TOKEN_RE.findall(data):
            if tok == "\x0c":
                self._raw(self._translate(tok))
                self._draw_status(force=True)
                cost = 4
            else:
                if (self.noise and len(tok) == 1 and tok not in "\n\r"
                        and random.random() < self.noise):
                    junk = "".join(random.choice(NOISE_CHARS)
                                   for _ in range(random.randint(1, 4)))
                    self._raw(junk)
                    self._t += per * len(junk)
                self._raw(self._translate(tok))
                cost = len(tok)  # 1 byte per char, escapes cost their length
            self._t += per * cost
            if self._t - time.monotonic() > 0.012:
                self._flush()
                self._wait_until(self._t)
        self._flush()

    # ------------------------------------------------------------------ time
    def _wait_until(self, t):
        while True:
            if self._resized:
                self._layout()
            now = time.monotonic()
            if now - self._last_status >= 1.0:
                self._draw_status()
                self._flush()
            left = t - now
            if left <= 0:
                return
            self._check_key(min(left, 0.25))

    def _check_key(self, timeout):
        if self.fd_in is None or not self.exit_on_key:
            time.sleep(timeout)
            return
        r, _, _ = select.select([self.fd_in], [], [], timeout)
        if r:
            raise KeyPressed()

    def pause(self, seconds):
        """Idle on the line (BBS thinking, user reading the screen)."""
        self._flush()
        self._wait_until(time.monotonic() + seconds / self.warp)
        self._t = time.monotonic()

    def rpause(self, lo, hi):
        self.pause(random.uniform(lo, hi))

    def type(self, text, fast=False):
        """The caller typing; characters are echoed back by the BBS."""
        for ch in text:
            if ch == " ":
                d = random.uniform(0.08, 0.25)
            else:
                d = random.uniform(0.04, 0.11) if fast else random.uniform(0.06, 0.22)
            if random.random() < 0.04:
                d += random.uniform(0.3, 0.9)  # hunt for a key
            self.pause(d)
            self.send(ch)

    def type_hidden(self, text, mask="*"):
        for _ in text:
            self.pause(random.uniform(0.07, 0.2))
            self.send(mask)

    def enter(self):
        self.pause(random.uniform(0.15, 0.45))
        self.send("\n")

    # ------------------------------------------------------------------ status
    def _draw_status(self, force=False):
        if not self.status_enabled or self.status_row > self.rows:
            return
        now = time.monotonic()
        if not force and now - self._last_status < 1.0:
            return
        self._last_status = now
        width = min(BBS_COLS, self.cols) - 1  # never write the last column
        name = self.status_name
        tail = " | ALT-Z for menu"
        if self.online_since is not None:
            e = int(now - self.online_since)
            mid = (f" | 14400/ARQ/HST | Connected: "
                   f"{e // 3600:02d}:{e % 3600 // 60:02d}:{e % 60:02d}")
            room = width - len(" " + mid + tail)
            text = " " + name[:max(0, room)] + mid + tail
        elif self.dialing:
            room = width - len(" Dialing ... | ALT-Z for menu")
            text = f" Dialing {name[:max(0, room)]}..." + tail
        else:
            text = " Offline" + tail
        text = text.replace("|", "||")
        bar = "|15|17" + ansi.rpad(ansi.truncate(text, width), width) + "|07|16"
        sgr_txt = ansi.pipe_to_ansi(bar, [7, 0])
        self._raw(f"\x1b7\x1b[{self.status_row};1H\x1b[0m\x1b[2K"
                  f"\x1b[{self.status_row};{self.left + 1}H{sgr_txt}\x1b[0m\x1b8")
