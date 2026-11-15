"""Baut die öffentliche Demo (ohne Wisehockey-Daten) nach outputs/public-demo/.

- Learn the Game läuft mit der simulierten Partie (learn_the_game/simulate_data.py).
- Die Be-a-Pro-Clips aus der lokalen Aufnahme bleiben draussen (sie zeigen echte Daten).
  Stattdessen gibt es eine kleine Pass-Vorschau auf der simulierten Partie.

Aufruf:  python3 website/build_public.py
"""
import json
import os
import math
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEARN = ROOT / "learn_the_game"
# VARIANT=video: Variante nur fürs Demovideo (lokal, nicht veröffentlichen): echte Daten, ohne Vorschau-Hinweise
VIDEO = os.environ.get("VARIANT") == "video"
OUT = ROOT / "outputs" / ("video-demo" if VIDEO else "public-demo")
DATA = LEARN / ("data.js" if VIDEO else "data.sim.js")

subprocess.run([sys.executable, str(LEARN / "simulate_data.py")], check=True)
if OUT.exists():
    shutil.rmtree(OUT)
(OUT / "app").mkdir(parents=True)
(OUT / "shared").mkdir()

# ---------------------------------------------------------------- App mit simulierten Daten
html = (LEARN / "index.html").read_text(encoding="utf-8")
for name, src in (("../shared/hv-account.js", ROOT / "shared/hv-account.js"), ("data.js", DATA), ("app.js", LEARN / "app.js")):
    js = src.read_text(encoding="utf-8").replace("</script", "<\\/script")
    tag = f'<script src="{name}"></script>'
    assert tag in html, tag
    html = html.replace(tag, f"<script>\n{js}\n</script>")
assert VIDEO or "MATCH_DATA = {\"match\":{\"date\":\"31.12.2025\"" not in html
assert '<meta charset="utf-8">' in html
html = html.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n<meta name="robots" content="noindex, nofollow">', 1)
(OUT / "app" / "index.html").write_text(html, encoding="utf-8")
shutil.copy(ROOT / "shared/hv-account.js", OUT / "shared/hv-account.js")

# ---------------------------------------------------------------- Szenen für Be a Pro (Replay und Game)
sim = DATA.read_text(encoding="utf-8")
D = json.loads(sim[sim.index("{"):sim.rindex("}") + 1])
EV = D["events"]
PL = D["players"]
DIRS = {"USC": 1, "HCD": -1}
ON = [e for e in EV if "on" in e]
goals = [e for e in EV if e["ty"] == "Goal"]


def shot_for(goal):
    return [e for e in EV if e["ty"] == "Shot" and e.get("res") == "Goal" and 0 <= goal["g"] - e["g"] < 8][-1]


def pos_at(g):
    """Positionen aller Spieler zur Zeit g (linear zwischen zwei Tracking-Events)."""
    a = [e for e in ON if e["g"] <= g][-1]
    later = [e for e in ON if e["g"] > g]
    b = later[0] if later else a
    f = (g - a["g"]) / (b["g"] - a["g"]) if b["g"] > a["g"] else 0
    bm = {pid: (x, y) for pid, x, y in b["on"]}
    return {pid: (x + (bm.get(pid, (x, y))[0] - x) * f, y + (bm.get(pid, (x, y))[1] - y) * f) for pid, x, y in a["on"]}


def smooth(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def scene(goal, start, end, offset_at=None):
    shot = shot_for(goal)
    frames = []
    for e in ON:
        if start <= e["g"] <= end:
            t = e["g"] - start
            row = []
            for pid, x, y in e["on"]:
                ox, oy = offset_at(t, pid) if offset_at else (0, 0)
                row.append([pid, round(x + ox, 2), round(y + oy, 2)])
            frames.append([round(t, 2), row])
    puck = [[round(e["g"] - start, 2), e["s"][0], e["s"][1]] for e in EV if "s" in e and start <= e["g"] <= goal["g"]]
    puck.append([round(goal["g"] - start - 0.05, 2), DIRS[goal["tm"]] * 26.4, max(-0.6, min(0.6, shot["s"][1] * 0.1))])
    puck.sort()
    marks = []
    for e in EV:
        if start <= e["g"] <= goal["g"] and e["ty"] in ("Pass", "Shot", "Goal", "BluelineCrossing", "Faceoff"):
            if e["ty"] == "Pass" and e.get("res") != "Successful":
                continue
            if e["ty"] == "BluelineCrossing" and e.get("bld") != "TowardsOpponent":
                continue
            marks.append([round(e["g"] - start, 2), e["ty"], e.get("pl"), e.get("pl2") or e.get("a1"), round(e.get("spd") or 0), e.get("res")])
    before = {"USC": 0, "HCD": 0}
    for g2 in goals:
        if g2["g"] < goal["g"]:
            before[g2["tm"]] += 1
    after = dict(before)
    after[goal["tm"]] += 1
    return {"dur": round(end - start, 2), "goalT": round(goal["g"] - start, 2), "p": goal["p"], "c0": round(goal["c"] - (goal["g"] - start), 1),
            "tm": goal["tm"], "before": before, "after": after, "frames": frames, "puck": puck, "marks": marks,
            "empty": shot.get("hg") is False or shot.get("ag") is False}


def seg_dist(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy or 1
    u = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L2))
    cx, cy = ax + u * dx, ay + u * dy
    return math.hypot(px - cx, py - cy), (px - cx, py - cy)


replays = []
for gi in (0, 1, len(goals) - 1):
    goal = goals[gi]
    shot = shot_for(goal)
    replays.append(scene(goal, shot["g"] - 9.0, goal["g"] + 1.6))

# Game-Modus: die zwei Pässe vor dem Tor. Bei jedem Pass ist genau ein Mitspieler frei.
def marking(ps):
    P = pos_at(ps["g"])
    gk = lambda pid: PL[str(pid)]["gk"]
    mates = [pid for pid in P if PL[str(pid)]["tm"] == ps["tm"] and not gk(pid) and pid not in (ps["pl"], ps["pl2"])]
    opps = [pid for pid in P if PL[str(pid)]["tm"] != ps["tm"] and not gk(pid)]
    s, e = tuple(ps["s"]), tuple(ps["e"])
    offsets, free = {}, list(opps)
    for m in mates:   # jeden anderen Mitspieler eng decken
        if not free:
            break
        d = min(free, key=lambda o: math.hypot(P[o][0] - P[m][0], P[o][1] - P[m][1]))
        free.remove(d)
        mx, my = P[m]
        vx, vy = s[0] - mx, s[1] - my
        n = math.hypot(vx, vy) or 1
        offsets[d] = (mx + vx / n * 1.1 - P[d][0], my + vy / n * 1.1 - P[d][1])
    for o in free:    # Passweg und Empfänger frei halten
        x, y = P[o]
        dist, (vx, vy) = seg_dist((x, y), s, e)
        de = math.hypot(x - e[0], y - e[1])
        if dist < 3.0 or de < 3.5:
            n = math.hypot(vx, vy) or 1
            if dist < 0.01:
                vx, vy, n = -(e[1] - s[1]), e[0] - s[0], math.hypot(e[0] - s[0], e[1] - s[1]) or 1
            push = max(3.4 - dist, 3.8 - de, 0)
            offsets[o] = (vx / n * push, vy / n * push)
    return offsets


def keyed(keys):
    """keys: [(t, {pid: (ox, oy)})] -> Versatz je Spieler, weich interpoliert."""
    def at(t, pid):
        if t <= keys[0][0] or t >= keys[-1][0]:
            return (0.0, 0.0)
        for (t0, a), (t1, b) in zip(keys, keys[1:]):
            if t0 <= t <= t1:
                f = smooth((t - t0) / (t1 - t0)) if t1 > t0 else 1
                ax, ay = a.get(pid, (0.0, 0.0)); bx, by = b.get(pid, (0.0, 0.0))
                return (ax + (bx - ax) * f, ay + (by - ay) * f)
        return (0.0, 0.0)
    return at


