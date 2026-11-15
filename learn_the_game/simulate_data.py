"""Erzeugt eine simulierte Partie (data.sim.js) im selben Format wie data.js.

Für die öffentliche Demo: keine Wisehockey-Daten. Spieler, Positionen, Statistiken und
Spielverlauf sind erfunden. Die Szenen sind so gebaut, dass die App dieselben Momente findet
(Bully, Icing, Stockschlag mit Powerplay-Tor, abgelenktes Tor, Abseits, hoher Stock, leeres Tor).

Aufruf:  python3 simulate_data.py   ->  data.sim.js
"""
import json
import math
import random
from pathlib import Path

HERE = Path(__file__).parent
R = random.Random(2026)
DIR = {'USC': 1, 'HCD': -1}          # USC (Heim) greift nach rechts an, HCD nach links
BLUE, GOAL = 7.14, 26.0
STEP, EMIT = 0.05, 0.25


def clamp(v, a, b):
    return max(a, min(b, v))


# ------------------------------------------------------------------ Kader (erfunden)
FIRST = {'HCD': ['Luca', 'Noah', 'Jan', 'Simon', 'Fabio', 'Marco', 'Nico', 'Reto', 'Elias', 'Joel', 'Livio', 'Dario',
                 'Yannick', 'Andrin', 'Cyrill', 'Mattia', 'Gian', 'Raphael', 'Timo', 'Lars', 'Silvan'],
         'USC': ['Jake', 'Ryan', 'Tyler', 'Connor', 'Owen', 'Liam', 'Mason', 'Caleb', 'Logan', 'Evan', 'Cole', 'Drew',
                 'Grant', 'Blake', 'Chase', 'Hunter', 'Nolan', 'Wyatt', 'Brady', 'Dylan', 'Grady']}
LAST = {'HCD': ['Brunold', 'Caflisch', 'Tscharner', 'Jenal', 'Padrutt', 'Casty', 'Juon', 'Mettier', 'Bivetti', 'Lanicca',
                'Cadonau', 'Zinsli', 'Sprecher', 'Buchli', 'Hartmann', 'Rageth', 'Valär', 'Disch', 'Flütsch', 'Gredig', 'Clavadetscher'],
        'USC': ['Holloway', 'Brennan', 'Whitaker', 'Calloway', 'Donnelly', 'Prescott', 'Langford', 'Ashby', 'Kerrigan', 'Mulroney',
                'Fairbanks', 'Thornton', 'Riordan', 'Halvorsen', 'Pemberton', 'Castellano', 'Garrity', 'Bramwell', 'Lockhart', 'Delaney', 'Vickers']}

PLAYERS = {}
ROSTER = {}
for tm, base in (('HCD', 1000), ('USC', 2000)):
    nums = R.sample([n for n in range(2, 99) if n not in (1, 30, 35)], 19)
    ids = []
    for k in range(21):
        pid = base + k + 1
        gk = k < 2
        no = (30, 1)[k] if (gk and tm == 'HCD') else (35, 31)[k] if gk else nums[k - 2]
        PLAYERS[pid] = {'n': f"{FIRST[tm][k]} {LAST[tm][k]}", 'no': no, 'tm': tm, 'gk': gk}
        ids.append(pid)
    # G, dann 3 Verteidigerpaare (LD, RD), dann 4 Sturmlinien (LW, C, RW), ein Ersatz
    ROSTER[tm] = {'G': ids[0], 'D': [ids[2:4], ids[4:6], ids[6:8]], 'F': [ids[8:11], ids[11:14], ids[14:17], ids[17:20]], 'X': ids[20]}


def unit(tm, f=0, d=0, goalie=True, extra=False):
    """Spieler einer Mannschaft auf dem Eis: {id: rolle}."""
    r = ROSTER[tm]
    on = {}
    if goalie:
        on[r['G']] = 'G'
    ld, rd = r['D'][d]
    on[ld], on[rd] = 'LD', 'RD'
    lw, c, rw = r['F'][f]
    on[lw], on[c], on[rw] = 'LW', 'C', 'RW'
    if extra:
        on[r['X']] = 'X'
    return on


def who(tm, role, f=0, d=0):
    r = ROSTER[tm]
    if role == 'G':
        return r['G']
    if role in ('LD', 'RD'):
        return r['D'][d][0 if role == 'LD' else 1]
    if role == 'X':
        return r['X']
    return r['F'][f][('LW', 'C', 'RW').index(role)]


