"""GRiDSWEEP v2.1: an early-90s style "dial scan" screen (simulation only).

A pure animation with made-up results.  It never touches a modem, port or
network: every number shown is in the movie-reserved 555-0100..0199 range,
and every outcome is a random draw.  All drawing goes through `modem.Line`;
the screen is painted once, then only the cells that change are redrawn.

State lives on the Dialer, so `run()` can be interrupted (by a screen switch,
say) and called again: it repaints everything and carries on with the scan.
"""

from . import ansi

RESULTS = ("busy", "voice", "noanswer", "carrier", "tone")
WEIGHTS = (12, 45, 30, 7, 6)  # same order as RESULTS

# result -> (label, heatmap char, pipe colour)
LOOK = {
    "busy": ("BUSY", "▓", 12),
    "voice": ("VOICE", "▒", 10),
    "noanswer": ("NO ANSWER", "░", 14),
    "carrier": ("CARRIER", "█", 11),
    "tone": ("TONE", "♦", 13),
}
NAMES = {"busy": "Busy", "voice": "Voice", "noanswer": "No answer",
         "carrier": "Carrier", "tone": "Tone"}

NOANSWER_SECS = 25   # ring-out time for a number nobody picks up
HOLD_SECS = 1.0      # result stays on the current-number line this long
SUMMARY_SECS = 8
LOG_ROWS = 4


def new_area(rng):
    """A made-up area code, 200-989, never an N11 service code."""
    while True:
        a = rng.randint(200, 989)
        if a % 100 != 11:
            return a


class Scan:
    """One sweep of the 100 numbers 555-0100..0199 under one area code."""

    def __init__(self, rng, area):
        self.area = area
        self.order = list(range(100))
        rng.shuffle(self.order)
        # What each number will turn out to be; `results` fills in as the
        # dialer gets to them.
        self.plan = {n: rng.choices(RESULTS, WEIGHTS)[0] for n in range(100)}
        self.results = {}

    def number(self, n):
        return f"({self.area}) 555-01{n:02d}"

    def done(self):
        return len(self.results) >= 100

    def counts(self):
        c = {"dialed": len(self.results), "left": 100 - len(self.results)}
        for r in RESULTS:
            c[r] = sum(1 for v in self.results.values() if v == r)
        return c


def _clock(secs):
    s = int(secs)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def _top(w, title):
    """Top border of a w-wide single-line box with a title."""
    head = f"─ |11{title} |03"
    return "|03┌" + head + "─" * (w - 2 - 3 - len(title)) + "┐"


def _row(text, w):
    """One box row: borders plus `text` padded to the w-2 inside columns."""
    return "|03│" + ansi.rpad(ansi.truncate(text, w - 2), w - 2) + "|03│"


def _bottom(w):
    return "|03└" + "─" * (w - 2) + "┘"


