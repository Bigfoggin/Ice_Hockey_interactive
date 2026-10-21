import sys
import os
import math
import time
import importlib.util
import multiprocessing
import pandas as pd
import numpy as np
import imageio.v2 as imageio
import pygame

# Set dummy video driver for headless/offscreen rendering with Pygame
os.environ["SDL_VIDEODRIVER"] = "dummy"

def load_simulation_module(script_name="02_prettier_simulation.py"):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    paths_to_check = [
        os.path.join(current_dir, script_name),
        os.path.join(current_dir, "..", "src", script_name),
        os.path.join(current_dir, "..", script_name),
        script_name
    ]
    
    script_path = None
    for p in paths_to_check:
        if os.path.exists(p):
            script_path = p
            break
            
    if not script_path or not os.path.exists(script_path):
        raise FileNotFoundError(f"Could not find simulation script '{script_name}' searched in: {paths_to_check}")
    
    spec = importlib.util.spec_from_file_location("prettier_simulation", script_path)
    sim_module = importlib.util.module_from_spec(spec)
    sys.modules["prettier_simulation"] = sim_module
    spec.loader.exec_module(sim_module)
    return sim_module

_worker_sim_module = None

def get_worker_sim_module():
    global _worker_sim_module
    if _worker_sim_module is None:
        _worker_sim_module = load_simulation_module("02_prettier_simulation.py")
    return _worker_sim_module


