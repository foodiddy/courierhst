"""A simulated call: dial, connect, log in, browse, log off."""

import random
import time

from . import ansi, content, doors
from .ansi import box, center, elite, fade_bar, gradient_rule, logo, rpad

CLS = "\x0c"


class Board:
    """One fictional BBS, with its own look and software flavour."""

    def __init__(self, rng, user):
        self.rng = rng
        self.user = user
        self.name = content.bbs_name(rng)
        self.city, self.state, area = rng.choice(content.CITIES)
        self.phone = content.phone(rng, area)
        self.style = rng.choice(["renegade", "renegade", "telegard", "pcboard"])
        self.software = content.SOFTWARE[self.style]
        self.palette = rng.choice(list(ansi.PALETTES))
        self.hi, self.lo = ansi.ACCENTS[self.palette]
        self.sysop = content.handle(rng)
        self.cosysop = content.handle(rng)
        self.nodes = rng.choice([1, 2, 2, 3, 4, 6])
        self.node = rng.randint(1, self.nodes)
        self.gigs = round(rng.uniform(0.6, 4.8), 1)
        self.affils = rng.sample(content.GROUPS, rng.randint(2, 4))
        self.calls = rng.randint(1800, 48000)
        self.logon_no = rng.randint(12, 900)
        self.time_total = rng.choice([45, 60, 60, 90, 120])
        self.started = time.monotonic()
        self.ul_k = rng.randint(4000, 90000)
        self.dl_k = int(self.ul_k * rng.uniform(1.2, 4.6))
        self.art_by = (content.handle(rng), rng.choice(content.ART_GROUPS))
        self.modem = rng.choice(["USR HST Dual Standard 16.8",
                                 "USR Courier HST 14.4", "USR HST DS 14.4"])

    def time_left(self):
        used = (time.monotonic() - self.started) / 60.0
        return max(1, int(self.time_total - used))

    def clock(self):
        t = time.localtime()
        return time.strftime("%H:%M", t)


# ==========================================================================
# Menu styles
# ==========================================================================

MAIN_CMDS = [
    ("M", "Message Bases", "msgs"), ("F", "File Areas", "files"),
    ("D", "Door Games", "doors"), ("L", "Last Callers", "last"),
    ("O", "OneLiners", "oneliners"), ("B", "Bulletins", "bulletins"),
    ("W", "Who's Online", "who"), ("Y", "Your Stats", "stats"),
    ("C", "Page Sysop", "page"), ("G", "Goodbye", "bye"),
]
PCB_KEYS = {"msgs": "R", "files": "F", "doors": "OPEN", "last": "LC",
            "oneliners": "1L", "bulletins": "B", "who": "WHO", "stats": "V",
            "page": "O", "bye": "G"}


def main_menu(b):
    if b.style == "renegade":
        rows = []
        cmds = MAIN_CMDS
        half = (len(cmds) + 1) // 2
        for i in range(half):
            left = cmds[i]
            right = cmds[i + half] if i + half < len(cmds) else None
            s = f"   |08[|{b.hi:02d}{left[0]}|08] |07{rpad(left[1], 24)}"
            if right:
                s += f"|08[|{b.hi:02d}{right[0]}|08] |07{right[1]}"
            rows.append(s)
        out = [CLS]
        out.append(gradient_rule(78, b.palette, "▄"))
        out += box(rows, 78, b.lo, title=f"|15{elite('Main Menu')}", double=True)
        out.append(gradient_rule(78, b.palette, "▀"))
        return out
    if b.style == "telegard":
        out = [CLS, "", center(f"|{b.lo:02d}-=|{b.hi:02d}≡|15 Main Menu |{b.hi:02d}≡|{b.lo:02d}=-"), ""]
        cmds = MAIN_CMDS
        for i in range(0, len(cmds), 2):
            a = cmds[i]
            s = f"     |{b.lo:02d}(|15{a[0]}|{b.lo:02d})|{b.hi:02d}{rpad(a[1], 26)}"
            if i + 1 < len(cmds):
                c = cmds[i + 1]
                s += f"|{b.lo:02d}(|15{c[0]}|{b.lo:02d})|{b.hi:02d}{c[1]}"
            out.append(s)
        out.append("")
        return out
    # pcboard
    out = [CLS, f"|{b.hi:02d}{b.name}", f"|{b.lo:02d}Main Board Commands", ""]
    pcb = [("R", "Read Messages", "B", "Bulletins"),
           ("F", "File Directories", "LC", "Last Callers"),
           ("OPEN", "Open a Door", "1L", "One-Liners"),
           ("WHO", "Who's on-line", "V", "View Settings"),
           ("O", "Page Sysop", "G", "Goodbye (hang up)")]
    for k1, l1, k2, l2 in pcb:
        out.append(f"  |15{rpad(k1, 5)}|03{rpad(l1, 28)}|15{rpad(k2, 5)}|03{l2}")
    out.append("")
    return out


