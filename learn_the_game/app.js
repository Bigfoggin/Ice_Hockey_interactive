/* Hockey verstehen – Prototyp für die Sport Innovation Challenge 2026
 * Zwei Einstiege: Neulinge lernen die Regeln, Kenner sehen den Spielbericht mit Advanced Stats.
 * Daten: Wisehockey-Export, Final Spengler Cup 31.12.2025 (USC = Home, HCD = Away)
 */
'use strict';

const D = window.MATCH_DATA;
const PL = D.players;
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const fmtClock = s => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
const pct = x => `${Math.round(x * 100)} %`;
const TEAM_COL = { HCD: ['#1D4ED8', '#FFD200'], USC: ['#C8102E', '#FFFFFF'] };
const PEN_DE = { Slashing: 'Stockschlags', CrossChecking: 'Crosschecks', HighSticking: 'hohen Stocks', Delay: 'Spielverzögerung' };
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
 * dann wird nur die Quelle ersetzt, Spielbericht und Quiz bauen sich neu.
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
  m.innerHTML = `<div class="box"><div class="grab"></div>${html}<button class="btn sec" style="margin-top:16px" data-close>Schliessen</button></div>`;
  m.addEventListener('click', ev => { if (ev.target === m || ev.target.hasAttribute('data-close')) m.remove(); });
  document.body.appendChild(m);
  return m;
}

/* ------------------------------------------------------------------ *
 * Schiri-Zeichen (vereinfachte Piktogramme nach IIHF-Handzeichen)
 * ------------------------------------------------------------------ */
const SIG = (() => {
  // Schiri von vorne: gestreiftes Shirt, oranges Armband (Hauptschiedsrichter), dicke Arme.
  // Bewegungen in Gelb. Arme: Schulter → Ellbogen → Hand.
  const SKIN = '#F3D2B5', INK = '#111827', MOVE = '#F59E0B', BAND = '#F97316';
  const SL = [40, 31], SR = [60, 31];
  const down = side => (side === 'L' ? [SL, [35, 46], [34, 60]] : [SR, [65, 46], [66, 60]]);
  const pts = a => a.map(p => p.join(',')).join(' ');
  function arm(a, band) {
    const [p0, p1] = a;
    const f = (t) => [p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t];
    const end = a[a.length - 1];
    // weisser Rand, damit der Arm vor dem gestreiften Shirt lesbar bleibt
    return `<polyline points="${pts(a)}" fill="none" stroke="#fff" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>` +
      `<polyline points="${pts(a)}" fill="none" stroke="${INK}" stroke-width="7.5" stroke-linecap="round" stroke-linejoin="round"/>` +
      (band ? `<line x1="${f(0.3)[0]}" y1="${f(0.3)[1]}" x2="${f(0.62)[0]}" y2="${f(0.62)[1]}" stroke="${BAND}" stroke-width="8"/>` : '') +
      `<circle cx="${end[0]}" cy="${end[1]}" r="5" fill="${SKIN}" stroke="${INK}" stroke-width="2"/>`;
  }
  const arrow = (d) => `<path d="${d}" fill="none" stroke="${MOVE}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>`;
  const head = (x, y, ang) => {
    const a = ang * Math.PI / 180, l = 6;
    const p = s => [x - l * Math.cos(a + s), y - l * Math.sin(a + s)];
    return arrow(`M${p(0.5).join(',')} L${x},${y} L${p(-0.5).join(',')}`);
  };
  function ref(L, R, extra = '') {
    return `<svg viewBox="0 0 100 100" width="100%" height="100%">
      <defs><pattern id="ref-st" width="7" height="10" patternUnits="userSpaceOnUse"><rect width="3.5" height="10" fill="${INK}"/><rect x="3.5" width="3.5" height="10" fill="#fff"/></pattern></defs>
      <path d="M45 62 L43 93 M55 62 L57 93" stroke="${INK}" stroke-width="8" stroke-linecap="round"/>
      <rect x="37" y="26" width="26" height="37" rx="7" fill="url(#ref-st)" stroke="${INK}" stroke-width="2"/>
      <circle cx="50" cy="15" r="9" fill="${SKIN}" stroke="${INK}" stroke-width="2"/><path d="M41 14a9 9 0 0 1 18 0z" fill="${INK}"/>
      ${arm(L, true)}${arm(R, true)}${extra}</svg>`;
  }
  return {
    goal: ref(down('L'), [SR, [78, 40], [93, 50]], `<rect x="84" y="62" width="13" height="10" fill="none" stroke="${INK}" stroke-width="2"/>` + arrow('M93 54 L91 60') + head(91, 60, 100)),
    washout: ref([SL, [23, 31], [6, 31]], [SR, [77, 31], [94, 31]], arrow('M40 20 L14 20') + head(14, 20, 180) + arrow('M60 20 L86 20') + head(86, 20, 0)),
    icing: ref([SL, [34, 41], [59, 41]], [SR, [66, 43], [41, 45]]),
    armup: ref(down('L'), [SR, [63, 17], [65, 5]]),
    slash: ref([SL, [33, 44], [59, 46]], [SR, [73, 30], [63, 39]], arrow('M77 21 Q78 32 68 37') + head(68, 37, 155)),
    high: ref([SL, [57, 22], [71, 20]], [SR, [74, 28], [71, 9]]),
    cross: ref([SL, [31, 40], [43, 45]], [SR, [69, 40], [57, 45]], arrow('M43 54 L43 64') + head(43, 64, 90) + arrow('M57 54 L57 64') + head(57, 64, 90)),
    hook: ref([SL, [22, 43], [40, 50]], [SR, [78, 43], [60, 50]], arrow('M10 58 L30 52') + head(30, 52, -17) + arrow('M90 58 L70 52') + head(70, 52, 197)),
    hold: ref([SL, [35, 44], [48, 46]], [SR, [66, 44], [53, 47]], `<circle cx="50" cy="46.5" r="8" fill="none" stroke="${MOVE}" stroke-width="3"/>`),
    trip: ref(down('L'), [SR, [68, 47], [60, 78]], arrow('M70 72 L76 70 M70 79 L77 80 M69 85 L74 89')),
    elbow: ref([SL, [23, 40], [38, 52]], [SR, [45, 38], [27, 39]], arrow('M18 30 L22 35 M26 29 L26 33 M14 37 L19 39')),
    board: ref([SL, [33, 44], [46, 47]], [SR, [67, 42], [53, 47]], arrow('M47 36 L45 40 M53 35 L53 39 M58 37 L56 40')),
  };
})();

