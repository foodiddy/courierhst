"""Door games. Original designs in the style of early-90s BBS doors."""

from . import content
from .ansi import box, center, elite, fade_bar, gradient_rule, logo, rpad

CLS = "\x0c"

MONSTERS = [
    ("Bog Ghoul", 14, 4, 22), ("Rabid Marsh Hound", 18, 5, 30),
    ("Hollow Knight-Errant", 30, 8, 55), ("Lantern Wisp", 12, 6, 26),
    ("Thornback Boar", 24, 7, 41), ("Mire Witch", 34, 10, 70),
    ("Rusted Golem", 40, 9, 80), ("Two-Headed Toad", 16, 4, 19),
    ("Grave Robber", 20, 6, 35), ("Eel of the Black Pool", 28, 9, 62),
]
WEAPONS = ["Rusty Dagger", "Hand Axe", "Bastard Sword", "Morning Star",
           "Elven Longbow", "Runed Claymore"]
ARMOR = ["Leather Vest", "Studded Leather", "Chain Shirt", "Scale Mail"]


def shadowmire(s):
    """A forest-fight RPG door."""
    L, r = s.line, s.rng
    lvl = r.randint(2, 9)
    hp_max = 20 + lvl * 13
    hp = hp_max - r.randint(0, lvl * 5)
    gold = r.randint(100, 9000)
    exp = r.randint(lvl * 400, lvl * 900)
    fights = r.randint(6, 18)
    weapon = WEAPONS[min(len(WEAPONS) - 1, lvl // 2)]
    armor = ARMOR[min(len(ARMOR) - 1, lvl // 3)]

    art = [CLS] + logo("SHADOWMIRE", "toxic") + [
        center("|02∙|10∙|02∙ |07The Swamp Kingdom of |10Vael |02∙|10∙|02∙"),
        center("|08v2.10 ∙ (c) 1992 Bogwater Software ∙ Registered to " + s.b.name),
        "", gradient_rule(78, "toxic", "─"), ""]
    s.out(art)
    L.rpause(1.5, 2.5)
    s.out([center(f"|07Welcome back, |10{s.user}|07. The fog is thick today."),
           center(f"|07You have |15{fights}|07 forest fights left."), ""])
    s.more()

    def town_menu():
        s.out([CLS, f"|02╔═══ |10{elite('Vael Town Square')} |02" + "═" * 54,
               "|02║ |07The muddy square is busy. A bard sings off key.", "|02╚" + "═" * 76, "",
               "  |02(|10F|02)|07orest - Look for something to kill",
               "  |02(|10H|02)|07ealer's Hut          |02(|10I|02)|07nn of the Drowned Rat",
               "  |02(|10W|02)|07eapon Smithy         |02(|10A|02)|07rmour Shop",
               "  |02(|10V|02)|07iew your stats       |02(|10D|02)|07aily news",
               "  |02(|10Q|02)|07uit to the BBS", ""])

    def town_prompt():
        return (f"|02[|10HP|02: |15{hp}|02/|15{hp_max}|02] |07The Town Square |08(|15? for menu|08)"
                f"\n|07Your command, {s.user}? |15")

    plan = ["V", "F", "F"] + r.sample(["F", "D", "H", "F"], r.randint(1, 3)) + ["Q"]
    for cmd in plan:
        town_menu()
        s.step()
        s.ask(town_prompt(), cmd, fast=True)
        if cmd == "V":
            s.out([""] + box([
                f"|07Name     |02: |10{s.user}",
                f"|07Level    |02: |15{lvl}      |07Experience |02: |15{exp:,}",
                f"|07Hitpoints|02: |15{hp}|07 of |15{hp_max}",
                f"|07Weapon   |02: |15{weapon}",
                f"|07Armour   |02: |15{armor}",
                f"|07Gold     |02: |14{gold:,}      |07Gems |02: |15{r.randint(0, 12)}",
                f"|07Fights   |02: |15{fights} left today",
            ], 60, 2, title=f"|10{elite('Stats')}") + [""])
            L.rpause(2.5, 4)
            s.more()
        elif cmd == "D":
            news = [f"|10{content.handle(r)}|07 was slain by a |12{r.choice(MONSTERS)[0]}|07.",
                    f"|10{content.handle(r)}|07 got married at the Inn! Drinks for all.",
                    f"|10{content.handle(r)}|07 advanced to level |15{r.randint(3, 12)}|07.",
                    f"|10{content.handle(r)}|07 attacked |10{s.user}|07 in their sleep and lost!"]
            s.out(["", center(f"|10{elite('Daily Happenings')}"), fade_bar(78, (2, 10, 15, 10, 2))]
                  + ["  |02∙ " + n for n in r.sample(news, 3)] + [""])
            L.rpause(3, 4)
            s.more()
        elif cmd == "H":
            cost = (hp_max - hp) * (lvl + 1)
            s.out(["", "|07The old healer squints at you.",
                   f"|07\"|15You look awful. {hp_max - hp} hitpoints will cost {cost} gold.|07\""])
            if hp < hp_max and gold >= cost:
                s.ask("|07Heal? |08(|15Y|08/|15N|08) |15", "Y")
                gold -= cost
                hp = hp_max
                s.out("|10You feel much better.")
            else:
                s.out("|07\"|15Come back when you're bleeding.|07\"")
            L.pause(1.2)
        elif cmd == "F":
            if fights <= 0:
                s.out(["", "|07You are too tired to fight any more today."])
                L.pause(1.5)
                continue
            fights -= 1
            name, mhp, matk, mgold = r.choice(MONSTERS)
            mhp += lvl * 3
            s.out([CLS, "", "|02░▒▓|10 The Murkwood |02▓▒░", "",
                   r.choice(["|07Vines tangle your boots as you push deeper...",
                             "|07Something splashes in the black water nearby...",
                             "|07The trees groan. You smell rot."]), ""])
            L.rpause(1.0, 2.0)
            s.out([f"|12**|15 You have encountered a |14{name}|15! |12**", ""])
            while True:
                s.out(f"|07Your hitpoints: |15{hp}   |07{name}'s hitpoints: |15{mhp}")
                s.ask("|02(|10A|02)|07ttack  |02(|10S|02)|07tats  |02(|10R|02)|07un : |15", "A", fast=True)
                dmg = r.randint(lvl * 2, lvl * 5 + 6)
                if r.random() < 0.12:
                    s.out(f"|07You miss the {name} completely!")
                elif r.random() < 0.1:
                    dmg *= 2
                    s.out(f"|14**CRITICAL** |07You smash the {name} for |15{dmg}|07 damage!")
                    mhp -= dmg
                else:
                    s.out(f"|07You hit the {name} with your {weapon} for |15{dmg}|07 damage!")
                    mhp -= dmg
                if mhp <= 0:
                    g = mgold * (lvl + 1) + r.randint(0, 40)
                    e = mgold * 3 + r.randint(5, 30) * lvl
                    gold += g
                    exp += e
                    s.out(["", f"|10You have killed the {name}!",
                           f"|07You find |14{g}|07 gold and gain |15{e}|07 experience.", ""])
                    break
                hit = max(0, r.randint(matk // 2, matk + lvl) - lvl // 2)
                if hit == 0:
                    s.out(f"|07The {name} swings wildly and misses.")
                else:
                    hp = max(1, hp - hit)
                    s.out(f"|12The {name} hits you for |15{hit}|12 damage!")
                L.rpause(0.4, 0.9)
            L.rpause(1.5, 2.5)
            s.more()
        elif cmd == "Q":
            s.out(["", "|07You head home to rest in your hut.",
                   "|08Saving player file...", ""])
            L.rpause(1, 2)


def starlane(s):
    """A space-trading door."""
    L, r = s.line, s.rng
    sector = r.randint(1, 2000)
    holds = r.choice([40, 60, 75, 120])
    credits = r.randint(3000, 250000)
    turns = r.randint(80, 400)
    cargo = {"Ore": r.randint(0, holds // 2), "Organics": 0, "Equipment": 0}

    s.out([CLS] + logo("STARLANE", "ice") + [
        center("|11M E R C H A N T"),
        center("|08v3.4 ∙ (c) 1993 Deep Orbit Software ∙ Shareware - please register!"),
        "", gradient_rule(78, "ice", "═"), ""])
    L.rpause(1.5, 2.5)
    s.out([center(f"|07Pilot |11{s.user}|07, your ship |15{r.choice(['Rustbucket', 'Night Heron', 'Wanderer', 'Bad Credit', 'Second Mortgage'])}|07 awaits."),
           center(f"|07You have |15{turns}|07 turns remaining."), ""])
    s.more()

    def sector_view():
        warps = sorted(r.sample(range(1, 2001), r.randint(2, 5)))
        port_cls = r.choice(["BBS", "BSB", "SBB", "SSB", "BSS", None])
        s.out(["", f"|14Sector  |15: |11{sector} |07in |{r.choice([10, 13, 12])}"
               f"{r.choice(['uncharted space', 'The Federation', 'The Cygnus Reach', 'Rim Territory'])}"])
        if port_cls:
            s.out(f"|14Port    |15: |11{r.choice(['Bastion', 'Kessler', 'Nadir', 'Halcyon', 'Ozymand'])} "
                  f"{r.choice(['Station', 'Depot', 'Exchange'])}|07, Class |15{r.randint(1, 8)}|07 (|15{port_cls}|07)")
        if r.random() < 0.4:
            s.out(f"|14Ships   |15: |12{content.handle(r)}|07 [Corp {r.randint(1, 20)}] w/ |15{r.randint(10, 900)}|07 fighters")
        if r.random() < 0.3:
            s.out(f"|14Planets |15: |10{r.choice(['Vesta Prime', 'Lumen IV', 'Cold Harbor', 'Gravel'])}|07 (Class {r.choice('MKLOH')})")
        s.out("|14Warps to Sector(s) |15: |11" + " |08- |11".join(str(w) for w in warps))
        s.out("")
        return warps, port_cls

    def cmd_prompt():
        return (f"|05Command [|14TL|05=|1500:{r.randint(10, 59):02d}:{r.randint(0, 59):02d}|05]"
                f"|07:|05[|11{sector}|05] |07(|15?=Help|07)? : |15")

    for _ in range(r.randint(2, 4)):
        warps, port = sector_view()
        if port and r.random() < 0.7:
            s.step()
            s.ask(cmd_prompt(), "P", fast=True)
            trade(s, port, holds, cargo)
            credits += r.randint(-2000, 9000)
        nxt = r.choice(warps)
        s.step()
        s.ask(cmd_prompt(), str(nxt), fast=True)
        s.out(["", f"|07Warping to sector |15{nxt}|07..."])
        L.rpause(0.6, 1.2)
        sector = nxt
        turns -= 1
    s.step()
    s.ask(cmd_prompt(), "Q", fast=True)
    s.ask("|07Confirmed? |08(|15Y|08/|15N|08) |15", "Y")
    s.out(["", f"|07Credits: |15{credits:,}  |07Turns left: |15{turns}",
           "|08Saving game data... done.", ""])
    L.rpause(1, 2)


def trade(s, port, holds, cargo):
    L, r = s.line, s.rng
    goods = ["Fuel Ore", "Organics", "Equipment"]
    s.out(["", "|11<|15T|11> Trade at this port", "", "|09Docking...", ""])
    L.rpause(0.8, 1.5)
    rows = []
    for g, bs in zip(goods, port):
        qty = r.randint(400, 3500)
        pct = r.randint(30, 100)
        rows.append(f" |11{rpad(g, 11)}|07{'Buying' if bs == 'B' else 'Selling':>8}  "
                    f"|15{qty:>5}  |07{pct:>3}%  |15{cargo.get(g.split()[-1], 0):>4}")
    s.out([f"|09 Items     Status  Trading % of max OnBoard",
           "|01 ─────     ──────  ─────── ──────── ───────"]
          + rows + [""])
    L.rpause(1.5, 2.5)
    g = goods[port.index("S")] if "S" in port else goods[0]
    amt = holds - sum(cargo.values())
    if amt <= 0:
        s.out("|07Your holds are full.")
        return
    price = r.randint(18, 45) * amt
    s.ask(f"|07How many holds of |11{g}|07 do you want to buy [|15{amt}|07]? |15", str(amt))
    s.out(f"|07We'll sell them for |15{price:,}|07 credits.")
    offer = int(price * r.uniform(0.86, 0.95))
    for _ in range(r.randint(1, 3)):
        s.ask("|07Your offer [|15" + f"{price:,}" + "|07] ? |15", str(offer))
        resp = r.random()
        if resp < 0.35:
            s.out(f"|11\"We'll take it.\"")
            price = offer
            break
        elif resp < 0.8:
            price = int((price + offer) / 2)
            s.out(f"|07\"{r.choice(['Very funny.', 'You insult my mother.', 'Close, but no.'])}\" "
                  f"Our final offer is |15{price:,}|07.")
            offer = price
        else:
            s.out("|12\"Get lost, scum!\"")
            return
    cargo[g.split()[-1]] = cargo.get(g.split()[-1], 0) + amt
    s.out([f"|07You get |15{r.randint(1, 12)}|07 experience point(s).", ""])
    L.rpause(1, 2)
