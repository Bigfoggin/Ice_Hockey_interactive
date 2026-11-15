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
| `index.html` | Be a Pro prototype (Replay and Game mode) by Alessio De Icco, on the branch `interpolation_optimization`. |
| `src/`, `notebooks/`, `data_analysis/` | Data preparation and earlier Python prototypes. |

## Run it locally

```bash
python3 website/build_public.py          # simulated game, no data needed
python3 -m http.server 8810              # then open http://localhost:8810/outputs/public-demo/
```

With the real data: put the Wisehockey CSV files into `data/match_data/` (see below), then run `python3 learn_the_game/build_data.py` and `python3 learn_the_game/bundle.py`, and open `website/index.html` through the local server. Be a Pro reads `data/match_data/event_data_sample_Match_events.csv` and runs from `index.html` on the branch `interpolation_optimization`.

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