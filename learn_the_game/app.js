/* Learn the Game – Prototyp für die Sport Innovation Challenge 2026
 * Für Neulinge: Bei jedem Pfiff erklärt die App, was gepfiffen wurde und warum.
 * Daten: Wisehockey-Export, Final Spengler Cup 31.12.2025 (USC = Home, HCD = Away)
 */
'use strict';

const D = window.MATCH_DATA;

// Sprache: ?lang=en, sonst dieselbe Wahl wie auf der Website, sonst Browsersprache
const LANG = (() => {
  try { return ((new URLSearchParams(location.search).get('lang') || localStorage.getItem('hv_lang') || navigator.language || 'de').slice(0, 2) === 'en') ? 'en' : 'de'; } catch (e) { return 'de'; }
})();
const tr = (de, en) => (LANG === 'en' ? en : de);
document.documentElement.lang = LANG;
const PL = D.players;
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const fmtClock = s => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
const pct = x => `${Math.round(x * 100)} %`;
const TEAM_COL = { HCD: ['#1D4ED8', '#FFD200'], USC: ['#C8102E', '#FFFFFF'] };
const TEAM_NAME = { HCD: 'HC Davos', USC: 'U.S. Collegiate Selects' };
const other = tm => (tm === 'HCD' ? 'USC' : 'HCD');
const attackDir = (tm, p = 1) => (D.attack[String(p)] || D.attack['1'])[tm];
const minuteOf = e => (e.p - 1) * 20 + e.c / 60;

function nm(id) {
  const p = PL[id];
  if (!p) return 'ein Spieler';
  return `#${p.no} ${p.n.split(' ').slice(-1)[0]}`;
}

/* ------------------------------------------------------------------ *
 * Daten-Feed. Der Prototyp lädt den Final aus der CSV (ReplayFeed).
 * Für künftige Spiele liefert Wisehockey die Events im selben Format;
 * dann wird nur die Quelle ersetzt, die Erklärungen erscheinen live.
 * ------------------------------------------------------------------ */
class EventStore {
  constructor() {
    this.ev = [];
    this.tracks = new Map();
    this.puck = { T: [], X: [], Y: [] };
    this.onIdx = [];
    this.onG = [];
  }
  append(e) {
    const i = this.ev.length;
    this.ev.push(e);
    if (e.on) {
      this.onIdx.push(i);
      this.onG.push(e.g);
      for (const [id, x, y] of e.on) {
        let t = this.tracks.get(id);
        if (!t) this.tracks.set(id, (t = { T: [], X: [], Y: [] }));
        t.T.push(e.g); t.X.push(x); t.Y.push(y);
      }
    }
    if (e.s) this.addPuck(e.g, e.s[0], e.s[1]);
    if (e.ty === 'Goal' && e.tm) {
      const shot = this.lastShotBefore(i);
      const y = shot && shot.s ? clamp(shot.s[1] * 0.1, -0.6, 0.6) : 0;
      this.addPuck(e.g - 0.05, attackDir(e.tm, e.p) * 26.4, y);
    }
  }
  addPuck(g, x, y) {
    const P = this.puck;
    let k = P.T.length;
    while (k > 0 && P.T[k - 1] > g) k--;
    P.T.splice(k, 0, g); P.X.splice(k, 0, x); P.Y.splice(k, 0, y);
  }
  lastShotBefore(i) {
    for (let k = i; k >= 0 && this.ev[i].g - this.ev[k].g < 8; k--) {
      if (this.ev[k].ty === 'Shot' && this.ev[k].res === 'Goal') return this.ev[k];
    }
    return null;
  }
  playersAt(g) {
    let lo = 0, hi = this.onG.length - 1, r = -1;
    while (lo <= hi) { const m = (lo + hi) >> 1; if (this.onG[m] <= g) { r = m; lo = m + 1; } else hi = m - 1; }
    if (r < 0) return [];
    const e = this.ev[this.onIdx[r]];
    if (g - e.g > 6) return [];
    const out = [];
    for (const [id] of e.on) {
      const p = interp(this.tracks.get(id), g, 6);
      if (p) out.push({ id, x: p[0], y: p[1] });
    }
    return out;
  }
  puckAt(g) { return interp(this.puck, g, 3, true); }
}

function interp(tr, t, maxGap, strict) {
  if (!tr || !tr.T.length) return null;
  const T = tr.T;
  let lo = 0, hi = T.length - 1, k = -1;
  while (lo <= hi) { const m = (lo + hi) >> 1; if (T[m] <= t) { k = m; lo = m + 1; } else hi = m - 1; }
  if (k < 0) return T[0] - t < 0.4 ? [tr.X[0], tr.Y[0]] : null;
  if (k === T.length - 1) return t - T[k] < 1.5 ? [tr.X[k], tr.Y[k]] : null;
  const dt = T[k + 1] - T[k];
  if (dt > maxGap) {
    if (strict && t - T[k] > 1.2) return null;
    return [tr.X[k], tr.Y[k]];
  }
  const f = dt > 0 ? (t - T[k]) / dt : 0;
  return [tr.X[k] + (tr.X[k + 1] - tr.X[k]) * f, tr.Y[k] + (tr.Y[k + 1] - tr.Y[k]) * f];
}

class ReplayFeed {
  constructor(events, store) { events.forEach(e => store.append(e)); }
}

const store = new EventStore();
new ReplayFeed(D.events, store);
const EV = store.ev;
const SHOTS = EV.filter(e => e.ty === 'Shot');
const GOALS = EV.map((e, i) => [e, i]).filter(([e]) => e.ty === 'Goal');
const SKATERS = Object.entries(PL).filter(([, p]) => !p.gk).map(([id, p]) => ({ id, ...p }));
const teamSum = (tm, k) => SKATERS.filter(p => p.tm === tm).reduce((s, p) => s + p[k], 0);

function scoreAt(g) {
  const s = { USC: 0, HCD: 0 };
  for (const [e] of GOALS) if (e.g <= g) s[e.tm]++;
  return s;
}

/* ------------------------------------------------------------------ *
 * Zustand (nur im Browser gespeichert)
 * ------------------------------------------------------------------ */
const KEY = 'hv_proto_v2';
const S = (() => {
  const base = { watched: {}, entered: false, best: 0 };
  try { return Object.assign(base, JSON.parse(localStorage.getItem(KEY) || '{}')); } catch { return base; }
})();
function save() { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch { /* privater Modus */ } }

function toast(html) {
  $$('.toast').forEach(t => t.remove());
  const t = document.createElement('div');
  t.className = 'toast';
  t.innerHTML = html;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2400);
}
function modal(html) {
  const m = document.createElement('div');
  m.className = 'modal';
  m.innerHTML = `<div class="box"><div class="grab"></div>${html}<button class="btn sec" style="margin-top:16px" data-close>${tr('Schliessen', 'Close')}</button></div>`;
  m.addEventListener('click', ev => { if (ev.target === m || ev.target.hasAttribute('data-close')) m.remove(); });
  document.body.appendChild(m);
  return m;
}

/* ------------------------------------------------------------------ *
 * Schiri-Zeichen (vereinfachte Piktogramme nach IIHF-Handzeichen)
 * ------------------------------------------------------------------ */