def prompt(b, area="Main"):
    if b.style == "renegade":
        return (f"|08[|07{b.clock()}|08] |{b.lo:02d}[|{b.hi:02d}{area}|{b.lo:02d}] "
                f"|08(|07Tl:|15{b.time_left()}|08) |07Command |08» |15")
    if b.style == "telegard":
        return f"|{b.lo:02d}[|{b.hi:02d}{area} Menu|{b.lo:02d}] |07Time Left: |15{b.time_left()} |07: |15"
    return f"|14({b.time_left()} min left), {area} Board Command? |15"


def key_for(b, action):
    if b.style == "pcboard":
        return PCB_KEYS[action]
    for k, _, a in MAIN_CMDS:
        if a == action:
            return k


# ==========================================================================
# Session
# ==========================================================================

class Session:
    def __init__(self, line, rng, user, xfer_speedup=30.0):
        self.line = line
        self.rng = rng
        self.user = user
        self.xfer_speedup = xfer_speedup
        self.b = Board(rng, user)

    # convenience
    def out(self, lines):
        if isinstance(lines, str):
            lines = [lines]
        for ln in lines:
            if ln == CLS:
                self.line.send(CLS)
            else:
                self.line.sendln(ansi.truncate(ln, 79))

    def ask(self, text, answer, hidden=False, fast=False):
        self.line.send(text)
        self.line.rpause(0.4, 1.6)
        if hidden:
            self.line.type_hidden(answer)
        else:
            self.line.type(answer, fast=fast)
        self.line.enter()

    def more(self):
        L = self.line
        L.send("|07|16")
        L.send("|08[|15Pause|08] |07Hit a key... ")
        L.rpause(1.5, 3.5)
        L.send("\r" + " " * 30 + "\r")

    # ---------------------------------------------------------------- run
    def run(self):
        if not self.dial():
            return
        L = self.line
        L.online_since = time.monotonic()
        L.status_name = self.b.name
        try:
            self.login()
            n = self.rng.randint(4, 8)
            actions = self._plan(n)
            for act in actions:
                self.show_main()
                self.ask(prompt(self.b), key_for(self.b, act), fast=True)
                getattr(self, "do_" + act)()
            self.show_main()
            self.ask(prompt(self.b), key_for(self.b, "bye"), fast=True)
            self.do_bye()
        finally:
            L.online_since = None
            L.connect_speed = ""

    def _plan(self, n):
        r = self.rng
        pool = (["files"] * 5 + ["msgs"] * 4 + ["doors"] * 4 +
                ["last", "oneliners", "bulletins", "who", "stats", "page"])
        acts = []
        while len(acts) < n:
            a = r.choice(pool)
            if acts and acts[-1] == a:
                continue
            acts.append(a)
        if "files" not in acts:
            acts[r.randrange(len(acts))] = "files"
        if "doors" not in acts and r.random() < 0.7:
            acts[r.randrange(len(acts))] = "doors"
        return acts

    def show_main(self):
        b = self.b
        if b.style == "renegade" or self.rng.random() < 0.5:
            self.out(main_menu(b))
        else:
            self.out("")

    # ---------------------------------------------------------------- dial
    def dial(self):
        L, b, r = self.line, self.b, self.rng
        L.cls_local()
        L.offline_msg = "DIALING"
        L.local(f"|08── |03Dialing directory entry |11#{r.randint(1, 40)}"
                f"|08 ── |15{b.name}|08 ── |07{b.city}, {b.state}\n\n")
        for cmd in ("ATZ", "AT&F1X4&B1&H1&R2"):
            self._modem_cmd(cmd)
            L.pause(0.3)
            L.local("\nOK\n")
            L.pause(0.4)
        attempts = 1 if r.random() < 0.55 else r.randint(2, 4)
        number = b.phone.replace("-", "")
        for a in range(1, attempts + 1):
            self._modem_cmd("ATDT" + number)
            L.local("\n")
            if a < attempts:
                L.rpause(2.5, 5.0)
                L.local("|15BUSY\n")
                L.local(f"|08   redial in 5s ─ attempt |07{a + 1}|08 of 50\n|07")
                L.pause(5)
            else:
                L.rpause(6.0, 11.0)
        speed = r.choice(["14400/ARQ/HST/HFC", "14400/ARQ/HST", "14400/ARQ/HST/HFC/MNP"])
        L.local(f"|15CONNECT {speed}\n|07")
        L.connect_speed = "14400 HST"
        L.offline_msg = "OFFLINE"
        L.pause(1.0)
        return True

    def _modem_cmd(self, cmd):
        L = self.line
        L.local("|07")
        for ch in cmd:
            L.pause(0.025)
            L.local(ch)

    # ---------------------------------------------------------------- login
    def login(self):
        L, b, r = self.line, self.b, self.rng
        L.send("\n")
        L.rpause(0.8, 1.6)
        if r.random() < 0.4:
            z = f"1:{r.randint(100, 399)}/{r.randint(1, 80)}"
            self.out([f"|07FidoNet node {z}  ∙  {b.name}",
                      "|07Press |15<ESC>|07 twice for the BBS..."])
            L.rpause(1.0, 2.0)
            L.send("|08∙ ∙ |07")
            L.rpause(0.6, 1.2)
            self.out("|15BBS!")
        self.out(["", "|07Detecting ANSI graphics... |15ANSI detected.", ""])
        L.pause(0.5)
        self.splash()
        L.rpause(2.0, 3.5)
        # Matrix / login
        if r.random() < 0.5:
            self.out(["", center(f"|08░▒▓ |{b.hi:02d}{elite('Private System')} |08▓▒░"),
                      center(f"|07Members only. Lamers will be |12deleted|07 on sight."), ""])
        self.ask(f"|{b.lo:02d}Enter your handle or |15NEW|{b.lo:02d}: |15", self.user)
        self.ask(f"|{b.lo:02d}Password: |15", "x" * r.randint(6, 10), hidden=True)
        if b.style == "renegade" or r.random() < 0.3:
            last4 = f"{r.randint(0, 9999):04d}"
            self.ask(f"|{b.lo:02d}Complete phone #: |07###-###-|15", last4, hidden=False)
        self.out("")
        L.pause(0.5)
        self.out([
            f"|07Logon |15#{b.calls:,}|07 on node |15{b.node}|07 at |15{b.clock()}",
            f"|07Welcome back, |{b.hi:02d}{self.user}|07! You have called |15{b.logon_no}|07 times.",
            f"|07You have |15{b.time_left()}|07 minutes left today.",
            "",
        ])
        L.rpause(1.0, 2.0)
        L.send("|07Scanning for new mail")
        for _ in range(3):
            L.rpause(0.3, 0.7)
            L.send(".")
        if r.random() < 0.4:
            self.out(f" |15{r.randint(1, 3)}|07 new.")
            L.pause(0.6)
            self.email()
        else:
            self.out(" none.")
        L.rpause(0.8, 1.5)
        self.do_last(compact=True)
        self.do_oneliners(add=False)

    def splash(self):
        b, r = self.b, self.rng
        name = b.name
        if name.startswith("The ") and r.random() < 0.5:
            name = name[4:]
        art = [CLS]
        art.append(fade_bar(78, (8, b.lo, b.hi, 15, b.hi, b.lo, 8)))
        art.append("")
        art += logo(name.upper(), b.palette)
        art.append("")
        art.append(gradient_rule(78, b.palette, "═"))
        tag = (f"|08[ |{b.hi:02d}{b.nodes}|07 node{'s' if b.nodes > 1 else ''} |08∙ "
               f"|{b.hi:02d}{b.gigs}|07 gigs |08∙ |07{b.modem}|08 ]")
        art.append(center(tag))
        aff = " |08∙ ".join(f"|{b.hi:02d}{g}" for g in b.affils)
        art.append(center(f"|07{elite('World HQ')}: |15{b.affils[0]}  |07Dist: {aff}"))
        art.append(center(f"|07Sysop |15{b.sysop}  |08│  |07CoSysop |15{b.cosysop}"))
        art.append(center(f"|08{b.software} ∙ {b.city}, {b.state} ∙ "
                          f"|07{b.phone[2:]}"))
        art.append(gradient_rule(78, b.palette, "═"))
        art.append(f"|08{' ' * 55}ansi by {b.art_by[0].lower()}/{b.art_by[1].lower()}")
        self.out(art)

    def email(self):
        r = self.rng
        frm = self.b.sysop if r.random() < 0.5 else content.handle(r)
        body = r.choice([
            ["Your upload of last week was validated. Thanks for the",
             "support, ratio bumped to 1:2 for the month.", "", f"  -{frm}"],
            ["Got your request. I'll have the disks up by Friday.",
             "Don't tell anyone where you got em.", "", f"  -{frm}"],
            ["Hey, are you still couriering for " + r.choice(content.GROUPS) + "?",
             "We need someone on the west coast run. Leave me mail.", "", f"  -{frm}"],
        ])
        b = self.b
        self.out([CLS, f"|{b.lo:02d}─── |15Private Mail |{b.lo:02d}" + "─" * 60,
                  f"|07From: |15{rpad(frm, 26)}|07Date: |15{content.date93(r).replace('-', '/')}",
                  f"|07  To: |15{rpad(self.user, 26)}|07Subj: |15re: hey", "|08" + "─" * 76])
        self.out(["|07" + x for x in body] + [""])
        self.line.rpause(3, 5)
        self.ask(f"|{b.lo:02d}[|15R|{b.lo:02d}]eply, [|15D|{b.lo:02d}]elete, [|15Q|{b.lo:02d}]uit: |15", "D")
        self.out("|07Message deleted.")
        self.line.pause(0.8)

    # ---------------------------------------------------------------- actions
    def do_last(self, compact=False):
        b, r = self.b, self.rng
        rows = []
        n = 6 if compact else 10
        for i in range(n):
            city, st, _ = r.choice(content.CITIES)
            grp = r.choice(content.GROUPS) if r.random() < 0.5 else "-"
            baud = r.choice(["14400", "14400", "14400", "9600", "16800", "2400", "19200"])
            rows.append(f" |15{b.calls - n + i:>6} |{b.hi:02d}{rpad(content.handle(r), 18)}"
                        f"|07{rpad(grp, 14)}|03{rpad(city + ', ' + st, 18)}"
                        f"|11{baud:>5} |08{r.randint(0, 23):02d}:{r.randint(0, 59):02d}")
        hdr = (f" |08{'Call':>6} {rpad('Handle', 18)}{rpad('Group', 14)}"
               f"{rpad('Location', 18)}{'Baud':>5} Time")
        out = [] if compact else [CLS]
        out += ["", center(f"|{b.lo:02d}▄▄▄ |15{elite('Last Callers')} |{b.lo:02d}▄▄▄"),
                hdr, "|08 " + "─" * 77] + rows + [""]
        self.out(out)
        self.line.rpause(2, 4)
        if not compact:
            self.more()

    def do_oneliners(self, add=None):
        b, r = self.b, self.rng
        self.out(["", gradient_rule(78, b.palette, "─"),
                  center(f"|15{elite('The Wall')} |08─ |07OneLiners"),
                  gradient_rule(78, b.palette, "─")])
        for _ in range(8):
            who = content.handle(r)
            txt = content.oneliner(r, b.name)
            self.out(f" |{b.hi:02d}{rpad(who[:16], 16)}|08│ |07{txt[:58]}")
        self.out("")
        self.line.rpause(2, 4)
        if add is None:
            add = r.random() < 0.5
        if add:
            self.ask(f"|07Add a oneliner? |08(|15y|08/|15N|08) |15", "Y")
            self.ask("|07> |15", r.choice([
                f"greets to all {r.choice(content.GROUPS)} members",
                "hst for life", "anyone got the new 0-day?",
                f"{b.name} is k-rad!!", "calling from my dads office lol"]))
            self.out("|07Saved.")
            self.line.pause(0.6)

    def do_bulletins(self):
        b, r = self.b, self.rng
        self.out([CLS] + [center(x, 80) for x in ansi.block_text("RULES", b.palette)] + [""])
        rules = [
            f"Upload/download ratio is |151:{r.choice([3, 4, 5])}|07. 0-day uploads are |15x3|07 credit.",
            "Do |12NOT|07 upload anything older than a week to the 0-day area.",
            "All uploads must include the original |15FILE_ID.DIZ|07 and NFO.",
            "No handles in |15ALL CAPS|07. No real names. No phone #'s in public.",
            "Courier ratings are posted every Sunday. Inactive = deleted.",
            "Do |12NOT|07 give out the number. This means YOU.",
            f"Newuser password changes monthly; ask {b.sysop} via feedback.",
        ]
        for i, x in enumerate(rules, 1):
            self.out(f"  |{b.hi:02d}{i:>2}|08∙ |07{x}")
        self.out(["", center(f"|08── |07{elite('Affiliations')} |08──")])
        for g in b.affils:
            role = r.choice(["World HQ", "US HQ", "Distro Site", "Member Board",
                             "East Coast HQ", "Courier Site"])
            self.out(center(f"|{b.hi:02d}{rpad(g, 14)} |07{role}"))
        self.out("")
        self.line.rpause(4, 7)
        self.more()

    def do_who(self):
        b, r = self.b, self.rng
        self.out(["", center(f"|15{elite('Who is Online')}"), f"|08 Node  {rpad('User', 22)}{rpad('Activity', 30)}Baud",
                  "|08 " + "─" * 60])
        for n in range(1, b.nodes + 1):
            if n == b.node:
                u, act, baud = self.user, "Who's Online", "14400"
            elif r.random() < 0.7:
                u = content.handle(r)
                act = r.choice(["Downloading", "Uploading", "Reading Messages",
                                f"Playing {r.choice(content.DOORS)[0]}",
                                "Browsing files", "Chatting w/Sysop", "Logging in"])
                baud = r.choice(["14400", "9600", "16800", "2400"])
            else:
                u, act, baud = "|08--", "|08Waiting for caller", ""
            self.out(f"  |15{n:>3}  |{b.hi:02d}{rpad(u, 22)}|07{rpad(act, 30)}|11{baud}")
        self.out("")
        self.line.rpause(2, 4)

    def do_stats(self):
        b, r = self.b, self.rng
        ratio = b.dl_k / max(1, b.ul_k)
        lines = [
            f"|07Handle    : |15{self.user}",
            f"|07Security  : |15{r.choice([50, 60, 100, 120, 200])} |08({r.choice(['Courier', 'Elite', 'Member', 'Validated'])})",
            f"|07Calls     : |15{b.logon_no}",
            f"|07Uploads   : |15{b.ul_k:,}k |08in |15{b.ul_k // 900}|08 files",
            f"|07Downloads : |15{b.dl_k:,}k |08in |15{b.dl_k // 1000}|08 files",
            f"|07Ratio     : |{12 if ratio > 4 else 15}1:{ratio:.1f}",
            f"|07Time left : |15{b.time_left()} |07minutes",
            f"|07Posts     : |15{r.randint(3, 400)}",
        ]
        self.out([""] + box(lines, 50, b.lo, title=f"|15{elite('Your Stats')}") + [""])
        self.line.rpause(2.5, 4)

    def do_page(self):
        b, r = self.b, self.rng
        self.ask("|07Reason for chat: |15", r.choice(["need upload credit", "got a new release",
                                                       "u there?", "nup?"]))
        self.line.send("|07Paging " + b.sysop)
        for _ in range(r.randint(4, 7)):
            self.line.rpause(0.6, 1.0)
            self.line.send("|15 \u0007.")
        self.out("")
        if r.random() < 0.3:
            self.out([f"|{b.hi:02d}Chat mode engaged. |08(sysop typing)", ""])
            self.line.send("|11")
            self.line.type(r.choice(["hey whats up", "yo, got a minute only",
                                     "sup, im in the middle of a game"]))
            self.line.send("\n|15")
            self.line.type(r.choice(["just uploaded the new release, can u validate?",
                                     "can i get a ratio bump? uploading tonight"]))
            self.line.send("\n|11")
            self.line.type(r.choice(["sure thing. done.", "ok np, ur good", "k, later"]))
            self.out(["", f"|{b.hi:02d}Chat ended."])
        else:
            self.out(f"|07The sysop is not available. Leave feedback instead.")
        self.line.pause(1.0)

    # ---------------------------------------------------------------- messages
    def do_msgs(self):
        b, r = self.b, self.rng
        bases = r.sample(content.MSG_BASES, 6)
        self.out([CLS, center(f"|{b.lo:02d}▄▄ |15{elite('Message Bases')} |{b.lo:02d}▄▄"), ""])
        for i, nm in enumerate(bases, 1):
            new = r.randint(0, 40)
            self.out(f"   |08[|{b.hi:02d}{i:>2}|08] |07{rpad(nm, 26)}|08{r.randint(100, 3000):>5} msgs  "
                     f"|{15 if new else 8}{new:>3} new")
        self.out("")
        pick = r.randint(1, len(bases))
        self.ask(f"|07Select base |08(|15Q|08=quit) |07: |15", str(pick))
        base = bases[pick - 1]
        total = r.randint(200, 2000)
        start = total - r.randint(3, 30)
        for i in range(r.randint(2, 4)):
            m = content.message(r, b.name)
            num = start + i
            out = [CLS,
                   f"|{b.lo:02d}╔══ |15{base} |{b.lo:02d}" + "═" * (73 - len(base)),
                   f"|{b.lo:02d}║ |07Msg#|08: |15{num} of {total}",
                   f"|{b.lo:02d}║ |07From|08: |{b.hi:02d}{rpad(m['from'], 26)}|07Date|08: |15{m['date']} {m['time']}",
                   f"|{b.lo:02d}║ |07  To|08: |{b.hi:02d}{rpad(m['to'], 26)}|07Subj|08: |15{m['subj']}",
                   f"|{b.lo:02d}╚" + "═" * 77, ""]
            out += ["|07" + x for x in m["body"]]
            if r.random() < 0.5:
                out += ["", f"|07Greets to: |03" + ", ".join(r.sample(content.GROUPS, 3))]
            out.append("")
            if m["tag"]:
                out.append("|08" + m["tag"])
            out.append(f"|08--- {b.software}")
            out.append(f"|08 * Origin: |07{b.name} |08({b.phone[2:]})")
            out.append("")
            self.out(out)
            self.line.rpause(3.5, 7)
            last = i == 2 or r.random() < 0.3
            key = "Q" if last else "N"
            self.ask(f"|{b.lo:02d}[|15N|{b.lo:02d}]ext, [|15R|{b.lo:02d}]eply, [|15A|{b.lo:02d}]gain, "
                     f"[|15Q|{b.lo:02d}]uit: |15", key)
            if last:
                break

    # ---------------------------------------------------------------- files
    def do_files(self):
        b, r = self.b, self.rng
        self.out([CLS] + [center(x, 80) for x in ansi.block_text("FILES", b.palette)] + [""])
        areas = content.FILE_AREAS
        for i, (nm, kind) in enumerate(areas, 1):
            files = r.randint(40, 2400)
            self.out(f"   |{b.hi:02d}{i:>2}|08│ |07{rpad(nm, 30)}|08{files:>5} files  "
                     f"|03{r.randint(5, 900):>4} megs")
        self.out("")
        pick = r.choice([1, 1, 1, 2, 2, 3, 4, 5])
        self.ask(f"|07File area |08(|15?|08=list) |07: |15", str(pick))
        kind = areas[pick - 1][1]
        self.out([f"|07Joined file area |15{areas[pick - 1][0]}", ""])
        self.line.pause(0.5)
        flagged = self.file_list(kind)
        if flagged:
            self.download(flagged)

    def _entries(self, kind):
        r = self.rng
        out = []
        if kind in ("fresh", "games"):
            for set_id in range(r.randint(2, 3)):
                rel = content.release(r)
                n = len(rel["files"])
                gcol = 12 if r.random() < 0.5 else 11
                for d, (fn, size) in enumerate(rel["files"]):
                    desc = [f"|15{rel['title']} |07(c) {rel['publisher']}"
                            if d == 0 else f"|07{rel['title']} - disk {d + 1}",
                            f"|08[|15{d + 1}|08/|15{n}|08] |{gcol}"
                            f"-=≡ {rel['group']} ≡=-|08 ∙ |07{rel['kind']}"]
                    if d == 0:
                        desc.append(f"|08Supplied by |07{rel['supplier']}|08 ∙ |07{rel['protect']}")
                    out.append((fn, size, rel["date"], rel["dl"], desc, set_id))
        elif kind == "utils":
            for fn, d in r.sample(content.UTILS, 4):
                out.append((fn + ".ZIP", r.randint(60, 900), content.date93(r), r.randint(1, 300),
                            ["|07" + d, f"|08Uploaded by |07{content.handle(r)}"], None))
        elif kind == "art":
            for _ in range(3):
                g = r.choice(content.ART_GROUPS)
                fn = f"{g[:4]}-{r.randint(1, 30):02d}93.ZIP"
                out.append((fn, r.randint(150, 900), content.date93(r), r.randint(5, 120),
                            [f"|13{elite(g)} |07art pack #{r.randint(1, 40)}",
                             f"|08ANSi, RiP, VGA and hi-res. {r.randint(20, 60)} files."], None))
        else:
            for t, d in r.sample(content.DEMO_TITLES, 3):
                out.append((content.eight3(t, r) + ".ZIP", r.randint(300, 1400),
                            content.date93(r), r.randint(3, 200),
                            [f"|15{t}", "|07" + d], None))
        return out

    def file_list(self, kind):
        b, r = self.b, self.rng
        entries = self._entries(kind)
        if b.style == "pcboard":
            self.out([f"|14Filename       Size      Date    Description of File Contents",
                      "|09============  ========  ======== " + "=" * 42])
        else:
            self.out([f"|08 ## {rpad('Filename', 13)}{'Size':>6} {'DLs':>4}  Description",
                      "|08 " + "─" * 77])
        for i, (fn, size, date, dls, desc, _) in enumerate(entries, 1):
            base, ext = fn.split(".")
            if b.style == "pcboard":
                head = f"|14{rpad(base, 8)}.{ext}  |02{size * 1024:>8}  |03{date}  "
                self.out(head + desc[0])
                for d in desc[1:]:
                    self.out(" " * 35 + "|09| " + d)
            else:
                head = (f" |15{i:>2} |{b.hi:02d}{rpad(base, 8)}|{b.lo:02d}.|{b.hi:02d}{ext} "
                        f"|07{size:>5}k |08[|07{dls:>3}|08] ")
                self.out(head + desc[0])
                for d in desc[1:]:
                    self.out(" " * 30 + d)
        self.out("")
        self.line.rpause(3, 6)
        flagged = []
        if r.random() < 0.85:
            # flag every disk of one release set (or a single file)
            pick = r.randrange(len(entries))
            sid = entries[pick][5]
            idx = [i for i, e in enumerate(entries)
                   if (sid is not None and e[5] == sid) or i == pick]
            flagged = [(entries[i][0], entries[i][1]) for i in idx]
            nums = " ".join(str(i + 1) for i in idx)
            self.ask(f"|{b.lo:02d}[|15N|{b.lo:02d}]ext, [|15F|{b.lo:02d}]lag, [|15V|{b.lo:02d}]iew, "
                     f"[|15D|{b.lo:02d}]ownload, [|15Q|{b.lo:02d}]uit: |15", "F")
            self.ask("|07Flag which file(s)? |15", nums)
            tot = sum(s for _, s in flagged)
            self.out(f"|07Flagged |15{len(flagged)}|07 file(s), |15{tot:,}k|07  "
                     f"Est. |15{tot * 1024 // 1650 // 60}:{tot * 1024 // 1650 % 60:02d}|07 at 14400")
            self.ask(f"|{b.lo:02d}[|15N|{b.lo:02d}]ext, [|15F|{b.lo:02d}]lag, [|15V|{b.lo:02d}]iew, "
                     f"[|15D|{b.lo:02d}]ownload, [|15Q|{b.lo:02d}]uit: |15", "D")
        else:
            self.ask(f"|{b.lo:02d}[|15N|{b.lo:02d}]ext, [|15F|{b.lo:02d}]lag, [|15V|{b.lo:02d}]iew, "
                     f"[|15D|{b.lo:02d}]ownload, [|15Q|{b.lo:02d}]uit: |15", "Q")
        return flagged

    def download(self, files):
        L, b, r = self.line, self.b, self.rng
        self.out(["", "|07Protocols: |08(|15Z|08)|07modem  |08(|15Y|08)|07modem-G  "
                      "|08(|15H|08)|07SLink  |08(|15X|08)|07modem"])
        self.ask("|07Protocol: |15", "Z")
        ratio_ok = r.random() < 0.9
        if not ratio_ok:
            self.out(["", "|12Sorry, your ratio is too low! Upload more files.", ""])
            L.pause(2)
            return
        self.out(["|07Ready to send in batch mode.",
                  "|07Start your |15Zmodem|07 receive now. |08(Ctrl-X to abort)"])
        L.pause(0.8)
        L.send("**\x18B00000000000000\n")  # ZRQINIT shows up as junk
        L.pause(0.4)
        self.transfer(files)
        self.out(["", "|07Transfer complete. |15Thanks for the download!", ""])
        b.dl_k += sum(s for _, s in files)
        L.pause(1.5)

    def transfer(self, files):
        """The local terminal program's Zmodem status window."""
        L, r = self.line, self.rng
        W = 62
        pad = " " * 8
        top = "|09╔" + "═" * (W - 2) + "╗"
        bot = "|09╚" + "═" * (W - 2) + "╝"

        def row(s):
            return pad + "|09║|07|17 " + rpad(s, W - 3) + "|09|16║"

        L.local("|07|16\n" + pad + top + "\n")
        L.local(row(f"|15|17 Zmodem download |07|17─ batch of {len(files)}") + "\n")
        for _ in range(4):
            L.local(row("") + "\n")
        L.local(pad + bot + "|07|16")
        cps_base = r.randint(1610, 1700)
        for idx, (fn, size_k) in enumerate(files):
            total = size_k * 1024
            got = 0
            t0 = time.monotonic()
            while got < total:
                cps = cps_base + r.randint(-40, 30)
                if r.random() < 0.01:
                    cps = r.randint(200, 900)  # line hit, retry
                dt = 0.2
                got = min(total, got + int(cps * dt * self.xfer_speedup))
                el = int((time.monotonic() - t0) * self.xfer_speedup)
                eta = int((total - got) / max(1, cps))
                barw = 30
                fill = int(barw * got / total)
                bar = "|11" + "█" * fill + "|09" + "░" * (barw - fill)
                lines = [
                    f"|07File: |15{rpad(fn, 13)}|07 {idx + 1} of {len(files)}",
                    f"|07Bytes:|15{got:>9,}|07 / {total:,}",
                    f"{bar}|07|17 {100 * got // total:>3}%",
                    f"|07CPS: |15{cps:>5}  |07Elapsed: |15{el // 60:02d}:{el % 60:02d}  "
                    f"|07ETA: |15{eta // 60:02d}:{eta % 60:02d}",
                ]
                L.local("\x1b[4A")
                for ln in lines:
                    L.local("\r" + row(ln) + "\x1b[1B")
                L.local("|07|16")
                L.pause(dt)
            L.pause(0.3)
        L.local("\n")

    # ---------------------------------------------------------------- doors
    def do_doors(self):
        b, r = self.b, self.rng
        self.out([CLS, center(f"|{b.lo:02d}▄▄ |15{elite('Door Games')} |{b.lo:02d}▄▄"), ""])
        for i, (nm, d) in enumerate(content.DOORS, 1):
            self.out(f"   |08[|{b.hi:02d}{i:>2}|08] |15{rpad(nm, 20)}|07{d}")
        self.out("")
        which = r.choice([1, 1, 2, 2])
        self.ask("|07Which door? |15", str(which))
        self.out(["", f"|07Loading |15{content.DOORS[which - 1][0]}|07...  writing DOOR.SYS",
                  "|08Please wait..."])
        self.line.rpause(1.5, 3)
        if which == 1:
            doors.shadowmire(self)
        else:
            doors.starlane(self)
        self.out(["", "|07Returning to |15" + b.name + "|07...", ""])
        self.line.rpause(1, 2)

    # ---------------------------------------------------------------- bye
    def do_bye(self):
        L, b, r = self.line, self.b, self.rng
        self.ask("|07Log off now? |08(|15Y|08/|15n|08) |15", "Y")
        bye = [CLS, ""] + logo(elite("Later"), b.palette) + [""]
        bye += [center(f"|07Thanks for calling |{b.hi:02d}{b.name}|07, {self.user}!"),
                center(f"|07You were on for |15{max(1, int((time.monotonic() - b.started) / 60))}|07 minutes."),
                "", center(fade_bar(40, (8, b.lo, b.hi, b.lo, 8))),
                center(f"|08Call back soon ∙ {b.phone[2:]} ∙ 24 hours"), ""]
        self.out(bye)
        L.rpause(1.5, 2.5)
        L.local("|07\n")
        L.local("|15NO CARRIER\n|07")
        L.online_since = None
        L.rpause(3, 5)
