"""Bereitet die Wisehockey-Daten des Finals (HCD - USC, 31.12.2025) als kompaktes JSON für den Prototyp auf.

Aufruf:  python3 build_data.py   (danach python3 bundle.py)
Ergebnis: data.js (wird von index.html geladen)
"""
import json
import os
import math
import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
# Daten liegen wie im übrigen Repo unter data/match_data (nicht im Git, siehe .gitignore).
# Anderer Ort: HOCKEY_DATA=/pfad/zum/ordner python3 build_data.py
SRC = Path(os.environ.get("HOCKEY_DATA", HERE.parent / "data" / "match_data"))
EVENTS = SRC / "U.S. Collegiate Selects_HC Davos_Wisehockey_Match_Events_31_12_2025.csv"
STATS = SRC / "U.S. Collegiate Selects_HC Davos_Wisehockey_Match_Statistics_31_12_2025 All.csv"

TEAM = {"Home": "USC", "Away": "HCD"}
MAX_GAP = 6.0       # längere Pausen (Unterbrüche, Drittelspausen) ...
GAP_REPLACE = 2.0   # ... werden für die Wiedergabe auf 2 s verkürzt


def xy(v):
    if not isinstance(v, str):
        return None
    a, b = v.split(",")
    return [round(float(a), 1), round(float(b), 1)]


def val(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return v


def main():
    e = pd.read_csv(EVENTS, encoding="utf-8-sig", low_memory=False)
    s = pd.read_csv(STATS, encoding="utf-8-sig")

    players = {}
    for i in range(1, 13):
        sub = e[[f"StartPlayerId{i}", f"StartPlayerName{i}", f"StartPlayerTeam{i}"]].dropna()
        for pid, name, team in sub.itertuples(index=False):
            players.setdefault(int(pid), (name, team))
    for pid, name, team in e[["EventPrimaryPlayerId", "EventPrimaryPlayerName", "EventPrimaryTeam"]].dropna().itertuples(index=False):
        players.setdefault(int(pid), (name, team))

    stats_by_key = {(r.Team, int(r.Jersey)): r for r in s.itertuples(index=False)}
    team_long = {"HCD": "HC Davos", "USC": "U.S. Collegiate Selects"}

    pl_out = {}
    for pid, (name, team) in players.items():
        m = re.match(r"#(\d+)\s+(.*)", name)
        num, full = (int(m.group(1)), m.group(2)) if m else (0, name)
        code = TEAM[team]
        st = stats_by_key.get((team_long[code], num))
        p = {"n": full, "no": num, "tm": code, "gk": st is None}
        if st is not None:
            p.update({
                "spd": float(st[s.columns.get_loc("SPD TOP (km/h)")]),
                "sht": float(st[s.columns.get_loc("S TOP (km/h)")]),
                "dist": int(st[s.columns.get_loc("Dist (m)")]),
                "toi": int(st[s.columns.get_loc("TOI (s)")]),
                "g": int(st.G), "a": int(st.A),
                "s": int(st.S),
                "xg": float(st.xGsum),
                "shf": int(st.Shifts),
                "avgs": float(st[s.columns.get_loc("AVG Shift (s)")]),
                "fow": int(st.FOW), "fo": int(st[s.columns.get_loc("No. FO")]),
                "pas": int(st.Passes), "pasall": int(st[s.columns.get_loc("All passes")]),
                "pim": int(st.PIM), "bks": int(st.BKS),
                "pcw": int(st.PCW), "pc": int(st[s.columns.get_loc("No. PC")]),
            })
        pl_out[pid] = p

    t0 = e.Timestamp.iloc[0]
    g = 0.0
    prev = None
    ev_out = []
    for r in e.itertuples(index=False):
        ts = r.Timestamp / 1000.0
        if prev is not None:
            dt = ts - prev
            g += GAP_REPLACE if dt > MAX_GAP else dt
        prev = ts
        ev = {"g": round(g, 2), "p": int(r.Period), "c": int(r.MatchClock), "ty": r.EventType}
        if val(r.EventPrimaryPlayerId) is not None:
            ev["pl"] = int(r.EventPrimaryPlayerId)
        if isinstance(r.EventPrimaryTeam, str):
            ev["tm"] = TEAM[r.EventPrimaryTeam]
        if val(r.EventSecondaryPlayerId) is not None:
            ev["pl2"] = int(r.EventSecondaryPlayerId)
        for key, col in (("s", r.EventStartCoordinate), ("e", r.EventEndCoordinate)):
            c = xy(col)
            if c:
                ev[key] = c
        if isinstance(r.TeamStrength, str):
            ev["st"] = r.TeamStrength
        if isinstance(r.TeamStrengthType, str):
            ev["sty"] = r.TeamStrengthType
        if val(r.HomeGoalieOnIce) is not None:
            ev["hg"] = bool(r.HomeGoalieOnIce)
            ev["ag"] = bool(r.AwayGoalieOnIce)
        extra = {
            "res": r.ShotResult if r.EventType == "Shot" else (r.PassResult if r.EventType == "Pass" else None),
            "spd": r.ShotSpeed if r.EventType == "Shot" else None,
            "xg": r.ShotXG,
            "blr": r.BluelineCrossingResult,
            "bld": r.BluelineCrossingDirection,
            "pcs": r.PuckControlState,
            "stop": r.StoppageOfPlayReason,
            "pen": r.PenaltyReason,
            "dres": r.DumpResult,
            "clr": r.ClearType,
        }
        for k, v in extra.items():
            v = val(v)
            if v is not None:
                ev[k] = round(float(v), 3) if isinstance(v, float) else v
        if r.EventType == "Goal":
            for k, col in (("a1", r.GoalAssist1Id), ("a2", r.GoalAssist2Id)):
                if val(col) is not None:
                    ev[k] = int(col)
        on = []
        for i in range(1, 13):
            pid = getattr(r, f"StartPlayerId{i}")
            c = xy(getattr(r, f"StartPlayerCoordinates{i}"))
            if val(pid) is not None and c:
                on.append([int(pid), c[0], c[1]])
        if on:
            ev["on"] = on
        ev_out.append(ev)

    # Angriffsrichtung pro Drittel und Team (Vorzeichen des Ziel-Tors auf der x-Achse)
    shots = e[e.EventType == "Shot"].copy()
    shots["x"] = shots.EventStartCoordinate.str.split(",").str[0].astype(float)
    attack = {}
    for (per, team), x in shots.groupby(["Period", "EventPrimaryTeam"]).x.mean().items():
        attack.setdefault(str(per), {})[TEAM[team]] = 1 if x > 0 else -1

    data = {
        "match": {"date": "31.12.2025", "title": "Final Spengler Cup 2025", "home": "USC", "away": "HCD"},
        "teams": {
            "HCD": {"name": "HC Davos", "short": "HCD"},
            "USC": {"name": "U.S. Collegiate Selects", "short": "USC"},
        },
        "attack": attack,
        "players": pl_out,
        "events": ev_out,
    }
    out = HERE / "data.js"
    out.write_text("window.MATCH_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"{len(ev_out)} Events, {len(pl_out)} Spieler, {out.stat().st_size/1024:.0f} KB -> {out}")
    print("Angriff:", attack)


if __name__ == "__main__":
    main()