const SIG = (() => {
  // Piktogramme nach den IIHF-Handzeichen, animiert: Ein Schiri-Zeichen ist eine Bewegung.
  // Ansicht von vorne: Die rechte Hand des Schiris (Pfeifenhand) ist für uns links.
  // Hauptschiedsrichter mit orangem Armband, Linienrichter ohne. Stock in Braun als Lesehilfe.
  const SKIN = '#F3D2B5', INK = '#111827', MOVE = '#F59E0B', BAND = '#F97316', STICK = '#8B5E34';
  const RS = [37, 32], LS = [63, 32]; // rechte / linke Schulter des Schiris (von vorne gesehen)
  const pts = a => a.map(p => p.join(',')).join(' ');
  const SPL = 'calcMode="spline" keyTimes="0;.5;1" keySplines=".45 0 .55 1;.45 0 .55 1" repeatCount="indefinite"';
  // startet in der Zeichen-Pose (B), geht zurück und wieder hin
  const an = (attr, A, B, dur) => `<animate attributeName="${attr}" values="${B};${A};${B}" dur="${dur}s" ${SPL}/>`;
  // arm(Pose, Armband?, Zielpose, Dauer): ohne Zielpose statisch, sonst pendelt der Arm zwischen beiden Posen
  function arm(a, band, b, dur = 1.4) {
    const end = x => x[x.length - 1];
    const f = (x, t) => [x[0][0] + (x[1][0] - x[0][0]) * t, x[0][1] + (x[1][1] - x[0][1]) * t];
    const mv = (attr, va, vb) => (b ? an(attr, va, vb, dur) : '');
    const poly = (w, c) => `<polyline points="${pts(a)}" fill="none" stroke="${c}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round">${mv('points', pts(a), b && pts(b))}</polyline>`;
    let band_ = '';
    if (band) {
      const A1 = f(a, 0.32), A2 = f(a, 0.66), B1 = b ? f(b, 0.32) : A1, B2 = b ? f(b, 0.66) : A2;
      band_ = `<line x1="${A1[0]}" y1="${A1[1]}" x2="${A2[0]}" y2="${A2[1]}" stroke="${BAND}" stroke-width="9">${mv('x1', A1[0], B1[0])}${mv('y1', A1[1], B1[1])}${mv('x2', A2[0], B2[0])}${mv('y2', A2[1], B2[1])}</line>`;
    }
    const E = end(a), F = b ? end(b) : E;
    return poly(13, '#fff') + poly(8.5, INK) + band_ +
      `<circle cx="${E[0]}" cy="${E[1]}" r="5.6" fill="${SKIN}" stroke="${INK}" stroke-width="2.2">${mv('cx', E[0], F[0])}${mv('cy', E[1], F[1])}</circle>`;
  }
  const line = (d, w = 3.6, c = MOVE) => `<path d="${d}" fill="none" stroke="${c}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round"/>`;
  // Aufprall-Striche blinken im Takt der Bewegung (sichtbar, wenn die Hand trifft)
  const hit = (d, dur = 1.4) => `<path d="${d}" fill="none" stroke="${MOVE}" stroke-width="3.6" stroke-linecap="round" opacity="0"><animate attributeName="opacity" values="1;0;0;0;1" keyTimes="0;.12;.88;.95;1" dur="${dur}s" repeatCount="indefinite"/></path>`;
  const stick = (x1, y1, x2, y2, dx = 0, dur = 1.4) => `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${STICK}" stroke-width="4.5" stroke-linecap="round">${dx ? an('x1', x1, x1 + dx, dur) + an('x2', x2, x2 + dx, dur) : ''}</line>`;
  const svg = body => `<svg viewBox="-5 -9 110 110" width="100%" height="100%"><defs><pattern id="ref-st" width="7" height="10" patternUnits="userSpaceOnUse"><rect width="3.5" height="10" fill="${INK}"/><rect x="3.5" width="3.5" height="10" fill="#fff"/></pattern></defs>${body}</svg>`;
  const torso = `<path d="M45 64 L43 94 M55 64 L57 94" stroke="${INK}" stroke-width="8.5" stroke-linecap="round"/>
      <rect x="36" y="27" width="28" height="39" rx="7" fill="url(#ref-st)" stroke="${INK}" stroke-width="2"/>
      <circle cx="50" cy="15" r="10" fill="${SKIN}" stroke="${INK}" stroke-width="2"/><path d="M40 14a10 10 0 0 1 20 0z" fill="${INK}"/>`;
  const side = body => svg(`<path d="M48 64 L44 94 M53 64 L57 94" stroke="${INK}" stroke-width="8.5" stroke-linecap="round"/>
      <rect x="40" y="27" width="20" height="39" rx="7" fill="url(#ref-st)" stroke="${INK}" stroke-width="2"/>
      <circle cx="50" cy="15" r="10" fill="${SKIN}" stroke="${INK}" stroke-width="2"/><path d="M40 14a10 10 0 0 1 17 -5 L52 14z" fill="${INK}"/><circle cx="56" cy="14" r="1.4" fill="${INK}"/>` + body);
  const downR = [RS, [34, 49], [33, 63]], downL = [LS, [66, 49], [67, 63]];
  const upL = [LS, [65, 17], [66, 2]];
  const net = `<path d="M82 60 h15 v12 h-15 z M82 66 h15 M87 60 v12 M92 60 v12" fill="none" stroke="#D7192D" stroke-width="1.8"/>`;
  const blueLine = `<path d="M80 50 v40" stroke="#1D4ED8" stroke-width="4"/>`;

  return {
    // Tor: zeigt mit ausgestrecktem Arm ins Tor
    goal: svg(torso + net + arm(downR, true) + arm([LS, [70, 42], [78, 50]], true, [LS, [78, 42], [90, 52]])),
    // Kein Tor / aufgehoben: beide Arme schwingen auf Schulterhöhe seitlich vor dem Körper
    washout: svg(torso + arm([RS, [44, 40], [62, 36]], true, [RS, [21, 32], [5, 32]], 1.2) + arm([LS, [56, 40], [38, 36]], true, [LS, [79, 32], [95, 32]], 1.2)),
    // Icing (Linienrichter): Arme vor der oberen Brust verschränken
    icing: svg(torso + arm(downR, false, [RS, [27, 40], [64, 37]], 1.8) + arm(downL, false, [LS, [73, 46], [36, 46]], 1.8)),
    // Angezeigte Strafe: freie Hand gestreckt über den Kopf
    armup: svg(torso + arm(downR, true) + arm(downL, true, upL, 1.8)),
    // Abseits (Linienrichter): freier Arm hoch, ohne Armband
    offside: svg(torso + blueLine + arm(downR, false) + arm(downL, false, upL, 1.8)),
    // Stockschlag: Handkante schlägt auf den Unterarm der anderen Hand
    slash: svg(torso + arm([RS, [26, 47], [64, 47]], true) + arm([LS, [80, 20], [70, 10]], true, [LS, [75, 27], [55, 36]], 1.0) + hit('M47 30 L44 26 M56 28 L57 23', 1.0)),
    // Hoher Stock: beide Fäuste übereinander seitlich am Kopf, der Stock geht nach oben
    high: svg(torso + stick(74, -7, 74, 34) + arm([RS, [54, 32], [74, 30]], true, [RS, [54, 28], [74, 20]], 1.6) + arm([LS, [84, 30], [74, 18]], true, [LS, [84, 22], [74, 7]], 1.6)),
    // Crosscheck (Profil): Fäuste mit gestreckten Armen vor- und zurückstossen, Stock quer
    cross: side(stick(66, 35, 66, 49, 16, 1.0) + arm([[50, 32], [58, 44], [66, 42]], true, [[50, 32], [64, 42], [82, 42]], 1.0)),
    // Haken (Profil): mit beiden Armen zum Bauch ziehen
    hook: side(arm([[50, 32], [66, 44], [86, 48]], true, [[50, 32], [56, 50], [62, 54]], 1.3)),
    // Halten: mit der freien Hand das Handgelenk der Pfeifenhand vor der Brust umfassen
    hold: svg(torso + arm([RS, [30, 47], [56, 44]], true) + arm(downL, true, [LS, [70, 47], [50, 46]], 1.6)),
    // Beinstellen: mit der rechten Hand unterhalb des Knies seitlich aufs rechte Bein schlagen
    trip: svg(torso + arm([RS, [30, 48], [29, 64]], true, [RS, [31, 52], [38, 80]], 1.1) + arm(downL, true) + hit('M31 76 L26 73 M30 82 L24 83 M32 88 L27 92', 1.1)),
    // Ellbogencheck: mit der freien Hand auf den Ellbogen der Pfeifenhand tippen
    elbow: svg(torso + arm([RS, [20, 42], [40, 38]], true) + arm([LS, [64, 52], [46, 52]], true, [LS, [55, 54], [24, 45]], 0.9) + hit('M14 36 L10 32 M13 44 L8 45 M16 51 L12 55', 0.9)),
    // Check gegen die Bande: Faust in die offene Handfläche schlagen
    board: svg(torso + arm([LS, [72, 56], [55, 56]], true) + `<ellipse cx="55" cy="56" rx="11" ry="4" fill="${SKIN}" stroke="${INK}" stroke-width="2.2"/>` + arm([RS, [26, 36], [50, 24]], true, [RS, [27, 46], [54, 50]], 1.0) + hit('M44 50 L40 47 M66 50 L70 47', 1.0)),
  };
})();