const SIGNALS = [
  { id: 'goal', name: 'Tor', text: 'Der Schiri zeigt mit ausgestrecktem Arm auf das Tor: Der Treffer zählt.' },
  { id: 'washout', name: 'Kein Tor / aufgehoben', text: 'Beide Arme seitlich auf Schulterhöhe ausgestreckt, Handflächen nach unten. Das Tor zählt nicht – oder ein angezeigtes Icing bzw. Abseits ist aufgehoben.' },
  { id: 'icing', name: 'Icing', text: 'Arme vor der Brust verschränkt. Der Puck wurde aus der eigenen Hälfte über die gegnerische Torlinie geschossen.' },
  { id: 'armup', name: 'Angezeigte Strafe', text: 'Ein Arm hoch: Ein Foul ist passiert, gepfiffen wird aber erst, wenn das foulende Team den Puck berührt. Der Linienrichter zeigt so auch ein verzögertes Abseits an.' },
  { id: 'slash', name: 'Stockschlag', text: 'Mit einer Hand auf den Unterarm der anderen Hand schlagen. Ein Spieler hat mit dem Stock auf den Gegner geschlagen.' },
  { id: 'high', name: 'Hoher Stock', text: 'Beide Fäuste übereinander seitlich am Kopf. Der Stock war über Schulterhöhe.' },
  { id: 'cross', name: 'Crosscheck', text: 'Beide Fäuste vor der Brust, mit einer Stossbewegung nach vorne. Der Gegner wurde mit dem quer gehaltenen Stock gestossen.' },
  { id: 'hook', name: 'Haken', text: 'Mit beiden Armen eine Zieh-Bewegung zum Bauch. Ein Spieler hat den Gegner mit dem Stock zurückgehalten.' },
  { id: 'hold', name: 'Halten', text: 'Das Handgelenk der Pfeifenhand vor der Brust mit der anderen Hand umfassen. Der Gegner wurde festgehalten.' },
  { id: 'trip', name: 'Beinstellen', text: 'Mit der Hand unterhalb des Knies aufs Bein schlagen. Der Gegner wurde zu Fall gebracht.' },
  { id: 'elbow', name: 'Ellbogencheck', text: 'Mit der Hand auf den Ellbogen des anderen Arms tippen. Der Gegner wurde mit dem Ellbogen gecheckt.' },
  { id: 'board', name: 'Check gegen die Bande', text: 'Mit der Faust in die offene Handfläche schlagen. Der Gegner wurde gefährlich in die Bande gecheckt.' },
];
const SIGMAP = Object.fromEntries(SIGNALS.map(s => [s.id, s]));
function openSignal(id) {
  const s = SIGMAP[id];
  modal(`<div class="bigsig">${SIG[id]}</div><div class="t2" style="text-align:center">${s.name}</div><p class="sub">${s.text}</p><div class="fn" style="text-align:center;margin-top:10px">Piktogramm vereinfacht</div>`);
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
      ctx.fillText('Angriffszone HCD', this.X(lx * 18.5), this.Y(12.4));
      ctx.fillText('Neutrale Zone', this.X(0), this.Y(12.4));
      ctx.fillText('Angriffszone USC', this.X(-lx * 18.5), this.Y(12.4));
    }
    ctx.fillStyle = 'rgba(15,23,42,.45)';
    ctx.fillText('Tor USC', this.X(lx * 23.5), this.Y(-12.6));
    ctx.fillText('Tor HCD', this.X(-lx * 23.5), this.Y(-12.6));
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
      const label = `Feldspieler  USC ${n.USC} : ${n.HCD} HCD`;
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
  const rows = p.gk ? [['Position', 'Torhüter']] : [
    ['Top-Speed', `${p.spd.toFixed(1)} km/h`], ['Härtester Schuss', p.sht ? `${p.sht.toFixed(0)} km/h` : '–'],
    ['Gelaufene Distanz', `${(p.dist / 1000).toFixed(1)} km`], ['Eiszeit', `${Math.round(p.toi / 60)} min`],
    ['Tore / Assists', `${p.g} / ${p.a}`], ['Torchancen (xG)', p.xg.toFixed(2)],
  ];
  modal(`<div class="row"><span class="badge" style="width:48px;height:48px;font-size:17px;background:${fill};color:${num}">${p.no}</span>
    <div><div class="t2" style="margin:0">${p.n}</div><div class="fn">${TEAM_NAME[p.tm]}</div></div></div>
    <div class="group" style="background:var(--fill);margin-top:16px">${rows.map(([k, v]) => `<div class="cell" style="min-height:48px"><span class="grow sub">${k}</span><span class="val">${v}</span></div>`).join('')}</div>`);
}

/* ------------------------------------------------------------------ *
 * Clip-Player: spielt einen Ausschnitt mit Untertiteln ab.
 * hold = Sekunden, die der Clip bei jedem Untertitel anhält (Erklärmodus)
 * ------------------------------------------------------------------ */
