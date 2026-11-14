"""G-Files: the BBS text-file library, read from ``data/gfiles/<section>/``.

Drop a ``.txt`` file into a section folder (and optionally a line in that
folder's ``files.bbs``) and it shows up; no code changes are needed.
"""

import os
import zlib

COLS = 79
DESC_MAX = 45

SECTIONS = [
    ("scene", "Scene & NFOs"),
    ("bbs", "BBS Lists & Ads"),
    ("rants", "Rants & Editorials"),
    ("misc", "Humor & Misc"),
]

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "data", "gfiles")


def fake_date(name):
    """Deterministic mm-dd-yy between 1990 and 1993, from a CRC of the name."""
    crc = zlib.crc32(name.encode("latin-1", "replace")) & 0xFFFFFFFF
    year = 90 + crc % 4
    month = (crc >> 4) % 12 + 1
    day = (crc >> 9) % 28 + 1
    return f"{month:02d}-{day:02d}-{year:02d}"


def _read_text(path):
    """Read a file as CP437, the way a DOS board would."""
    with open(path, "rb") as fh:
        return fh.read().decode("cp437", "replace")


def _index(folder_path):
    """Parse files.bbs into {NAME: description}; never raises."""
    descs, last = {}, None
    try:
        text = _read_text(os.path.join(folder_path, "files.bbs"))
    except OSError:
        return descs
    for line in text.splitlines():
        if not line.strip():
            continue
        if line[0] in " \t":
            continue  # continuation line: the first line is the description
        parts = line.split(None, 1)
        last = parts[0].upper()
        descs[last] = parts[1].strip()[:DESC_MAX] if len(parts) > 1 else ""
    return descs


def _first_line(path):
    try:
        for line in _read_text(path).splitlines():
            if line.strip():
                return line.strip()[:DESC_MAX]
    except OSError:
        pass
    return ""


def _folders(root):
    """Known sections first, then any extra folders, title-cased."""
    try:
        found = sorted(d for d in os.listdir(root)
                       if os.path.isdir(os.path.join(root, d)))
    except OSError:
        return []
    known = [f for f, _ in SECTIONS]
    titles = dict(SECTIONS)
    out = [(f, titles[f]) for f in known if f in found]
    for f in found:
        if f not in titles:
            out.append((f, f.replace("_", " ").replace("-", " ").title()))
    return out


def load(root=None):
    """All non-empty sections: ``[{folder, title, files: [...]}, ...]``."""
    root = root or DATA_DIR
    sections = []
    for folder, title in _folders(root):
        path = os.path.join(root, folder)
        descs = _index(path)
        files = []
        try:
            names = sorted(n for n in os.listdir(path)
                           if n.lower().endswith(".txt")
                           and os.path.isfile(os.path.join(path, n)))
        except OSError:
            continue
        for name in names:
            fpath = os.path.join(path, name)
            try:
                size = os.path.getsize(fpath)
            except OSError:
                continue
            desc = descs.get(name.upper())
            if not desc:
                desc = _first_line(fpath)
            files.append({"name": name, "size": size, "date": fake_date(name),
                          "desc": desc[:DESC_MAX], "path": fpath})
        if files:
            sections.append({"folder": folder, "title": title, "files": files})
    return sections


def read(entry):
    """The file's lines, tabs expanded, each at most 79 columns."""
    try:
        text = _read_text(entry["path"])
    except OSError:
        return []
    lines = []
    for ln in text.splitlines():
        ln = "".join(c for c in ln if c == "\t" or c >= " " and c != "\x7f")
        lines.append(ln.expandtabs(8).rstrip()[:COLS])
    return lines