const SIGNALS = [
  { id: 'goal', name: tr('Tor', 'Goal'), text: tr('Der Schiri zeigt mit ausgestrecktem Arm auf das Tor: Der Treffer zählt.', 'The referee points at the net with an outstretched arm: the goal counts.') },
  { id: 'washout', name: tr('Kein Tor / aufgehoben', 'No goal / washed out'), text: tr('Beide Arme seitlich auf Schulterhöhe ausgestreckt, Handflächen nach unten. Das Tor zählt nicht, oder ein angezeigtes Icing bzw. Abseits ist aufgehoben.', 'Both arms swung out to the side at shoulder height, palms down. The goal does not count, or a pending icing or offside is cancelled.') },
  { id: 'icing', name: 'Icing', text: tr('Der Linienrichter verschränkt die Arme vor der Brust. Der Puck wurde aus der eigenen Hälfte unberührt über die gegnerische Torlinie geschossen.', 'The linesman folds his arms across the upper chest. The puck was shot from the own half across the opponent’s goal line, untouched.') },
  { id: 'offside', name: tr('Abseits', 'Offside'), text: tr('Der Linienrichter hebt den freien Arm. Ein Angreifer war vor dem Puck über der blauen Linie. Spielt das Team den Puck zurück, senkt er den Arm wieder.', 'The linesman raises his free arm. An attacker crossed the blue line ahead of the puck. If the team clears the zone, he lowers the arm again.') },
  { id: 'armup', name: tr('Angezeigte Strafe', 'Delayed penalty'), text: tr('Der Schiri streckt den freien Arm hoch: Ein Foul ist passiert. Gepfiffen wird erst, wenn das foulende Team den Puck berührt.', 'The referee raises his free arm straight up: a foul happened. Play is stopped once the offending team touches the puck.') },
  { id: 'slash', name: tr('Stockschlag', 'Slashing'), text: tr('Mit einer Hand auf den Unterarm der anderen Hand schlagen. Ein Spieler hat mit dem Stock auf den Gegner geschlagen.', 'A chopping motion onto the opposite forearm. A player hit the opponent with the stick.') },
  { id: 'high', name: tr('Hoher Stock', 'High-sticking'), text: tr('Beide Fäuste übereinander seitlich am Kopf. Der Stock war über Schulterhöhe.', 'Both fists held one above the other at the side of the head. The stick was above shoulder height.') },
  { id: 'cross', name: 'Crosscheck', text: tr('Beide Fäuste mit gestreckten Armen vor der Brust, vor und zurück gestossen. Der Gegner wurde mit dem quer gehaltenen Stock gestossen.', 'Both fists clenched, arms extended from the chest, pushed forward and back. The opponent was pushed with the stick held across.') },
  { id: 'hook', name: tr('Haken', 'Hooking'), text: tr('Mit beiden Armen eine Zieh-Bewegung zum Bauch. Ein Spieler hat den Gegner mit dem Stock zurückgehalten.', 'A pulling motion towards the stomach with both arms. A player held the opponent back with the stick.') },
  { id: 'hold', name: tr('Halten', 'Holding'), text: tr('Das Handgelenk der Pfeifenhand vor der Brust mit der anderen Hand umfassen. Der Gegner wurde festgehalten.', 'Clasping the wrist of the whistle hand in front of the chest. The opponent was held.') },
  { id: 'trip', name: tr('Beinstellen', 'Tripping'), text: tr('Mit der rechten Hand unterhalb des Knies seitlich aufs rechte Bein schlagen. Der Gegner wurde zu Fall gebracht.', 'Striking the side of the right leg below the knee with the right hand. The opponent was tripped.') },
  { id: 'elbow', name: tr('Ellbogencheck', 'Elbowing'), text: tr('Mit der Hand auf den Ellbogen des anderen Arms tippen. Der Gegner wurde mit dem Ellbogen gecheckt.', 'Tapping the elbow with the opposite hand. The opponent was checked with the elbow.') },
  { id: 'board', name: tr('Check gegen die Bande', 'Boarding'), text: tr('Mit der Faust in die offene Handfläche schlagen. Der Gegner wurde gefährlich in die Bande gecheckt.', 'Pounding the fist into the open palm. The opponent was checked dangerously into the boards.') },
];
const SIGMAP = Object.fromEntries(SIGNALS.map(s => [s.id, s]));
function openSignal(id) {
  const s = SIGMAP[id];
  modal(`<div class="bigsig">${SIG[id]}</div><div class="t2" style="text-align:center">${s.name}</div><p class="sub">${s.text}</p><div class="fn" style="text-align:center;margin-top:10px">${tr('Piktogramm vereinfacht', 'Simplified pictogram')}</div>`);
}
const sigTile = id => `<div class="sig" data-sig="${id}"><div class="pic">${SIG[id]}</div><div class="nm">${SIGMAP[id].name}</div></div>`;
document.addEventListener('click', ev => { const s = ev.target.closest('[data-sig]'); if (s) openSignal(s.dataset.sig); });

/* ------------------------------------------------------------------ *
 * Rink-Darstellung (IIHF-Feld 60 × 30 m, Koordinaten in Metern, Mitte = 0/0)
 * ------------------------------------------------------------------ */