def render_single_frame(args):
    """
    Worker function to render an individual frame independently in a parallel process.
    """
    idx, frame_data, sim_constants, home_team_name, away_team_name = args
    
    sim = get_worker_sim_module()
    
    VIRTUAL_WIDTH = sim_constants["VIRTUAL_WIDTH"]
    VIRTUAL_HEIGHT = sim_constants["VIRTUAL_HEIGHT"]
    ACTUAL_WIDTH = sim_constants["ACTUAL_WIDTH"]
    ACTUAL_HEIGHT = sim_constants["ACTUAL_HEIGHT"]
    PIP_WIDTH_RATIO = sim_constants["PIP_WIDTH_RATIO"]
    PIP_HEIGHT_RATIO = sim_constants["PIP_HEIGHT_RATIO"]
    PANEL_BG = sim_constants["PANEL_BG"]
    CYAN_NEON = sim_constants["CYAN_NEON"]
    GOLD_NEON = sim_constants["GOLD_NEON"]
    HOME_TEAM = sim_constants["HOME_TEAM"]
    AWAY_TEAM = sim_constants["AWAY_TEAM"]
    WHITE = sim_constants["WHITE"]

    # Initialize headless Pygame surfaces locally for this worker process
    rink_surface = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT)).convert()
    sim.draw_master_rink(rink_surface)

    master_surface = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT)).convert()
    crop_surface = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT)).convert()
    screen = pygame.Surface((ACTUAL_WIDTH, ACTUAL_HEIGHT)).convert()

    pip_w = max(1, int(ACTUAL_WIDTH * PIP_WIDTH_RATIO))
    pip_h = max(1, int(ACTUAL_HEIGHT * PIP_HEIGHT_RATIO))
    pip_background = pygame.transform.smoothscale(rink_surface, (pip_w, pip_h)).convert()
    pip_surface = pygame.Surface((pip_w, pip_h)).convert()

    hud_height = max(1, int(ACTUAL_HEIGHT * 0.085))
    hud_surface = pygame.Surface((ACTUAL_WIDTH, hud_height), pygame.SRCALPHA)
    hud_surface.fill(PANEL_BG)

    cur_cam_x = frame_data["cur_cam_x"]
    cur_cam_y = frame_data["cur_cam_y"]
    cur_cam_w = frame_data["cur_cam_w"]
    cur_cam_h = frame_data["cur_cam_h"]
    current_sim_time = frame_data["current_sim_time"]

    master_surface.blit(rink_surface, (0, 0))

    # Render Active Event Popups
    for popup in frame_data.get("active_popups", []):
        adapted_popup = popup.copy()
        adapted_popup["start_time"] = time.time() - (current_sim_time - popup["start_time"])
        sim.draw_world_event_banner(master_surface, adapted_popup, is_underlayer=False)

    # Draw Players & Puck
    for p_data in frame_data["players"].values():
        sim.draw_player(master_surface, p_data)
    sim.draw_puck(master_surface, frame_data)

    # Monkey-patch actual resolution globally for 02's blit function scaling math
    original_actual_width = getattr(sim, "ACTUAL_WIDTH", 1920)
    original_actual_height = getattr(sim, "ACTUAL_HEIGHT", 1080)
    sim.ACTUAL_WIDTH = ACTUAL_WIDTH
    sim.ACTUAL_HEIGHT = ACTUAL_HEIGHT

    # Camera View Blit (handles full-screen scaling properly)
    cam_x, cam_y, cam_w, cam_h = sim.blit_camera_view(
        master_surface, screen, cur_cam_x, cur_cam_y, cur_cam_w, cur_cam_h, crop_surface
    )

    sim.ACTUAL_WIDTH = original_actual_width
    sim.ACTUAL_HEIGHT = original_actual_height

    # PIP Minimap
    if cam_w < float(VIRTUAL_WIDTH) - 50:
        pip_surface.blit(pip_background, (0, 0))
        for p_data in frame_data["players"].values():
            mx, my = sim.scale_coordinates(*p_data["coord"])
            mx = int(mx * pip_w / VIRTUAL_WIDTH)
            my = int(my * pip_h / VIRTUAL_HEIGHT)
            color = HOME_TEAM if p_data["team"].lower() == "home" else AWAY_TEAM
            pygame.draw.circle(pip_surface, color, (mx, my), 3)

        if frame_data["puck"] is not None:
            mx, my = sim.scale_coordinates(*frame_data["puck"])
            mx = int(mx * pip_w / VIRTUAL_WIDTH)
            my = int(my * pip_h / VIRTUAL_HEIGHT)
            pygame.draw.circle(pip_surface, CYAN_NEON, (mx, my), 3)

        pip_rect = pygame.Rect(ACTUAL_WIDTH - pip_w - 30, 70, pip_w, pip_h)
        screen.blit(pip_surface, pip_rect)
        pygame.draw.rect(screen, CYAN_NEON, pip_rect, 2, border_radius=6)

        view_box = pygame.Rect(
            pip_rect.x + int(cam_x * pip_w / VIRTUAL_WIDTH),
            pip_rect.y + int(cam_y * pip_h / VIRTUAL_HEIGHT),
            max(1, int(cam_w * pip_w / VIRTUAL_WIDTH)),
            max(1, int(cam_h * pip_h / VIRTUAL_HEIGHT)),
        )
        pygame.draw.rect(screen, GOLD_NEON, view_box, 2)

    # HUD Top Bar
    screen.blit(hud_surface, (0, 0))
    pygame.draw.line(screen, CYAN_NEON, (0, hud_height), (ACTUAL_WIDTH, hud_height), 3)

    mode_str = "[MORPH ZOOM]" if cam_w < float(VIRTUAL_WIDTH) - 100 else "[FULL VIEW]"
    txt_status = sim.FONT_MD.render(f"[RECORDING] {mode_str}", True, (0, 255, 180))
    screen.blit(txt_status, (30, hud_height // 2 - txt_status.get_height() // 2))

    txt_home_label = sim.FONT_SM.render("HOME", True, (180, 190, 210))
    txt_away_label = sim.FONT_SM.render("AWAY", True, (180, 190, 210))
    txt_home_name = sim.FONT_HUGE.render(home_team_name, True, HOME_TEAM)
    txt_home_score = sim.FONT_HUGE.render(f" {frame_data['home_score']} ", True, GOLD_NEON)
    txt_dash = sim.FONT_HUGE.render(" - ", True, WHITE)
    txt_away_score = sim.FONT_HUGE.render(f" {frame_data['away_score']} ", True, GOLD_NEON)
    txt_away_name = sim.FONT_HUGE.render(away_team_name, True, AWAY_TEAM)

    screen_center_x = ACTUAL_WIDTH // 2
    dash_x = screen_center_x - (txt_dash.get_width() // 2)
    left_block_width = txt_home_name.get_width() + txt_home_score.get_width()
    home_start_x = dash_x - left_block_width
    away_start_x = dash_x + txt_dash.get_width()

    y_labels = 6
    y_names = hud_height // 2 + 5

    curr_x = home_start_x
    screen.blit(txt_home_name, (curr_x, y_names - txt_home_name.get_height() // 2))
    curr_x += txt_home_name.get_width()
    screen.blit(txt_home_score, (curr_x, y_names - txt_home_score.get_height() // 2))
    home_score_x = curr_x

    screen.blit(txt_dash, (dash_x, y_names - txt_dash.get_height() // 2))

    curr_x = away_start_x
    screen.blit(txt_away_score, (curr_x, y_names - txt_away_score.get_height() // 2))
    away_score_x = curr_x
    curr_x += txt_away_score.get_width()
    screen.blit(txt_away_name, (curr_x, y_names - txt_away_name.get_height() // 2))

    home_score_center = home_score_x + (txt_home_score.get_width() // 2)
    away_score_center = away_score_x + (txt_away_score.get_width() // 2)

    screen.blit(txt_home_label, (home_score_center - (txt_home_label.get_width() // 2), y_labels))
    screen.blit(txt_away_label, (away_score_center - (txt_away_label.get_width() // 2), y_labels))

    info_text = f"Clock: {frame_data['match_clock']}  |  Type: {frame_data['event_type']}"
    txt_info = sim.FONT_MD.render(info_text, True, WHITE)
    screen.blit(txt_info, txt_info.get_rect(right=ACTUAL_WIDTH - 30, centery=hud_height // 2))

    # Leaderboard Overlay
    cycle_duration = 45.0
    cycle_time = current_sim_time % cycle_duration

    if cycle_time >= 30.0:
        active_time = cycle_time - 30.0
        window_idx = int(active_time // 5.0)
        sub_time = active_time % 5.0

        if window_idx == 0:
            mode = "INTERACTION %"
            data = frame_data.get("interaction_shares", {})
            formatter = lambda val: f"{val:5.1f}%"
        elif window_idx == 1:
            mode = "SHOTS LEADERS"
            data = frame_data.get("shots_ranked", {})
            formatter = lambda val: f"{val} Shots"
        else:
            mode = "PASSES LEADERS"
            data = frame_data.get("passes_ranked", {})
            formatter = lambda val: f"{val} Passes"

        anim_duration = 0.6
        if sub_time < anim_duration:
            p = sub_time / anim_duration
            anim_progress = 1.0 - math.pow(1.0 - p, 3)
        elif sub_time > (5.0 - anim_duration):
            p = (5.0 - sub_time) / anim_duration
            anim_progress = 1.0 - math.pow(1.0 - p, 3)
        else:
            anim_progress = 1.0

        anim_progress = max(0.0, min(1.0, anim_progress))

        if anim_progress > 0.0:
            table_w, table_h = 420, 240
            table_surf = pygame.Surface((table_w, table_h), pygame.SRCALPHA)
            table_surf.fill((10, 16, 28, 240))

            header_txt = sim.FONT_MD.render(f"TOP {mode}", True, GOLD_NEON)
            table_surf.blit(header_txt, (16, 14))
            pygame.draw.line(table_surf, CYAN_NEON, (16, 38), (table_w - 16, 38), 2)

            y_offset = 50
            count = 0
            for item, val in data.items():
                if count >= 5:
                    break
                if len(item) == 3:
                    jersey, name, team = item
                else:
                    jersey, name = item
                    team = ""

                is_home = team.lower() == "home"
                jersey_color = HOME_TEAM if is_home else AWAY_TEAM

                txt_hash = sim.FONT_MD.render("#", True, WHITE)
                txt_jersey = sim.FONT_MD.render(str(jersey), True, jersey_color)
                txt_rest = sim.FONT_MD.render(f" {name:<20} {formatter(val)}", True, WHITE)

                current_x = 16
                table_surf.blit(txt_hash, (current_x, y_offset))
                current_x += txt_hash.get_width()
                table_surf.blit(txt_jersey, (current_x, y_offset))
                current_x += txt_jersey.get_width()
                table_surf.blit(txt_rest, (current_x, y_offset))

                y_offset += 32
                count += 1

            pygame.draw.rect(table_surf, CYAN_NEON, pygame.Rect(0, 0, table_w, table_h), 2, border_radius=6)
            target_x = 30
            start_x_box = -table_w - 30
            current_x_box = int(start_x_box + (target_x - start_x_box) * anim_progress)
            screen.blit(table_surf, (current_x_box, hud_height + 15))

    # Convert Surface to Numpy Array
    img_array = pygame.surfarray.array3d(screen)
    img_array = np.transpose(img_array, (1, 0, 2))
    return idx, img_array


def convert_replay_to_video(
    csv_file=None,
    output_video="replay_output.mp4",
    max_frames=None,
    fps=30
):
    print("Loading simulation module from 02_prettier_simulation.py...")
    sim = load_simulation_module("02_prettier_simulation.py")
    
    if csv_file is None:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        csv_file = os.path.join(current_dir, "..", "data", "match_data", "event_data_sample_Match_events.csv")
        if not os.path.exists(csv_file):
            csv_file = "data/match_data/event_data_sample_Match_events.csv"
            
    print(f"Reading match event data from '{csv_file}'...")
    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"Data file '{csv_file}' not found.")
    
    df = pd.read_csv(csv_file)
    
    home_team_name = getattr(sim, "HOME_TEAM_NAME", "EV Zug")
    away_team_name = getattr(sim, "AWAY_TEAM_NAME", "HC Davos")
    for _, row in df.iterrows():
        p1 = str(row.get("StartPlayerName1", ""))
        p7 = str(row.get("StartPlayerName7", ""))
        if "Aeschlimann" in p1 or "Stransky" in p1:
            away_team_name = "HC Davos"
        if "Gajan" in p7 or "Finley" in p7:
            home_team_name = "EV Zug"

    print("Precomputing replay timeline...")
    raw_frames = sim.precompute_replay_timeline(df)
    target_fps = getattr(sim, "TARGET_FPS", fps)
    
    if hasattr(sim, "optimize_stagnant_frames"):
        master_frames = sim.optimize_stagnant_frames(raw_frames, movement_radius=0.15, fps=target_fps)
    else:
        master_frames = raw_frames

    if not master_frames:
        print("No frames generated from event data.")
        return

    if max_frames is not None:
        master_frames = master_frames[:max_frames]

    total_frames = len(master_frames)
    print(f"Precomputing camera trajectories for {total_frames:,} frames...")

    VIRTUAL_WIDTH = getattr(sim, "VIRTUAL_WIDTH", 1500)
    VIRTUAL_HEIGHT = getattr(sim, "VIRTUAL_HEIGHT", 800)
    ACTUAL_WIDTH, ACTUAL_HEIGHT = 1920, 1080
    CAMERA_SMOOTH_SPEED = getattr(sim, "CAMERA_SMOOTH_SPEED", 0.04)
    POPUP_DURATION_SECONDS = getattr(sim, "POPUP_DURATION_SECONDS", 2.5)

    cur_cam_x, cur_cam_y = 0.0, 0.0
    cur_cam_w, cur_cam_h = float(VIRTUAL_WIDTH), float(VIRTUAL_HEIGHT)
    
    active_celebration_idx = -1
    active_popups = []
    processed_frames_data = []

    for idx, current_frame in enumerate(master_frames):
        current_sim_time = idx / float(target_fps)

        target_x = current_frame["target_x"]
        target_y = current_frame["target_y"]
        target_w = current_frame["target_w"]
        target_h = current_frame["target_h"]

        cur_cam_x += (target_x - cur_cam_x) * CAMERA_SMOOTH_SPEED
        cur_cam_y += (target_y - cur_cam_y) * CAMERA_SMOOTH_SPEED
        cur_cam_w += (target_w - cur_cam_w) * CAMERA_SMOOTH_SPEED
        cur_cam_h += (target_h - cur_cam_h) * CAMERA_SMOOTH_SPEED

        if current_frame.get("banner_text"):
            if active_celebration_idx != current_frame.get("event_idx"):
                active_celebration_idx = current_frame.get("event_idx")
                active_popups.append({
                    "text": current_frame["banner_text"],
                    "color": current_frame.get("banner_color", getattr(sim, "P3_YELLOW", (255, 230, 0))),
                    "anchor": current_frame.get("banner_anchor"),
                    "start_time": current_sim_time,
                    "event_idx": active_celebration_idx
                })

        active_popups = [p for p in active_popups if (current_sim_time - p["start_time"]) < POPUP_DURATION_SECONDS]

        frame_payload = current_frame.copy()
        frame_payload["cur_cam_x"] = cur_cam_x
        frame_payload["cur_cam_y"] = cur_cam_y
        frame_payload["cur_cam_w"] = cur_cam_w
        frame_payload["cur_cam_h"] = cur_cam_h
        frame_payload["current_sim_time"] = current_sim_time
        frame_payload["active_popups"] = list(active_popups)

        processed_frames_data.append(frame_payload)

    sim_constants = {
        "VIRTUAL_WIDTH": VIRTUAL_WIDTH,
        "VIRTUAL_HEIGHT": VIRTUAL_HEIGHT,
        "ACTUAL_WIDTH": ACTUAL_WIDTH,
        "ACTUAL_HEIGHT": ACTUAL_HEIGHT,
        "PIP_WIDTH_RATIO": getattr(sim, "PIP_WIDTH_RATIO", 0.24),
        "PIP_HEIGHT_RATIO": getattr(sim, "PIP_HEIGHT_RATIO", 0.22),
        "PANEL_BG": getattr(sim, "PANEL_BG", (10, 16, 28, 240)),
        "CYAN_NEON": getattr(sim, "CYAN_NEON", (0, 240, 255)),
        "GOLD_NEON": getattr(sim, "GOLD_NEON", (255, 190, 30)),
        "HOME_TEAM": getattr(sim, "HOME_TEAM", (40, 130, 255)),
        "AWAY_TEAM": getattr(sim, "AWAY_TEAM", (255, 45, 95)),
        "WHITE": getattr(sim, "WHITE", (255, 255, 255))
    }

    print(f"Initializing video writer -> '{output_video}'...")
    writer = imageio.get_writer(output_video, fps=target_fps, codec="libx264", quality=8)

    num_workers = max(1, multiprocessing.cpu_count() - 1)
    print(f"Rendering frames in parallel using {num_workers} CPU cores...")

    worker_args = [(idx, frame_data, sim_constants, home_team_name, away_team_name) 
                   for idx, frame_data in enumerate(processed_frames_data)]

    chunk_size = 100
    rendered_buffer = {}
    next_frame_to_write = 0

    with multiprocessing.Pool(processes=num_workers) as pool:
        for idx, img_array in pool.imap_unordered(render_single_frame, worker_args, chunksize=20):
            rendered_buffer[idx] = img_array

            while next_frame_to_write in rendered_buffer:
                writer.append_data(rendered_buffer.pop(next_frame_to_write))
                if (next_frame_to_write + 1) % 100 == 0 or (next_frame_to_write + 1) == total_frames:
                    print(f"Processed & Written {next_frame_to_write + 1}/{total_frames} frames ({((next_frame_to_write + 1) / total_frames) * 100:.1f}%)")
                next_frame_to_write += 1

    writer.close()
    print(f"Video conversion complete! File saved to: {output_video}")

if __name__ == "__main__":
    convert_replay_to_video()