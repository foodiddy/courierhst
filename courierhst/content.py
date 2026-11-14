"""Fictional period content: boards, handles, groups, releases, messages.

All names here are invented.  They are built to *sound* like 1992-1994 scene
material without referring to real boards, people, groups or products.
"""

import random

from .ansi import elite

BBS_FIRST = [
    "The", "The", "The", "", "",
]
BBS_ADJ = [
    "Neon", "Twilight", "Obsidian", "Crimson", "Silent", "Shattered",
    "Frozen", "Electric", "Hollow", "Sunken", "Phantom", "Midnight",
    "Iron", "Static", "Burning", "Lost", "Infinite", "Velvet", "Toxic",
    "Black", "Chrome", "Forgotten", "Digital", "Final",
]
BBS_NOUN = [
    "Abyss", "Forge", "Citadel", "Asylum", "Vault", "Labyrinth", "Nexus",
    "Domain", "Wasteland", "Crypt", "Fortress", "Outpost", "Underground",
    "Sanctum", "Horizon", "Inferno", "Matrix", "Frontier", "Reactor",
    "Monolith", "Catacombs", "Spire", "Junction", "Dimension",
]

HANDLE_A = [
    "Neon", "Dark", "Cyber", "Night", "Steel", "Acid", "Silent", "Mad",
    "Lord", "Zero", "Black", "Toxic", "Grim", "Hyper", "Static", "Crimson",
    "Ghost", "Iron", "Void", "Data", "Phantom", "Psycho", "Turbo", "Frost",
]
HANDLE_B = [
    "Wraith", "Reaper", "Byte", "Viper", "Raven", "Knight", "Spectre",
    "Hacker", "Druid", "Cobra", "Shadow", "Dragon", "Warlock", "Jester",
    "Nomad", "Phreak", "Blade", "Rider", "Demon", "Prophet", "Fury",
    "Lynx", "Pulse", "Mage",
]
HANDLE_SOLO = [
    "Mr. Kaos", "The Dentist", "Bit Rot", "Captain Zilog", "Dr. Modem",
    "Count Zer0", "The Archivist", "Sector 7", "Null Pointer", "Lamer X",
    "MaxBaud", "Carrier Lost", "The Locksmith", "Doc Holiday", "Paperclip",
]

GROUPS = [
    "CRiMSON TiDE", "NEURAL FLUX", "OBSiDiAN", "HYPERiON", "VELVET CODE",
    "STATiC", "ZEPHYR", "DARKSiDE iNC", "QUANTUM", "NiGHTFALL", "PHOTON",
    "SiLiCON DREAM", "VORTEX9", "ECLiPSE", "ARCANE", "MONOLiTH",
]
ART_GROUPS = ["NOiR", "PRiZM", "HUE", "SPECTRA", "iNK", "CHROMA"]

CITIES = [
    ("Sacramento", "CA", 916), ("Austin", "TX", 512), ("Tampa", "FL", 813),
    ("Cleveland", "OH", 216), ("Denver", "CO", 303), ("Phoenix", "AZ", 602),
    ("Seattle", "WA", 206), ("Boston", "MA", 617), ("Detroit", "MI", 313),
    ("Portland", "OR", 503), ("Atlanta", "GA", 404), ("Chicago", "IL", 312),
    ("Pittsburgh", "PA", 412), ("Omaha", "NE", 402), ("Raleigh", "NC", 919),
    ("Albany", "NY", 518), ("Tucson", "AZ", 520), ("Las Vegas", "NV", 702),
    ("Baltimore", "MD", 410), ("St. Louis", "MO", 314),
]

SOFTWARE = {
    "renegade": "Renegade v04-05 Exp",
    "telegard": "Telegard v2.7",
    "pcboard": "PCBoard v14.5a",
    "mystic": "Mystic BBS v1.07",
}

# What a board's affiliation with a scene group is called, in rank order
# (left splash corner), and the board's own standing (right splash corner).
AFFIL_ROLES = ["World HQ", "US HQ", "Distro Site", "East Coast HQ",
               "West Coast HQ", "Courier Site", "Member Board"]
BOARD_ROLES = ["Member Board", "Courier Site", "Distro Site", "Trading Post"]