def arrival(puck, tf, e):
    for k in range(1, len(puck)):
        t0, x0, y0 = puck[k - 1]; t1, x1, y1 = puck[k]
        if t1 <= tf:
            continue
        for u in range(21):
            tt = t0 + (t1 - t0) * u / 20
            if tt <= tf:
                continue
            x, y = x0 + (x1 - x0) * u / 20, y0 + (y1 - y0) * u / 20
            if math.hypot(x - e[0], y - e[1]) < 0.7:
                return round(tt, 2)
    return round(tf + 0.7, 2)


scenes = []
for goal in goals:
    shot = shot_for(goal)
    cand = [e for e in EV if e["ty"] == "Pass" and e.get("res") == "Successful" and e["tm"] == goal["tm"] and 0 < shot["g"] - e["g"] < 9]
    if len(cand) < 2:
        continue
    p1, p2 = cand[-2], cand[-1]
    start = p1["g"] - 3.0
    tf1, tf2 = p1["g"] - start, p2["g"] - start
    o1, o2 = marking(p1), marking(p2)
    keys = [(max(0.0, tf1 - 2.4), {}), (tf1, o1), (tf2, o2), (tf2 + 1.4, {})]
    sc = scene(goal, start, goal["g"] + 1.4, keyed(keys))
    passes = []
    for ps, tf in ((p1, tf1), (p2, tf2)):
        passes.append({"tf": round(tf, 2), "s": ps["s"], "e": ps["e"], "from": ps["pl"], "to": ps["pl2"], "tArr": arrival(sc["puck"], tf, ps["e"])})
    sc.update({"id": f"sim-{int(p1['g'])}", "passes": passes})
    scenes.append(sc)

used = {pid for sc in replays + scenes for f in sc["frames"] for pid, _, _ in f[1]}
rp_players = {str(pid): [PL[str(pid)]["no"], PL[str(pid)]["n"].split(" ")[-1], PL[str(pid)]["tm"], PL[str(pid)]["gk"]] for pid in used}
cnt_p, cnt_s = {}, {}
for e in EV:
    if e["ty"] == "Pass" and e.get("res") == "Successful":
        cnt_p[e["pl"]] = cnt_p.get(e["pl"], 0) + 1
    if e["ty"] == "Shot":
        cnt_s[e["pl"]] = cnt_s.get(e["pl"], 0) + 1
lead = lambda c: [[f"#{PL[str(k)]['no']} {PL[str(k)]['n'].split(' ')[-1]}", PL[str(k)]["tm"], v] for k, v in sorted(c.items(), key=lambda kv: -kv[1])[:3]]
leaders = {"passes": lead(cnt_p), "shots": lead(cnt_s)}

# ---------------------------------------------------------------- Website
web = (ROOT / "website" / "index.html").read_text(encoding="utf-8")


def rep(a, b, n=1):
    global web
    assert web.count(a) == n, (web.count(a), a[:80])
    web = web.replace(a, b)


rep("../learn_the_game/Hockey-verstehen.html", "app/index.html")
rep('src="../shared/hv-account.js"', 'src="shared/hv-account.js"')
rep('<meta charset="utf-8">', '<meta charset="utf-8">\n<meta name="robots" content="noindex, nofollow">\n<link href="https://fonts.googleapis.com/css2?family=Rajdhani:ital,wght@0,600;0,700;1,700;1,800&display=swap" rel="stylesheet">')
if not VIDEO:
    rep('Im Betrieb laufen beide Angebote mit den Live-Trackingdaten von Wisehockey. Der Prototyp nutzt die Daten des Finals 2025.',
        'Im Betrieb laufen beide Angebote mit den Live-Trackingdaten von Wisehockey. Diese öffentliche Demo zeigt eine simulierte Partie, die echten Daten bleiben privat.')
    rep('In operation, both offers run on live Wisehockey tracking data. The prototype uses the data of the 2025 final.',
        'In operation, both offers run on live Wisehockey tracking data. This public demo shows a simulated game; the real data stays private.')
    PREV = '<p class="prev reveal d2"><b>{b}</b> {t}</p>'
    rep('<span data-l="en">Rule collected</span></li></ol>', '<span data-l="en">Rule collected</span></li></ol>\n      ' + PREV.format(
        b='<span data-l="de">Statische Vorschau.</span><span data-l="en">Static preview.</span>',
        t='<span data-l="de">Hier läuft eine simulierte Partie. Im Betrieb erklärt Learn the Game die Pfiffe live während des Spiels, mit den Trackingdaten in Echtzeit.</span><span data-l="en">This runs a simulated game. In operation, Learn the Game explains the whistles live during the game, with real-time tracking data.</span>'))
    rep('<span data-l="en">Points for accuracy</span></li></ol>', '<span data-l="en">Points for accuracy</span></li></ol>\n      ' + PREV.format(
        b='<span data-l="de">Statische Vorschau.</span><span data-l="en">Static preview.</span>',
        t='<span data-l="de">Die Szenen stammen aus einer simulierten Partie. Im Betrieb kommen die Schlüsselszenen live aus dem laufenden Spiel, in der Pause und nach dem Schlusspfiff.</span><span data-l="en">The scenes come from a simulated game. In operation, the key scenes come live from the game in progress, in the break and after the final whistle.</span>'))
rep(".lb .x{", ".prev{margin-top:22px;max-width:560px;font-size:14px;line-height:1.5;color:var(--mist);border-left:3px solid #F5B800;padding:4px 0 4px 14px}\n.prev b{color:#F5B800}\n.lb .x{")
L = lambda de, en: f'<span data-l="de">{de}</span><span data-l="en">{en}</span>'
ps = web.index('<button class="demo" id="proDemo"')
pe = web.index('</button>', ps) + len('</button>')
web = web[:ps] + ('<div class="bpmodes" role="tablist">'
    + '<button type="button" data-m="replay" class="on"><b>REPLAY MODE</b><span>Watch cinematic broadcast</span><span>Fully automated playback</span></button>'
    + '<button type="button" data-m="game" class="game"><b>GAME MODE</b><span>Draw puck prediction vectors</span><span>Score points with distance accuracy</span></button></div>'
    + '<div class="bpwrap" id="proGame"><canvas id="bapCanvas" aria-label="Be a Pro"></canvas></div>'
    + ('<p class="bpnote" hidden><span id="bapNote"></span></p>' if VIDEO else '<p class="bpnote">' + L('Statische Vorschau im Design des Be-a-Pro-Prototyps · simulierte Partie · ', 'Static preview in the design of the Be a Pro prototype · simulated game · ') + '<span id="bapNote"></span></p>')) + web[pe:]

