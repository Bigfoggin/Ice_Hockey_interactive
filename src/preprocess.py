import os
import numpy as np
import pandas as pd


def parse_coord(coord_str):
  if pd.isna(coord_str) or not isinstance(coord_str, str):
    return np.array([np.nan, np.nan])
  try:
    parts = coord_str.split(",")
    return np.array([float(parts[0]), float(parts[1])])
  except:
    return np.array([np.nan, np.nan])


def parse_dir(dir_str):
  if pd.isna(dir_str) or not isinstance(dir_str, str):
    return np.array([0.0, 0.0])
  try:
    parts = dir_str.split(",")
    return np.array([float(parts[0]), float(parts[1])])
  except:
    return np.array([0.0, 0.0])


def cubic_hermite_interpolate(p0, v0, p1, v1, t_normalized):
  t = t_normalized[:, np.newaxis]
  t2 = t**2
  t3 = t**3
  h00 = 2 * t3 - 3 * t2 + 1
  h10 = t3 - 2 * t2 + t
  h01 = -2 * t3 + 3 * t2
  h11 = t3 - t2
  return h00 * p0 + h10 * v0 + h01 * p1 + h11 * v1


def preprocess_match_data(
    input_path="data/match_data/event_data_sample_Match_events.csv", output_path="data/match_data/match_data_30fps.csv"
):
  if not os.path.exists(input_path):
    if os.path.exists("../event_data_sample_Match_events.csv"):
      input_path = "../event_data_sample_Match_events.csv"

  print(f"Loading data from {input_path}...")
  df = pd.read_csv(input_path)
  df = df.sort_values(by="MatchClock").reset_index(drop=True)

  fps = 30
  dt = 1.0 / fps
  start_time = float(df["MatchClock"].min())
  end_time = float(df["MatchClock"].max())
  timeline = np.arange(start_time, end_time, dt)

  num_slots = 12
  slot_indices = range(1, num_slots + 1)

  # 1. Extract Player Trajectories
  player_trajectories = {}
  for _, row in df.iterrows():
    t = float(row["MatchClock"])
    for i in slot_indices:
      pid = row.get(f"StartPlayerId{i}")
      if pd.isna(pid):
        continue
      pos = parse_coord(row.get(f"StartPlayerCoordinates{i}"))
      if np.isnan(pos).any():
        continue
      speed = row.get(f"StartPlayerVelocity{i}")
      speed = float(speed) if not pd.isna(speed) else 0.0
      d_vec = parse_dir(row.get(f"StartPlayerDirection{i}"))
      vel = speed * d_vec

      if pid not in player_trajectories:
        player_trajectories[pid] = []
      player_trajectories[pid].append({"time": t, "pos": pos, "vel": vel})

  player_interpolators = {}
  for pid, events in player_trajectories.items():
    events = sorted(events, key=lambda x: x["time"])
    if len(events) < 2:
      continue
    player_interpolators[pid] = {
        "times": np.array([e["time"] for e in events]),
        "positions": np.array([e["pos"] for e in events]),
        "velocities": np.array([e["vel"] for e in events]),
    }

  # 2. Extract Puck Trajectories from Start and End Coordinates
  puck_events = []
  for _, row in df.iterrows():
    t = float(row["MatchClock"])
    sc = parse_coord(row.get("EventStartCoordinate"))
    if not np.isnan(sc).any():
      puck_events.append({"time": t, "pos": sc})
    ec = parse_coord(row.get("EventEndCoordinate"))
    if not np.isnan(ec).any():
      # End coordinate usually happens slightly into the duration towards the next clock
      puck_events.append({"time": t + 0.5, "pos": ec})

  puck_events = sorted(puck_events, key=lambda x: x["time"])
  puck_times = np.array([e["time"] for e in puck_events]) if puck_events else np.array([])
  puck_positions = np.array([e["pos"] for e in puck_events]) if puck_events else np.array([])

  def get_interpolated_puck(t_target):
    if len(puck_times) == 0:
      return np.array([0.0, 0.0])
    idx = np.searchsorted(puck_times, t_target)
    if idx == 0:
      return puck_positions[0]
    elif idx >= len(puck_times):
      return puck_positions[-1]
    else:
      t0 = puck_times[idx - 1]
      t1 = puck_times[idx]
      p0 = puck_positions[idx - 1]
      p1 = puck_positions[idx]
      if t1 == t0:
        return p1
      # Linear or smooth interpolation for puck
      alpha = (t_target - t0) / (t1 - t0)
      return p0 + (p1 - p0) * alpha

  def get_interpolated_player_state(pid, t_target):
    if pid not in player_interpolators:
      return None, None
    interp = player_interpolators[pid]
    times, positions, velocities = interp["times"], interp["positions"], interp["velocities"]

    idx = np.searchsorted(times, t_target)
    if idx == 0:
      return positions[0], velocities[0]
    elif idx >= len(times):
      return positions[-1], velocities[-1]
    else:
      t0 = times[idx - 1]
      t1 = times[idx]
      seg_dur = t1 - t0
      if seg_dur <= 0:
        return positions[idx], velocities[idx]
      t_norm = (t_target - t0) / seg_dur
      p0, p1 = positions[idx - 1], positions[idx]
      v0, v1 = velocities[idx - 1] * seg_dur, velocities[idx] * seg_dur
      pos = cubic_hermite_interpolate(p0, v0, p1, v1, np.array([t_norm]))[0]
      vel = (v1 * t_norm + v0 * (1 - t_norm)) / seg_dur
      return pos, vel

  interpolated_rows = []

  for t_target in timeline:
    nearest_idx = (df["MatchClock"] - t_target).abs().idxmin()
    base_row = df.loc[nearest_idx].copy()

    base_row["MatchClock"] = t_target
    mm = int(t_target // 60)
    ss = int(t_target % 60)
    base_row["MatchClock (mm:ss)"] = f"{mm:02d}:{ss:02d}"

    # Interpolate Puck and store in EventStartCoordinate for the simulation to read
    pk_pos = get_interpolated_puck(t_target)
    base_row["EventStartCoordinate"] = f"{pk_pos[0]:.1f},{pk_pos[1]:.1f}"

    # Interpolate Players
    for i in slot_indices:
      pid = base_row.get(f"StartPlayerId{i}")
      if pd.isna(pid):
        continue
      pos, vel = get_interpolated_player_state(pid, t_target)
      if pos is not None:
        base_row[f"StartPlayerCoordinates{i}"] = f"{pos[0]:.1f},{pos[1]:.1f}"
        speed_val = np.linalg.norm(vel)
        base_row[f"StartPlayerVelocity{i}"] = round(float(speed_val), 3)
        if speed_val > 0:
          d_vec = vel / speed_val
          base_row[f"StartPlayerDirection{i}"] = f"{d_vec[0]:.3f},{d_vec[1]:.3f}"

    interpolated_rows.append(base_row)

    if len(interpolated_rows) % 1000 == 0:
      print(f"Processed {len(interpolated_rows)} frames...")

  os.makedirs(os.path.dirname(output_path), exist_ok=True)
  out_df = pd.DataFrame(interpolated_rows)
  out_df.to_csv(output_path, index=False)
  print(f"Success! Saved smooth 30 FPS interpolated data to {output_path} ({len(out_df)} frames).")


if __name__ == "__main__":
  preprocess_match_data()