# ------------------------------------------------------------------ Bewegung
def formation(tm, role, px, py, poss):
    d = DIR[tm]
    s = d                      # linke Seite in Angriffsrichtung
    gx = -d * GOAL             # eigene Torlinie
    if role == 'G':
        return gx + d * 1.0, clamp(py * 0.15, -0.9, 0.9)
    if poss == tm:
        depth = px * d
        if role in ('LD', 'RD'):
            xr = clamp(depth - 11, -22, 9.5)
            y = (5.5 if role == 'LD' else -5.5) * s + 0.25 * py
        elif role == 'C':
            xr = min(depth + 1.5, 23.5)
            y = 0.45 * py
        elif role == 'X':
            xr = min(depth + 4, 23.5)
            y = 0.3 * py - 1.5 * s
        else:
            xr = min(depth + 4, 23.5)
            y = (7.5 if role == 'LW' else -7.5) * s + 0.3 * py
        x = xr * d
    else:
        if role in ('LD', 'RD'):
            x = px + (gx - px) * 0.5
            y = 0.5 * py + (3.2 if role == 'LD' else -3.2) * s
        elif role == 'C':
            x = px + (gx - px) * 0.18
            y = 0.75 * py
        else:
            x = px + (gx - px) * 0.32
            y = 0.4 * py + (6 if role == 'LW' else -6) * s
        if abs(x) > 24:
            x = math.copysign(24, x)
    return clamp(x, -27.5, 27.5), clamp(y, -13.5, 13.5)


def faceoff_spot(tm, role, fx, fy):
    d = DIR[tm]
    s = d
    if role == 'G':
        return -d * GOAL + d * 1.0, 0.0
    off = {'C': (-1.0, 0), 'LW': (-1.6, 4.2 * s), 'RW': (-1.6, -4.2 * s), 'LD': (-7.5, 3.5 * s), 'RD': (-7.5, -3.5 * s), 'X': (-4, 0)}[role]
    x = clamp(fx + d * off[0], -25, 25)
    return x, clamp(fy + off[1], -13.5, 13.5)