class Rink {
  constructor(canvas) {
    this.c = canvas;
    this.ctx = canvas.getContext('2d');
    this.last = [];
    this.w = 0;
    canvas.addEventListener('click', ev => this.onClick(ev));
  }
  fit() {
    const w = this.c.parentElement.clientWidth;
    if (!w || w === this.w) return;
    this.w = w;
    const dpr = window.devicePixelRatio || 1;
    this.pad = 6;
    this.k = (w - 2 * this.pad) / 60;
    this.h = Math.round(30 * this.k + 2 * this.pad);
    this.c.width = w * dpr; this.c.height = this.h * dpr;
    this.c.style.height = this.h + 'px';
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  X(x) { return this.pad + (x + 30) * this.k; }
  Y(y) { return this.pad + (15 - y) * this.k; }
  ice(opt = {}) {
    const { ctx, k } = this;
    ctx.clearRect(0, 0, this.w, this.h);
    const r = 8.5 * k;
    const x0 = this.X(-30), y0 = this.Y(15), W = 60 * k, H = 30 * k;
    ctx.save();
    ctx.beginPath(); ctx.roundRect(x0, y0, W, H, r); ctx.fillStyle = '#eef4fa'; ctx.fill();
    ctx.clip();
    const vline = (x, col, wd) => { ctx.fillStyle = col; ctx.fillRect(this.X(x) - wd * k / 2, y0, wd * k, H); };
    const left = attackDir('HCD') < 0; // HCD greift nach links an
    if (opt.zones) {
      ctx.fillStyle = 'rgba(29,78,216,.16)'; ctx.fillRect(x0, y0, (30 - 7.14) * k, H);
      ctx.fillStyle = 'rgba(148,163,184,.12)'; ctx.fillRect(this.X(-7.14), y0, 14.28 * k, H);
      ctx.fillStyle = 'rgba(220,38,38,.16)'; ctx.fillRect(this.X(7.14), y0, (30 - 7.14) * k, H);
    } else {
      ctx.fillStyle = 'rgba(29,78,216,.05)'; ctx.fillRect(x0, y0, (30 - 7.14) * k, H);
      ctx.fillStyle = 'rgba(220,38,38,.05)'; ctx.fillRect(this.X(7.14), y0, (30 - 7.14) * k, H);
    }
    if (opt.blue) { vline(-7.14, 'rgba(250,204,21,.55)', 1.4); vline(7.14, 'rgba(250,204,21,.55)', 1.4); }
    if (opt.goalLine) { vline(-26, 'rgba(250,204,21,.6)', 0.9); vline(26, 'rgba(250,204,21,.6)', 0.9); }
    vline(0, '#d33', 0.3); vline(-7.14, '#2b59c3', 0.3); vline(7.14, '#2b59c3', 0.3);
    vline(-26, '#d33', 0.06); vline(26, '#d33', 0.06);
    ctx.lineWidth = Math.max(1, 0.06 * k);
    const circ = (x, y, rr, col) => { ctx.beginPath(); ctx.arc(this.X(x), this.Y(y), rr * k, 0, 7); ctx.strokeStyle = col; ctx.stroke(); };
    const dot = (x, y, col) => { ctx.beginPath(); ctx.arc(this.X(x), this.Y(y), 0.3 * k, 0, 7); ctx.fillStyle = col; ctx.fill(); };
    circ(0, 0, 4.5, '#2b59c3'); dot(0, 0, '#2b59c3');
    for (const sx of [-1, 1]) {
      for (const sy of [-1, 1]) { circ(sx * 20, sy * 7, 4.5, '#d33'); dot(sx * 20, sy * 7, '#d33'); dot(sx * 5.6, sy * 7, '#d33'); }
      ctx.beginPath(); ctx.moveTo(this.X(sx * 26), this.Y(1.8));
      ctx.arc(this.X(sx * 26), this.Y(0), 1.8 * k, sx > 0 ? Math.PI / 2 : -Math.PI / 2, sx > 0 ? 1.5 * Math.PI : Math.PI / 2);
      ctx.closePath(); ctx.fillStyle = 'rgba(96,165,250,.35)'; ctx.fill();
      ctx.strokeStyle = '#d33'; ctx.strokeRect(Math.min(this.X(sx * 26), this.X(sx * 27.1)), this.Y(0.915), 1.1 * k, 1.83 * k);
    }
    ctx.restore();
    ctx.beginPath(); ctx.roundRect(x0, y0, W, H, r); ctx.strokeStyle = '#7c8aa5'; ctx.lineWidth = 2; ctx.stroke();
    ctx.font = `700 ${Math.max(9, 1.3 * k)}px -apple-system,sans-serif`;
    ctx.fillStyle = 'rgba(15,23,42,.45)'; ctx.textAlign = 'center'; ctx.textBaseline = 'alphabetic';
    const lx = left ? -1 : 1;
    if (opt.zones) {
      ctx.fillStyle = 'rgba(15,23,42,.7)';
      ctx.fillText(tr('Angriffszone HCD', 'HCD attacking zone'), this.X(lx * 18.5), this.Y(12.4));
      ctx.fillText(tr('Neutrale Zone', 'Neutral zone'), this.X(0), this.Y(12.4));
      ctx.fillText(tr('Angriffszone USC', 'USC attacking zone'), this.X(-lx * 18.5), this.Y(12.4));
    }
    ctx.fillStyle = 'rgba(15,23,42,.45)';
    ctx.fillText(tr('Tor USC', 'USC net'), this.X(lx * 23.5), this.Y(-12.6));
    ctx.fillText(tr('Tor HCD', 'HCD net'), this.X(-lx * 23.5), this.Y(-12.6));
  }
  arrow(a, b) {
    const { ctx } = this;
    ctx.save(); ctx.strokeStyle = 'rgba(234,179,8,.95)'; ctx.lineWidth = 2.5; ctx.setLineDash([6, 5]);
    ctx.beginPath(); ctx.moveTo(this.X(a[0]), this.Y(a[1])); ctx.lineTo(this.X(b[0]), this.Y(b[1])); ctx.stroke();
    ctx.setLineDash([]);
    const ang = Math.atan2(this.Y(b[1]) - this.Y(a[1]), this.X(b[0]) - this.X(a[0]));
    ctx.beginPath(); ctx.moveTo(this.X(b[0]), this.Y(b[1]));
    ctx.lineTo(this.X(b[0]) - 10 * Math.cos(ang - 0.4), this.Y(b[1]) - 10 * Math.sin(ang - 0.4));
    ctx.lineTo(this.X(b[0]) - 10 * Math.cos(ang + 0.4), this.Y(b[1]) - 10 * Math.sin(ang + 0.4));
    ctx.closePath(); ctx.fillStyle = 'rgba(234,179,8,.95)'; ctx.fill(); ctx.restore();
  }
  draw(g, opt = {}) {
    this.fit();
    if (!this.w) return;
    const { ctx, k } = this;
    this.ice(opt);
    if (opt.arrow) this.arrow(opt.arrow[0], opt.arrow[1]);
    ctx.save(); ctx.strokeStyle = 'rgba(15,23,42,.35)'; ctx.lineWidth = 2; ctx.beginPath();
    let started = false;
    for (let t = g - 1.2; t <= g; t += 0.06) {
      const p = store.puckAt(t);
      if (!p) { started = false; continue; }
      if (!started) { ctx.moveTo(this.X(p[0]), this.Y(p[1])); started = true; } else ctx.lineTo(this.X(p[0]), this.Y(p[1]));
    }
    ctx.stroke(); ctx.restore();
    const r = Math.max(7, 1.05 * k);
    this.last = [];
    const players = store.playersAt(g);
    for (const p of players) {
      const info = PL[p.id] || {};
      const [fill, num] = TEAM_COL[info.tm] || ['#666', '#fff'];
      const X = this.X(p.x), Y = this.Y(p.y);
      if (opt.ring === p.id) { ctx.beginPath(); ctx.arc(X, Y, r + 5, 0, 7); ctx.strokeStyle = '#eab308'; ctx.lineWidth = 3.5; ctx.stroke(); }
      ctx.beginPath(); ctx.arc(X, Y, r, 0, 7); ctx.fillStyle = fill; ctx.fill();
      ctx.lineWidth = info.gk ? 3 : 1.5; ctx.strokeStyle = info.gk ? '#111827' : 'rgba(255,255,255,.9)'; ctx.stroke();
      ctx.fillStyle = num; ctx.font = `800 ${Math.round(r * 1.05)}px -apple-system,sans-serif`;
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(info.no ?? '', X, Y + 0.5);
      this.last.push({ id: p.id, X, Y, r });
    }
    const pk = store.puckAt(g);
    if (pk) {
      ctx.beginPath(); ctx.arc(this.X(pk[0]), this.Y(pk[1]), Math.max(3.5, 0.4 * k), 0, 7);
      ctx.fillStyle = '#0b0b0b'; ctx.fill(); ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.5; ctx.stroke();
    }
    if (opt.counts) {
      const n = { USC: 0, HCD: 0 };
      players.forEach(p => { const i = PL[p.id]; if (i && !i.gk) n[i.tm]++; });
      const label = `${tr('Feldspieler', 'Skaters')}  USC ${n.USC} : ${n.HCD} HCD`;
      ctx.font = `800 ${Math.max(11, 1.4 * k)}px -apple-system,sans-serif`;
      const w = ctx.measureText(label).width + 16;
      ctx.fillStyle = 'rgba(11,18,32,.85)'; ctx.beginPath(); ctx.roundRect(this.w / 2 - w / 2, this.pad + 4, w, 22, 8); ctx.fill();
      ctx.fillStyle = '#facc15'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(label, this.w / 2, this.pad + 15);
    }
  }
  onClick(ev) {
    const b = this.c.getBoundingClientRect();
    const x = ev.clientX - b.left, y = ev.clientY - b.top;
    let best = null, bd = 1e9;
    for (const p of this.last) { const d = Math.hypot(p.X - x, p.Y - y); if (d < p.r * 1.8 && d < bd) { bd = d; best = p; } }
    if (best) openPlayer(best.id);
  }
}


/* ------------------------------------------------------------------ *
 * Icons (eine Linienstärke, eine Bildsprache)
 * ------------------------------------------------------------------ */
const ICON = (() => {
  const w = d => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
  return {
    home: w('<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"/>'),
    learn: w('<path d="M2.5 6c3.2-1.6 6.3-1.6 9.5 0v13c-3.2-1.6-6.3-1.6-9.5 0zM21.5 6c-3.2-1.6-6.3-1.6-9.5 0v13c3.2-1.6 6.3-1.6 9.5 0z"/>'),
    report: w('<path d="M4 20V11M10 20V5M16 20v-6M21 20H3"/>'),
    game: w('<path d="M8 4h8v5a4 4 0 0 1-8 0zM8 6H5a3 3 0 0 0 3 3M16 6h3a3 3 0 0 1-3 3M12 13v4M8 20h8"/>'),
    spick: w('<circle cx="9" cy="14" r="5.5"/><path d="M13 10.5 21 7v4l-6.3 1.6M9 14h.01"/>'),
    play: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M7 4.5v15l12.5-7.5z"/></svg>',
    pause: '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4.5" width="4" height="15" rx="1"/><rect x="14" y="4.5" width="4" height="15" rx="1"/></svg>',
    replay: w('<path d="M4 12a8 8 0 1 0 2.4-5.7M4 4v4h4"/>'),
  };
})();
$$('[data-icon]').forEach(el => (el.innerHTML = ICON[el.dataset.icon] || ''));

function openPlayer(id) {
  const p = PL[id];
  if (!p) return;
  const [fill, num] = TEAM_COL[p.tm];
  const rows = p.gk ? [['Position', tr('Torhüter', 'Goalie')]] : [
    ['Top-Speed', `${p.spd.toFixed(1)} km/h`], [tr('Härtester Schuss', 'Hardest shot'), p.sht ? `${p.sht.toFixed(0)} km/h` : '–'],
    [tr('Gelaufene Distanz', 'Distance skated'), `${(p.dist / 1000).toFixed(1)} km`], [tr('Eiszeit', 'Ice time'), `${Math.round(p.toi / 60)} min`],
    [tr('Tore / Assists', 'Goals / assists'), `${p.g} / ${p.a}`],
  ];
  modal(`<div class="row"><span class="badge" style="width:48px;height:48px;font-size:17px;background:${fill};color:${num}">${p.no}</span>
    <div><div class="t2" style="margin:0">${p.n}</div><div class="fn">${TEAM_NAME[p.tm]}</div></div></div>
    <div class="group" style="background:var(--fill);margin-top:16px">${rows.map(([k, v]) => `<div class="cell" style="min-height:48px"><span class="grow sub">${k}</span><span class="val">${v}</span></div>`).join('')}</div>`);
}

/* ------------------------------------------------------------------ *
 * Tor-Szenen mit Erklär-Momenten
 * ------------------------------------------------------------------ */
function situationText(shot, goal) {
  const tm = goal.tm;
  if (shot.hg === false && shot.ag === false)
    return { x: 'Beide Torhüter sind vom Eis: USC will mit einem sechsten Feldspieler den Anschluss, HCD hat wegen einer angezeigten Strafe ebenfalls einen Extra-Spieler drauf.', tag: 'Leeres Tor' };
  const emptyTeam = shot.hg === false ? 'USC' : shot.ag === false ? 'HCD' : null;
  if (emptyTeam) return { x: `${emptyTeam} hat den Torhüter vom Eis genommen. Das Tor ist leer.`, tag: 'Leeres Tor' };
  if (shot.sty === 'AwayPowerplay' || shot.sty === 'HomePowerplay') {
    const pp = shot.sty === 'AwayPowerplay' ? 'HCD' : 'USC';
    return { x: `Powerplay für ${pp}: ${other(pp)} hat eine Strafe kassiert und spielt mit einem Mann weniger.`, tag: 'Powerplay' };
  }
  return { x: `5 gegen 5. ${tm} greift an, das Tor von ${other(tm)} ist ${attackDir(tm) < 0 ? 'links' : 'rechts'}.`, tag: '5 gegen 5' };
}

const SCENES = GOALS.map(([goal, gi], n) => {
  let si = gi;
  for (let k = gi; k >= 0 && goal.g - EV[k].g < 8; k--) if (EV[k].ty === 'Shot' && EV[k].res === 'Goal') { si = k; break; }
  const shot = EV[si];
  let start = shot.g - 20, fi = -1;
  for (let k = si; k >= 0 && shot.g - EV[k].g <= 30; k--) if (EV[k].ty === 'Faceoff') { fi = k; break; }
  if (fi >= 0) start = Math.min(EV[fi].g - 0.3, shot.g - 8);
  const end = goal.g + 2.5, tm = goal.tm, kp = [];
  const sit = situationText(shot, goal);
  kp.push({ g: start, k: 'Die Situation', x: sit.x });
  if (fi >= 0 && EV[fi].g > start) kp.push({ g: EV[fi].g + 0.1, k: 'Bully', x: `${nm(EV[fi].pl)} gewinnt das Bully für ${EV[fi].tm}.`, ring: EV[fi].pl });
  let entry = null;
  for (let k = si; k > 0 && EV[k].g >= start; k--) {
    const e = EV[k];
    if (e.ty === 'BluelineCrossing' && e.tm === tm && e.bld === 'TowardsOpponent' && e.blr !== 'PossessionLost') { entry = e; break; }
  }
  if (entry) kp.push({ g: entry.g, k: 'Blaue Linie', ring: entry.pl, x: `${nm(entry.pl)} bringt den Puck in die Angriffszone.` });
  const passes = [];
  for (let k = si - 1; k > 0 && shot.g - EV[k].g < 7 && passes.length < 2; k--) {
    const e = EV[k];
    if (e.ty === 'Pass' && e.tm === tm && e.res === 'Successful' && e.pl2 && (!entry || e.g > entry.g)) passes.unshift(e);
  }
  for (const p of passes) kp.push({ g: p.g, k: 'Pass', x: `${nm(p.pl)} passt auf ${nm(p.pl2)}.`, ring: p.pl2, arrow: p.s && p.e ? [p.s, p.e] : null });
  let sx;
  if (shot.xg == null) sx = `${nm(shot.pl)} schiesst aus der eigenen Hälfte, rund ${Math.round(Math.abs(attackDir(tm) * 26 - shot.s[0]))} Meter weit, ins leere Tor.`;
  else if (shot.spd > 0) sx = `${nm(shot.pl)} schiesst mit ${shot.spd.toFixed(0)} km/h. Torchance: ${pct(shot.xg)}.`;
  else sx = `${nm(shot.pl)} lenkt den Puck vor dem Tor ab. Torchance: ${pct(shot.xg)}.`;
  kp.push({ g: shot.g - 0.05, k: 'Schuss', x: sx, ring: shot.pl });
  const sc = scoreAt(goal.g);
  const ast = [goal.a1, goal.a2].filter(Boolean).map(nm);
  kp.push({ g: goal.g, k: 'Tor', x: `${nm(goal.pl)} trifft${ast.length ? `, Assist ${ast.join(' und ')}` : ''}. ${sc.USC}:${sc.HCD}.`, ring: goal.pl });
  kp.sort((a, b) => a.g - b.g);
  return { n, goal, shot, start, end, kp, tm, sc, tag: sit.tag };
});
// Die Situation steht vor dem Abspielen da, damit man sie in Ruhe lesen kann
const sceneClip = (sc, extra = {}) => ({ from: sc.start, to: sc.end, intro: sc.kp[0], caps: sc.kp.slice(1), ...extra });

/* ------------------------------------------------------------------ *
 * Navigation
 * ------------------------------------------------------------------ */
const views = {};
let active = 'learn';
function show(v) {
  if (views[active] && views[active].leave) views[active].leave();
  active = v;
  $$('.view').forEach(s => s.classList.toggle('active', s.id === `v-${v}`));
  $$('nav.tabs button').forEach(b => b.classList.toggle('on', b.dataset.v === v));
  window.scrollTo(0, 0);
  if (views[v] && views[v].enter) views[v].enter();
}
$$('nav.tabs button').forEach(b => (b.onclick = () => show(b.dataset.v)));
document.addEventListener('click', ev => { const g = ev.target.closest('[data-go]'); if (g) show(g.dataset.go); });

/* ------------------------------------------------------------------ *
 * Erklär-Animationen: schematische Mini-Szenen auf dem Eis.
 * Blau (A) greift nach links an, Rot (B) verteidigt – wie HCD gegen USC im Final.
 * ------------------------------------------------------------------ */
class Schematic extends Rink {
  pos(path, t) {
    if (t <= path[0][0]) return [path[0][1], path[0][2]];
    for (let i = 1; i < path.length; i++) {
      const [t1, x1, y1] = path[i], [t0, x0, y0] = path[i - 1];
      if (t <= t1) { const f = t1 > t0 ? (t - t0) / (t1 - t0) : 1; return [x0 + (x1 - x0) * f, y0 + (y1 - y0) * f]; }
    }
    const l = path[path.length - 1];
    return [l[1], l[2]];
  }
  pill(text, tone, y) {
    const { ctx } = this;
    ctx.font = `600 ${Math.max(12, 1.45 * this.k)}px -apple-system,sans-serif`;
    const w = ctx.measureText(text).width + 20, h = Math.max(24, 2.4 * this.k);
    ctx.fillStyle = tone === 'bad' ? '#B91C1C' : tone === 'ok' ? '#15803D' : 'rgba(14,26,43,.9)';
    ctx.beginPath(); ctx.roundRect(this.w / 2 - w / 2, y, w, h, h / 2); ctx.fill();
    ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(text, this.w / 2, y + h / 2 + 0.5);
  }
  drawAnim(a, t) {
    this.fit();
    if (!this.w) return;
    const { ctx, k } = this;
    if (a.custom) { a.custom(this, t); return; }
    this.ice(a.opts || {});
    const area = (x0, y0, x1, y1, label) => {
      ctx.fillStyle = 'rgba(14,26,43,.08)'; ctx.fillRect(this.X(x0), this.Y(y1), (x1 - x0) * k, (y1 - y0) * k);
      ctx.strokeStyle = 'rgba(14,26,43,.35)'; ctx.lineWidth = 1; ctx.strokeRect(this.X(x0), this.Y(y1), (x1 - x0) * k, (y1 - y0) * k);
      ctx.fillStyle = 'rgba(14,26,43,.6)'; ctx.font = `600 ${Math.max(10, 1.1 * k)}px -apple-system,sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(label, this.X((x0 + x1) / 2), this.Y((y0 + y1) / 2));
    };
    if (a.box) area(-3.5, -14.8, 3.5, -11.6, tr('Strafbank', 'Penalty box'));
    if (a.bench) area(-14, 11.6, 2, 14.8, tr('Spielerbank', 'Bench'));
    for (const [t0, t1, x, y] of a.marks || []) {
      if (t < t0 || t > t1) continue;
      const r = (1.6 + Math.sin(t * 6) * 0.4) * k;
      ctx.beginPath(); ctx.arc(this.X(x), this.Y(y), r, 0, 7); ctx.strokeStyle = '#F5B800'; ctx.lineWidth = 3; ctx.stroke();
    }
    if (a.puck) {
      ctx.save(); ctx.strokeStyle = 'rgba(14,26,43,.3)'; ctx.lineWidth = 2; ctx.beginPath();
      for (let s = Math.max(0, t - 0.8); s <= t; s += 0.05) { const p = this.pos(a.puck, s); s === Math.max(0, t - 0.8) ? ctx.moveTo(this.X(p[0]), this.Y(p[1])) : ctx.lineTo(this.X(p[0]), this.Y(p[1])); }
      ctx.stroke(); ctx.restore();
    }
    const r = Math.max(7, 1.15 * k);
    for (const tok of a.tokens) {
      if (tok.from != null && t < tok.from) continue;
      if (tok.until != null && t > tok.until) continue;
      const [x, y] = this.pos(tok.p, t);
      const X = this.X(x), Y = this.Y(y);
      ctx.beginPath(); ctx.arc(X, Y, r, 0, 7);
      if (tok.c === 'R') {
        ctx.fillStyle = '#fff'; ctx.fill(); ctx.save(); ctx.clip();
        ctx.fillStyle = '#111827'; for (let sx = -r; sx < r; sx += r / 1.5) ctx.fillRect(X + sx, Y - r, r / 3, 2 * r);
        ctx.restore(); ctx.beginPath(); ctx.arc(X, Y, r, 0, 7); ctx.strokeStyle = '#F97316'; ctx.lineWidth = 2.5; ctx.stroke();
      } else {
        ctx.fillStyle = tok.c[0] === 'A' ? '#1D4ED8' : '#C8102E'; ctx.fill();
        ctx.lineWidth = tok.c.length > 1 ? 3 : 1.5; ctx.strokeStyle = tok.c.length > 1 ? '#111827' : '#fff'; ctx.stroke();
        if (tok.c.length > 1) { ctx.fillStyle = '#fff'; ctx.font = `800 ${Math.round(r)}px -apple-system,sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText('G', X, Y + 0.5); }
      }
      if (tok.hi && t >= tok.hi[0] && t <= tok.hi[1]) { ctx.beginPath(); ctx.arc(X, Y, r + 5, 0, 7); ctx.strokeStyle = '#F5B800'; ctx.lineWidth = 3; ctx.stroke(); }
    }
    if (a.puck) {
      const p = this.pos(a.puck, t);
      ctx.beginPath(); ctx.arc(this.X(p[0]), this.Y(p[1]), Math.max(3.5, 0.45 * k), 0, 7);
      ctx.fillStyle = '#0B0B0B'; ctx.fill(); ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.5; ctx.stroke();
    }
    const lab = (a.labels || []).find(([t0, t1]) => t >= t0 && t <= t1);
    if (lab) this.pill(lab[2], lab[3], this.pad + 6);
  }
}