old_start = web.index("// Smart Link Be a Pro")
old_end = web.index("// Sprache: ?lang=en")
web = web[:old_start] + """// Be a Pro, Vorschau: Szenen aus der simulierten Partie. Das ganze Spiel läuft im Prototyp mit Replay- und Game-Modus.
const REPLAYS = """ + json.dumps(replays, separators=(",", ":")) + """;
const RP = """ + json.dumps(rp_players, separators=(",", ":"), ensure_ascii=False) + """;
const LEADERS = """ + json.dumps(leaders, separators=(",", ":"), ensure_ascii=False) + """;
const PASS_SCENES = """ + json.dumps(scenes, separators=(",", ":")) + """;
// Be a Pro, Vorschau im Design des Prototyps (Alessio): Replay Mode und Game Mode auf der simulierten Partie.
(function bePro() {
  const cv = document.getElementById('bapCanvas'); if (!cv || !PASS_SCENES.length) return;
  const ctx = cv.getContext('2d');
  // Farben und Schrift wie im Prototyp
  const ARENA_BG = '#04070C', BOARD = 'rgba(0,212,255,.8)', WHITE = '#FFFFFF', CYAN = '#00F0FF', P3_CYAN = '#00E5FF', P3_RED = '#FF1A40';
  const LINE_RED = '#FF2E4C', LINE_BLUE = '#0088FF', HOME = '#2882FF', AWAY = '#FF2D5F', GREEN = '#30FF96';
  const TEAM = { USC: HOME, HCD: AWAY };   // USC spielt zu Hause
  const F = (w, sz) => `italic ${w} ${sz}px 'Rajdhani', sans-serif`;
  let W = 0, H = 0, TOP = 0, k = 1, ox = 0, oy = 0, f = 1, small = false;
  const cam = { cx: 0, cy: 0, span: 60 };
  function fit() {
    const r = cv.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
    if (r.width !== W || r.height !== H) { W = r.width; H = r.height; cv.width = W * dpr; cv.height = H * dpr; }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    small = W < 640; TOP = small ? 46 : 62;
    const vw = W - 8, vh = H - TOP - 6;
    const full = cam.span >= 60;
    k = full ? Math.min(W / (1500 / 17.5), H / (800 / 17.5)) : Math.min(vw / cam.span, vh / Math.min(30.6, cam.span / 2));
    const hw = vw / (2 * k), hh = vh / (2 * k);
    const cx = full || hw >= 31 ? 0 : Math.max(-31 + hw, Math.min(31 - hw, cam.cx)), cy = full || hh >= 15.3 ? 0 : Math.max(-15.3 + hh, Math.min(15.3 - hh, cam.cy));
    ox = W / 2 - (cx + 30) * k; oy = full ? H / 2 - 15 * k : TOP + vh / 2 - (15 - cy) * k; f = full ? k / 17.5 : k / 22.7;
  }
  const X = x => ox + (x + 30) * k, Y = y => oy + (15 - y) * k;
  const toWorld = (px, py) => [(px - ox) / k - 30, 15 - (py - oy) / k];
  function rr(x, y, w, h, r, fill, stroke) {
    ctx.beginPath(); ctx.moveTo(x + r, y); ctx.lineTo(x + w - r, y); ctx.quadraticCurveTo(x + w, y, x + w, y + r); ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h); ctx.lineTo(x + r, y + h); ctx.quadraticCurveTo(x, y + h, x, y + h - r); ctx.lineTo(x, y + r); ctx.quadraticCurveTo(x, y, x + r, y); ctx.closePath();
    if (fill) ctx.fill(); if (stroke) ctx.stroke();
  }
  const nm = id => RP[id] ? RP[id][1] : '';

  // ---------- Eisfläche wie drawMasterRink
  function rink(goalFlash) {
    const g = ctx.createRadialGradient(W / 2, H / 2, 40, W / 2, H / 2, Math.max(W, H) * .7);
    g.addColorStop(0, '#0B1220'); g.addColorStop(1, ARENA_BG); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    const x0 = X(-30.8), y0 = Y(14.85), rw = 61.6 * k, rh = 29.7 * k, rad = Math.max(10, 40 * f);
    ctx.fillStyle = 'rgba(0,0,0,.7)'; rr(x0 - 12 * f, y0 - 12 * f, rw + 24 * f, rh + 24 * f, rad + 12 * f, true, false);
    const ig = ctx.createRadialGradient(X(0), Y(0), 100 * f, X(0), Y(0), 700 * f); ig.addColorStop(0, '#121E36'); ig.addColorStop(1, '#0A1220');
    ctx.fillStyle = ig; rr(x0, y0, rw, rh, rad, true, false);
    ctx.save(); rr(x0, y0, rw, rh, rad, false, false); ctx.clip();
    const vline = (x, col, lw, inset = 0) => { ctx.strokeStyle = col; ctx.lineWidth = lw; ctx.beginPath(); ctx.moveTo(X(x), y0 + inset); ctx.lineTo(X(x), y0 + rh - inset); ctx.stroke(); };
    vline(0, LINE_RED, Math.max(1.5, 3 * f));
    ctx.strokeStyle = 'rgba(0,240,255,.6)'; ctx.lineWidth = Math.max(1, 2 * f); ctx.beginPath(); ctx.arc(X(0), Y(0), 65 / 17.5 * k, 0, 7); ctx.stroke();
    ctx.fillStyle = LINE_RED; ctx.beginPath(); ctx.arc(X(0), Y(0), Math.max(2, 6 * f), 0, 7); ctx.fill();
    vline(-8.5, LINE_BLUE, Math.max(2, 3.5 * f)); vline(8.5, LINE_BLUE, Math.max(2, 3.5 * f));
    vline(-26, 'rgba(255,46,76,.7)', Math.max(1, 2 * f), 10 * f); vline(26, 'rgba(255,46,76,.7)', Math.max(1, 2 * f), 10 * f);
    for (const [dx, dy] of [[-20, -6], [-20, 6], [20, -6], [20, 6]]) {
      ctx.strokeStyle = 'rgba(0,240,255,.4)'; ctx.lineWidth = Math.max(1, 1.5 * f); ctx.beginPath(); ctx.arc(X(dx), Y(dy), 45 / 17.5 * k, 0, 7); ctx.stroke();
      ctx.fillStyle = CYAN; ctx.beginPath(); ctx.arc(X(dx), Y(dy), Math.max(2, 4 * f), 0, 7); ctx.fill();
    }
    for (const [dx, dy] of [[-6, -6], [-6, 6], [6, -6], [6, 6]]) { ctx.fillStyle = CYAN; ctx.beginPath(); ctx.arc(X(dx), Y(dy), Math.max(2, 4 * f), 0, 7); ctx.fill(); }
    for (const sx of [-1, 1]) {
      ctx.fillStyle = 'rgba(15,50,90,.6)'; ctx.beginPath(); ctx.arc(X(sx * 26), Y(0), 20 / 17.5 * k, 0, 7); ctx.fill();
      ctx.strokeStyle = CYAN; ctx.lineWidth = Math.max(1, 1.5 * f); ctx.stroke();
      const hot = goalFlash && goalFlash.side === sx ? goalFlash.a : 0;
      const nw = 14 / 17.5 * k, nh = 24 / 17.5 * k, nx = sx < 0 ? X(-26) - nw : X(26), ny = Y(0) - nh / 2;
      ctx.fillStyle = hot ? `rgba(255,26,64,${.35 + .6 * hot})` : 'rgba(60,20,20,.8)'; ctx.fillRect(nx, ny, nw, nh);
      ctx.strokeStyle = LINE_RED; ctx.lineWidth = Math.max(1, 1.5 * f); ctx.strokeRect(nx, ny, nw, nh);
    }
    ctx.restore();
    ctx.strokeStyle = BOARD; ctx.lineWidth = Math.max(2, 3.5 * f); rr(x0, y0, rw, rh, rad, false, true);
  }
  function player(id, x, y, vx, vy) {
    const info = RP[id] || [0, '', 'USC'], px = X(x), py = Y(y), R = Math.max(8, 16 * f), r = R * 14 / 16;
    if (vx !== undefined && Math.hypot(vx, vy) > .25) {
      const a = Math.atan2(-vy, vx), d = R + 6 * f, ts = Math.max(4, 7 * f);
      ctx.save(); ctx.translate(px, py); ctx.rotate(a); ctx.fillStyle = CYAN; ctx.strokeStyle = '#0F1624'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(d + ts, 0); ctx.lineTo(d - ts, -ts * .7); ctx.lineTo(d - ts, ts * .7); ctx.closePath(); ctx.fill(); ctx.stroke(); ctx.restore();
    }
    ctx.fillStyle = 'rgba(0,0,0,.6)'; ctx.beginPath(); ctx.arc(px + 2 * f, py + 3 * f, R, 0, 7); ctx.fill();
    ctx.fillStyle = '#0F1624'; ctx.beginPath(); ctx.arc(px, py, R, 0, 7); ctx.fill();
    ctx.fillStyle = TEAM[info[2]]; ctx.beginPath(); ctx.arc(px, py, r, 0, 7); ctx.fill();
    ctx.strokeStyle = CYAN; ctx.lineWidth = Math.max(1, 2 * f); ctx.beginPath(); ctx.arc(px, py, R, 0, 7); ctx.stroke();
    ctx.font = F(700, Math.max(10, Math.round(16 * f))); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillStyle = '#000'; ctx.fillText(info[0], px + 1, py + 1); ctx.fillStyle = WHITE; ctx.fillText(info[0], px, py);
  }
  function puck(p, v, acc) {
    const px = X(p[0]), py = Y(p[1]), r = Math.max(4, 7 * f);
    ctx.fillStyle = 'rgba(0,0,0,.6)'; ctx.beginPath(); ctx.arc(px + 3 * f, py + 3 * f, r, 0, 7); ctx.fill();
    ctx.fillStyle = '#0A0A0E'; ctx.beginPath(); ctx.arc(px, py, r, 0, 7); ctx.fill();
    ctx.strokeStyle = CYAN; ctx.lineWidth = 1.5; ctx.stroke();
    if (v > 3) { ctx.font = F(800, Math.max(12, Math.round(15 * f))); ctx.fillStyle = acc ? '#00FFB4' : '#FF3B56'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(`${Math.round(v)} km/h`, px, py + Math.max(14, 20 * f)); }
  }
  // Schräge Event-Banner wie drawWorldEventBannerForeground
  const POPUP = 2.5;
  let popups = [];
  function popup(text, color, anchor) { popups.push({ text, color, anchor, t0: performance.now() / 1000 }); if (popups.length > 3) popups.shift(); }
  function drawPopups() {
    const now = performance.now() / 1000;
    popups = popups.filter(p => now - p.t0 < POPUP);
    popups.forEach((p, i) => {
      const under = i < popups.length - 1, el = now - p.t0, prog = el / POPUP;
      const intro = Math.min(1, prog / .12), outro = Math.min(1, (1 - prog) / .12);
      let vis = Math.min(intro, outro); if (under) vis *= .5;
      const sc = (0.7 + 0.3 * (1 - Math.pow(1 - intro, 3))) * (under ? .85 : 1) * (small ? .75 : 1);
      const sh = (1 - Math.min(1, el / .4)) * (under ? 2 : 4);
      const ax = Math.max(80, Math.min(W - 80, X(p.anchor[0]))) + Math.sin(el * 60) * sh, ay = Math.min(H - 70, Math.max(TOP + 40, Y(p.anchor[1]) - 45 - (under ? 20 : 0))) + Math.cos(el * 50) * sh * .5;
      ctx.save(); ctx.font = F(800, 22); const w = ctx.measureText(p.text).width + 64, h = 42;
      ctx.translate(ax, ay); ctx.scale(sc, sc); ctx.globalAlpha = vis;
      ctx.save(); ctx.transform(1, 0, -.22, 1, 6, 6); ctx.fillStyle = 'rgba(0,0,0,.75)'; ctx.fillRect(-w / 2, -h / 2, w, h); ctx.restore();
      ctx.save(); ctx.transform(1, 0, -.22, 1, 0, 0); ctx.fillStyle = p.color; ctx.fillRect(-w / 2 - 4, -h / 2 - 4, w + 8, h + 8);
      ctx.fillStyle = '#0A0F1D'; ctx.fillRect(-w / 2, -h / 2, w, h); ctx.fillStyle = p.color; ctx.fillRect(-w / 2, -h / 2, 8, h); ctx.restore();
      ctx.fillStyle = WHITE; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(p.text, 2, 1);
      ctx.restore();
    });
  }
  // ---------- Daten abspielen
  function framesAt(Fr, tt) {
    if (tt <= Fr[0][0]) return Fr[0][1];
    for (let i = 1; i < Fr.length; i++) if (tt < Fr[i][0]) {
      const A = Fr[i - 1], B = Fr[i], u = (tt - A[0]) / (B[0] - A[0]), m = new Map(B[1].map(q => [q[0], q]));
      return A[1].map(([id, x, y]) => { const q = m.get(id); return q ? [id, x + (q[1] - x) * u, y + (q[2] - y) * u] : [id, x, y]; });
    }
    return Fr[Fr.length - 1][1];
  }
  function puckAt(P, tt) {
    if (tt < P[0][0] - .3 || tt > P[P.length - 1][0] + 1.2) return null;
    if (tt <= P[0][0]) return [P[0][1], P[0][2]];
    for (let i = 1; i < P.length; i++) if (tt < P[i][0]) { const A = P[i - 1], B = P[i], u = (tt - A[0]) / (B[0] - A[0]); return [A[1] + (B[1] - A[1]) * u, A[2] + (B[2] - A[2]) * u]; }
    const Z = P[P.length - 1]; return [Z[1], Z[2]];
  }
  const speed = (P, tt) => { const a = puckAt(P, tt - .2), b = puckAt(P, tt); return a && b && tt <= P[P.length - 1][0] ? Math.hypot(b[0] - a[0], b[1] - a[1]) / .2 * 3.6 : 0; };
  function bannerFor(m) {
    if (m[1] === 'Goal') return ['GOAL!!!', P3_RED];
    if (m[1] === 'Shot') return m[5] === 'Saved' ? ['GREAT SAVE!', P3_CYAN] : ['SHOT ON TARGET!', WHITE];
    if (m[1] === 'Pass') return ['CLEAN PASS!', GREEN];
    if (m[1] === 'BluelineCrossing') return ['ZONE ENTRY!', P3_CYAN];
    return null;
  }
  function fireMarks(sc, t0, t1) {
    for (const m of sc.marks) if (m[0] > t0 && m[0] <= t1) { const b = bannerFor(m), p = puckAt(sc.puck, m[0]); if (b && p) popup(b[0], b[1], p); }
  }
  function scene(sc, tt) {
    const gf = tt >= sc.goalT - .05 && tt < sc.goalT + 1.6 ? { side: sc.tm === 'USC' ? 1 : -1, a: 1 - Math.max(0, tt - sc.goalT) / 1.6 } : null;
    rink(gf);
    const ps = framesAt(sc.frames, tt), pk = puckAt(sc.puck, tt), tc = Math.min(tt, sc.goalT);
    const pv = new Map(framesAt(sc.frames, Math.max(0, tt - .25)).map(q => [q[0], q]));
    for (const [id, x, y] of ps) { const q = pv.get(id); player(id, x, y, q ? (x - q[1]) / .25 : 0, q ? (y - q[2]) / .25 : 0); }
    if (pk) puck(pk, frozen ? 0 : speed(sc.puck, tc), speed(sc.puck, tc) >= speed(sc.puck, tc - .2));
    return { ps, pk };
  }
  // ---------- HUD: Anzeigetafel, Minikarte, Spielerkarten
  function scoreboard(sc, tt, status, statusColor, info) {
    const s = tt >= sc.goalT ? sc.after : sc.before, cl = Math.min(1200, sc.c0 + tt);
    const clock = `${String(Math.floor(cl / 60)).padStart(2, '0')}:${String(Math.floor(cl % 60)).padStart(2, '0')}`;
    const bw = Math.min(1100, W - 16), bh = small ? 36 : 48, bx = (W - bw) / 2, by = 6, cy = by + bh / 2;
    ctx.fillStyle = 'rgba(10,18,32,.8)'; ctx.strokeStyle = 'rgba(255,255,255,.12)'; ctx.lineWidth = 1; rr(bx, by, bw, bh, small ? 10 : 14, true, true);
    ctx.textBaseline = 'middle';
    if (!small) { ctx.font = F(800, 15); ctx.fillStyle = statusColor; ctx.textAlign = 'left'; ctx.fillText(status, bx + 18, cy); }
    const mid = small ? bx + bw * .38 : bx + bw / 2;
    ctx.textAlign = 'center'; ctx.font = F(800, small ? 18 : 22);
    ctx.fillStyle = HOME; ctx.fillText('USC', mid - (small ? 62 : 95), cy);
    ctx.font = F(800, small ? 22 : 26); ctx.fillStyle = WHITE; ctx.fillText(String(s.USC), mid - (small ? 22 : 34), cy);
    ctx.fillStyle = 'rgba(255,255,255,.4)'; ctx.fillText('-', mid, cy); ctx.fillStyle = WHITE; ctx.fillText(String(s.HCD), mid + (small ? 22 : 34), cy);
    ctx.font = F(800, small ? 18 : 22); ctx.fillStyle = AWAY; ctx.fillText('HCD', mid + (small ? 62 : 95), cy);
    ctx.textAlign = 'right'; ctx.font = F(700, small ? 12 : 14); ctx.fillStyle = '#94A3B8';
    ctx.fillText(small ? clock : `CLOCK: ${clock}${info ? ' | ' + info : ''}`, bx + bw - 14, cy);
  }
  function minimap(ps, pk) {
    const pw = Math.round(W * .2), ph = Math.round(pw / 2), px = W - pw - 16, py = TOP + 10;
    ctx.fillStyle = 'rgba(8,14,24,.85)'; rr(px - 4, py - 4, pw + 8, ph + 8, 10, true, false);
    ctx.fillStyle = '#0D172A'; rr(px, py, pw, ph, 6, true, false);
    const mx = x => px + (x + 30) / 60 * pw, my = y => py + (15 - y) / 30 * ph;
    ctx.strokeStyle = LINE_BLUE; ctx.lineWidth = 1; for (const x of [-7.14, 7.14]) { ctx.beginPath(); ctx.moveTo(mx(x), py); ctx.lineTo(mx(x), py + ph); ctx.stroke(); }
    ctx.strokeStyle = LINE_RED; ctx.beginPath(); ctx.moveTo(mx(0), py); ctx.lineTo(mx(0), py + ph); ctx.stroke();
    for (const [id, x, y] of ps) { ctx.fillStyle = TEAM[(RP[id] || [0, '', 'USC'])[2]]; ctx.beginPath(); ctx.arc(mx(x), my(y), 3, 0, 7); ctx.fill(); }
    if (pk) { ctx.fillStyle = CYAN; ctx.beginPath(); ctx.arc(mx(pk[0]), my(pk[1]), 3, 0, 7); ctx.fill(); }
    ctx.strokeStyle = 'rgba(0,240,255,.4)'; rr(px, py, pw, ph, 6, false, true);
    const [vx0, vy0] = toWorld(0, TOP), [vx1, vy1] = toWorld(W, H);
    ctx.strokeStyle = WHITE; ctx.lineWidth = 1.5; ctx.strokeRect(mx(Math.max(-30, vx0)), my(Math.min(15, vy0)), mx(Math.min(30, vx1)) - mx(Math.max(-30, vx0)), my(Math.max(-15, vy1)) - my(Math.min(15, vy0)));
    return py + ph + 8;
  }
  // Avatar wie getP3PlayerAvatar (Alessio)
  const AV = {};
  function avatar(jersey, home) {
    const key = jersey + (home ? 'h' : 'a'); if (AV[key]) return AV[key];
    const c = document.createElement('canvas'); c.width = c.height = 120; const a = c.getContext('2d');
    a.fillStyle = home ? '#0A255C' : '#5C0A1E'; a.beginPath(); a.moveTo(10, 0); a.lineTo(120, 15); a.lineTo(105, 120); a.lineTo(0, 95); a.closePath(); a.fill();
    const seed = (parseInt(jersey) || 0) % 5;
    a.fillStyle = '#1E293B'; a.beginPath(); a.moveTo(15, 110); a.lineTo(105, 110); a.lineTo(85, 75); a.lineTo(35, 75); a.closePath(); a.fill();
    a.fillStyle = '#F8FAFC'; a.beginPath(); a.moveTo(40, 45); a.lineTo(75, 45); a.lineTo(70, 78); a.lineTo(55, 88); a.lineTo(42, 75); a.closePath(); a.fill();
    a.fillStyle = home ? '#1D4ED8' : '#9F1239'; a.beginPath();
    if (seed === 0) { a.moveTo(30, 35); a.lineTo(85, 25); a.lineTo(75, 55); a.lineTo(60, 42); a.lineTo(45, 60); }
    else if (seed === 1) { a.moveTo(25, 45); a.lineTo(80, 20); a.lineTo(65, 50); a.lineTo(50, 35); a.lineTo(35, 55); }
    else { a.moveTo(35, 25); a.lineTo(88, 35); a.lineTo(70, 58); a.lineTo(55, 45); a.lineTo(40, 65); }
    a.closePath(); a.fill();
    a.fillStyle = '#0F172A'; a.beginPath(); a.moveTo(48, 56); a.lineTo(58, 54); a.lineTo(56, 60); a.closePath(); a.moveTo(64, 54); a.lineTo(74, 56); a.lineTo(66, 60); a.closePath(); a.fill();
    a.strokeStyle = CYAN; a.lineWidth = 2; a.beginPath(); a.moveTo(42, 54); a.lineTo(78, 54); a.stroke();
    return (AV[key] = c);
  }
  // Spielerkarten wie drawPersonaPartyHUD (Alessio), auf die Canvas-Breite skaliert
  function partyCards(ps, pk, rightTop, leftTop) {
    if (W < 860) return;
    const s = Math.max(.72, Math.min(1, W / 1500)), cardH = 48 * s, gap = 12 * s, cw = 210 * s, y0 = TOP + 40 * s;
    const side = (tm, dir, startY) => {
      ps.filter(([id]) => RP[id] && RP[id][2] === tm && !RP[id][3]).slice(0, 5).forEach(([id, x, y], i) => {
        const yy = startY + i * (cardH + gap), home = tm === 'USC';
        const xr = home ? 20 * s + i * 8 * s : W - 230 * s - i * 8 * s, xx = xr + .15 * dir * (yy + cardH / 2);
        const carrier = pk && Math.hypot(x - pk[0], y - pk[1]) < 2.5;
        ctx.save(); ctx.transform(1, 0, -.15 * dir, 1, 0, 0);
        ctx.fillStyle = carrier ? (home ? 'rgba(0,240,255,.25)' : 'rgba(255,45,95,.3)') : (home ? 'rgba(10,22,40,.85)' : 'rgba(26,10,20,.85)');
        ctx.strokeStyle = carrier ? (home ? CYAN : WHITE) : (home ? 'rgba(40,130,255,.5)' : 'rgba(255,45,95,.5)'); ctx.lineWidth = carrier ? 2.5 : 1.5;
        rr(xx, yy, cw, cardH, 6, true, true);
        ctx.drawImage(avatar(String(RP[id][0]), home), home ? xx - 8 * s : xx + 160 * s, yy - 4 * s, 52 * s, 52 * s);
        const tx = home ? xx + 50 * s : xx + 15 * s;
        ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
        ctx.font = F(700, Math.round(17 * s)); ctx.fillStyle = WHITE; ctx.fillText(nm(id).toUpperCase().slice(0, 11), tx, yy + 22 * s);
        ctx.font = F(700, Math.round(18 * s)); ctx.fillStyle = home ? CYAN : AWAY; ctx.fillText(`#${RP[id][0]}`, home ? xx + 168 * s : xx + 125 * s, yy + 22 * s);
        ctx.font = F(800, Math.max(9, Math.round(11 * s))); ctx.fillStyle = carrier ? WHITE : '#64748B'; ctx.fillText(carrier ? '★ IN CONTROL' : 'ACTIVE ON ICE', tx, yy + 38 * s);
        ctx.restore();
      });
    };
    side('USC', 1, Math.max(y0, leftTop || 0)); side('HCD', -1, Math.max(y0, rightTop));
  }
  function leaders(list, title, a) {
    const tw = Math.min(330, W - 40), th = 44 + list.length * 30, tx = -tw - 30 + (20 + tw + 30) * a, ty = TOP + 14;
    ctx.fillStyle = 'rgba(10,18,32,.85)'; ctx.strokeStyle = 'rgba(0,240,255,.3)'; ctx.lineWidth = 1; rr(tx, ty, tw, th, 10, true, true);
    ctx.font = F(800, 17); ctx.fillStyle = WHITE; ctx.textAlign = 'left'; ctx.textBaseline = 'top'; ctx.fillText(`TOP ${title}`, tx + 16, ty + 12);
    ctx.strokeStyle = 'rgba(0,240,255,.2)'; ctx.beginPath(); ctx.moveTo(tx + 16, ty + 36); ctx.lineTo(tx + tw - 16, ty + 36); ctx.stroke();
    ctx.textBaseline = 'middle';
    list.forEach(([n, tm, v], i) => {
      const yy = ty + 54 + i * 30; ctx.font = F(700, 15);
      ctx.fillStyle = TEAM[tm]; ctx.fillText(n.split(' ')[0], tx + 16, yy); ctx.fillStyle = WHITE; ctx.fillText(n.split(' ').slice(1).join(' ').toUpperCase(), tx + 64, yy);
      ctx.textAlign = 'right'; ctx.fillStyle = P3_CYAN; ctx.fillText(`${v} ${title.startsWith('SHOT') ? 'Shots' : 'Passes'}`, tx + tw - 16, yy); ctx.textAlign = 'left';
    });
  }

  // ---------- Modi
  let mode = 'replay', last = performance.now(), frozen = false;
  let ri = 0, rt = 0;
  let gi = 0, gt = 0, pi = 0, gstate = 'lead', drawing = false, mouse = null, userEnd = null, lastDist = 0, lastPts = 0, sceneScore = 0;
  let total = 0, predictions = 0;
  const note = document.getElementById('bapNote');
  function setNote() { note.textContent = mode === 'replay' ? `Replay ${ri + 1}/${REPLAYS.length}` : `Scene ${gi + 1}/${PASS_SCENES.length} · Pass ${Math.min(pi + 1, 2)}/2`; }
  function setMode(m) {
    mode = m; popups = []; frozen = false;
    document.querySelectorAll('.bpmodes button').forEach(b => b.classList.toggle('on', b.dataset.m === m));
    if (m === 'replay') { rt = 0; } else startScene(gi);
    setNote();
  }
  function startScene(i) { gi = i; gt = 0; pi = 0; gstate = 'lead'; userEnd = null; mouse = null; drawing = false; sceneScore = 0; popups = []; setNote(); }
  document.querySelectorAll('.bpmodes button').forEach(b => b.addEventListener('click', () => setMode(b.dataset.m)));

  function tickReplay(dt) {
    const sc = REPLAYS[ri], OUT = 4.2, prev = rt;
    rt += dt;
    if (rt > sc.dur + OUT) { ri = (ri + 1) % REPLAYS.length; rt = 0; popups = []; setNote(); return; }
    const tt = Math.min(rt, sc.dur), pk0 = puckAt(sc.puck, tt);
    if (pk0) { const z = rt < .05 ? 1 : Math.min(1, dt * 2.2); cam.cx += (pk0[0] - cam.cx) * z; cam.cy += (pk0[1] * .5 - cam.cy) * z; }
    cam.span = small ? 26 : 60; fit(); // ganzes Feld, kein Zoom
    fireMarks(sc, prev, tt);
    const { ps, pk } = scene(sc, tt);
    drawPopups();
    const ev = (() => { let c = null; for (const m of sc.marks) if (m[0] <= tt) c = m; return c ? ({ Pass: 'PASS', Shot: 'SHOT', Goal: 'GOAL', BluelineCrossing: 'ZONE ENTRY', Faceoff: 'FACEOFF' })[c[1]] : 'PLAY'; })();
    scoreboard(sc, tt, '[REPLAY] PLAYING', '#00FFB4', ev);
    let rightTop = TOP + 12;
    if (!small && cam.span < 60) rightTop = minimap(ps, pk) + 4;
    const lead = ri % 2 ? LEADERS.shots : LEADERS.passes;
    partyCards(ps, pk, rightTop, rt > sc.dur ? TOP + 14 + 44 + lead.length * 30 + 16 : 0);
    if (rt > sc.dur) {
      const a = Math.min(1, (rt - sc.dur) / .6, (sc.dur + OUT - rt) / .6), e = 1 - Math.pow(1 - Math.max(0, a), 3);
      leaders(ri % 2 ? LEADERS.shots : LEADERS.passes, ri % 2 ? 'SHOTS LEADERS' : 'PASSES LEADERS', e);
    }
  }

  function tickGame(dt) {
    const sc = PASS_SCENES[gi], P = sc.passes[Math.min(pi, sc.passes.length - 1)], prev = gt;
    if (gstate === 'lead' || gstate === 'roll') {
      gt += dt;
      if (gstate === 'lead' && gt >= P.tf) { gt = P.tf; gstate = 'draw'; popup('DRAW PUCK VECTOR', P3_CYAN, [P.s[0], P.s[1] - 7]); }
      if (gstate === 'roll' && gt >= sc.dur) { gt = sc.dur; gstate = 'end'; }
    } else if (gstate === 'watch') {
      const nx = sc.passes[pi + 1], stop = Math.min(P.tArr + .25, nx ? nx.tf : Infinity);
      gt += dt; if (gt >= stop) { gt = stop; gstate = 'review'; }
    }
    frozen = gstate === 'draw';
    // Kamera auf die Hälfte, in der der Spielzug läuft
    const xs = sc.passes.flatMap(q => [q.s[0], q.e[0]]);
    cam.span = small ? 26 : 60; cam.cx = small ? (P.s[0] + P.e[0]) / 2 : xs.reduce((a, b) => a + b, 0) / xs.length; const ys = sc.passes.flatMap(q => [q.s[1], q.e[1]]); cam.cy = small ? (P.s[1] + P.e[1]) / 2 : ys.reduce((a, b) => a + b, 0) / ys.length;
    fit();
    if (gstate !== 'draw' && gstate !== 'review') fireMarks(sc, prev, gt);
    const { ps, pk } = scene(sc, gt);
    partyCards(ps, pk, TOP + 12);
    // Vorhersage und Auswertung
    if (gstate === 'draw') {
      const ph = (performance.now() / 1000 % 1.2) / 1.2;
      ctx.strokeStyle = `rgba(0,240,255,${1 - ph})`; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(X(P.s[0]), Y(P.s[1]), 10 + ph * 26, 0, 7); ctx.stroke();
      if (mouse) {
        ctx.strokeStyle = WHITE; ctx.lineWidth = 3; ctx.setLineDash([6, 4]); ctx.beginPath(); ctx.moveTo(X(P.s[0]), Y(P.s[1])); ctx.lineTo(mouse[0], mouse[1]); ctx.stroke(); ctx.setLineDash([]);
        ctx.fillStyle = CYAN; ctx.beginPath(); ctx.arc(mouse[0], mouse[1], 6, 0, 7); ctx.fill();
      }
    }
    if ((gstate === 'watch' || gstate === 'review') && userEnd) {
      ctx.strokeStyle = WHITE; ctx.lineWidth = 3; ctx.setLineDash(gstate === 'watch' ? [6, 4] : []); ctx.beginPath(); ctx.moveTo(X(P.s[0]), Y(P.s[1])); ctx.lineTo(X(userEnd[0]), Y(userEnd[1])); ctx.stroke(); ctx.setLineDash([]);
    }
    if (gstate === 'review') {
      ctx.lineWidth = 4; ctx.strokeStyle = P3_CYAN; ctx.beginPath(); ctx.moveTo(X(P.s[0]), Y(P.s[1])); ctx.lineTo(X(P.e[0]), Y(P.e[1])); ctx.stroke();
      ctx.fillStyle = WHITE; ctx.beginPath(); ctx.arc(X(P.s[0]), Y(P.s[1]), 7, 0, 7); ctx.fill();
      const tag = `${lastDist.toFixed(1)}m Error`; ctx.font = F(700, 15); const tw = ctx.measureText(tag).width + 20;
      const tx = Math.min(W - tw - 8, X(P.e[0]) + 15), ty = Y(P.e[1]) - 12;
      ctx.fillStyle = 'rgba(10,18,32,.9)'; ctx.strokeStyle = P3_CYAN; ctx.lineWidth = 1.5; rr(tx, ty, tw, 26, 6, true, true);
      ctx.fillStyle = P3_CYAN; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(tag, tx + tw / 2, ty + 13);
    }
    drawPopups();
    const statusMap = { lead: ['PLAYING', '#00FFB4'], roll: ['PLAYING', '#00FFB4'], draw: ['PREDICT PUCK PATH', WHITE], watch: ['WATCHING RESULT...', P3_CYAN], review: ['REVIEW', WHITE], end: ['REVIEW', WHITE] };
    const [st, sc2] = statusMap[gstate];
    scoreboard(sc, gt, `[GAME] ${st}`, sc2, '');
    // Banner unten in der Mitte
    const banner = (l1, l2, l3) => {
      const bw = Math.min(540, W - 24), bh = l2 ? 85 : 60, bx = (W - bw) / 2, by = H - bh - (small ? 14 : 84);
      ctx.fillStyle = 'rgba(10,18,32,.92)'; ctx.strokeStyle = WHITE; ctx.lineWidth = 2; rr(bx, by, bw, bh, 12, true, true);
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.font = F(800, small ? 15 : 18); ctx.fillStyle = WHITE; ctx.fillText(l1, bx + bw / 2, by + 20);
      if (l2) { ctx.font = F(700, small ? 13 : 15); ctx.fillStyle = WHITE; ctx.fillText('— Your Prediction', bx + bw * .3, by + 45); ctx.fillStyle = P3_CYAN; ctx.fillText('— Actual Movement', bx + bw * .68, by + 45); }
      ctx.font = F(800, small ? 13 : 15); ctx.fillStyle = WHITE; ctx.fillText(l3, bx + bw / 2, by + bh - 16);
    };
    if (gstate === 'review') banner(`PREDICTION RESULT — DISTANCE ERROR: ${lastDist.toFixed(1)}M`, true, '▶ CLICK TO CONTINUE');
    if (gstate === 'end') banner(`SCENE COMPLETE — +${sceneScore} PTS`, false, gi + 1 < PASS_SCENES.length ? '▶ CLICK FOR THE NEXT SCENE' : '▶ CLICK TO START AGAIN');
    // Punktekarte unten rechts
    if (!small || gstate === 'lead' || gstate === 'roll') {
      const s = `SCORE: ${total} PTS  |  PREDICTIONS: ${predictions}`; ctx.font = F(800, small ? 13 : 17); const cw = ctx.measureText(s).width + 30, ch = small ? 32 : 42;
      const cx = W - cw - (small ? 10 : 25), cy = H - ch - (small ? 10 : 25);
      if (!(gstate === 'review' || gstate === 'end') || !small) { ctx.fillStyle = 'rgba(10,18,32,.85)'; ctx.strokeStyle = 'rgba(255,255,255,.4)'; ctx.lineWidth = 1; rr(cx, cy, cw, ch, 10, true, true);
        ctx.fillStyle = WHITE; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(s, cx + cw / 2, cy + ch / 2); }
    }
  }
  // Eingabe: Vektor ziehen (oder antippen)
  const pos = ev => { const r = cv.getBoundingClientRect(); return [ev.clientX - r.left, ev.clientY - r.top]; };
  cv.addEventListener('pointerdown', ev => {
    if (mode !== 'game') return;
    if (gstate === 'draw') { drawing = true; mouse = pos(ev); cv.setPointerCapture(ev.pointerId); ev.preventDefault(); }
    else if (gstate === 'review') { pi++; gstate = pi < PASS_SCENES[gi].passes.length ? 'lead' : 'roll'; userEnd = null; mouse = null; setNote(); }
    else if (gstate === 'end') { startScene((gi + 1) % PASS_SCENES.length); if (gi === 0 && window.HVAccount) document.getElementById('ranking').scrollIntoView({ behavior: 'smooth' }); }
  });
  cv.addEventListener('pointermove', ev => { if (drawing) mouse = pos(ev); });
  cv.addEventListener('pointerup', ev => {
    if (!drawing) return; drawing = false; mouse = pos(ev);
    const sc = PASS_SCENES[gi], P = sc.passes[pi];
    userEnd = toWorld(mouse[0], mouse[1]);
    lastDist = Math.hypot(userEnd[0] - P.e[0], userEnd[1] - P.e[1]);
    lastPts = Math.max(0, Math.round(100 * (1 - Math.min(lastDist, 15) / 15)));
    total += lastPts; sceneScore += lastPts; predictions++;
    if (window.HVAccount) { HVAccount.addPass(`${sc.id}-${pi}`, lastPts); renderAccount(); }
    popup(`SCORE: ${lastPts} PTS (${lastDist.toFixed(1)}M OFF)`, lastPts > 50 ? WHITE : P3_RED, P.e);
    gstate = 'watch';
  });
  function loop(now) {
    const dt = Math.min(.1, (now - last) / 1000); last = now;
    cv.style.touchAction = mode === 'game' && gstate === 'draw' ? 'none' : 'auto';
    cv.style.cursor = mode === 'game' && (gstate === 'draw' || gstate === 'review' || gstate === 'end') ? 'crosshair' : 'default';
    if (mode === 'replay') tickReplay(dt); else tickGame(dt);
    requestAnimationFrame(loop);
  }
  // für das Demovideo: Zustand lesen und Modus steuern
  window.BAP = { state: () => (mode === 'game' ? gstate : 'replay'), setMode, start(i) { gi = i; setMode('game'); }, target() { const P = PASS_SCENES[gi].passes[Math.min(pi, PASS_SCENES[gi].passes.length - 1)]; const r = cv.getBoundingClientRect(); return { s: [r.left + X(P.s[0]), r.top + Y(P.s[1])], e: [r.left + X(P.e[0]), r.top + Y(P.e[1])] }; }, replay: () => ({ ri, rt }) };
  setMode('replay'); requestAnimationFrame(loop);
})();

""" + web[old_end:]
rep(".lb .x{", """#pro .showgrid.pro{grid-template-columns:1fr;gap:34px}
#pro .showgrid.pro .lead,#pro .prev{max-width:760px}
.bpmodes{display:flex;gap:16px;margin-bottom:16px;max-width:640px}
.bpmodes button{flex:1;background:rgba(20,35,60,.6);border:1px solid rgba(0,130,210,.5);border-radius:12px;padding:14px 16px;cursor:pointer;color:#fff;text-align:center;font-family:'Rajdhani',sans-serif;font-style:italic;transform:skewX(-8deg);transition:all .25s cubic-bezier(.16,1,.3,1)}
.bpmodes button b{display:block;font-size:22px;font-weight:800;letter-spacing:1px}
.bpmodes button span{display:block;font-size:14px;font-weight:700;color:#94A3B8;margin-top:2px}
.bpmodes button:hover,.bpmodes button.on{background:rgba(0,210,255,.15);border-color:#00F0FF;box-shadow:0 10px 25px rgba(0,240,255,.25)}
.bpmodes button.game.on,.bpmodes button.game:hover{background:rgba(255,255,255,.12);border-color:#fff;box-shadow:0 10px 25px rgba(255,255,255,.2)}
.bpwrap{position:relative;width:100%;aspect-ratio:16/9;border-radius:14px;overflow:hidden;background:radial-gradient(circle at center,#0B1220 0%,#04070C 100%);box-shadow:0 30px 90px -30px rgba(0,240,255,.35);border:1px solid rgba(0,240,255,.18)}
.bpwrap canvas{position:absolute;inset:0;width:100%;height:100%;display:block}
.bpnote{margin-top:10px;font-size:12px;color:var(--mist)}
@media (max-width:640px){.bpwrap{aspect-ratio:3/4}.bpmodes{gap:10px}.bpmodes button{padding:10px 8px}.bpmodes button b{font-size:17px}.bpmodes button span{font-size:12px}}
.lb .x{""")

