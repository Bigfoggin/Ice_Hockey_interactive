import importlib
import pandas as pd

# Dynamically import module starting with a number
prettier_sim = importlib.import_module("02_prettier_simulation")

precompute_replay_timeline = prettier_sim.precompute_replay_timeline
optimize_stagnant_frames = prettier_sim.optimize_stagnant_frames
TARGET_FPS = prettier_sim.TARGET_FPS


def main():
    csv_file = "data/match_data/event_data_sample_Match_events.csv"
    print(f"Loading match data from {csv_file}...")
    try:
        df = pd.read_csv(csv_file)
    except FileNotFoundError:
        print(f"Error: Could not find '{csv_file}'.")
        return

    # Run the precomputation and optimization pipeline
    print("Running precomputation timeline...")
    raw_frames = precompute_replay_timeline(df)
    
    print("Optimizing frames...")
    master_frames = optimize_stagnant_frames(raw_frames, movement_radius=0.15, fps=TARGET_FPS)

    if not master_frames:
        print("No frames generated.")
        return

    # Flatten and extract metadata into a tabular format
    debug_rows = []
    for idx, frame in enumerate(master_frames):
        debug_rows.append({
            "frame_index": idx,
            "match_clock": frame.get("match_clock"),
            "event_type": frame.get("event_type"),
            "is_zoom": frame.get("is_zoom"),
            "event_idx": frame.get("event_idx"),
            "puck_x": frame.get("puck")[0] if frame.get("puck") else None,
            "puck_y": frame.get("puck")[1] if frame.get("puck") else None,
            "speed_kmh": frame.get("speed"),
            "accelerating": frame.get("accelerating"),
            "target_x": frame.get("target_x"),
            "target_y": frame.get("target_y"),
            "target_w": frame.get("target_w"),
            "target_h": frame.get("target_h"),
            "home_score": frame.get("home_score"),
            "away_score": frame.get("away_score"),
            "banner_text": frame.get("banner_text"),
        })

    debug_df = pd.DataFrame(debug_rows)
    output_filename = "frames_debug_log.csv"
    debug_df.to_csv(output_filename, index=False)
    print(f"Successfully saved {len(debug_df):,} frames to '{output_filename}'.")


if __name__ == "__main__":
    main()