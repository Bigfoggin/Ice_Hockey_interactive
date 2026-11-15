# In the Game · Spengler Cup Davos

**Don't just watch. Be in the game.** Two ways into the Spengler Cup, built on Wisehockey tracking data.
FHGR Team 3, Data-hack Challenge 2026 (Sport Innovation Challenge).

- **Learn the Game** (for newcomers, during the periods): at every whistle the phone explains what was called and why, shows the real situation on the ice and the animated referee signal. Every rule goes into a rulebook of 30 rules and earns 10 points.
- **Be a Pro** (for fans, in the breaks and after the game): the key scenes come back in a Replay mode (broadcast view) and a Game mode (the scene freezes, you draw the next pass and score up to 100 points by distance to the real pass).
- **Hockey IQ**: rule points plus pass points on one leaderboard; points can be redeemed in a shop or played for leaderboard prizes.

**Live demo:** https://inthegame.jstalder.com (public version with a simulated game, see *Data* below)

## Repository structure

| Path | What |
|---|---|
| `website/` | Landing page that brings both games together (DE/EN, login, Hockey IQ, prizes). `build_public.py` builds the public demo into `outputs/public-demo/`. |
| `learn_the_game/` | Learn the Game web app (`index.html`, `app.js`). `build_data.py` turns the Wisehockey export into `data.js`, `simulate_data.py` creates the simulated game `data.sim.js`, `bundle.py` packs everything into one HTML file. |
| `shared/hv-account.js` | Shared login and Hockey IQ (rule points + pass points), stored in the browser. |
| `index.html` | Be a Pro prototype (Replay and Game mode) by Alessio De Icco. Runs on the real Wisehockey export, see *Data*. |
| `src/`, `notebooks/`, `data_analysis/` | Data preparation and earlier Python prototypes. |

## Try it yourself (simulated game, no data needed)

Everything below runs on a simulated game, so you need neither the Wisehockey data nor an account. You only need Python 3 (no extra packages) and a browser.

```bash
git clone https://github.com/Bigfoggin/Ice_Hockey_interactive.git
cd Ice_Hockey_interactive

python3 learn_the_game/simulate_data.py   # optional: rebuilds the simulated game learn_the_game/data.sim.js
python3 website/build_public.py           # builds the demo into outputs/public-demo/
python3 -m http.server 8000               # serves the folder locally
```

Then open http://localhost:8000/outputs/public-demo/ in your browser. This is the same version as the live demo.

What to try:

1. **Learn the Game:** click *Learn the rules*. The simulated game plays like a live game. At every whistle a popup explains what was called and why, with the real situation on the ice and the referee signal. Collected rules go into the rulebook (*Cheat sheet*).
2. **Be a Pro:** click *Play a pass*. *Replay mode* plays the key scenes like a broadcast. In *Game mode* the scene freezes: drag from the puck to where you think the pass goes. The real play then rolls on and you get up to 100 points per pass, two passes per scene.
3. **Hockey IQ:** log in with any name (stored only in your browser). Rule points and pass points add up to your Hockey IQ, shown on the leaderboard and the prize list.

How the simulation works: `learn_the_game/simulate_data.py` creates a full game in the same format as the real export (`data.js`), with invented teams, players, positions and statistics. The key moments are scripted so that the app finds the same situations as in the real final (faceoff, icing, slashing with power play goal, deflected goal, offside, high-sticking, empty net). It uses a fixed random seed, so every run gives the same game. `website/build_public.py` then builds the website, the Learn the Game app and the Be a Pro preview from it, and checks that no real name ends up in the output.

## Run it with the real data (team only)

Put the Wisehockey CSV files into `data/match_data/` (see below), then:

```bash
python3 learn_the_game/build_data.py      # real data -> learn_the_game/data.js
python3 learn_the_game/bundle.py          # Learn the Game as a single file
VARIANT=video python3 website/build_public.py   # website on real data -> outputs/video-demo/ (stays local)
```

Be a Pro (`index.html`) reads `data/match_data/event_data_sample_Match_events.csv`; serve the repository with `python3 -m http.server` and open `index.html`.

## Data

The Wisehockey tracking data of the challenge is **not** part of this repository (`data/` is git-ignored), in line with the data terms. The public demo therefore runs on a simulated game (`learn_the_game/data.sim.js`): players, positions and statistics are invented, the scenes follow the same rules. Locally, both prototypes run on the real tracking data of the 2025 final.

## Team

Jason Stalder, Alessio De Icco, Anna Skrylnyk, Nicola Augsburger (FHGR)

---

## Original working tree notes

The purpose of this repo is to develop an interactive data-oriented project that makes ice hockey more engaging.



## Repo Working Tree

The code will expect the following structure.


(note: if you want to check the working tree on linux just type this into the terminal: "find . -type d -not -path '*/.*' | sed -e 's/[^-][^\/]*\// |-- /g' -e 's/|\([^ ]\)/|-- \1/'")

```
.   (Ice_hockey_interactive)
├── notebooks
├── doc
├── data
│   ├── match_data
│   ├── us_data
│   └── player_data
├── src
└── competition_files
```

## convert_excel_to_csv.py

once you put the data in the right place, run convert_excel_to_csv.py to... obviously convert the excel files to csv.