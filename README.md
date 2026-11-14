# courierhst
sleek. sharp. black.

A Linux console screensaver that dials up early-1990s warez-scene BBSes on a
**US Robotics Courier HST 14.4** and browses them for you. All output is
metered at a real 14,400 bps (1,440 cps, 8N1), so every ANSI logo, menu and
file listing paints in at true modem speed.

Each call:

- **Dials** from the terminal program: `ATZ`, init string, `ATDT`, sometimes
  `BUSY` and a redial, then `CONNECT 14400/ARQ/HST`
- **Logs in**: mailer "press ESC twice", ANSI detection, a block-letter ANSI
  logo with gradients and drop shadows, handle/password/phone check, logon
  stats, mail scan, last callers, oneliners
- **Browses** with period menus in four flavours (Renegade-, Telegard-, Mystic- and
  PCBoard-style), picking from:
  - message bases (scene chatter, courier wanted ads, FS: modems, origin lines)
  - file areas: 0-day and game releases as multi-disk 8.3 ZIP sets with group
    tags, then flag, pick Zmodem, and watch the transfer window at about 1,650 cps
  - door games: **Shadowmire** (forest-fight RPG) and **Starlane Merchant**
    (space trading with haggling)
  - bulletins and rules, who's online, your stats, paging the sysop
- **Logs off**: goodbye screen, `NO CARRIER`, and dials the next board

A terminal-program status bar (connect speed, board name, online timer) sits
under the 80x25 BBS window. The window is centred in larger terminals. There
is occasional line noise.

Every board, handle, group, release title and door game is fictional.

## Run

```sh
python3 -m courierhst          # from the repo, no dependencies
# or
pip install . && courierhst
```

Press any key to exit.

| option | |
|---|---|
| `--bps N` | line speed (default 14400; try 2400 for pain) |
| `--handle NAME` | your handle (default: random) |
| `--seed N` | repeatable run |
| `--noise P` | line-noise chance per character (default 0.0015, 0 = off) |
| `--xfer-speedup X` | time compression for Zmodem downloads (default 40, 1 = real time) |
| `--no-center` / `--no-status` | draw at top-left / hide the status bar |
| `--calls N` | exit after N calls (default: forever) |
| `--step-pause SECONDS` | seconds the caller lingers before each next step: menu command, message, file prompt, door move (default 5, 0 disables; `--warp` scales it) |
| `--warp X` | speed everything up (for previewing) |
| `--board-style S` | force the BBS software style: `renegade`, `telegard`, `mystic` or `pcboard` (default: random mix) |
| `--no-exit-on-key` | only Ctrl-C exits |

The art uses CP437 block and box characters, which the Linux console's
default fonts and any modern terminal font can display. For the authentic
look, use a VGA font (e.g. `setfont` with a `Lat2-VGA16` / `default8x16` font
on the console).

## Use it as a screensaver

**tmux** (works on the Linux console and in any terminal):

```tmux
set -g lock-after-time 300          # idle seconds
set -g lock-command "courierhst"
```

**zsh** (bare Linux console, no tmux):

```zsh
TMOUT=300
TRAPALRM() { courierhst }
```

(bash's `TMOUT` logs the shell out instead of running a hook, so on bash use
tmux.)

## Development

The program itself has no dependencies (stdlib only, Python 3.8+). Run the
tests with:

```sh
python3 -m unittest discover -s tests
```

The unit tests (`ansi`, `modem.Line` metering and status bar) need nothing
extra. The pty acceptance tests (`tests/test_session_pty.py`) run the whole
program for seeds 1-20 at 80x26, 80x24 and 120x40 and check the output with
the `pyte` VT emulator; they are skipped if `pyte` is missing. Install it
with `pip install pyte` (or `pip install -e '.[test]'`). The full pty run
takes about 30 seconds.