// Standard-Aufstellung, damit jede Animation ein volles Feld zeigt
const still = (c, x, y) => ({ c, p: [[0, x, y]] });
const lineupB = () => [still('BG', -26.6, 0), still('B', -20, 6), still('B', -20, -6), still('B', -14, 1)];
const lineupA = () => [still('AG', 26.6, 0), still('A', 14, -5)];

const ANIM = {
  bully: { dur: 6, tokens: [
      still('R', 0, 3), { c: 'A', p: [[0, -1.3, 0], [2, -1.3, 0], [3.5, -6, -3]] }, { c: 'B', p: [[0, 1.3, 0]] },
      still('A', -5, 7), still('A', -5, -7), still('B', 5, 7), still('B', 5, -7), still('AG', 26.6, 0), still('BG', -26.6, 0)],
    puck: [[0, 0, 2], [1.4, 0, 2], [1.8, 0, 0], [2.2, 0, 0], [3.5, -7, -3.5]],
    labels: [[0, 1.8, tr('Der Schiri wirft den Puck ein', 'The referee drops the puck'), 'info'], [2.2, 6, tr('Blau gewinnt das Bully', 'Blue wins the faceoff'), 'ok']] },

  icing: { dur: 7, opts: { goalLine: true }, tokens: [
      { c: 'A', p: [[0, 14, -6]], hi: [0.4, 2.2] }, still('A', 8, 6), ...lineupA().slice(0, 1),
      { c: 'B', p: [[0, 4, -3], [3, 2, -6]] }, { c: 'B', p: [[0, 6, 8], [3, 3, 7]] }, still('BG', -26.6, 0)],
    puck: [[0, 13, -5.5], [1, 13, -5.5], [3.2, -29, 5]],
    marks: [[4.2, 7, 20, -7]],
    labels: [[0, 1, tr('Blau in der eigenen Hälfte', 'Blue in its own half'), 'info'], [1, 3.2, tr('Weitschuss übers ganze Feld …', 'A long shot across the ice …'), 'info'], [3.2, 4.2, tr('… über die Torlinie: Icing!', '… over the goal line: icing!'), 'bad'], [4.2, 7, tr('Bully vor dem eigenen Tor', 'Faceoff in front of the own net'), 'info']] },

  offside: { dur: 10, opts: { blue: true }, tokens: [
      { c: 'A', p: [[0, 3, -2], [3, -9, -2], [5, -9, -2], [5, 3, -2], [8, -9, -2]] },
      { c: 'A', p: [[0, -2, 6], [1.6, -11, 6], [5, -11, 6], [5, -2, 6], [6.6, -2, 6], [8.4, -11, 6]], hi: [0, 3] },
      ...lineupB()],
    puck: [[0, 2, -2.6], [3, -10, -2.6], [5, -10, -2.6], [5, 2, -2.6], [8, -10, -2.6]],
    labels: [[0, 1.4, tr('Achte auf die blaue Linie', 'Watch the blue line'), 'info'], [1.4, 4.9, tr('Abseits: Spieler vor dem Puck', 'Offside: player ahead of the puck'), 'bad'], [5, 6.8, tr('So ist es richtig …', 'This is how it works …'), 'info'], [6.8, 10, tr('Puck zuerst: korrekt', 'Puck first: onside'), 'ok']] },

  penalty: { dur: 8, box: true, tokens: [
      still('R', 2, 9), ...lineupA(), still('A', -10, -4), still('A', -6, 5), still('A', 2, -6),
      still('BG', -26.6, 0), still('B', -18, 5), still('B', -16, -6), still('B', -8, -2),
      { c: 'B', p: [[0, -4, 3], [2.5, -4, 3], [4.5, 0, -13.2]], hi: [1, 4.5] }],
    labels: [[0, 1.2, tr('Foul von Rot', 'Foul by red'), 'bad'], [1.2, 2.5, tr('Schiri hebt den Arm', 'Referee raises the arm'), 'info'], [2.5, 4.5, tr('Ab auf die Strafbank: 2 Minuten', 'Off to the box: 2 minutes'), 'info'], [4.5, 8, tr('Powerplay: 5 gegen 4 für Blau', 'Power play: 5 on 4 for blue'), 'ok']] },

  ppgoal: { dur: 8, box: true, tokens: [
      ...lineupA(), { c: 'A', p: [[0, -14, -7], [1.2, -15, -7]] }, { c: 'A', p: [[0, -18, 7], [1.2, -20, 4]], hi: [1, 2.6] }, still('A', -10, 1), still('A', -8, -9),
      still('BG', -26.6, 0), still('B', -20, -3), still('B', -16, 6), still('B', -12, -4),
      { c: 'B', p: [[0, 0, -13.2], [3.6, 0, -13.2], [6, 5, -6]], hi: [3.4, 6] }],
    puck: [[0, -14, -6.5], [1.2, -15, -6.5], [1.6, -20, 3.5], [2.2, -20, 3.5], [2.6, -26.5, 0.4]],
    labels: [[0, 2.6, tr('Blau im Powerplay', 'Blue on the power play'), 'info'], [2.6, 3.6, tr('Tor!', 'Goal!'), 'ok'], [3.6, 8, tr('Strafe vorbei: wieder 5 gegen 5', 'Penalty over: back to 5 on 5'), 'info']] },

  emptynet: { dur: 9, bench: true, tokens: [
      { c: 'BG', p: [[0, -26.6, 0], [0.6, -26.6, 0], [3, -8, 13.2]], until: 3 },
      { c: 'B', p: [[3, -4, 13.2], [5, 10, 5]], from: 3, hi: [3, 5] },
      still('B', 12, -4), still('B', 16, 7), still('B', 8, -9), still('B', 18, -1),
      { c: 'A', p: [[0, 14, -8]], hi: [5.2, 6.8] }, still('A', 20, 4), still('AG', 26.6, 0)],
    puck: [[0, 15, -8.3], [5.6, 15, -8.3], [7, -26.6, 0.2]],
    labels: [[0, 3, tr('Rot holt den Goalie vom Eis', 'Red pulls the goalie'), 'info'], [3, 5.4, tr('Dafür ein 6. Feldspieler', 'A 6th skater comes on'), 'info'], [5.4, 7, tr('Schuss aus der eigenen Hälfte …', 'A shot from the own half …'), 'info'], [7, 9, tr('… ins leere Tor!', '… into the empty net!'), 'ok']] },

  // Nahaufnahme der Torlinie: halb drüber zählt nicht
  goalline: { dur: 7, custom(s, t) {
    const { ctx } = s;
    const W = s.w, H = s.h;
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = '#EEF4FA'; ctx.fillRect(0, 0, W, H);
    const lx = W * 0.62;
    ctx.fillStyle = 'rgba(96,165,250,.35)'; ctx.beginPath(); ctx.arc(lx, H / 2, H * 0.34, Math.PI / 2, 1.5 * Math.PI); ctx.fill();
    ctx.fillStyle = '#C8102E'; ctx.fillRect(lx - 2, 0, 4, H);
    ctx.strokeStyle = '#C8102E'; ctx.lineWidth = 3; ctx.strokeRect(lx, H * 0.28, W * 0.12, H * 0.44);
    ctx.strokeStyle = 'rgba(200,16,46,.25)'; ctx.lineWidth = 1;
    for (let i = 1; i < 6; i++) { ctx.beginPath(); ctx.moveTo(lx + (W * 0.12 * i) / 6, H * 0.28); ctx.lineTo(lx + (W * 0.12 * i) / 6, H * 0.72); ctx.stroke(); }
    const pr = H * 0.07;
    const phase = t < 3.5 ? 0 : 1;
    const tt = phase ? t - 3.5 : t;
    const target = phase ? lx + pr * 1.6 : lx + pr * 0.2;
    const x = W * 0.2 + Math.min(1, tt / 1.2) * (target - W * 0.2);
    ctx.beginPath(); ctx.arc(x, H / 2, pr, 0, 7); ctx.fillStyle = '#0B0B0B'; ctx.fill();
    ctx.fillStyle = 'rgba(14,26,43,.55)'; ctx.font = `600 ${Math.max(11, H * 0.06)}px -apple-system,sans-serif`; ctx.textAlign = 'center';
    ctx.fillText(tr('Torlinie', 'Goal line'), lx, H - 10);
    if (tt > 1.3) s.pill(phase ? tr('Ganz über der Linie: Tor', 'Fully over the line: goal') : tr('Auf der Linie: kein Tor', 'On the line: no goal'), phase ? 'ok' : 'bad', 10);
  } },
};

