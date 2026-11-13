# Shared: Demo-Login und Scores

`hv-account.js` wird von der Website und von Learn the Game genutzt. Damit erscheinen Be-a-Pro-Scores in der Rangliste der Website, ohne dass die Projekte technisch zusammenhängen.

**Prototyp:** Name und Scores liegen im `localStorage` des Browsers. Kein Passwort, kein Server, nichts wird gesendet. Für eine echte Rangliste über alle Geräte muss nur der Speicher in `hv-account.js` gegen eine API getauscht werden, die Funktionen bleiben gleich.

## Für Be a Pro (optional, 2 Zeilen)

```html
<script src="shared/hv-account.js"></script>
```

```js
// am Ende einer Runde
if (window.HVAccount && HVAccount.current()) HVAccount.saveScore('be-a-pro', totalPoints);
```

## Funktionen

| Funktion | Zweck |
|---|---|
| `HVAccount.current()` | angemeldeter Nutzer `{ name, email }` oder `null` |
| `HVAccount.login(name, email)` / `logout()` | an- und abmelden |
| `HVAccount.saveScore(game, value)` | Score speichern (`'be-a-pro'`, `'learn-the-game'`) |
| `HVAccount.best(game)` | bester Score des Nutzers |
| `HVAccount.leaderboard(game, n)` | Top n, inkl. Demo-Einträgen |
| `HVAccount.onChange(fn)` | reagiert auf An- und Abmelden |