const CLIPS = [];
class Clip {
  constructor(root) {
    root.innerHTML = `<div class="rinkwrap"><canvas class="rink"></canvas></div>
      <div class="clipbar"><button class="playbtn" aria-label="Abspielen">${ICON.play}</button>
      <div class="scrub"><i></i></div>
      <div class="seg" style="flex:none"><button data-r="1">Echtzeit</button><button data-r="0.45">Zeitlupe</button></div></div>
      <div class="cap"><div class="k"></div><div class="x"></div></div>`;
    this.root = root;
    this.rink = new Rink($('canvas', root));
    this.btn = $('.playbtn', root);
    this.btn.onclick = () => (this.playing ? this.pause() : this.play());
    $$('[data-r]', root).forEach(b => (b.onclick = () => { this.setRate(+b.dataset.r); if (!this.playing) this.play(); }));
    CLIPS.push(this);
  }
  setRate(r) { this.rate = r; $$('[data-r]', this.root).forEach(x => x.classList.toggle('on', +x.dataset.r === r)); }
  icon(n, label) { this.btn.innerHTML = ICON[n]; this.btn.setAttribute('aria-label', label); }
  load(spec, autoplay) {
    this.spec = spec;
    this.t = spec.from; this.cur = null; this.hold = 0;
    this.setRate(spec.rate || 1);
    this.setCap(spec.intro || { k: 'Bereit', x: 'Drücke Play.' });
    this.playing = false; this.icon('play', 'Abspielen');
    if (autoplay) this.play();
  }
  play() { if (this.t >= this.spec.to) { this.t = this.spec.from; this.cur = null; } this.playing = true; this.icon('pause', 'Pause'); }
  pause() { this.playing = false; this.icon('play', 'Abspielen'); }
  setCap(c) { $('.k', this.root).textContent = c.k; $('.x', this.root).textContent = c.x; }
  visible() { return this.root.offsetParent !== null; }
  tick(dt) {
    if (!this.spec || !this.visible()) return;
    const sp = this.spec;
    if (this.playing) {
      if (this.hold > 0) this.hold -= dt;
      else {
        this.t += dt * this.rate;
        for (const c of sp.caps || []) {
          if (c.g <= this.t && c !== this.cur && (!this.cur || c.g > this.cur.g)) {
            this.cur = c; this.setCap(c);
            if (sp.hold && this.rate < 1) { this.hold = sp.hold; this.t = c.g; }
            break;
          }
        }
        if (this.t >= sp.to) { this.t = sp.to; this.playing = false; this.icon('replay', 'Nochmal'); }
      }
    }
    $('.scrub i', this.root).style.width = `${((this.t - sp.from) / (sp.to - sp.from)) * 100}%`;
    const deco = this.cur && this.t - this.cur.g < 3.5;
    this.rink.draw(this.t, { ...sp.opts, ring: deco ? this.cur.ring : null, arrow: deco && this.cur.arrow ? this.cur.arrow : sp.opts && sp.opts.arrow });
  }
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
let active = 'start';
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

views.start = {
  enter() {
    const n = Object.keys(S.watched || {}).length;
    $('#doorProg').classList.toggle('hidden', !n);
    $('#doorProg .bar i').style.width = `${(n / MOMENTS.length) * 100}%`;
    $('#doorProg .fn').textContent = n === MOMENTS.length ? 'Ganzes Spiel geschaut' : `${n} von ${MOMENTS.length} Momenten gesehen`;
  },
};

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
    if (a.box) area(-3.5, -14.8, 3.5, -11.6, 'Strafbank');
    if (a.bench) area(-14, 11.6, 2, 14.8, 'Spielerbank');
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
    labels: [[0, 1.8, 'Der Schiri wirft den Puck ein', 'info'], [2.2, 6, 'Blau gewinnt das Bully', 'ok']] },

  icing: { dur: 7, opts: { goalLine: true }, tokens: [
      { c: 'A', p: [[0, 14, -6]], hi: [0.4, 2.2] }, still('A', 8, 6), ...lineupA().slice(0, 1),
      { c: 'B', p: [[0, 4, -3], [3, 2, -6]] }, { c: 'B', p: [[0, 6, 8], [3, 3, 7]] }, still('BG', -26.6, 0)],
    puck: [[0, 13, -5.5], [1, 13, -5.5], [3.2, -29, 5]],
    marks: [[4.2, 7, 20, -7]],
    labels: [[0, 1, 'Blau in der eigenen Hälfte', 'info'], [1, 3.2, 'Weitschuss übers ganze Feld …', 'info'], [3.2, 4.2, '… über die Torlinie: Icing!', 'bad'], [4.2, 7, 'Bully vor dem eigenen Tor', 'info']] },

  offside: { dur: 10, opts: { blue: true }, tokens: [
      { c: 'A', p: [[0, 3, -2], [3, -9, -2], [5, -9, -2], [5, 3, -2], [8, -9, -2]] },
      { c: 'A', p: [[0, -2, 6], [1.6, -11, 6], [5, -11, 6], [5, -2, 6], [6.6, -2, 6], [8.4, -11, 6]], hi: [0, 3] },
      ...lineupB()],
    puck: [[0, 2, -2.6], [3, -10, -2.6], [5, -10, -2.6], [5, 2, -2.6], [8, -10, -2.6]],
    labels: [[0, 1.4, 'Achte auf die blaue Linie', 'info'], [1.4, 4.9, 'Abseits: Spieler vor dem Puck', 'bad'], [5, 6.8, 'So ist es richtig …', 'info'], [6.8, 10, 'Puck zuerst: korrekt', 'ok']] },

  penalty: { dur: 8, box: true, tokens: [
      still('R', 2, 9), ...lineupA(), still('A', -10, -4), still('A', -6, 5), still('A', 2, -6),
      still('BG', -26.6, 0), still('B', -18, 5), still('B', -16, -6), still('B', -8, -2),
      { c: 'B', p: [[0, -4, 3], [2.5, -4, 3], [4.5, 0, -13.2]], hi: [1, 4.5] }],
    labels: [[0, 1.2, 'Foul von Rot', 'bad'], [1.2, 2.5, 'Schiri hebt den Arm', 'info'], [2.5, 4.5, 'Ab auf die Strafbank: 2 Minuten', 'info'], [4.5, 8, 'Powerplay: 5 gegen 4 für Blau', 'ok']] },

  ppgoal: { dur: 8, box: true, tokens: [
      ...lineupA(), { c: 'A', p: [[0, -14, -7], [1.2, -15, -7]] }, { c: 'A', p: [[0, -18, 7], [1.2, -20, 4]], hi: [1, 2.6] }, still('A', -10, 1), still('A', -8, -9),
      still('BG', -26.6, 0), still('B', -20, -3), still('B', -16, 6), still('B', -12, -4),
      { c: 'B', p: [[0, 0, -13.2], [3.6, 0, -13.2], [6, 5, -6]], hi: [3.4, 6] }],
    puck: [[0, -14, -6.5], [1.2, -15, -6.5], [1.6, -20, 3.5], [2.2, -20, 3.5], [2.6, -26.5, 0.4]],
    labels: [[0, 2.6, 'Blau im Powerplay', 'info'], [2.6, 3.6, 'Tor!', 'ok'], [3.6, 8, 'Strafe vorbei: wieder 5 gegen 5', 'info']] },

  emptynet: { dur: 9, bench: true, tokens: [
      { c: 'BG', p: [[0, -26.6, 0], [0.6, -26.6, 0], [3, -8, 13.2]], until: 3 },
      { c: 'B', p: [[3, -4, 13.2], [5, 10, 5]], from: 3, hi: [3, 5] },
      still('B', 12, -4), still('B', 16, 7), still('B', 8, -9), still('B', 18, -1),
      { c: 'A', p: [[0, 14, -8]], hi: [5.2, 6.8] }, still('A', 20, 4), still('AG', 26.6, 0)],
    puck: [[0, 15, -8.3], [5.6, 15, -8.3], [7, -26.6, 0.2]],
    labels: [[0, 3, 'Rot holt den Goalie vom Eis', 'info'], [3, 5.4, 'Dafür ein 6. Feldspieler', 'info'], [5.4, 7, 'Schuss aus der eigenen Hälfte …', 'info'], [7, 9, '… ins leere Tor!', 'ok']] },

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
    ctx.fillText('Torlinie', lx, H - 10);
    if (tt > 1.3) s.pill(phase ? 'Ganz über der Linie: Tor' : 'Auf der Linie: kein Tor', phase ? 'ok' : 'bad', 10);
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
  { from: EV[0].g - 0.5, to: EV[0].g + 4, title: 'Das Bully', anim: 'bully',
    seen: 'Spielbeginn: Der Schiri wirft den Puck ein.',
    text: `Jedes Drittel und jede Unterbrechung startet mit einem Bully. Gespielt werden 3 × 20 Minuten, pro Team stehen 5 Feldspieler und ein Torhüter auf dem Eis. Gewechselt wird mitten im Spiel, ein Einsatz dauert nur rund ${avgShift} Sekunden.` },
  { from: icingDump.g - 6, to: icingStop.g + 0.2, title: 'Icing', anim: 'icing', sig: 'icing',
    seen: `${nm(icingDump.pl)} (${icingDump.tm}) hat den Puck aus der eigenen Hälfte bis hinter die gegnerische Torlinie geschossen.`,
    text: 'Ein Weitschuss aus der eigenen Hälfte über die gegnerische Torlinie, den niemand berührt, ist Icing. Die Folge: Bully vor dem eigenen Tor, und das Team darf vorher nicht wechseln. In Unterzahl ist der Befreiungsschlag erlaubt.' },
  { from: ppPenalty.g - 9, to: ppPenalty.g + 0.2, title: 'Strafe', anim: 'penalty', sig: 'slash',
    seen: `${nm(ppPenalty.pl)} (${ppPenalty.tm}) hat mit dem Stock zugeschlagen.`,
    text: `Bei einem Foul hebt der Schiri den Arm und pfeift, sobald das foulende Team den Puck berührt. Der Spieler muss 2 Minuten auf die Strafbank, ${ppPenalty.tm} spielt in Unterzahl. Für ${other(ppPenalty.tm)} heisst das Powerplay.` },
  { from: ppPenalty.g + 0.5, to: ppScene.goal.g + 0.6, title: 'Tor im Powerplay', anim: 'ppgoal', sig: 'goal',
    seen: `${nm(ppScene.goal.pl)} trifft nur drei Sekunden nach dem Bully zum ${ppScene.sc.USC}:${ppScene.sc.HCD}.`,
    text: 'Trifft das Team im Powerplay, ist die 2-Minuten-Strafe sofort vorbei. Der bestrafte Spieler darf zurück aufs Eis, es steht wieder 5 gegen 5.' },
  { from: walsh.shot.g - 12, to: walsh.goal.g + 0.6, title: 'Wann zählt ein Tor?', anim: 'goalline', sig: 'goal',
    seen: `${nm(walsh.goal.pl)} lenkt den Puck direkt vor dem Tor ab: ${walsh.sc.USC}:${walsh.sc.HCD}.`,
    text: 'Ein Tor zählt nur, wenn der Puck die Torlinie vollständig überquert hat. Liegt er auf der Linie, geht das Spiel weiter. In knappen Fällen prüfen die Schiris das Video.' },
  { from: offside.g - 10, to: offside.g + 0.2, title: 'Abseits', anim: 'offside', sig: 'armup',
    seen: `Ein Angreifer von ${offsideTeam} war vor dem Puck in der Angriffszone.`,
    text: 'Angreifer dürfen die blaue Linie erst nach dem Puck überqueren. Ist einer zu früh in der Angriffszone, pfeift der Linienrichter ab. Das Bully gibt es dann ausserhalb der Zone.' },
  { from: hsPenalty.g - 9, to: hsPenalty.g + 0.2, title: 'Hoher Stock', anim: 'penalty', sig: 'high',
    seen: `${nm(hsPenalty.pl)} (${hsPenalty.tm}) hat einen Gegner mit dem Stock über Schulterhöhe getroffen.`,
    text: `Der Stock war über Schulterhöhe. Das gibt normalerweise 2 Minuten, bei einer Verletzung 2+2 Minuten.${hsDouble ? ` ${nm(hsPenalty.pl)} bekam 2+2 Minuten.` : ''}` },
  { from: enScene.shot.g - 16, to: enScene.goal.g + 0.6, title: 'Leeres Tor', anim: 'emptynet',
    seen: `${nm(enScene.goal.pl)} trifft aus der eigenen Hälfte ins leere Tor: ${enScene.sc.USC}:${enScene.sc.HCD}.`,
    text: 'Kurz vor Schluss nehmen Teams im Rückstand oft den Torhüter vom Eis und bringen einen sechsten Feldspieler. Mehr Angreifer, aber das eigene Tor ist leer.' },
  { from: finalWhistle.g - 8, to: finalWhistle.g, title: 'Schlusspfiff', end: true,
    seen: 'HC Davos gewinnt den Final 6:3 und den 97. Spengler Cup.',
    text: 'Du hast gerade die wichtigsten Regeln an echten Szenen gesehen: Bully, Icing, Strafen, Powerplay, Tor, Abseits und das leere Tor. Damit verstehst du jeden Pfiff.' },
];