HERO_RINK_JS = """<script>
// Header: Spielfeld im Be-a-Pro-Stil, zehn simulierte Spieler und ein Puck bewegen sich ruhig (keine echten Daten)
(() => {
  const cv = document.querySelector('.herorink'); if (!cv) return;
  const ctx = cv.getContext('2d'), still = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const HOME = '#2882FF', AWAY = '#FF2D5F', CYAN = '#00F0FF';
  const P = Array.from({ length: 10 }, (_, i) => ({ home: i < 5, no: [9, 14, 21, 27, 33, 7, 11, 18, 24, 41][i],
    bx: (i < 5 ? -1 : 1) * (4 + (i % 5) * 4.2), by: [-9, -3, 3, 9, 0][i % 5] * .95, a: Math.random() * 6, b: Math.random() * 6, s: .25 + Math.random() * .2 }));
  let W = 0, H = 0, k = 1, ox = 0, oy = 0, vis = true;
  function fit() { const r = cv.getBoundingClientRect(), d = Math.min(2, devicePixelRatio || 1); W = r.width; H = r.height; cv.width = W * d; cv.height = H * d; ctx.setTransform(d, 0, 0, d, 0, 0);
    const n = W < 760; k = n ? Math.min(W * .95 / 61.6, H * .5 / 29.7) : Math.min(W * .56 / 61.6, H * .62 / 29.7); ox = n ? W * .5 : W * .7; oy = n ? H * .74 : H * .5; }
  const X = x => ox + x * k, Y = y => oy - y * k;
  function rr(x, y, w, h, r) { ctx.beginPath(); ctx.roundRect ? ctx.roundRect(x, y, w, h, r) : ctx.rect(x, y, w, h); }
  function rink() {
    ctx.clearRect(0, 0, W, H);
    const x0 = X(-30.8), y0 = Y(14.85), w = 61.6 * k, h = 29.7 * k;
    ctx.fillStyle = 'rgba(10,18,32,.55)'; rr(x0, y0, w, h, 2.3 * k); ctx.fill();
    ctx.strokeStyle = 'rgba(0,212,255,.8)'; ctx.lineWidth = 3; rr(x0, y0, w, h, 2.3 * k); ctx.stroke();
    const v = (x, c, lw) => { ctx.strokeStyle = c; ctx.lineWidth = lw; ctx.beginPath(); ctx.moveTo(X(x), y0); ctx.lineTo(X(x), y0 + h); ctx.stroke(); };
    v(0, '#FF2E4C', 3); v(-8.5, '#0088FF', 3.5); v(8.5, '#0088FF', 3.5); v(-26, 'rgba(255,46,76,.7)', 2); v(26, 'rgba(255,46,76,.7)', 2);
    ctx.strokeStyle = 'rgba(0,240,255,.5)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(X(0), Y(0), 3.7 * k, 0, 7); ctx.stroke();
    for (const [x, y] of [[-20, -6], [-20, 6], [20, -6], [20, 6]]) { ctx.strokeStyle = 'rgba(0,240,255,.35)'; ctx.beginPath(); ctx.arc(X(x), Y(y), 2.6 * k, 0, 7); ctx.stroke();
      ctx.fillStyle = CYAN; ctx.beginPath(); ctx.arc(X(x), Y(y), 3, 0, 7); ctx.fill(); }
  }
  function frame(t) {
    if (!vis) return requestAnimationFrame(frame);
    t /= 1000; rink();
    const pos = P.map(p => [p.bx + Math.sin(t * p.s + p.a) * 3.2 + Math.sin(t * .11 + p.b) * 2, p.by + Math.cos(t * p.s * .8 + p.b) * 2.4]);
    const seg = Math.floor(t / 2.2), u = (t / 2.2) % 1, from = pos[(seg * 3) % 5], to = pos[(seg * 3 + 2) % 5 + (seg % 4 === 3 ? 5 : 0)];
    const e = u < .55 ? 0 : Math.min(1, (u - .55) / .35), pk = [from[0] + (to[0] - from[0]) * e, from[1] + (to[1] - from[1]) * e];
    const R = Math.max(7, k * .5);
    pos.forEach(([x, y], i) => { const p = P[i];
      ctx.fillStyle = 'rgba(0,0,0,.5)'; ctx.beginPath(); ctx.arc(X(x) + 2, Y(y) + 3, R, 0, 7); ctx.fill();
      ctx.fillStyle = p.home ? HOME : AWAY; ctx.beginPath(); ctx.arc(X(x), Y(y), R * .88, 0, 7); ctx.fill();
      ctx.strokeStyle = CYAN; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(X(x), Y(y), R, 0, 7); ctx.stroke();
      ctx.fillStyle = '#fff'; ctx.font = `italic 700 ${Math.round(R)}px Rajdhani, sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(p.no, X(x), Y(y) + 1); });
    ctx.fillStyle = '#0A0A0E'; ctx.strokeStyle = CYAN; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(X(pk[0]), Y(pk[1]), Math.max(4, R * .4), 0, 7); ctx.fill(); ctx.stroke();
    if (!still) requestAnimationFrame(frame);
  }
  fit(); addEventListener('resize', () => { fit(); if (still) frame(0); });
  new IntersectionObserver(es => { vis = es[0].isIntersecting; }).observe(cv);
  requestAnimationFrame(frame);
})();
</script>
"""