/* ------------------------------------------------------------------ *
 * Tür 1: Mitschauen – der Final in Schlüsselmomenten.
 * Das Spiel hält an, sobald etwas passiert, das man wissen sollte,
 * und ein Popup erklärt es. Im Echtbetrieb lösen die Live-Events das aus.
 * ------------------------------------------------------------------ */
const icingDump = EV.find(e => e.ty === 'Dump' && e.dres === 'Icing' && e.s && e.e);
const icingStop = EV.find(e => e.stop === 'Icing' && e.g > icingDump.g);
const offside = EV.find(e => e.stop === 'Offside');
const offsideTeam = [...EV].reverse().find(e => e.g < offside.g && e.ty === 'BluelineCrossing' && e.bld === 'TowardsOpponent').tm;
const ppScene = SCENES.find(s => s.tag === 'Powerplay');
const ppPenalty = [...EV].reverse().find(e => e.ty === 'Penalty' && e.g < ppScene.shot.g);
const hsPenalty = EV.find(e => e.pen === 'HighSticking');
const hsDouble = EV.filter(e => e.ty === 'Penalty' && e.pl === hsPenalty.pl && e.c === hsPenalty.c).length > 1;
const walsh = SCENES.find(s => s.tm === 'USC');
const enScene = SCENES.find(s => s.tag === 'Leeres Tor');
const finalWhistle = EV[EV.length - 1];
const avgShift = Math.round(SKATERS.reduce((s, p) => s + p.avgs, 0) / SKATERS.length);