class Segment:
    """Ein Spielabschnitt rund um eine Szene. Zeiten t relativ zum Start."""

    def __init__(self, p, c0, on, strength, puck, end, events=(), override=None, dead=(), faceoffs=(), leave=(), lead=0.0):
        if lead:
            # Vorlauf: der erste Puckträger fährt schon ein paar Sekunden vorher an
            sh = lambda t: t + lead
            x0, y0, car = puck[0][1], puck[0][2], puck[0][3]
            d = DIR[PLAYERS[car]['tm']] if car else 0
            puck = [(0.0, clamp(x0 - d * 3.2 * lead, -27, 27), y0, car)] + [(sh(w[0]), *w[1:]) for w in puck]
            events = [(sh(t), e) for t, e in events]
            override = {k: [(sh(t), x, y) for t, x, y in v] for k, v in (override or {}).items()}
            dead = [(sh(a), sh(b)) for a, b in dead]
            faceoffs = [(sh(t), x, y) for t, x, y in faceoffs]
            leave = {k: sh(t) for k, t in dict(leave).items()}
            strength = [strength[0]] + [(sh(x[0]), *x[1:]) for x in strength[1:]]
            c0, end = c0 - lead, end + lead
        self.p, self.c0, self.on, self.end = p, c0, on, end
        self.strength = strength          # [(t, st, sty, hg, ag)]
        self.puck = puck                  # [(t, x, y, carrier)]
        self.events = list(events)        # [(t, dict)]
        self.override = override or {}    # id -> [(t, x, y)]
        self.dead = list(dead)            # [(t0, t1)]  kein Puck im Spiel
        self.faceoffs = list(faceoffs)    # [(t, x, y)]
        self.leave = dict(leave)          # id -> t (verlässt das Eis)

    def team(self, pid):
        return PLAYERS[pid]['tm']

    def puck_at(self, t):
        P = self.puck
        if t <= P[0][0]:
            return P[0][1], P[0][2]
        for a, b in zip(P, P[1:]):
            if t <= b[0]:
                f = (t - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 1
                return a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f
        return P[-1][1], P[-1][2]

    def leg(self, t):
        P = self.puck
        for i, (a, b) in enumerate(zip(P, P[1:])):
            if a[0] <= t < b[0]:
                return i, a, b
        return len(P) - 1, P[-1], None

    def carrier(self, t):
        i, a, b = self.leg(t)
        if b is None:
            return a[3]
        return a[3] if a[3] is not None and a[3] == b[3] else None

    def poss(self, t):
        i, a, b = self.leg(t)
        for k in range(i, -1, -1):
            if self.puck[k][3] is not None:
                return self.team(self.puck[k][3])
        nxt = [w for w in self.puck if w[3] is not None]
        return self.team(nxt[0][3]) if nxt else None

    def strength_at(self, t):
        cur = self.strength[0]
        for s in self.strength:
            if s[0] <= t:
                cur = s
        return {'st': cur[1], 'sty': cur[2], 'hg': cur[3], 'ag': cur[4]}

    def in_dead(self, t):
        return any(a <= t < b for a, b in self.dead)

    def next_faceoff(self, t):
        for f in self.faceoffs:
            if f[0] >= t - 0.05:
                return f
        return None

    def run(self):
        ids = list(self.on)
        wob = {pid: (R.uniform(0, 6.3), R.uniform(0.35, 0.8), R.uniform(0.5, 1.2)) for pid in ids}
        pos, vel = {}, {pid: [0.0, 0.0] for pid in ids}
        # Startaufstellung
        if self.faceoffs and self.faceoffs[0][0] <= 0.01:
            fx, fy = self.faceoffs[0][1:]
            for pid in ids:
                pos[pid] = list(faceoff_spot(self.team(pid), self.on[pid], fx, fy))
        else:
            px, py = self.puck_at(0)
            for pid in ids:
                x, y = formation(self.team(pid), self.on[pid], px, py, self.poss(0))
                pos[pid] = [x + R.uniform(-1, 1), y + R.uniform(-1, 1)]
        out = []
        t, next_emit = 0.0, 0.0
        while t <= self.end + 1e-6:
            px, py = self.puck_at(t)
            poss = self.poss(t)
            car = self.carrier(t)
            i, a, b = self.leg(t)
            receiver = b[3] if (b is not None and b[3] is not None and b[3] != a[3]) else None
            # Annahme: Empfänger fährt schon kurz vor dem Pass zum Zielpunkt
            soon = None
            for w0, w1 in zip(self.puck, self.puck[1:]):
                if w1[3] is not None and w1[3] != w0[3] and w0[0] - 1.2 <= t < w1[0]:
                    soon = (w1[3], w1[1], w1[2])
                    break
            dead = self.in_dead(t)
            fo = self.next_faceoff(t) if dead else None
            for pid in ids:
                if pid in self.leave and t >= self.leave[pid]:
                    continue
                tm, role = self.team(pid), self.on[pid]
                vmax, tau = 7.2, 0.7
                if pid == car:
                    _, a2, b2 = self.leg(t)
                    if b2 is not None:
                        dx, dy = b2[1] - a2[1], b2[2] - a2[2]
                    else:
                        dx, dy = DIR[tm], 0
                    n = math.hypot(dx, dy) or 1
                    pos[pid] = [px - 0.55 * dx / n, py - 0.55 * dy / n]
                    vel[pid] = [0.0, 0.0]
                    continue
                ov = self.override.get(pid)
                if ov and ov[0][0] <= t <= ov[-1][0]:
                    for o0, o1 in zip(ov, ov[1:]):
                        if t <= o1[0]:
                            f = (t - o0[0]) / (o1[0] - o0[0]) if o1[0] > o0[0] else 1
                            tx, ty = o0[1] + (o1[1] - o0[1]) * f, o0[2] + (o1[2] - o0[2]) * f
                            break
                    vmax, tau = 9.0, 0.25
                elif soon and soon[0] == pid:
                    tx, ty = soon[1] - 0.5 * DIR[tm], soon[2]
                    vmax, tau = 8.0, 0.35
                elif fo is not None:
                    tx, ty = faceoff_spot(tm, role, fo[1], fo[2])
                    vmax, tau = 6.0, 0.5
                else:
                    tx, ty = formation(tm, role, px, py, poss)
                    ph, fr, am = wob[pid]
                    if role != 'G':
                        tx += am * math.sin(ph + fr * t)
                        ty += am * math.cos(ph * 1.3 + fr * 0.8 * t)
                    if role == 'G':
                        vmax, tau = 4.0, 0.3
                vx, vy = (tx - pos[pid][0]) / tau, (ty - pos[pid][1]) / tau
                sp = math.hypot(vx, vy)
                if sp > vmax:
                    vx, vy = vx / sp * vmax, vy / sp * vmax
                k = min(1, STEP / 0.3)
                vel[pid][0] += (vx - vel[pid][0]) * k
                vel[pid][1] += (vy - vel[pid][1]) * k
                pos[pid][0] += vel[pid][0] * STEP
                pos[pid][1] += vel[pid][1] * STEP
            # Abstand halten
            act = [q for q in ids if not (q in self.leave and t >= self.leave[q])]
            for x1 in range(len(act)):
                for x2 in range(x1 + 1, len(act)):
                    p1, p2 = pos[act[x1]], pos[act[x2]]
                    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
                    dd = math.hypot(dx, dy)
                    if 0 < dd < 1.5:
                        push = (1.5 - dd) * 0.25
                        fixed1 = act[x1] == car or self.on[act[x1]] == 'G'
                        fixed2 = act[x2] == car or self.on[act[x2]] == 'G'
                        if not fixed1:
                            p1[0] -= dx / dd * push; p1[1] -= dy / dd * push
                        if not fixed2:
                            p2[0] += dx / dd * push; p2[1] += dy / dd * push
            for q in act:
                pos[q][0] = clamp(pos[q][0], -29, 29)
                pos[q][1] = clamp(pos[q][1], -14.3, 14.3)
            if t >= next_emit - 1e-9:
                e = {'t': round(t, 2), 'ty': 'PuckControl',
                     'on': [[q, round(pos[q][0], 1), round(pos[q][1], 1)] for q in act]}
                if not dead:
                    nx, ny = self.puck_at(t + EMIT)
                    e['s'] = [round(px, 1), round(py, 1)]
                    e['e'] = [round(nx, 1), round(ny, 1)]
                    e['pcs'] = 'Loose' if car is None else ('HomeControl' if self.team(car) == 'USC' else 'AwayControl')
                out.append(e)
                next_emit += EMIT
            t += STEP
        # Pässe und Blaue-Linie-Überquerungen aus dem Puckweg
        P = self.puck
        for w0, w1 in zip(P, P[1:]):
            if w0[3] and w1[3] and w0[3] != w1[3] and self.team(w0[3]) == self.team(w1[3]) and not any(
                    abs(ev[0] - w0[0]) < 0.02 and ev[1]['ty'] in ('Shot', 'Dump', 'Pass') for ev in self.events):
                self.events.append((w0[0], {'ty': 'Pass', 'pl': w0[3], 'tm': self.team(w0[3]), 'pl2': w1[3],
                                            's': [w0[1], w0[2]], 'e': [w1[1], w1[2]], 'res': 'Successful'}))
            if w0[3] and w0[3] == w1[3]:
                tm = self.team(w0[3])
                for bl in (-BLUE, BLUE):
                    if (w0[1] - bl) * (w1[1] - bl) < 0:
                        f = (bl - w0[1]) / (w1[1] - w0[1])
                        tc = w0[0] + f * (w1[0] - w0[0])
                        towards = (w1[1] - w0[1]) * DIR[tm] > 0
                        self.events.append((round(tc, 2), {'ty': 'BluelineCrossing', 'pl': w0[3], 'tm': tm,
                                                           's': [round(bl, 1), round(w0[2] + f * (w1[2] - w0[2]), 1)],
                                                           'bld': 'TowardsOpponent' if towards else 'TowardsHome',
                                                           'blr': 'PossessionMaintained'}))
        for tt, ev in self.events:
            e = {'t': round(tt, 2)}
            e.update(ev)
            if ev['ty'] not in ('StoppageOfPlay', 'Penalty'):
                for k2, v in self.strength_at(tt).items():
                    e.setdefault(k2, v)
            out.append(e)
        return out


# ------------------------------------------------------------------ Spielverlauf
def H(role, f=0, d=0):
    return who('HCD', role, f, d)


def U(role, f=0, d=0):
    return who('USC', role, f, d)


FULL = ('5v5', 'FullStrength', True, True)
SEGS = []

# 1) Eröffnungsbully, 1. Drittel 00:00
SEGS.append(Segment(1, 0, {**unit('USC', 0, 0), **unit('HCD', 0, 0)}, [(0, *FULL)], [
    (0.0, 0.0, 0.0, H('C')), (0.25, 0.4, -0.3, H('C')), (1.0, 6.0, -3.4, H('LD')), (2.4, 4.5, -5.0, H('LD')),
    (3.3, -2.5, -8.5, H('LW')), (5.4, -9.5, -9.0, H('LW')), (6.4, -13.5, -7.5, H('LW')), (7.4, -19.0, -4.0, H('C')),
    (8.6, -20.5, -1.0, H('C'))], end=8.6,
    events=[(0.0, {'ty': 'Faceoff', 'pl': H('C'), 'tm': 'HCD', 'pl2': U('C'), 's': [0.0, 0.0]})],
    faceoffs=[(0.0, 0.0, 0.0)]))

# 2) Icing USC, 1. Drittel ~03:00
SEGS.append(Segment(1, 178, {**unit('USC', 1, 1), **unit('HCD', 1, 1)}, [(0, *FULL)], [
    (0.0, -10.0, 5.0, H('C', 1)), (1.6, -15.0, 7.5, H('C', 1)), (2.6, -21.0, -5.5, H('RW', 1)), (3.6, -22.5, -3.5, H('RW', 1)),
    (4.3, -19.0, -0.5, U('LD', 1, 1)), (5.6, -16.5, 2.5, U('LD', 1, 1)), (7.2, 26.0, -1.2, None), (7.5, 29.2, -3.0, None),
    (8.4, 28.6, -6.5, None), (9.4, 28.3, -7.2, None)], end=9.8,
    events=[(3.6, {'ty': 'Pass', 'pl': H('RW', 1), 'tm': 'HCD', 'pl2': U('LD', 1, 1), 's': [-22.5, -3.5], 'e': [-19.0, -0.5], 'res': 'Intercepted'}),
            (5.6, {'ty': 'Dump', 'pl': U('LD', 1, 1), 'tm': 'USC', 's': [-16.5, 2.5], 'e': [29.2, -3.0], 'dres': 'Icing'}),
            (9.4, {'ty': 'StoppageOfPlay', 'stop': 'Icing'})],
    override={H('RD', 1, 1): [(5.8, 20.0, -4.0), (8.6, 26.5, -6.0), (9.8, 27.2, -6.4)]}, lead=2.0))

# 3) Stockschlag USC (angezeigte Strafe) und Powerplay-Tor HCD, 1. Drittel ~11:10
SL = U('RW', 2, 2)
PP = ('4v5', 'AwayPowerplay', True, True)
SEGS.append(Segment(1, 664, {**unit('USC', 2, 2), **unit('HCD', 0, 0)}, [(0, *FULL), (9.6, *PP)], [
    (0.0, 6.0, 3.0, H('C')), (1.8, -6.5, 4.0, H('C')), (2.8, -12.0, 6.0, H('C')), (3.6, -17.0, -6.0, H('LW')),
    (5.0, -21.0, -8.5, H('LW')), (6.0, -11.0, -5.5, H('LD')), (6.8, -11.5, -2.0, H('LD')), (7.6, -18.0, 5.5, H('RW')),
    (8.3, -19.0, 4.5, H('RW')), (8.55, -25.0, 0.6, None), (8.9, -24.0, 2.5, None), (9.45, -23.0, 3.2, SL),
    (9.6, -22.6, 3.5, SL),
    (12.0, -20.0, 7.0, H('C')), (12.2, -20.6, 6.6, H('C')), (12.8, -12.0, 7.5, H('RD')), (13.3, -12.4, 6.0, H('RD')),
    (13.9, -20.5, -5.5, H('LW')), (14.15, -26.3, 0.4, None), (14.3, -26.4, 0.4, None)], end=15.2,
    events=[(8.3, {'ty': 'Shot', 'pl': H('RW'), 'tm': 'HCD', 's': [-19.0, 4.5], 'e': [-25.0, 0.6], 'res': 'Saved', 'xg': 0.07, 'spd': 112.0}),
            (9.6, {'ty': 'Penalty', 'pl': SL, 'tm': 'USC', 'pen': 'Slashing'}),
            (9.75, {'ty': 'StoppageOfPlay', 'stop': 'Penalty'}),
            (12.0, {'ty': 'Faceoff', 'pl': H('C'), 'tm': 'HCD', 'pl2': U('C', 2, 2), 's': [-20.0, 7.0]}),
            (13.9, {'ty': 'Shot', 'pl': H('LW'), 'tm': 'HCD', 's': [-20.5, -5.5], 'e': [-26.3, 0.4], 'res': 'Goal', 'xg': 0.14, 'spd': 124.0}),
            (14.3, {'ty': 'Goal', 'pl': H('LW'), 'tm': 'HCD', 'a1': H('RD'), 'a2': H('C')}),
            (14.3, {'ty': 'StoppageOfPlay', 'stop': 'Goal'})],
    override={SL: [(2.4, -9.0, 2.0), (3.8, -15.5, -4.5), (4.9, -19.8, -7.4), (5.6, -19.5, -6.5), (8.6, -21.0, 2.0), (9.45, -22.8, 3.0)]},
    dead=[(9.75, 12.0)], faceoffs=[(12.0, -20.0, 7.0)], leave={SL: 10.4}))

# 4) Abgelenktes Tor USC, 1. Drittel ~14:20
SEGS.append(Segment(1, 855, {**unit('USC', 0, 0), **unit('HCD', 1, 1)}, [(0, *FULL)], [
    (0.0, -16.0, -4.0, U('RD')), (2.5, -10.0, -6.0, U('RD')), (3.3, -1.0, -2.0, U('C')), (4.8, 6.0, -1.0, U('C')),
    (5.6, 11.0, -2.0, U('C')), (6.4, 18.0, -9.0, U('RW')), (7.8, 22.0, -10.0, U('RW')), (8.8, 11.5, 7.5, U('LD')),
    (9.8, 13.0, 5.0, U('LD')), (10.35, 24.3, 0.8, U('C')), (10.5, 26.4, 0.3, None)], end=11.4,
    events=[(10.35, {'ty': 'Shot', 'pl': U('C'), 'tm': 'USC', 's': [24.3, 0.8], 'e': [26.4, 0.3], 'res': 'Goal', 'xg': 0.21, 'spd': 0.0}),
            (10.5, {'ty': 'Goal', 'pl': U('C'), 'tm': 'USC', 'a1': U('LD'), 'a2': U('RW')}),
            (10.5, {'ty': 'StoppageOfPlay', 'stop': 'Goal'})],
    override={U('C'): [(8.4, 21.0, 1.0), (9.6, 23.8, 1.2), (10.3, 24.0, 0.9)]}, lead=3.0))

# 5) Abseits HCD, 1. Drittel ~16:00
OFF = H('LW', 2, 2)
SEGS.append(Segment(1, 952, {**unit('USC', 3, 1), **unit('HCD', 2, 2)}, [(0, *FULL)], [
    (0.0, 20.0, -6.0, H('LD', 2, 2)), (1.8, 16.0, -3.0, H('LD', 2, 2)), (2.6, 15.0, 6.0, H('RD', 2, 2)), (4.0, 11.0, 6.0, H('RD', 2, 2)),
    (4.9, 2.0, -3.0, H('C', 2, 2)), (7.3, -8.5, -3.0, H('C', 2, 2)), (7.8, -10.0, -3.2, H('C', 2, 2))], end=8.4,
    events=[(8.0, {'ty': 'StoppageOfPlay', 'stop': 'Offside'})],
    override={OFF: [(4.6, -2.0, -8.0), (6.2, -10.5, -9.0), (7.4, -12.5, -8.0), (8.4, -12.0, -7.5)]}, lead=3.0))

# 6) HCD-Tor 2:1 ... ein paar Tore, die man nicht als Moment sieht
def goal_seg(p, c0, tm, f, d, ofx, scorer_role, a1_role, a2_role, xg, spd):
    o = 'HCD' if tm == 'USC' else 'USC'
    s = DIR[tm]
    W = lambda role: who(tm, role, f, d)
    return Segment(p, c0, {**unit(tm, f, d), **unit(o, (f + 1) % 4, (d + 1) % 3)}, [(0, *FULL)], [
        (0.0, s * -2.0, 3.0 * s, W('C')), (1.6, s * 9.0, 3.5 * s, W('C')), (2.4, s * 18.0, 8.0 * s, W(a2_role)),
        (3.6, s * 21.0, 6.0 * s, W(a2_role)), (4.4, s * 13.0, -5.0 * s, W(a1_role)), (5.2, s * 19.5, -2.5 * s, W(scorer_role)),
        (5.5, s * 26.3, ofx, None), (5.6, s * 26.4, ofx, None)], end=6.4,
        events=[(5.2, {'ty': 'Shot', 'pl': W(scorer_role), 'tm': tm, 's': [s * 19.5, -2.5 * s], 'e': [s * 26.3, ofx], 'res': 'Goal', 'xg': xg, 'spd': spd}),
                (5.6, {'ty': 'Goal', 'pl': W(scorer_role), 'tm': tm, 'a1': W(a1_role), 'a2': W(a2_role)}),
                (5.6, {'ty': 'StoppageOfPlay', 'stop': 'Goal'})])


SEGS.append(Segment(1, 1192, {**unit('USC', 1, 2), **unit('HCD', 3, 1)}, [(0, *FULL)], [
    (0.0, -3.0, 4.0, H('C', 3, 1)), (4.0, -6.0, 6.0, H('C', 3, 1)), (5.0, 10.0, 1.0, None), (8.0, 14.0, 0.0, None)], end=8.0,
    events=[(5.0, {'ty': 'Dump', 'pl': H('C', 3, 1), 'tm': 'HCD', 's': [-6.0, 6.0], 'e': [10.0, 1.0], 'dres': 'Possession'}),
            (8.0, {'ty': 'StoppageOfPlay', 'stop': 'PeriodEnd'})]))
SEGS.append(goal_seg(2, 418, 'HCD', 1, 1, 0.5, 'C', 'RW', 'LD', 0.18, 131.0))
SEGS.append(goal_seg(2, 903, 'USC', 2, 2, -0.4, 'RW', 'C', 'LW', 0.11, 118.0))

# 7) Hoher Stock USC, 2. Drittel ~19:40
HS, HV = U('LD', 1, 0), H('C', 1, 0)
SEGS.append(Segment(2, 1178, {**unit('USC', 1, 0), **unit('HCD', 1, 0)}, [(0, *FULL)], [
    (0.0, 4.0, -2.0, H('LD', 1, 0)), (1.5, 1.0, -4.0, H('LD', 1, 0)), (2.3, -8.5, -8.0, H('LW', 1, 0)), (3.8, -15.0, -9.5, H('LW', 1, 0)),
    (4.6, -20.0, 4.0, HV), (6.2, -24.0, 8.5, HV), (7.4, -25.5, 10.0, HV), (8.4, -23.5, 11.5, HV), (9.0, -23.0, 11.6, HV)], end=10.2,
    events=[(9.0, {'ty': 'Penalty', 'pl': HS, 'tm': 'USC', 'pen': 'HighSticking'}),
            (9.6, {'ty': 'StoppageOfPlay', 'stop': 'Penalty'})],
    override={HS: [(3.6, -21.0, 1.0), (5.4, -22.5, 6.0), (7.2, -24.2, 9.0), (8.6, -23.2, 10.6), (10.2, -22.8, 10.4)]},
    dead=[(9.6, 10.3)]))
SEGS.append(Segment(2, 1192, {**unit('USC', 2, 1), **unit('HCD', 2, 2)}, [(0, '4v5', 'AwayPowerplay', True, True)], [
    (0.0, -12.0, 6.0, H('RD', 2, 2)), (4.0, -13.0, 2.0, H('RD', 2, 2)), (5.0, -20.0, -6.0, H('LW', 2, 2)), (8.0, -22.0, -5.0, H('LW', 2, 2))], end=8.0,
    events=[(8.0, {'ty': 'StoppageOfPlay', 'stop': 'PeriodEnd'})]))

# 8) Tor HCD 1:3 im letzten Drittel
SEGS.append(goal_seg(3, 545, 'HCD', 0, 0, -0.3, 'RW', 'C', 'RD', 0.24, 109.0))

# 9) Leeres Tor: USC ohne Goalie, HCD trifft aus der eigenen Hälfte, 3. Drittel ~18:50
EN = ('6v5', 'EqualStrength', False, True)
SEGS.append(Segment(3, 1120, {**unit('USC', 0, 0, goalie=False, extra=True), **unit('HCD', 3, 2)}, [(0, *EN)], [
    (0.0, 9.0, 7.0, U('LD')), (2.0, 11.5, 6.5, U('LD')), (2.9, 20.0, -8.5, U('RW')), (4.6, 23.0, -6.5, U('RW')),
    (5.5, 13.0, -6.0, U('RD')), (6.4, 12.5, -2.0, U('RD')), (7.3, 20.5, 6.5, U('LW')), (8.6, 22.0, 4.0, U('LW')),
    (9.4, 19.0, 2.0, U('C')), (10.1, 19.5, 1.0, U('C')), (10.3, 21.5, 0.6, None), (10.8, 17.0, -2.5, None),
    (11.3, 15.0, -3.2, H('LW', 3, 2)), (12.2, 11.5, -2.0, H('LW', 3, 2)), (13.8, -26.4, 0.2, None), (13.9, -26.4, 0.2, None)], end=14.8,
    events=[(10.1, {'ty': 'Shot', 'pl': U('C'), 'tm': 'USC', 's': [19.5, 1.0], 'e': [21.5, 0.6], 'res': 'Blocked', 'xg': 0.09, 'spd': 98.0}),
            (12.2, {'ty': 'Shot', 'pl': H('LW', 3, 2), 'tm': 'HCD', 's': [11.5, -2.0], 'e': [-26.4, 0.2], 'res': 'Goal', 'spd': 92.0}),
            (13.9, {'ty': 'Goal', 'pl': H('LW', 3, 2), 'tm': 'HCD', 'a1': H('RD', 3, 2)}),
            (13.9, {'ty': 'StoppageOfPlay', 'stop': 'Goal'})],
    override={H('RD', 3, 2): [(9.0, 22.5, 2.5), (10.2, 21.8, 0.9), (11.2, 20.0, -1.0)]}, lead=5.5))

# 10) Schlusspfiff
SEGS.append(Segment(3, 1190, {**unit('USC', 1, 1), **unit('HCD', 0, 1)}, [(0, *FULL)], [
    (0.0, 14.0, 5.0, H('RD', 0, 1)), (2.4, 9.0, 6.0, H('RD', 0, 1)), (3.2, 2.0, -4.0, H('C', 0, 1)), (6.0, -3.0, -5.0, H('C', 0, 1)),
    (7.0, -4.0, 2.0, H('RW', 0, 1)), (10.0, -9.0, 4.0, H('RW', 0, 1))], end=10.0,
    events=[(10.0, {'ty': 'StoppageOfPlay', 'stop': 'PeriodEnd'})]))


# ------------------------------------------------------------------ Zusammensetzen
PERIOD_G = {1: 0.0, 2: 1225.0, 3: 2455.0}
ORDER = {'Faceoff': 0, 'Penalty': 3, 'Shot': 1, 'Goal': 4, 'StoppageOfPlay': 5}
events = []
for sg in SEGS:
    for e in sg.run():
        t = e.pop('t')
        clock = min(1200.0, sg.c0 + t)
        e = {'g': round(PERIOD_G[sg.p] + clock, 2), 'p': sg.p, 'c': int(clock), **e}
        events.append(e)
events.sort(key=lambda e: (e['g'], ORDER.get(e['ty'], 2)))
# Das erste Event muss das Eröffnungsbully sein
fo = next(i for i, e in enumerate(events) if e['ty'] == 'Faceoff')
events.insert(0, events.pop(fo))

# Spielerstatistik (erfunden, zu den Toren passend)
for pid, p in PLAYERS.items():
    if p['gk']:
        continue
    p.update({'spd': round(R.uniform(29.5, 37.5), 1), 'sht': round(R.uniform(70, 152), 1), 'dist': R.randint(2600, 5600),
              'toi': R.randint(620, 1450), 'g': 0, 'a': 0, 's': R.randint(0, 5), 'xg': round(R.uniform(0, 0.5), 3),
              'shf': R.randint(18, 30), 'avgs': round(R.uniform(38, 49), 1), 'fow': 0, 'fo': 0,
              'pas': R.randint(5, 24), 'pasall': 0, 'pim': 0, 'bks': R.randint(0, 3), 'pcw': R.randint(1, 9), 'pc': 0})
    p['pasall'] = p['pas'] + R.randint(2, 7)
    p['pc'] = p['pcw'] + R.randint(0, 4)
for e in events:
    if e['ty'] == 'Goal':
        PLAYERS[e['pl']]['g'] += 1
        for k in ('a1', 'a2'):
            if e.get(k):
                PLAYERS[e[k]]['a'] += 1
    if e['ty'] == 'Penalty':
        PLAYERS[e['pl']]['pim'] += 2

data = {
    'sim': True,
    'match': {'date': 'Simulation', 'title': 'Simulierte Partie', 'home': 'USC', 'away': 'HCD'},
    'teams': {'HCD': {'name': 'HC Davos', 'short': 'HCD'}, 'USC': {'name': 'U.S. Collegiate Selects', 'short': 'USC'}},
    'attack': {str(p): {'HCD': -1, 'USC': 1} for p in (1, 2, 3)},
    'players': {str(k): v for k, v in PLAYERS.items()},
    'events': events,
}
out = HERE / 'data.sim.js'
out.write_text('window.MATCH_DATA = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';\n', encoding='utf-8')
goals = [(e['tm'], e['p'], e['c']) for e in events if e['ty'] == 'Goal']
print(f"{out.name}: {out.stat().st_size / 1024:.0f} KB, {len(events)} Events, Tore: {goals}")