# Mystic-style message networks, per message base
NETWORKS = ["local", "fido", "scene", "warez"]

PUBLISHERS = [
    "Polaris Interactive", "Omnisoft", "Brightstar Games", "Krystal Software",
    "Thundergate", "Mindscope", "Arcturus Entertainment", "Wyvern Studios",
    "Hexagon Labs", "Silverline", "Paragon Edge", "Redshift Software",
]
GAMES = [
    "Stellar Dominion II", "Iron Legion", "Wyrmspire: The Dark Pact",
    "Tank Commander Gold", "Galactic Freight Co.", "Necropolis Rising",
    "Hellcat Squadron", "Codename: Firewall", "Dungeon Delvers III",
    "Rally Fever '93", "Pyramid of Ka", "Corsair Seas", "Mech Assault Zero",
    "Blackwater Inn", "Chrono Raider", "Neon Knights", "Ultra Pinball 2",
    "Space Rescue Ranger", "Siege of Valdor", "Drift Racer Turbo",
    "Planetfall Tactics", "Monster Bash", "The Clockwork Tower",
    "Gridiron Pro '94", "Skyfortress", "Lunar Lander Deluxe",
]
UTILS = [
    ("QZIP204G", "QuikZip v2.04g - the archiver everyone uses"),
    ("TURBOCMD", "TurboCommander v3.1 - file manager w/ ZIP view"),
    ("DSKCACHE", "DiskCache Pro 2.0 - 386 disk caching TSR"),
    ("MDMTEST", "ModemTest v1.4 - HST/V.32bis diagnostics"),
    ("ANSIVIEW", "AnsiView 5.2 - view ANSI/iCE art, SAUCE aware"),
    ("TERMX300", "TermX v3.00 - comm program, Zmodem/HSLink"),
    ("UNPAK", "UnPak 1.1 - extracts ZIP/ARJ/LZH/ARC at once"),
    ("MEMXPRT", "MemExpert 2.1 - squeeze 620k of base memory!"),
]

DOORS = [
    ("Shadowmire", "Forest fights, dragons, romance at the Inn"),
    ("Starlane Merchant", "Trade, haggle & conquer 2000 sectors"),
    ("Cellar of Sorrow", "Multi-node dungeon crawl"),
    ("Hex Wars", "Conquer the hex map. Daily turns"),
    ("BBS Casino", "Blackjack, slots, keno - win file credits"),
    ("Pit Fighter", "Gladiator arena, 12 classes"),
    ("Neon Lotto", "Daily drawing, win download time"),
    ("Galactic Empire 2", "Inter-BBS empire building"),
]

MSG_BASES = [
    "General Chit-Chat", "Warez Requests", "Courier Lounge", "Releases/NFOs",
    "Hardware Swap Meet", "ANSi/Art Scene", "Sysop Feedback", "Phun & Games",
]

FILE_AREAS = [
    ("0-Day Releases", "fresh"), ("PC Games", "games"),
    ("Utilities", "utils"), ("ANSi Art Packs", "art"),
    ("Demos & Music", "demo"), ("BBS Software", "bbs"),
    ("Group NFOs/Intros", "nfo"), ("Upload Area (unvalidated)", "ul"),
]

DEMO_TITLES = [
    ("Second Horizon", "2nd at the summer party, GUS/SB, 4 meg"),
    ("Velocity Crash", "VGA tunnel madness, needs 486"),
    ("Polygon Dreams", "Gouraud vectors! SB Pro music"),
    ("Cold Copper", "64k intro winner, plasma + rotozoom"),
    ("Mod Pak #17", "15 tracker MODs, 4ch/8ch"),
]

ONELINERS = [
    "anyone got a working 16.8 dual standard for sale??",
    "{group} rules all, the rest are lame",
    "NUP NUP NUP - courier positions open, msg sysop",
    "ratio is 1:5 now, upload or get deleted ;)",
    "who keeps camping on node 1 all night?? share!!",
    "greets to everyone on the {area} scene!",
    "this board is kRaD. long live {bbs}!",
    "new {group} release in 0-day, get it before the leechers",
    "wtf my mom picked up the phone during a zmodem",
    "whoever keeps uploading crcd files - stop it",
    "the hst is SO much better than v.32bis, fight me",
    "net mail is down again, blame fidonet",
    "first! ...oh wait",
    "BUSY BUSY BUSY 2 hours of redial for this?",
    "check out my new ansi in the art area",
]