const MOMENTS = [
  { from: EV[0].g - 0.5, to: EV[0].g + 4, title: tr('Das Bully', 'The faceoff'), anim: 'bully', rule: 'Bully', ruleEn: 'Faceoff',
    why: tr('Jedes Drittel und jede Unterbrechung beginnt mit einem Bully.', 'Every period and every stoppage starts with a faceoff.'),
    seen: tr('Spielbeginn: Der Schiri wirft den Puck ein.', 'Start of the game: the referee drops the puck.'),
    text: tr(`Jedes Drittel und jede Unterbrechung startet mit einem Bully. Gespielt werden 3 × 20 Minuten, pro Team stehen 5 Feldspieler und ein Torhüter auf dem Eis. Gewechselt wird mitten im Spiel, ein Einsatz dauert nur rund ${avgShift} Sekunden.`,
      `Every period and every stoppage starts with a faceoff. A game has 3 × 20 minutes, each team has 5 skaters and a goalie on the ice. Lines change on the fly, a shift lasts only about ${avgShift} seconds.`) },
  { from: icingDump.g - 6, to: icingStop.g + 0.2, title: 'Icing', anim: 'icing', sig: 'icing', rule: 'Icing', ruleEn: 'Icing',
    why: tr('Puck aus der eigenen Hälfte unberührt über die gegnerische Torlinie: Bully vor dem eigenen Tor.', 'Puck from the own half untouched across the opponent’s goal line: faceoff in front of the own net.'),
    seen: tr(`${nm(icingDump.pl)} (${icingDump.tm}) hat den Puck aus der eigenen Hälfte bis hinter die gegnerische Torlinie geschossen.`, `${nm(icingDump.pl)} (${icingDump.tm}) shot the puck from the defensive half past the opponent’s goal line.`),
    text: tr('Ein Weitschuss aus der eigenen Hälfte über die gegnerische Torlinie, den niemand berührt, ist Icing. Die Folge: Bully vor dem eigenen Tor, und das Team darf vorher nicht wechseln. In Unterzahl ist der Befreiungsschlag erlaubt.',
      'A shot from the own half across the opponent’s goal line that nobody touches is icing. The faceoff then takes place in front of the own net, and the team may not change lines. A short-handed team is allowed to ice the puck.') },
  { from: ppPenalty.g - 9, to: ppPenalty.g + 0.2, title: tr('Strafe', 'Penalty'), anim: 'penalty', sig: 'slash', rule: 'Strafe', ruleEn: 'Penalty',
    why: tr('Stockschlag ist ein Foul: 2 Minuten auf die Strafbank, das andere Team spielt im Powerplay.', 'Slashing is a foul: 2 minutes in the box, the other team gets a power play.'),
    seen: tr(`${nm(ppPenalty.pl)} (${ppPenalty.tm}) hat mit dem Stock zugeschlagen.`, `${nm(ppPenalty.pl)} (${ppPenalty.tm}) slashed an opponent.`),
    text: tr(`Bei einem Foul hebt der Schiri den Arm und pfeift, sobald das foulende Team den Puck berührt. Der Spieler muss 2 Minuten auf die Strafbank, ${ppPenalty.tm} spielt in Unterzahl. Für ${other(ppPenalty.tm)} heisst das Powerplay.`,
      `After a foul the referee raises his arm and blows the whistle once the offending team touches the puck. The player sits 2 minutes in the penalty box, ${ppPenalty.tm} plays short-handed. For ${other(ppPenalty.tm)} that means a power play.`) },
  { from: ppPenalty.g + 0.5, to: ppScene.goal.g + 0.6, title: tr('Tor im Powerplay', 'Power-play goal'), anim: 'ppgoal', sig: 'goal', rule: 'Powerplay', ruleEn: 'Power play',
    why: tr('Fällt im Powerplay ein Tor, endet die Strafe sofort. Wieder 5 gegen 5.', 'A power-play goal ends the penalty at once. Back to 5 on 5.'),
    seen: tr(`${nm(ppScene.goal.pl)} trifft nur drei Sekunden nach dem Bully zum ${ppScene.sc.USC}:${ppScene.sc.HCD}.`, `${nm(ppScene.goal.pl)} scores only three seconds after the faceoff: ${ppScene.sc.USC}:${ppScene.sc.HCD}.`),
    text: tr('Trifft das Team im Powerplay, ist die 2-Minuten-Strafe sofort vorbei. Der bestrafte Spieler darf zurück aufs Eis, es steht wieder 5 gegen 5.',
      'If the team on the power play scores, the 2-minute penalty ends at once. The penalised player returns to the ice, it is 5 on 5 again.') },
  { from: walsh.shot.g - 12, to: walsh.goal.g + 0.6, title: tr('Wann zählt ein Tor?', 'When does a goal count?'), anim: 'goalline', sig: 'goal', rule: 'Torlinie', ruleEn: 'Goal line',
    why: tr('Ein Tor zählt nur, wenn der Puck ganz über der Linie ist.', 'A goal counts only when the puck is fully across the line.'),
    seen: tr(`${nm(walsh.goal.pl)} lenkt den Puck direkt vor dem Tor ab: ${walsh.sc.USC}:${walsh.sc.HCD}.`, `${nm(walsh.goal.pl)} deflects the puck right in front of the net: ${walsh.sc.USC}:${walsh.sc.HCD}.`),
    text: tr('Ein Tor zählt nur, wenn der Puck die Torlinie vollständig überquert hat. Liegt er auf der Linie, geht das Spiel weiter. In knappen Fällen prüfen die Schiris das Video.',
      'A goal counts only when the puck has fully crossed the goal line. If it is on the line, play goes on. In close cases the referees check the video.') },
  { from: offside.g - 10, to: offside.g + 0.2, title: tr('Abseits', 'Offside'), anim: 'offside', sig: 'offside', rule: 'Abseits', ruleEn: 'Offside',
    why: tr('Angreifer dürfen erst nach dem Puck über die blaue Linie.', 'Attackers may cross the blue line only after the puck.'),
    seen: tr(`Ein Angreifer von ${offsideTeam} war vor dem Puck in der Angriffszone.`, `A ${offsideTeam} forward entered the attacking zone ahead of the puck.`),
    text: tr('Angreifer dürfen die blaue Linie erst nach dem Puck überqueren. Ist einer zu früh in der Angriffszone, pfeift der Linienrichter ab. Das Bully gibt es dann ausserhalb der Zone.',
      'Attackers may cross the blue line only after the puck. If one is in the attacking zone too early, the linesman stops play. The faceoff then takes place outside the zone.') },
  { from: hsPenalty.g - 9, to: hsPenalty.g + 0.2, title: tr('Hoher Stock', 'High-sticking'), anim: 'penalty', sig: 'high', rule: 'Hoher Stock', ruleEn: 'High stick',
    why: tr('Der Stock über Schulterhöhe ist verboten: 2 Minuten, bei Verletzung 2+2.', 'A stick above shoulder height is not allowed: 2 minutes, 2+2 if someone is hurt.'),
    seen: tr(`${nm(hsPenalty.pl)} (${hsPenalty.tm}) hat einen Gegner mit dem Stock über Schulterhöhe getroffen.`, `${nm(hsPenalty.pl)} (${hsPenalty.tm}) hit an opponent with the stick above shoulder height.`),
    text: tr(`Der Stock war über Schulterhöhe. Das gibt normalerweise 2 Minuten, bei einer Verletzung 2+2 Minuten.${hsDouble ? ` ${nm(hsPenalty.pl)} bekam 2+2 Minuten.` : ''}`,
      `The stick was above shoulder height. That usually means 2 minutes, 2+2 minutes if the opponent is injured.${hsDouble ? ` ${nm(hsPenalty.pl)} got 2+2 minutes.` : ''}`) },
  { from: enScene.shot.g - 16, to: enScene.goal.g + 0.6, title: tr('Leeres Tor', 'Empty net'), anim: 'emptynet', rule: 'Leeres Tor', ruleEn: 'Empty net',
    why: tr('Wer zurückliegt, tauscht den Goalie gegen einen sechsten Feldspieler. Das Risiko: ein leeres Tor.', 'A trailing team swaps the goalie for a sixth skater. The risk: an empty net.'),
    seen: tr(`${nm(enScene.goal.pl)} trifft aus der eigenen Hälfte ins leere Tor: ${enScene.sc.USC}:${enScene.sc.HCD}.`, `${nm(enScene.goal.pl)} scores from the defensive half into the empty net: ${enScene.sc.USC}:${enScene.sc.HCD}.`),
    text: tr('Kurz vor Schluss nehmen Teams im Rückstand oft den Torhüter vom Eis und bringen einen sechsten Feldspieler. Mehr Angreifer, aber das eigene Tor ist leer.',
      'Late in the game, a trailing team often pulls the goalie for a sixth skater. More attackers, but their own net is empty.') },
  { from: finalWhistle.g - 8, to: finalWhistle.g, title: tr('Schlusspfiff', 'Final whistle'), end: true,
    why: tr('Nach 3 × 20 Minuten ist Schluss.', 'After 3 × 20 minutes the game is over.'),
    seen: tr('HC Davos gewinnt den Final 6:3 und den 97. Spengler Cup.', 'HC Davos wins the final 6:3 and the 97th Spengler Cup.'),
    text: tr('Du hast die wichtigsten Pfiffe an echten Szenen gesehen: Bully, Icing, Strafen, Powerplay, Tor, Abseits und das leere Tor. Damit verstehst du jeden Pfiff.',
      'You have seen the key whistles in real scenes: faceoff, icing, penalties, power play, goal, offside and the empty net. Now you understand every whistle.') },
];

// Regel-Sammlung: jede Regel wird beim ersten echten Pfiff dieser Art freigeschaltet
const RULES = MOMENTS.map((m, i) => ({ ...m, i })).filter(m => m.rule);
const learned = () => RULES.filter(r => (S.watched || {})[r.i]).length;
function renderRules() {
  const got = learned(), total = RULES.length;
  const chips = RULES.map(r => (S.watched || {})[r.i]
    ? `<span class="chip on">${tr(r.rule, r.ruleEn)}</span>`
    : '<span class="chip">?</span>').join('');
  const bar = `<div class="rulebar"><i style="width:${Math.round(got / total * 100)}%"></i></div>`;
  const head = `<div class="ruleshead"><b>${got}/${total}</b> ${tr('Regeln verstanden', 'rules understood')}</div>`;
  $('#rulesLive').innerHTML = head + bar + `<div class="chips">${chips}</div>`;
  $('#rulesList').innerHTML = head + bar + RULES.map(r => (S.watched || {})[r.i]
    ? `<details><summary>${tr(r.rule, r.ruleEn)}</summary><p>${r.text}</p></details>`
    : `<div class="cell locked"><span class="grow">?</span><span class="fn">${tr('Beim nächsten Pfiff dieser Art', 'At the next whistle of this kind')}</span></div>`).join('');
}

