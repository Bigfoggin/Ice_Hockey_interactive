# Learn the Game

Prototyp für Einsteiger:innen: Sobald der Schiri pfeift, erklärt die App, **was** gepfiffen wurde und **warum**, mit kurzer Animation und dem Handzeichen. Im Prototyp werden die Pfiffe des Finals HCD – USC (31.12.2025) nachgespielt, als wäre das Spiel live.

Weitere Bereiche im Prototyp: Spielbericht (Tore als 2D-Replay), Schiri-Spick.

## Starten

Die Spieldaten sind nicht im Repo. Die Wisehockey-CSV-Dateien des Finals gehören nach `data/match_data/` (wie im übrigen Repo).

```bash
cd learn_the_game
python3 build_data.py   # erzeugt data.js aus den CSV-Dateien
python3 bundle.py       # packt alles in Hockey-verstehen.html
open Hockey-verstehen.html
```

Liegen die CSV-Dateien woanders: `HOCKEY_DATA=/pfad/zum/ordner python3 build_data.py`

## Dateien

| Datei | Inhalt |
|---|---|
| `index.html` | Oberfläche und Design |
| `app.js` | Logik: Datenspeicher, Eisfeld, Erklär-Popups, Spielbericht |
| `build_data.py` | Wandelt die Wisehockey-CSV in `data.js` um |
| `bundle.py` | Packt alles in eine einzelne Datei `Hockey-verstehen.html` |

`data.js` und `Hockey-verstehen.html` enthalten die Spieldaten und werden deshalb nicht committet.