def bbs_name(rng=random):
    first = rng.choice(BBS_FIRST)
    name = f"{rng.choice(BBS_ADJ)} {rng.choice(BBS_NOUN)}"
    return (first + " " + name).strip()


def handle(rng=random):
    r = rng.random()
    if r < 0.18:
        return rng.choice(HANDLE_SOLO)
    if r < 0.6:
        return f"{rng.choice(HANDLE_A)} {rng.choice(HANDLE_B)}"
    return f"{rng.choice(HANDLE_A)}{rng.choice(HANDLE_B)}"


def phone(rng=random, area=None):
    if area is None:
        area = rng.choice(CITIES)[2]
    return f"1-{area}-555-01{rng.randint(0, 99):02d}"


def date93(rng=random):
    y = rng.choice([92, 93, 93, 93, 94])
    return f"{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}-{y}"


def eight3(title, rng=random, disk=None):
    """Turn a title into a plausible 8.3 filename."""
    letters = "".join(c for c in title.upper() if c.isalnum())
    words = [w for w in "".join(c if c.isalnum() else " " for c in title.upper()).split()]
    if len(words) >= 2:
        base = (words[0][:4] + words[1][:3])
    else:
        base = letters[:7]
    if disk is not None:
        base = base[:7] + "ABCDEFGHIJ"[disk]
    else:
        base = base[:8]
    return base


def release(rng=random):
    """A warez release: dict with files and nfo-ish metadata."""
    title = rng.choice(GAMES)
    disks = rng.choice([1, 2, 2, 3, 3, 4, 5, 6])
    group = rng.choice(GROUPS)
    files = []
    for d in range(disks):
        name = eight3(title, rng, d if disks > 1 else None) + ".ZIP"
        size = rng.randint(1180, 1430) if d < disks - 1 else rng.randint(180, 1400)
        files.append((name, size))
    return {
        "title": title,
        "publisher": rng.choice(PUBLISHERS),
        "group": group,
        "supplier": handle(rng),
        "cracker": handle(rng),
        "files": files,
        "date": date93(rng),
        "dl": rng.randint(0, 87),
        "kind": rng.choice(["VGA Action", "Strategy", "RPG", "Simulation",
                            "Arcade", "Adventure", "Sports", "Wargame"]),
        "protect": rng.choice(["Doc check removed", "Manual lookup removed",
                               "Code wheel removed", "Disk check removed",
                               "No protection, just supplied", "Key disk cracked"]),
    }


# --------------------------------------------------------------------------
# Messages
# --------------------------------------------------------------------------