views.learn = (() => {
  const rink = new Rink($('#c-watch'));
  let mi = 0, t = MOMENTS[0].from, playing = false, rate = 1, pop = null;
  const seen = () => Object.keys(S.watched || {}).length;
  function strengthAt(g) {
    for (let k = lastIdx; k >= 0; k--) {
      const e = EV[k];
      if (e.g > g || e.hg === undefined) continue;
      if (e.hg === false && e.ag === false) return 'Beide Tore leer';
      if (e.hg === false) return 'USC ohne Goalie';
      if (e.ag === false) return 'HCD ohne Goalie';
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
    $('#wClock').textContent = `${e.p}. Drittel · ${fmtClock(e.c)}${st ? ' · ' + st : ''}`;
  }
  function dots() {
    $('#wDots').innerHTML = MOMENTS.map((m, i) => `<span class="${i === mi ? 'cur' : (S.watched || {})[i] ? 'on' : ''}"></span>`).join('');
    $('#wNext').textContent = `Nächster Halt: ${MOMENTS[mi].title}`;
  }
  function load(i, autoplay) {
    mi = i; t = MOMENTS[i].from; dots(); board();
    setPlaying(!!autoplay);
  }
  function setPlaying(p) { playing = p; $('#wPlay').innerHTML = p ? ICON.pause : ICON.play; }
  $('#wPlay').onclick = () => setPlaying(!playing);
  $$('#wRate button').forEach(b => (b.onclick = () => { rate = +b.dataset.r; $$('#wRate button').forEach(x => x.classList.toggle('on', x === b)); }));
  $('#wSkip').onclick = () => { t = MOMENTS[mi].to; };

  function openPop() {
    const m = MOMENTS[mi];
    S.watched = S.watched || {}; S.watched[mi] = 1; save(); dots();
    const el = document.createElement('div');
    el.className = 'modal';
    const last = mi + 1 >= MOMENTS.length;
    el.innerHTML = `<div class="box"><div class="grab"></div>
      <div class="fn">${mi + 1} von ${MOMENTS.length} · ${$('#wClock').textContent}</div>
      <div class="t2" style="margin:4px 0 8px">${m.title}</div>
      <div class="seen">${m.seen}</div>
      ${m.anim ? `<div class="rinkwrap" style="margin-top:14px"><canvas class="rink"></canvas></div>` : ''}
      <p class="lesson" style="margin:14px 0 0">${m.text}</p>
      ${m.sig ? `<button class="cell sigrow" data-sig="${m.sig}"><span class="sigpic">${SIG[m.sig]}</span><span class="grow"><span class="hl">So zeigt es der Schiri</span><br><span class="fn">${SIGMAP[m.sig].name}</span></span><span class="chev">›</span></button>` : ''}
      ${last ? `<button class="btn" style="margin-top:18px" data-w="quiz">Zum Quiz</button><button class="btn sec" style="margin-top:8px" data-w="report">Spielbericht ansehen</button>`
        : `<button class="btn" style="margin-top:18px" data-w="next">Weiter schauen</button><button class="btn sec" style="margin-top:8px" data-w="again">Szene nochmal</button>`}
    </div>`;
    document.body.appendChild(el);
    pop = { el, sch: m.anim ? new Schematic($('canvas', el)) : null, a: ANIM[m.anim], t: 0 };
    el.addEventListener('click', ev => {
      const b = ev.target.closest('[data-w]');
      if (!b) return;
      close();
      if (b.dataset.w === 'next') load(mi + 1, true);
      else if (b.dataset.w === 'again') load(mi, true);
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
    tick(dt) {
      if (playing && !pop) {
        t += dt * rate;
        if (t >= MOMENTS[mi].to) { t = MOMENTS[mi].to; setPlaying(false); board(); openPop(); }
      }
      board();
      rink.draw(t);
      if (pop && pop.sch) { pop.t = (pop.t + dt) % pop.a.dur; pop.sch.drawAnim(pop.a, pop.t); }
    },
  };
})();

/* ------------------------------------------------------------------ *
 * Tür 2: Spielbericht – ein Thema pro Ansicht
 * ------------------------------------------------------------------ */
views.report = (() => {
  const fin = scoreAt(Infinity);
  $('#score').innerHTML = `<span class="tm"><span class="dot" style="background:var(--usc)"></span>USC</span><span class="res">${fin.USC}:${fin.HCD}</span><span class="tm">HCD<span class="dot" style="background:var(--hcd)"></span></span>`;
  let panel = 'goals';
  const clip = new Clip($('#goalClip'));
  $('#repSeg').addEventListener('click', ev => {
    const b = ev.target.closest('[data-p]'); if (!b) return;
    panel = b.dataset.p;
    $$('#repSeg button').forEach(x => x.classList.toggle('on', x === b));
    $$('[data-panel]').forEach(p => p.classList.toggle('hidden', p.dataset.panel !== panel));
    if (panel !== 'goals') clip.pause();
    if (panel === 'shots') drawShots();
  });

  // Tore
  let sel = 0;
  function renderGoals() {
    $('#goalList').innerHTML = SCENES.map(s => `<button class="gl ${s.n === sel ? 'on' : ''}" data-g="${s.n}">
      <span class="t">${s.goal.p}. ${fmtClock(s.goal.c)}</span><span class="dot" style="background:var(--${s.tm.toLowerCase()})"></span>
      <span class="s">${s.sc.USC}:${s.sc.HCD}</span><span class="grow">${nm(s.goal.pl)}</span>
      <span class="chip">${s.tag === '5 gegen 5' ? (s.shot.xg != null ? 'xG ' + pct(s.shot.xg) : '') : s.tag}</span></button>`).join('');
  }
  $('#goalList').addEventListener('click', ev => {
    const g = ev.target.closest('[data-g]'); if (!g) return;
    sel = +g.dataset.g; renderGoals(); clip.load(sceneClip(SCENES[sel]), true);
    $('#goalClip').scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  renderGoals(); clip.load(sceneClip(SCENES[0]));

  // xG-Verlauf
  (function xgChart() {
    const W = 340, H = 180, L = 22, R = 6, T = 8, B = 24;
    const maxX = 60, series = {};
    let maxY = 0;
    for (const tm of ['HCD', 'USC']) {
      let c = 0; const pts = [[0, 0]];
      for (const s of SHOTS) if (s.tm === tm && s.xg != null) { c += s.xg; pts.push([minuteOf(s), c]); }
      pts.push([maxX, c]); series[tm] = pts; maxY = Math.max(maxY, c);
    }
    maxY = Math.ceil(maxY);
    const X = m => L + (m / maxX) * (W - L - R), Y = v => H - B - (v / maxY) * (H - T - B);
    const step = pts => pts.map((p, i) => (i ? `H${X(p[0]).toFixed(1)}V${Y(p[1]).toFixed(1)}` : `M${X(p[0])},${Y(p[1])}`)).join('');
    let svg = `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="xG-Verlauf: HCD ${teamSum('HCD', 'xg').toFixed(1)}, USC ${teamSum('USC', 'xg').toFixed(1)}">`;
    for (let v = 0; v <= maxY; v++) svg += `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" style="stroke:var(--line)"/><text x="${L - 6}" y="${Y(v) + 4}" font-size="11" text-anchor="end" style="fill:var(--ink2)">${v}</text>`;
    ['1. Drittel', '2. Drittel', '3. Drittel'].forEach((t, i) => (svg += `<text x="${X(i * 20 + 10)}" y="${H - 6}" font-size="11" text-anchor="middle" style="fill:var(--ink2)">${t}</text>`));
    for (const m of [20, 40]) svg += `<line x1="${X(m)}" x2="${X(m)}" y1="${T}" y2="${H - B}" style="stroke:var(--line)" stroke-dasharray="3 3"/>`;
    for (const tm of ['USC', 'HCD']) svg += `<path d="${step(series[tm])}" fill="none" stroke-width="2.5" style="stroke:var(--${tm.toLowerCase()})"/>`;
    const valAt = (tm, m) => { let v = 0; for (const p of series[tm]) if (p[0] <= m) v = p[1]; return v; };
    for (const [g] of GOALS) svg += `<circle cx="${X(minuteOf(g))}" cy="${Y(valAt(g.tm, minuteOf(g)))}" r="4.5" stroke-width="2" style="fill:var(--${g.tm.toLowerCase()});stroke:var(--surface)"/>`;
    $('#xgChart').innerHTML = svg + '</svg>';
    $('#xgInfo').innerHTML = `HCD erspielte <b>${teamSum('HCD', 'xg').toFixed(1)} xG</b> und traf <b>6-mal</b>. USC kam auf ${teamSum('USC', 'xg').toFixed(1)} xG und traf 3-mal. HCD war deutlich effizienter, als die Chancen erwarten liessen.`;
  })();

  // Shot-Map
  const shotRink = new Rink($('#c-shots'));
  let filter = 'all';
  function drawShots() {
    shotRink.fit(); if (!shotRink.w) return;
    shotRink.ice();
    const { ctx, k } = shotRink;
    for (const s of SHOTS) {
      if (!s.s || (filter !== 'all' && s.tm !== filter)) continue;
      const r = Math.max(3, Math.sqrt(s.xg || 0.02) * 2.6 * k);
      ctx.beginPath(); ctx.arc(shotRink.X(s.s[0]), shotRink.Y(s.s[1]), r, 0, 7);
      ctx.fillStyle = s.tm === 'HCD' ? 'rgba(29,78,216,.5)' : 'rgba(200,16,46,.5)'; ctx.fill();
      if (s.res === 'Goal') { ctx.lineWidth = 3; ctx.strokeStyle = '#F5B800'; ctx.stroke(); }
    }
    const list = SHOTS.filter(s => filter === 'all' || s.tm === filter);
    const goals = list.filter(s => s.res === 'Goal').length;
    const near = list.filter(s => s.s && Math.abs(Math.abs(s.s[0]) - 26) < 9 && Math.abs(s.s[1]) < 7);
    $('#shotInfo').innerHTML = `<b>${list.length} Schüsse, ${goals} Tore.</b> ${near.length} Schüsse kamen aus dem Slot direkt vor dem Tor, dort fielen ${near.filter(s => s.res === 'Goal').length} der ${goals} Tore.`;
  }
  $$('#shotFilter button').forEach(b => (b.onclick = () => { filter = b.dataset.f; $$('#shotFilter button').forEach(x => x.classList.toggle('on', x === b)); drawShots(); }));

  // Team-Vergleich
  const shotsBy = tm => SHOTS.filter(s => s.tm === tm).length;
  const rows = [
    ['Schüsse', shotsBy('USC'), shotsBy('HCD'), v => v],
    ['Torchancen (xG)', teamSum('USC', 'xg'), teamSum('HCD', 'xg'), v => v.toFixed(1)],
    ['Pass-Quote', teamSum('USC', 'pas') / teamSum('USC', 'pasall'), teamSum('HCD', 'pas') / teamSum('HCD', 'pasall'), pct],
    ['Bullys gewonnen', teamSum('USC', 'fow'), teamSum('HCD', 'fow'), v => v],
    ['Zweikämpfe gewonnen', teamSum('USC', 'pcw') / teamSum('USC', 'pc'), teamSum('HCD', 'pcw') / teamSum('HCD', 'pc'), pct],
    ['Geblockte Schüsse', teamSum('USC', 'bks'), teamSum('HCD', 'bks'), v => v],
    ['Strafminuten', teamSum('USC', 'pim'), teamSum('HCD', 'pim'), v => v],
    ['Gelaufene Distanz', teamSum('USC', 'dist') / 1000, teamSum('HCD', 'dist') / 1000, v => `${v.toFixed(0)} km`],
  ];
  $('#compare').innerHTML = rows.map(([lab, u, h, f]) => {
    const tot = u + h || 1;
    return `<div class="r"><div class="l"><b>${f(u)}</b><span>${lab}</span><b>${f(h)}</b></div>
      <div class="bars"><i style="width:${(u / tot) * 100}%;background:var(--usc)"></i><i style="width:${(h / tot) * 100}%;background:var(--hcd)"></i></div></div>`;
  }).join('');

  // Spieler-Ranglisten
  const LB = [['spd', 'Speed', p => `${p.spd.toFixed(1)} km/h`], ['sht', 'Schuss', p => `${p.sht.toFixed(0)} km/h`], ['dist', 'Distanz', p => `${(p.dist / 1000).toFixed(1)} km`], ['toi', 'Eiszeit', p => fmtClock(p.toi)], ['xg', 'xG', p => p.xg.toFixed(2)]];
  let lb = 'spd';
  function renderLB() {
    $('#lbSeg').innerHTML = LB.map(([k, n]) => `<button data-k="${k}" class="${k === lb ? 'on' : ''}">${n}</button>`).join('');
    const [k, , f] = LB.find(x => x[0] === lb);
    $('#lbList').innerHTML = [...SKATERS].sort((a, b) => b[k] - a[k]).slice(0, 5).map((p, i) => `<button class="cell" data-pid="${p.id}">
      <span class="fn" style="width:14px">${i + 1}</span><span class="badge" style="background:${TEAM_COL[p.tm][0]};color:${TEAM_COL[p.tm][1]}">${p.no}</span>
      <span class="grow">${p.n}</span><span class="val">${f(p)}</span></button>`).join('');
  }
  $('#lbSeg').addEventListener('click', ev => { const b = ev.target.closest('[data-k]'); if (b) { lb = b.dataset.k; renderLB(); } });
  $('#lbList').addEventListener('click', ev => { const l = ev.target.closest('[data-pid]'); if (l) openPlayer(l.dataset.pid); });
  renderLB();

  return {
    leave() { clip.pause(); },
    tick() { if (panel === 'shots' && shotRink.c.parentElement.clientWidth !== shotRink.w) drawShots(); },
  };
})();

/* ------------------------------------------------------------------ *
 * Gewinnspiel: Schätz- und Spielerfragen nach dem Spiel
 * ------------------------------------------------------------------ */
views.game = (() => {
  const top = k => [...SKATERS].sort((a, b) => b[k] - a[k]);
  const shuffle = a => [...a].sort(() => Math.random() - 0.5);
  const pick = (right, pool) => shuffle([right, ...shuffle(pool.filter(p => p.id !== right.id)).slice(0, 3)]);
  const scorers = SKATERS.filter(p => p.g > 0);

  function questions() {
    const sht = top('sht'), spd = top('spd'), dist = top('dist');
    const two = scorers.find(p => p.g === 2);
    return [
      { ty: 'num', q: 'Wie schnell war der härteste Schuss im Final?', unit: 'km/h', min: 60, max: 180, step: 1, real: sht[0].sht, tol: 30, dec: 0,
        why: 'Aus 18 Metern bleibt dem Goalie bei diesem Tempo weniger als eine halbe Sekunde. Wer so hart schiesst? Nächste Frage.' },
      { ty: 'pick', q: `Wer hat den härtesten Schuss abgefeuert (${sht[0].sht.toFixed(0)} km/h)?`, right: sht[0], opts: pick(sht[0], sht.slice(1, 10)),
        why: `${sht[0].n}, knapp vor ${sht[1].n} mit ${sht[1].sht.toFixed(1)} km/h.` },
      { ty: 'num', q: 'Wie schnell war der schnellste Spieler auf dem Eis?', unit: 'km/h', min: 20, max: 50, step: 0.5, real: spd[0].spd, tol: 6, dec: 1,
        why: 'In jeder 30er-Zone wärst du geblitzt worden, auf Schlittschuhen und mit voller Ausrüstung.' },
      { ty: 'pick', q: `Wer erreichte die ${spd[0].spd.toFixed(1)} km/h?`, right: spd[0], opts: pick(spd[0], spd.slice(1, 10)),
        why: `${spd[0].n}. Platz 2: ${spd[1].n} mit ${spd[1].spd.toFixed(1)} km/h.` },
      { ty: 'num', q: 'Wie viele Kilometer lief der fleissigste Spieler im Final?', unit: 'km', min: 1, max: 10, step: 0.1, real: dist[0].dist / 1000, tol: 2, dec: 1,
        why: `In nur ${Math.round(dist[0].toi / 60)} Minuten Eiszeit, fast nur Sprints.` },
      { ty: 'pick', q: 'Wer lief die meisten Kilometer?', right: dist[0], opts: pick(dist[0], dist.slice(1, 10)),
        why: `${dist[0].n} stand auch am längsten auf dem Eis: ${Math.round(dist[0].toi / 60)} Minuten.` },
      { ty: 'num', q: 'Wie lange bleibt ein Spieler im Schnitt am Stück auf dem Eis?', unit: 's', min: 10, max: 180, step: 5, real: avgShift, tol: 30, dec: 0,
        why: 'Danach geht es auf die Bank. Eishockey ist ein Sprint, kein Marathon.' },
      { ty: 'num', q: 'Wie viele Schüsse gaben beide Teams zusammen ab, inklusive geblockter und verfehlter?', unit: 'Schüsse', min: 20, max: 200, step: 1, real: SHOTS.length, tol: 40, dec: 0,
        why: `${SHOTS.length} Schüsse, ${GOALS.length} Tore: Nur etwa jeder ${Math.round(SHOTS.length / GOALS.length)}. Schuss geht rein.` },
      { ty: 'num', q: 'HCD traf 6-mal. Wie viele Tore liessen die Torchancen (xG) erwarten?', unit: 'Tore', min: 0, max: 10, step: 0.1, real: teamSum('HCD', 'xg'), tol: 2.5, dec: 1,
        why: `HCD traf deutlich öfter als erwartet. USC kam auf ${teamSum('USC', 'xg').toFixed(1)} xG bei 3 Toren.` },
      { ty: 'pick', q: 'Wer schoss im Final als Einziger zwei Tore?', right: two, opts: pick(two, scorers), why: 'Zwei Tore im Final, ein Kandidat für die Three Stars.' },
    ];
  }

  let qs = [], qi = 0, score = 0, answered = false;
  const box = $('#sqBox');
  function head() {
    $('#sqProg').textContent = qi < qs.length ? `Frage ${qi + 1} von ${qs.length} · ${score} Punkte` : `${score} Punkte`;
    $('#sqBar').style.width = `${(Math.min(qi, qs.length) / qs.length) * 100}%`;
  }
  function render() {
    const q = qs[qi]; answered = false; head();
    if (q.ty === 'num') {
      // Regler startet ohne Wert, damit die Mitte nicht zufällig ein Treffer ist
      box.innerHTML = `<div class="hl">${q.q}</div>
        <div class="big"><span id="sqv">?</span> <small>${q.unit}</small></div>
        <input type="range" id="sqr" min="${q.min}" max="${q.max}" step="${q.step}" value="${q.min}" aria-label="${q.q}">
        <div class="row fn" style="justify-content:space-between"><span>${q.min}</span><span>${q.max}</span></div>
        <button class="btn" style="margin-top:16px" data-sq="go" disabled>Tipp abgeben</button><div id="sqRes"></div>`;
      $('#sqr').oninput = e => { $('#sqv').textContent = (+e.target.value).toFixed(q.dec); $('[data-sq=go]', box).disabled = false; };
    } else {
      box.innerHTML = `<div class="hl" style="margin-bottom:12px">${q.q}</div>${q.opts.map(p => `<button class="opt" data-pid="${p.id}"><span class="pl">
        <span class="badge" style="background:${TEAM_COL[p.tm][0]};color:${TEAM_COL[p.tm][1]}">${p.no}</span><span>${p.n}<br><span class="fn">${TEAM_NAME[p.tm]}</span></span></span></button>`).join('')}<div id="sqRes"></div>`;
    }
  }
  function reveal(pts, head2) {
    answered = true; score += pts;
    $('#sqRes').innerHTML = `<div class="cap"><div class="k">${head2}</div><div class="x">${qs[qi].why}</div></div>
      <button class="btn" style="margin-top:8px" data-sq="next">${qi + 1 < qs.length ? 'Nächste Frage' : 'Zur Auswertung'}</button>`;
    head();
  }
  box.addEventListener('click', ev => {
    const q = qs[qi];
    const o = ev.target.closest('[data-pid]');
    if (o && !answered) {
      const ok = o.dataset.pid === q.right.id;
      $$('.opt', box).forEach(b => { b.disabled = true; if (b.dataset.pid === q.right.id) b.classList.add('right'); });
      if (!ok) o.classList.add('wrong');
      reveal(ok ? 10 : 0, ok ? 'Richtig · +10' : `Es war ${q.right.n} · +0`);
      return;
    }
    const b = ev.target.closest('[data-sq]');
    if (!b) return;
    const a = b.dataset.sq;
    if (a === 'go' && !answered) {
      const g = +$('#sqr').value, diff = Math.abs(g - q.real);
      const pts = Math.max(0, Math.round(10 - (10 * diff) / q.tol));
      b.remove(); $('#sqr').disabled = true;
      $('.big', box).innerHTML = `${q.real.toFixed(q.dec)} <small>${q.unit}</small>`;
      reveal(pts, `Dein Tipp: ${g.toFixed(q.dec)} ${q.unit} · ${pts >= 9 ? 'Volltreffer' : pts >= 5 ? 'Nah dran' : 'Daneben'} · +${pts}`);
    } else if (a === 'next') { qi++; qi < qs.length ? render() : done(); }
    else if (a === 'enter') enter();
    else if (a === 'again') begin();
  });
  const FANS = [['Lena, Davos', 88], ['Marco, Chur', 81], ['Sandra, Zürich', 76], ['Nico, Klosters', 70], ['Jonas, Bern', 63]];
  function done() {
    head();
    S.best = Math.max(S.best, score); save();
    const all = [...FANS, ['Du', score, true]].sort((a, b) => b[1] - a[1]);
    const rank = all.findIndex(f => f[2]) + 1;
    box.innerHTML = `<div class="fn" style="text-align:center">Dein Endstand</div>
      <div class="big" style="margin-top:4px">${score} <small>von ${qs.length * 10}</small></div>
      <div class="hl" style="text-align:center">${score >= 80 ? 'Hockey-Experte.' : score >= 50 ? 'Starker Auftritt.' : 'Guter Start. Jetzt kennst du die Zahlen.'}</div>
      <div class="fn" style="text-align:center;margin-top:4px">Platz ${rank} von ${all.length} in der Rangliste zum Final</div>
      <div class="fn" style="margin:20px 0 6px">Rangliste zum Final (Demo)</div>
      <div class="group" style="background:var(--fill)">${all.map((f, i) => `<div class="cell" style="min-height:44px;${f[2] ? 'font-weight:700' : ''}"><span class="fn" style="width:14px">${i + 1}</span><span class="grow">${f[0]}</span><span class="val">${f[1]}</span></div>`).join('')}</div>
      <div class="group pad" style="background:var(--fill);margin-top:16px"><div class="hl">Tickets für den Spengler Cup 2026</div><div class="sub">Sammle über alle 11 Spiele Punkte. Die Besten kommen in die Verlosung (symbolisch).</div></div>
      <div class="fn" style="margin:20px 0 0">Teilnehmen</div>
      ${S.entered ? '<div class="fb"><b>Du bist dabei.</b> Nach dem nächsten Spiel gibt es ein neues Quiz.</div>' : `
      <input class="field" id="gName" placeholder="Vorname" autocomplete="given-name">
      <input class="field" id="gMail" type="email" placeholder="E-Mail" autocomplete="email">
      <label class="chk"><input type="checkbox" id="gOk"> Ich akzeptiere die Teilnahmebedingungen und möchte ans nächste Quiz erinnert werden.</label>
      <button class="btn" data-sq="enter">An der Verlosung teilnehmen</button>
      <div class="fn" style="margin-top:8px">Prototyp: Es wird nichts gesendet oder gespeichert.</div>`}
      <button class="btn sec" style="margin-top:10px" data-sq="again">Nochmal spielen</button>`;
  }
  function enter() {
    const name = $('#gName').value.trim(), mail = $('#gMail').value.trim();
    if (!name) return toast('Bitte gib deinen Vornamen ein.');
    if (!/^\S+@\S+\.\S+$/.test(mail)) return toast('Bitte gib eine gültige E-Mail-Adresse ein.');
    if (!$('#gOk').checked) return toast('Bitte akzeptiere die Teilnahmebedingungen.');
    S.entered = true; save(); toast(`Danke, ${name}. Du bist dabei.`); done();
  }
  function begin() { $('#gameIntro').classList.add('hidden'); $('#gamePlay').classList.remove('hidden'); qs = questions(); qi = 0; score = 0; render(); }
  $('#gameStart').onclick = begin;
  return { enter() { if (!qs.length) { $('#gameIntro').classList.remove('hidden'); $('#gamePlay').classList.add('hidden'); } } };
})();

/* ------------------------------------------------------------------ *
 * Schiri-Spick und Begriffe
 * ------------------------------------------------------------------ */
$('#sigGrid').innerHTML = SIGNALS.map(s => sigTile(s.id)).join('');
const GLOSS_NEW = [
  ['Bully', 'Der Schiri wirft den Puck zwischen zwei Spieler ein. So beginnt jedes Drittel und jede Unterbrechung.'],
  ['Powerplay und Unterzahl', 'Nach einer Strafe spielt ein Team mit einem Mann mehr (Powerplay), das andere mit einem weniger (Unterzahl).'],
  ['Icing', 'Puck aus der eigenen Hälfte über die gegnerische Torlinie, ohne Berührung. Bully vor dem eigenen Tor.'],
  ['Abseits', 'Ein Angreifer ist vor dem Puck über die blaue Linie gefahren. Bully ausserhalb der Zone.'],
  ['Slot', 'Der Raum direkt vor dem Tor. Von hier fallen die meisten Tore.'],
  ['Assist', 'Die Vorlage zum Tor. Bis zu zwei Spieler bekommen einen Assist.'],
  ['Empty Net', 'Das leere Tor, wenn ein Team den Goalie für einen Feldspieler vom Eis genommen hat.'],
];
const GLOSS_PRO = [
  ['xG (Expected Goals)', 'Wahrscheinlichkeit, dass ein Schuss ein Tor wird. Wisehockey berücksichtigt Distanz, Winkel, Pässe davor, Screens und die Position des Goalies.'],
  ['Corsi (CF %)', 'Anteil aller Schussversuche bei 5 gegen 5, während ein Spieler auf dem Eis ist. Über 50 % heisst: Sein Team hat mehr vom Spiel.'],
  ['Fenwick (FF %)', 'Wie Corsi, aber ohne geblockte Schüsse.'],
  ['PDO', 'Schussquote plus Fangquote bei 5 gegen 5. Werte weit über 1.0 deuten oft auf Glück hin.'],
  ['EPV', 'Expected Possession Value: Wie wahrscheinlich ein Puckbesitz in den nächsten 8 Sekunden zu einem Tor führt.'],
  ['Pressure', 'Wie stark ein Spieler beim Pass oder Schuss bedrängt wird: Distanz, Position und Bewegung des Gegners.'],
];
const gl = list => list.map(([t, d]) => `<details><summary>${t}</summary><p>${d}</p></details>`).join('');
$('#glossNew').innerHTML = gl(GLOSS_NEW);
$('#glossPro').innerHTML = gl(GLOSS_PRO);

/* ------------------------------------------------------------------ */
views.start.enter();
// Direktlinks für Screenshots: ?demo=watch | report | spick
(function demo() {
  const d = new URLSearchParams(location.search).get('demo');
  if (d === 'watch') { show('learn'); views.learn._demo(1, 3.6); }
  else if (d === 'watch-pp') { show('learn'); views.learn._demo(2, 6); }
  else if (d && document.getElementById('v-' + d)) show(d);
})();
let lastTs = performance.now();
function loop(ts) {
  const dt = Math.min(0.1, (ts - lastTs) / 1000);
  lastTs = ts;
  CLIPS.forEach(c => c.tick(dt));
  const v = views[active];
  if (v && v.tick) v.tick(dt);
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);