class Dialer:
    def __init__(self, line, rng):
        self.line = line
        self.rng = rng
        self.scan = Scan(rng, new_area(rng))
        self.cur = None        # the number in progress, if any
        self.last = None       # (n, result) of the number finished last
        self.log = []          # (stamp, n, result), newest last
        self.elapsed = 0.0     # simulated seconds into this scan
        self.sumleft = SUMMARY_SECS

    # ---------------------------------------------------------------- loop
    def run(self):
        """Scan, show a summary, start over; leaves only by exception."""
        line = self.line
        try:
            self._draw_all()
            while True:
                while not self.scan.done():
                    self._number()
                self._draw_summary()
                while self.sumleft > 0:
                    self._tick(1.0, count=False)
                    self.sumleft -= 1
                    self._draw_summary()
                self._new_scan()
                self._draw_all()
        finally:
            line.status_text = None

    def _new_scan(self):
        self.scan = Scan(self.rng, new_area(self.rng))
        self.cur = self.last = None
        self.log = []
        self.elapsed = 0.0
        self.sumleft = SUMMARY_SECS

    def _tick(self, secs, count=True):
        """Let simulated time pass (the only place that waits)."""
        self.line.pause(secs)
        if count:
            old = int(self.elapsed)
            self.elapsed += secs
            if int(self.elapsed) != old:
                self.line.at(11, 18, f"|15{_clock(self.elapsed)}  |07|16")

    # -------------------------------------------------------------- numbers
    def _begin(self):
        s = self.scan
        n = s.order[len(s.results)]
        res = s.plan[n]
        if res == "noanswer":
            ring = NOANSWER_SECS
        elif res in ("busy", "voice"):
            ring = self.rng.randint(3, 10)
        else:
            ring = self.rng.randint(5, 12)
        self.cur = {"n": n, "res": res, "stage": 0, "t": 0.0, "ring": ring,
                    "dial": round(self.rng.uniform(1, 2), 1)}
        self._draw_cell(n)
        self._draw_current()
        return self.cur

    @staticmethod
    def _rings(c):
        return 1 + int(c["t"] // 3 + 1e-9)

    def _number(self):
        c = self.cur or self._begin()
        if c["stage"] == 0:
            self._tick(c["dial"])
            c["stage"], c["t"] = 1, 0.0
            self._draw_current()
        while c["t"] < c["ring"]:
            step = min(1.0, c["ring"] - c["t"])
            self._tick(step)
            before = self._rings(c)
            c["t"] += step
            if self._rings(c) != before and c["t"] < c["ring"]:
                self._draw_current()
        self._finish(c)
        self._tick(HOLD_SECS)

    def _finish(self, c):
        """Record the outcome (no waiting in here, so it is all-or-nothing)."""
        n, res = c["n"], c["res"]
        self.scan.results[n] = res
        self.log = (self.log + [(_clock(self.elapsed), n, res)])[-LOG_ROWS:]
        self.last = (n, res)
        self.cur = None
        self._draw_cell(n)
        self._draw_stats()
        self._draw_current()
        self._draw_log()

    # -------------------------------------------------------------- drawing
    def _draw_all(self):
        """Paint the whole screen from the current state."""
        L, s = self.line, self.scan
        L.status_text = f"GRiDSWEEP scanning ({s.area}) 555-01xx"
        L.cls_local()
        title = " GRiDSWEEP v2.1"
        tail = "(c) 1993 Crossbar Coders "
        gap = " " * (79 - len(title) - len(tail))
        L.at(1, 1, "|15|17" + title + gap + "|14" + tail + "|07|16")
        L.at(2, 2, f"|08Range |07({s.area}) 555-0100 to 555-0199   "
                   "|08Order |07random   |08Dial |07tone|07|16")
        # stats panel (cols 1-38)
        L.at(3, 1, _top(38, "SCAN STATS"))
        for i in range(8):
            L.at(4 + i, 1, _row("", 38))
        names = [("", "Dialed"), ("", "Left")]
        names += [(f"|{LOOK[r][2]:02d}{LOOK[r][1]}", NAMES[r]) for r in RESULTS]
        names += [("", "Elapsed")]
        for i, (mark, name) in enumerate(names):
            L.at(4 + i, 3, f"{mark or ' '} |07{name}|07|16")
        L.at(12, 1, _bottom(38))
        # current number panel
        L.at(13, 1, _top(38, "NOW DIALING"))
        for r in (14, 15, 16):
            L.at(r, 1, _row("", 38))
        L.at(17, 1, _bottom(38))
        # heatmap (cols 41-79)
        L.at(3, 41, _top(39, "HEATMAP  rows=tens cols=ones"))
        for r in range(4, 17):
            L.at(r, 41, _row("", 39))
        L.at(4, 46, "|08" + "".join(f" {d} " for d in range(10)) + "|07|16")
        for r in range(10):
            L.at(5 + r, 43, f"|08{r}_|07|16")
        L.at(15, 43, "|12▓ |07busy  |10▒ |07voice  |14░ |07no answer|07|16")
        L.at(16, 43, "|11█ |07carrier  |13♦ |07tone  |08· |07wait  "
                     "|00|23 ■ |07|16")
        L.at(17, 41, _bottom(39))
        # log
        L.at(18, 1, _top(79, "LOG"))
        for r in range(19, 23):
            L.at(r, 1, _row("", 79))
        L.at(23, 1, _bottom(79))
        L.at(min(25, L.height), 2, "|08Simulated scan: every number and result is made up."
                    "|07|16")
        for r in range(10):
            self._draw_hm_row(r)
        self._draw_stats()
        self._draw_current()
        self._draw_log()
        if self.scan.done():
            self._draw_summary()

    def _cell(self, n):
        res = self.scan.results.get(n)
        if res:
            _, ch, col = LOOK[res]
            return f"|{col:02d} {ch} "
        if self.cur and self.cur["n"] == n:
            return "|00|23 ■ |07|16"
        return "|08 · "

    def _draw_hm_row(self, r):
        text = "".join(self._cell(r * 10 + c) for c in range(10))
        self.line.at(5 + r, 46, text + "|07|16")

    def _draw_cell(self, n):
        self.line.at(5 + n // 10, 46 + 3 * (n % 10), self._cell(n) + "|07|16")

    def _draw_stats(self):
        c = self.scan.counts()
        keys = ["dialed", "left"] + list(RESULTS)
        for i, k in enumerate(keys):
            col = LOOK[k][2] if k in LOOK else 15
            self.line.at(4 + i, 18, f"|{col:02d}{c[k]:<5}|07|16")
        self.line.at(11, 18, f"|15{_clock(self.elapsed)}  |07|16")

    def _draw_current(self):
        L, s = self.line, self.scan
        c = self.cur
        if c:
            n = c["n"]
            if c["stage"] == 0:
                state = "|14DIALING"
            else:
                state = f"|11RINGING {self._rings(c)}"
        elif self.last:
            n, res = self.last
            lab, _, col = LOOK[res]
            state = f"|{col:02d}{lab}"
        else:
            n, state = None, "|08waiting"
        num = s.number(n) if n is not None else ""
        L.at(14, 3, ansi.rpad("|15" + num, 34) + "|07|16")
        L.at(15, 3, ansi.rpad(state, 34) + "|07|16")
        done = len(s.results)
        k = done // 5
        L.at(16, 3, f"|08Scan |10{'█' * k}|08{'░' * (20 - k)} |07{done:>3}%"
                    "|07|16")

    def _draw_log(self):
        for i in range(LOG_ROWS):
            if i < len(self.log):
                stamp, n, res = self.log[i]
                lab, _, col = LOOK[res]
                text = (f" |08{stamp}  |07{self.scan.number(n)}  "
                        f"|{col:02d}{lab}")
            else:
                text = ""
            self.line.at(19 + i, 2, ansi.rpad(text, 77) + "|07|16")

    def _draw_summary(self):
        """The SCAN COMPLETE box, centred over the screen."""
        L, s = self.line, self.scan
        c = s.counts()
        w = 40
        rows = [
            f" |07Area code   |15({s.area}) 555-01xx",
            f" |07Dialed      |15{c['dialed']}",
            "",
            f" |11Carriers    {c['carrier']:<4} |13Tones   {c['tone']}",
            f" |10Voice       {c['voice']:<4} |12Busy    {c['busy']}",
            f" |14No answer   {c['noanswer']}",
            f" |07Elapsed     |15{_clock(self.elapsed)}",
            "",
            f" |08Next scan in {self.sumleft}s, new area code",
        ]
        L.at(8, 21, "|15╔═ SCAN COMPLETE " + "═" * (w - 2 - 16) + "╗")
        for i, text in enumerate(rows):
            L.at(9 + i, 21, "|15║" + ansi.rpad(text, w - 2) + "|15║|07|16")
        L.at(9 + len(rows), 21, "|15╚" + "═" * (w - 2) + "╝|07|16")