_MSG_TEMPLATES = [
    ("new {group} rls?", [
        "Yo, anyone know when the {group} release of {game} is hitting?",
        "Heard it was supplied last nite and they're packing it now.",
        "My distro site in {city} doesn't have it yet. If it shows up",
        "here first I'll eat my US Robotics manual.",
    ]),
    ("Re: ratios", [
        "Listen, I know the ratio is 1:5 but I just uploaded {mb} megs of",
        "brand new stuff and the sysop STILL hasn't validated it. My file",
        "points are at zero. Can somebody with co-sysop access hook me up?",
        "",
        "Not trying to whine. Ok maybe a little.",
    ]),
    ("courier wanted", [
        "{group} is looking for 2 couriers with access to at least 5",
        "distro sites, HST or v.32bis minimum. You must be able to move",
        "0-day within the hour. No lamers, no leeches, no bust-outs.",
        "",
        "Leave me email here if you think you're elite enough.",
    ]),
    ("FS: Courier HST 14.4", [
        "Upgrading to a dual standard so I'm selling my Courier HST 14.4.",
        "Works perfect, has the manual and the wall wart. $250 or best",
        "offer. Will also trade for a 120 meg IDE drive + cash.",
        "",
        "Local pickup only, {city} area.",
    ]),
    ("lamer alert", [
        "Watch out for a user called '{lamer}'. Uploaded a 'new' release",
        "that was really a 6 month old game renamed with a fake NFO.",
        "Sysop has been notified. Don't download anything he puts up.",
    ]),
    ("Re: best terminal program?", [
        "I've used them all and honestly it comes down to Zmodem with",
        "crash recovery and a good dialing directory. Put 40 boards in",
        "the queue, go to bed, and wake up connected. Thats the dream.",
        "",
        "Also turn the modem speaker OFF before your parents wake up.",
    ]),
    ("my new ansi", [
        "Just finished a new logo for {bbs}, it's in the ANSi area as",
        "{art}.ANS. 80x50, iCE colors, took me 3 nights in TheDraw-",
        "style editor. Comments welcome, flames ignored.",
    ]),
    ("Re: busy signals", [
        "Dude this board has been busy every single night this week.",
        "Sysop PLEASE add another node. I'll donate a 2400 if I have to.",
        "Ok maybe not a 2400, nobody wants those.",
    ]),
    ("phone bill", [
        "Got my phone bill. {money} dollars in long distance. My dad",
        "found out who 'Courier HST' was and it was me. Grounded for 2",
        "weeks so if you don't see me online, thats why.",
        "",
        "Back on the 15th. Save me a slot in the {door} tourney.",
    ]),
    ("Re: {door} scores", [
        "Who the heck is '{handle}' and how are they level 11 already?",
        "I've been playing every day since the reset. Something is up.",
        "Sysop - check the player file, I'm calling shenanigans.",
    ]),
    ("SB vs GUS", [
        "Sound Blaster is standard but the Gravis sounds WAY better in",
        "demos. Saw {demo} on a GUS at a copy party and nearly cried.",
        "Anyone want to trade a SB Pro for a GUS + cash?",
    ]),
    ("Re: system crash", [
        "The board went down Tuesday because the hard drive filled up",
        "during a batch upload. Files from 2am-6am are gone, please",
        "upload again and you'll get double credit.  -Sysop",
    ]),
]

TAGLINES = [
    "... Back up my hard drive? How do I put it in reverse?",
    "... 14.4k? In MY day we had 300 baud and LIKED it.",
    "... Press any key... no, not THAT key!",
    "... I'd tell you a UDP joke but you might not get it.",
    "... Modem (n): device for turning money into phone bills.",
    "... CONNECT 14400 / NO CARRIER: the circle of life.",
    "... ATH0 - The last command you'll ever need.",
    "... Windows 3.1: a 16-bit shell for an 8-bit OS...",
    "... RAM disk is NOT an installation procedure.",
]


def fill(s, ctx):
    try:
        return s.format(**ctx)
    except (KeyError, IndexError):
        return s


def message_context(rng, bbs):
    return {
        "group": rng.choice(GROUPS), "game": rng.choice(GAMES),
        "city": rng.choice(CITIES)[0], "mb": rng.randint(3, 22),
        "lamer": handle(rng), "bbs": bbs, "art": "".join(
            rng.choice("ABCDEFGHIJKLMNOPRSTW") for _ in range(6)),
        "money": rng.choice([212, 347, 488, 516, 731]),
        "door": rng.choice(DOORS)[0], "handle": handle(rng),
        "demo": rng.choice(DEMO_TITLES)[0],
        "area": rng.choice(CITIES)[2],
    }


def message(rng, bbs):
    ctx = message_context(rng, bbs)
    subj, body = rng.choice(_MSG_TEMPLATES)
    return {
        "from": handle(rng),
        "to": rng.choice(["All", "All", "All", "Sysop", handle(rng)]),
        "subj": fill(subj, ctx),
        "body": [fill(b, ctx) for b in body],
        "date": date93(rng).replace("-", "/"),
        "time": f"{rng.randint(1, 12):02d}:{rng.randint(0, 59):02d}{rng.choice('ap')}",
        "tag": rng.choice(TAGLINES) if rng.random() < 0.6 else None,
    }


def oneliner(rng, bbs):
    return fill(rng.choice(ONELINERS), message_context(rng, bbs))


def group_tag(rng=random):
    return elite(rng.choice(GROUPS))