views.learn = (() => {
  const rink = new Rink($('#c-watch'));
  let mi = 0, t = MOMENTS[0].from, playing = false, pop = null;
  const seen = () => Object.keys(S.watched || {}).length;
  function strengthAt(g) {
    for (let k = lastIdx; k >= 0; k--) {
      const e = EV[k];
      if (e.g > g || e.hg === undefined) continue;
      if (e.hg === false && e.ag === false) return tr('Beide Tore leer', 'Both nets empty');
      if (e.hg === false) return tr('USC ohne Goalie', 'USC without goalie');
      if (e.ag === false) return tr('HCD ohne Goalie', 'HCD without goalie');
      if (e.sty === 'AwayPowerplay') return 'Powerplay HCD';
      if (e.sty === 'HomePowerplay') return 'Powerplay USC';
      return '';
    }
    return '';
  }
  let lastIdx = 0;
  function board() {
    while (lastIdx + 1 < EV.length && EV[lastIdx + 1].g <= t) lastIdx++;
    while (lastIdx > 0 && EV[lastIdx].g > t) lastIdx--;
    const e = EV[lastIdx], s = scoreAt(t);
    $('#wScore').innerHTML = `<span class="tm"><span class="dot" style="background:var(--usc)"></span>USC</span><span class="res">${s.USC}:${s.HCD}</span><span class="tm">HCD<span class="dot" style="background:var(--hcd)"></span></span>`;
    const st = strengthAt(t);
    $('#wClock').textContent = `${tr(`${e.p}. Drittel`, `Period ${e.p}`)} · ${fmtClock(e.c)}${st ? ' · ' + st : ''}`;
  }
  function dots() {
    // Live: Was als Nächstes passiert, ist unbekannt – also nichts ankündigen
    $('#wNext').innerHTML = `<span class="live"><i></i>LIVE</span> · ${playing ? tr('Spiel läuft', 'Game on') : tr('Pausiert', 'Paused')}`;
  }
  function load(i, autoplay) {
    mi = i; t = MOMENTS[i].from; dots(); board();
    setPlaying(!!autoplay);
  }
  function setPlaying(p) { playing = p; $('#wPlay').innerHTML = p ? ICON.pause : ICON.play; dots(); }
  $('#wPlay').onclick = () => setPlaying(!playing);

  function openPop() {
    const m = MOMENTS[mi];
    S.watched = S.watched || {}; const wasKnown = !!S.watched[mi]; S.watched[mi] = 1; save(); dots(); renderRules();
    if (window.HVAccount && HVAccount.current()) HVAccount.saveScore('learn-the-game', learned(), { rules: RULES.length });
    const el = document.createElement('div');
    el.className = 'modal';
    const last = mi + 1 >= MOMENTS.length;
    const isNew = m.rule && !wasKnown;
    const got = learned(), total = RULES.length;
    el.innerHTML = `<div class="box"><div class="grab"></div>
      <div class="pophead"><span class="fn">${tr('Pfiff', 'Whistle')} · ${$('#wClock').textContent}</span>
        ${isNew ? `<span class="newrule">${tr('Neue Regel', 'New rule')} · ${got}/${total}</span>` : ''}</div>
      <div class="t2" style="margin:6px 0 10px">${m.title}</div>
      <div class="qa"><span class="k">${tr('Was', 'What')}</span><span>${m.seen}</span></div>
      <div class="qa"><span class="k">${tr('Warum', 'Why')}</span><span class="hl">${m.why}</span></div>
      ${m.anim ? `<div class="rinkwrap" style="margin-top:14px"><canvas class="rink"></canvas></div>` : ''}
      ${m.sig ? `<button class="cell sigrow" data-sig="${m.sig}"><span class="sigpic">${SIG[m.sig]}</span><span class="grow"><span class="hl">${tr('So zeigt es der Schiri', 'The referee signal')}</span><br><span class="fn">${SIGMAP[m.sig].name}</span></span><span class="chev">›</span></button>` : ''}
      <details class="more"><summary>${tr('Mehr dazu', 'More')}</summary><p>${m.text}</p></details>
      ${last ? `<button class="btn" style="margin-top:18px" data-w="spick">${got === total ? tr('Alle Regeln ansehen', 'See all rules') : tr('Deine Regeln ansehen', 'See your rules')}</button><button class="linkbtn" data-w="restart">${tr('Nochmal von vorne', 'Start again')}</button>`
        : `<button class="btn" style="margin-top:18px" data-w="next">${tr('Weiter schauen', 'Keep watching')}</button><button class="linkbtn" data-w="again">${tr('Szene nochmal', 'Replay scene')}</button>`}
    </div>`;
    document.body.appendChild(el);
    pop = { el, sch: m.anim ? new Schematic($('canvas', el)) : null, a: ANIM[m.anim], t: 0 };
    el.addEventListener('click', ev => {
      const b = ev.target.closest('[data-w]');
      if (!b) return;
      close();
      if (b.dataset.w === 'next') load(mi + 1, true);
      else if (b.dataset.w === 'again') load(mi, true);
      else if (b.dataset.w === 'restart') { load(0, true); }
      else show(b.dataset.w);
    });
  }
  function close() { if (pop) { pop.el.remove(); pop = null; } }

  return {
    enter() {
      const first = MOMENTS.findIndex((m, i) => !(S.watched || {})[i]);
      if (!pop && !playing) load(first < 0 ? 0 : first, false);
    },
    leave() { setPlaying(false); close(); },
    // für Screenshots: direkt das Popup eines Moments zeigen
    _demo(i, animT) { load(i, false); t = MOMENTS[i].to; board(); openPop(); if (pop) pop.t = animT; },
    // für das Demovideo: Moment i live abspielen
    _play(i) { close(); load(i, true); },
    tick(dt) {
      if (playing && !pop) {
        t += dt;
        if (t >= MOMENTS[mi].to) { t = MOMENTS[mi].to; setPlaying(false); board(); openPop(); }
      }
      board();
      rink.draw(t);
      if (pop && pop.sch) { pop.t = (pop.t + dt) % pop.a.dur; pop.sch.drawAnim(pop.a, pop.t); }
    },
  };
})();

/* ------------------------------------------------------------------ *
 * Schiri-Spick und Begriffe
 * ------------------------------------------------------------------ */
$('#sigGrid').innerHTML = SIGNALS.map(s => sigTile(s.id)).join('');
renderRules();
const GLOSS = [
  ['Bully', 'Faceoff', 'Der Schiri wirft den Puck zwischen zwei Spieler ein. So beginnt jedes Drittel und jede Unterbrechung.', 'The referee drops the puck between two players. Every period and every stoppage starts this way.'],
  ['Powerplay und Unterzahl', 'Power play and short-handed', 'Nach einer Strafe spielt ein Team mit einem Mann mehr (Powerplay), das andere mit einem weniger (Unterzahl).', 'After a penalty one team plays with an extra skater (power play), the other with one fewer (short-handed).'],
  ['Icing', 'Icing', 'Puck aus der eigenen Hälfte über die gegnerische Torlinie, ohne Berührung. Bully vor dem eigenen Tor.', 'The puck goes from the own half across the opponent’s goal line untouched. Faceoff in front of the own net.'],
  ['Abseits', 'Offside', 'Ein Angreifer ist vor dem Puck über die blaue Linie gefahren. Bully ausserhalb der Zone.', 'An attacker crossed the blue line ahead of the puck. Faceoff outside the zone.'],
  ['Slot', 'Slot', 'Der Raum direkt vor dem Tor. Von hier fallen die meisten Tore.', 'The area right in front of the net. Most goals are scored from here.'],
  ['Assist', 'Assist', 'Die Vorlage zum Tor. Bis zu zwei Spieler bekommen einen Assist.', 'The pass that sets up a goal. Up to two players get an assist.'],
  ['Empty Net', 'Empty net', 'Das leere Tor, wenn ein Team den Goalie für einen Feldspieler vom Eis genommen hat.', 'The empty net when a team has pulled its goalie for an extra skater.'],
];
$('#glossNew').innerHTML = GLOSS.map(([td, te, dd, de]) => `<details><summary>${tr(td, te)}</summary><p>${tr(dd, de)}</p></details>`).join('');

/* ------------------------------------------------------------------ */
// Sprachwahl in der App: gleiche Einstellung wie auf der Website
$$('[data-setlang]').forEach(b => {
  b.classList.toggle('on', b.dataset.setlang === LANG);
  b.onclick = () => { try { localStorage.setItem('hv_lang', b.dataset.setlang); } catch (e) { /* egal */ } const u = new URL(location.href); u.searchParams.set('lang', b.dataset.setlang); location.href = u.toString(); };
});
show('learn');
// Direktlinks für Screenshots: ?demo=watch | watch-pp | spick
(function demo() {
  const d = new URLSearchParams(location.search).get('demo');
  if (d === 'watch') views.learn._demo(1, 3.6);
  else if (d === 'watch-pp') views.learn._demo(2, 6);
  else if (d && document.getElementById('v-' + d)) show(d);
})();
let lastTs = performance.now();
function loop(ts) {
  const dt = Math.min(0.1, (ts - lastTs) / 1000);
  lastTs = ts;
  const v = views[active];
  if (v && v.tick) v.tick(dt);
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);
