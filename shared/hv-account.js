/* In the Game: Konto und Hockey-IQ für Learn the Game und Be a Pro.
 *
 * Ein Spiel, ein Punktestand:
 *   Hockey-IQ = Regel-Punkte (Learn the Game, 10 pro gelernter Regel, max. 30 Regeln)
 *             + Pass-Punkte (Be a Pro, 0–100 pro Szene, bester Versuch zählt)
 *   Die Punkte sind zugleich Währung für Prämien (Rabattcodes, virtuelle und echte Preise).
 *
 * Prototyp: alles liegt im localStorage des Browsers, ohne Passwort und ohne Server.
 * Für eine echte Rangliste wird nur der Speicher (STORE) gegen eine API getauscht.
 *
 * Einbinden:  <script src="../shared/hv-account.js"></script>
 * Nutzen:     HVAccount.current()                  → { name } oder null
 *             HVAccount.login(name, email) / logout()
 *             HVAccount.addRule(ruleId)             → { isNew, count, rulePoints, iq }
 *             HVAccount.addPass(sceneId, points)
 *             HVAccount.stats(name?)                → { rules, rulePoints, pass, iq }
 *             HVAccount.board(n)                    → Rangliste nach Hockey-IQ
 *             HVAccount.saveScore('be-a-pro', 83)   → wie bisher (zählt als Pass-Punkte)
 *             HVAccount.onChange(fn)
 */
(function () {
  'use strict';
  const KEY = 'hv_account_v2';
  const GAME = 'SC-G11'; // Prototyp: das eine Spiel, das wir nachspielen
  const RULE_POINTS = 10; // Punkte pro gelernter Regel

  const STORE = {
    read() {
      try { return JSON.parse(localStorage.getItem(KEY)) || { user: null, prog: {} }; } catch (e) { return { user: null, prog: {} }; }
    },
    write(s) { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) { /* privater Modus */ } },
  };

  // Beispiel-Freunde, damit die Rangliste im Prototyp nicht leer ist
  const DEMO = [
    ['Sandra', { rules: 9, pass: 120 }],
    ['Nico', { rules: 3, pass: 172 }],
    ['Jonas', { rules: 6, pass: 104 }],
    ['Mia', { rules: 11, pass: 61 }],
  ];

  const listeners = [];
  let state = STORE.read();
  state.prog = state.prog || {};
  const emit = () => listeners.forEach(fn => { try { fn(state.user); } catch (e) { console.error(e); } });
  const save = () => { STORE.write(state); emit(); };
  const me = () => (state.user ? state.user.name : '_guest');
  const prog = (name = me()) => (state.prog[name] = state.prog[name] || { rules: {}, passes: {}, checkins: {} });

  function stats(name = me()) {
    const p = prog(name);
    const rules = Object.keys(p.rules).length;
    const rulePoints = rules * RULE_POINTS;
    const pass = Math.round(Object.values(p.passes).reduce((s, v) => s + v, 0));
    return { rules, rulePoints, pass, iq: rulePoints + pass };
  }

  window.HVAccount = {
    GAME,
    current() { return state.user; },
    login(name, email) {
      name = String(name || '').trim();
      if (!name) throw new Error('Name fehlt');
      // Fortschritt als Gast übernehmen
      const guest = state.prog._guest;
      if (guest) {
        const p = prog(name);
        Object.assign(p.checkins, guest.checkins);
        for (const [id, live] of Object.entries(guest.rules)) p.rules[id] = p.rules[id] || live;
        for (const [id, v] of Object.entries(guest.passes)) p.passes[id] = Math.max(p.passes[id] || 0, v);
        delete state.prog._guest;
      }
      state.user = { name, email: String(email || '').trim(), since: Date.now() };
      save();
      return state.user;
    },
    logout() { state.user = null; save(); },

    // Check-in: Code im Stadion oder im TV-Bild scannen
    checkIn(gameId = GAME) { prog().checkins[gameId] = Date.now(); save(); return true; },
    isLive(gameId = GAME) { return !!prog().checkins[gameId]; },

    // Learn the Game: eine Regel ins Regelbuch (10 Punkte, einmalig)
    addRule(ruleId) {
      const p = prog(), had = ruleId in p.rules;
      if (!had) p.rules[ruleId] = true;
      save();
      const s = stats();
      return { isNew: !had, count: s.rules, rulePoints: s.rulePoints, iq: s.iq, points: had ? 0 : RULE_POINTS };
    },
    hasRule(ruleId) { return ruleId in prog().rules; },
    rules() { return { ...prog().rules }; },

    // Be a Pro: Punkte für eine Szene (bester Versuch zählt)
    addPass(sceneId, points) {
      const v = Number(points);
      const p = prog();
      p.passes[sceneId] = Math.max(p.passes[sceneId] || 0, v);
      save();
      return stats();
    },

    stats,
    board(n = 10) {
      const rows = [];
      for (const [name, p] of Object.entries(state.prog)) {
        if (name === '_guest' || !p) continue;
        const s = stats(name);
        if (s.iq > 0 || (state.user && state.user.name === name)) rows.push({ name, ...s, me: !!(state.user && state.user.name === name), demo: false });
      }
      for (const [name, d] of DEMO) {
        if (rows.some(r => r.name === name)) continue;
        const rulePoints = d.rules * RULE_POINTS;
        rows.push({ name, rules: d.rules, rulePoints, pass: d.pass, iq: rulePoints + d.pass, me: false, demo: true });
      }
      return rows.sort((a, b) => b.iq - a.iq).slice(0, n);
    },

    // Kompatibel zur ersten Version (z. B. Be a Pro: saveScore('be-a-pro', punkte))
    saveScore(game, value) {
      if (game === 'be-a-pro') { this.addPass('s' + Date.now(), value); return true; }
      return false;
    },
    best(game) { return game === 'be-a-pro' ? stats().pass : stats().rules; },
    leaderboard(game, n = 10) { return this.board(n).map(r => ({ name: r.name, value: r.iq, me: r.me, demo: r.demo })); },

    // nur für Demos und das Demovideo: Fortschritt einer Person setzen
    _seed(name, data) {
      const p = prog(name);
      if (data.rules) for (const [id, live] of Object.entries(data.rules)) p.rules[id] = live;
      if (data.passes) Object.assign(p.passes, data.passes);
      if (data.checkins) Object.assign(p.checkins, data.checkins);
      save();
    },
    _reset() { state = { user: null, prog: {} }; save(); },
    onChange(fn) { listeners.push(fn); },
  };
  window.addEventListener('storage', e => { if (e.key === KEY) { state = STORE.read(); state.prog = state.prog || {}; emit(); } });
})();
