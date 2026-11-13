/* Demo-Login und Score-Speicher für Be a Pro und Learn the Game.
 *
 * Prototyp: Profil und Scores liegen im localStorage des Browsers,
 * ohne Passwort und ohne Server. Für eine echte, geräteübergreifende
 * Rangliste muss nur der Speicher (STORE) gegen eine API getauscht werden;
 * die Funktionen unten bleiben gleich.
 *
 * Einbinden:  <script src="../shared/hv-account.js"></script>
 * Nutzen:     HVAccount.current()            → { name, email } oder null
 *             HVAccount.login(name, email)
 *             HVAccount.logout()
 *             HVAccount.saveScore('be-a-pro', 83)
 *             HVAccount.best('be-a-pro')     → höchster Score des Nutzers
 *             HVAccount.leaderboard('be-a-pro', 10)
 *             HVAccount.onChange(fn)         → fn(user) bei Login/Logout
 */
(function () {
  'use strict';
  const KEY = 'hv_account_v1';

  const STORE = {
    read() {
      try { return JSON.parse(localStorage.getItem(KEY)) || { user: null, scores: [] }; } catch (e) { return { user: null, scores: [] }; }
    },
    write(state) {
      try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* privater Modus: Scores bleiben nur bis zum Neuladen */ }
    },
  };

  // Beispiel-Einträge, damit die Rangliste im Prototyp nicht leer ist
  const DEMO = {
    'be-a-pro': [['Lena, Davos', 812], ['Marco, Chur', 744], ['Sandra, Zürich', 690], ['Nico, Klosters', 615], ['Jonas, Bern', 540]],
  };

  const listeners = [];
  let state = STORE.read();
  const emit = () => listeners.forEach(fn => { try { fn(state.user); } catch (e) { console.error(e); } });

  window.HVAccount = {
    current() { return state.user; },
    login(name, email) {
      name = String(name || '').trim();
      if (!name) throw new Error('Name fehlt');
      state.user = { name, email: String(email || '').trim(), since: Date.now() };
      STORE.write(state); emit();
      return state.user;
    },
    logout() { state.user = null; STORE.write(state); emit(); },
    saveScore(game, value, meta) {
      if (!state.user) return false;
      state.scores.push({ game, value: Number(value), name: state.user.name, at: Date.now(), meta: meta || null });
      STORE.write(state);
      return true;
    },
    best(game) {
      const mine = state.scores.filter(s => s.game === game && state.user && s.name === state.user.name);
      return mine.length ? Math.max(...mine.map(s => s.value)) : null;
    },
    leaderboard(game, n = 10) {
      const best = {};
      for (const s of state.scores) if (s.game === game) best[s.name] = Math.max(best[s.name] || 0, s.value);
      for (const [name, value] of DEMO[game] || []) if (!(name in best)) best[name] = value;
      return Object.entries(best).map(([name, value]) => ({ name, value, me: !!(state.user && state.user.name === name), demo: (DEMO[game] || []).some(d => d[0] === name) }))
        .sort((a, b) => b.value - a.value).slice(0, n);
    },
    onChange(fn) { listeners.push(fn); },
  };
  window.addEventListener('storage', e => { if (e.key === KEY) { state = STORE.read(); emit(); } });
})();