if not VIDEO:
    # Vorgabe ThinkSport (15.11.): keine Spengler-Cup-Videos in öffentlich zugänglichen Demos, nur Platzhalter
    import re as _re
    # Header: eigene Grafik statt Video, Spielfeld im Be-a-Pro-Stil mit simulierten Spielern
    web = _re.sub(r'<video class="herovid"[^>]*>\s*</video>', '<canvas class="herovid herorink" aria-hidden="true"></canvas>', web, count=1)
    i = web.rindex('</body>'); web = web[:i] + HERO_RINK_JS + web[i:]
    a = web.index('<button class="yt reveal"'); b = web.index('</p>', web.index('<p class="src">', a)) + 4
    web = web[:a] + ('<div class="ytph reveal"><b>' + L('Platzhalter für die Highlights', 'Placeholder for the highlights') + '</b><span>'
        + L('In der öffentlichen Demo betten wir keine Videos des Spengler Cup ein. Im Betrieb läuft hier das Highlight-Video des letzten Finals.',
            'The public demo embeds no Spengler Cup videos. In operation, the highlight video of the last final plays here.') + '</span>'
        + '<a class="ytlink" href="https://www.youtube.com/watch?v=O3rLScC5SKw" target="_blank" rel="noopener">'
        + L('Highlights des Finals auf YouTube ansehen', 'Watch the final highlights on YouTube') + ' ↗</a></div>') + web[b:]
    rep(".lb .x{", ".ytph{margin-top:28px;aspect-ratio:16/9;max-width:900px;border-radius:14px;border:1px dashed rgba(102,193,211,.5);background:linear-gradient(135deg,#0A2A4A,#00142B);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;text-align:center;padding:24px}\n.ytph b{font-size:20px;color:#66C1D3}.ytlink{margin-top:6px;font-weight:700;color:#fff;border:1px solid rgba(102,193,211,.6);border-radius:10px;padding:10px 18px;text-decoration:none}.ytlink:hover{background:rgba(102,193,211,.15)}.herorink{opacity:.85}.ytph span{max-width:520px;color:var(--mist);font-size:15px;line-height:1.5}\n.lb .x{")
    assert "Headervideo" not in web and "ytimg" not in web and "data-yt=" not in web
    (OUT / ".htaccess").write_text('# Nicht in Suchmaschinen listen\n<IfModule mod_headers.c>\n  Header set X-Robots-Tag "noindex, nofollow"\n</IfModule>\n', encoding="utf-8")
assert "be-a-pro-demo.mp4" not in web and "be-a-pro-loop.mp4" not in web
(OUT / "index.html").write_text(web, encoding="utf-8")

# Kontrolle: keine echten Namen oder Daten im Ergebnis
real = (LEARN / "data.js").read_text(encoding="utf-8") if (LEARN / "data.js").exists() else ""
if real and not VIDEO:
    R = json.loads(real[real.index("{"):real.rindex("}") + 1])
    names = [p["n"] for p in R["players"].values()]
    for f in OUT.rglob("*"):
        if f.is_file():
            txt = f.read_text(encoding="utf-8", errors="ignore")
            hit = [n for n in names if n in txt]
            assert not hit, (f, hit[:3])
for f in sorted(OUT.rglob("*")):
    if f.is_file():
        print(f"{f.relative_to(OUT)}  {f.stat().st_size / 1024:.0f} KB")
print(f"{len(scenes)} Pass-Szenen")
