import os
import sys
import math
import time
import numpy as np
import pandas as pd
import pygame
from PIL import Image
import streamlit as st

# Configure headless Pygame for server rendering
os.environ["SDL_VIDEODRIVER"] = "dummy"
pygame.init()

# Load 04_website_simulation.py dynamically from the same src/ directory
import importlib.util
current_dir = os.path.dirname(__file__)
sim_path = os.path.join(current_dir, "04_website_simulation.py")

spec = importlib.util.spec_from_file_location("website_simulation", sim_path)
sim = importlib.util.module_from_spec(spec)
sys.modules["website_simulation"] = sim
spec.loader.exec_module(sim)

# ---------------------------------------------------------------------------
# Streamlit Page Config & Styling
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Pro Hockey Analytics — Web Edition",
    page_icon="🏒",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp {
        background-color: #060a12;
        color: #ffffff;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def load_data_from_simulation():
    csv_file = os.path.join(current_dir, "..", "data", "match_data", "event_data_sample_Match_events.csv")
    if not os.path.exists(csv_file):
        return None
    df = pd.read_csv(csv_file)
    return sim.precompute_replay_timeline(df)


def render_simulation_frame_for_web(current_frame, rink_surface, font_sm, font_md, font_title, cycle_time):
    master_surface = pygame.Surface((sim.VIRTUAL_WIDTH, sim.VIRTUAL_HEIGHT))
    crop_surface = pygame.Surface((sim.VIRTUAL_WIDTH, sim.VIRTUAL_HEIGHT))
    screen_surf = pygame.Surface((sim.VIRTUAL_WIDTH, sim.VIRTUAL_HEIGHT))

    # 1. Rink and Entity Drawing using 04 simulation module functions
    master_surface.blit(rink_surface, (0, 0))
    for p_data in current_frame["players"].values():
        sim.draw_player(master_surface, p_data, font_md)
    sim.draw_puck(master_surface, current_frame, font_md)

    # 2. Camera Morphing & Zoom
    cam_w = max(10, min(float(sim.VIRTUAL_WIDTH), current_frame["cam_w"]))
    cam_h = max(10, min(float(sim.VIRTUAL_HEIGHT), current_frame["cam_h"]))
    cam_x = max(0.0, min(float(sim.VIRTUAL_WIDTH) - cam_w, current_frame["cam_x"]))
    cam_y = max(0.0, min(float(sim.VIRTUAL_HEIGHT) - cam_h, current_frame["cam_y"]))

    crop_surface.fill(sim.ARENA_BG)
    crop_surface.blit(master_surface, (-int(cam_x), -int(cam_y)))
    crop_view = crop_surface.subsurface((0, 0, int(cam_w), int(cam_h)))
    scaled_view = pygame.transform.scale(crop_view, (sim.VIRTUAL_WIDTH, sim.VIRTUAL_HEIGHT))
    screen_surf.blit(scaled_view, (0, 0))

    # 3. Picture-in-Picture (PIP) Mini-Map View
    pip_w = max(1, int(sim.VIRTUAL_WIDTH * sim.PIP_WIDTH_RATIO))
    pip_h = max(1, int(sim.VIRTUAL_HEIGHT * sim.PIP_HEIGHT_RATIO))
    
    if cam_w < float(sim.VIRTUAL_WIDTH) - 50:
        pip_background = pygame.transform.scale(rink_surface, (pip_w, pip_h))
        pip_surface = pygame.Surface((pip_w, pip_h))
        pip_surface.blit(pip_background, (0, 0))

        for p_data in current_frame["players"].values():
            mx, my = sim.scale_coordinates(*p_data["coord"])
            mx = int(mx * pip_w / sim.VIRTUAL_WIDTH)
            my = int(my * pip_h / sim.VIRTUAL_HEIGHT)
            color = sim.HOME_TEAM if p_data["team"].lower() == "home" else sim.AWAY_TEAM
            pygame.draw.circle(pip_surface, color, (mx, my), 3)

        if current_frame["puck"] is not None:
            mx, my = sim.scale_coordinates(*current_frame["puck"])
            mx = int(mx * pip_w / sim.VIRTUAL_WIDTH)
            my = int(my * pip_h / sim.VIRTUAL_HEIGHT)
            pygame.draw.circle(pip_surface, sim.CYAN_NEON, (mx, my), 3)

        pip_rect = pygame.Rect(sim.VIRTUAL_WIDTH - pip_w - 30, 70, pip_w, pip_h)
        screen_surf.blit(pip_surface, pip_rect)
        pygame.draw.rect(screen_surf, sim.CYAN_NEON, pip_rect, 2, border_radius=6)

        view_box = pygame.Rect(
            pip_rect.x + int(cam_x * pip_w / sim.VIRTUAL_WIDTH),
            pip_rect.y + int(cam_y * pip_h / sim.VIRTUAL_HEIGHT),
            max(1, int(cam_w * pip_w / sim.VIRTUAL_WIDTH)),
            max(1, int(cam_h * pip_h / sim.VIRTUAL_HEIGHT)),
        )
        pygame.draw.rect(screen_surf, sim.GOLD_NEON, view_box, 2)

    # 4. HUD Top Bar
    hud_height = max(1, int(sim.VIRTUAL_HEIGHT * 0.07))
    hud_surface = pygame.Surface((sim.VIRTUAL_WIDTH, hud_height), pygame.SRCALPHA)
    hud_surface.fill(sim.PANEL_BG)
    screen_surf.blit(hud_surface, (0, 0))
    pygame.draw.line(screen_surf, sim.CYAN_NEON, (0, hud_height), (sim.VIRTUAL_WIDTH, hud_height), 3)

    mode_str = "[MORPH ZOOM]" if cam_w < float(sim.VIRTUAL_WIDTH) - 100 else "[FULL VIEW]"
    txt_status = font_md.render(f"[PLAYING] {mode_str}", True, (0, 255, 180))
    screen_surf.blit(txt_status, (30, hud_height // 2 - txt_status.get_height() // 2))

    score_text = f"HOME  {current_frame['home_score']} - {current_frame['away_score']}  AWAY"
    txt_score = font_title.render(score_text, True, sim.GOLD_NEON)
    screen_surf.blit(txt_score, txt_score.get_rect(center=(sim.VIRTUAL_WIDTH // 2, hud_height // 2)))

    info_text = f"Clock: {current_frame['match_clock']}  |  Type: {current_frame['event_type']}"
    txt_info = font_md.render(info_text, True, sim.WHITE)
    screen_surf.blit(txt_info, txt_info.get_rect(right=sim.VIRTUAL_WIDTH - 30, centery=hud_height // 2))

    # 5. F1-Style Rotating Leaderboards State Machine
    cycle_duration = 45.0
    mod_cycle_time = cycle_time % cycle_duration

    if mod_cycle_time >= 30.0:
        active_time = mod_cycle_time - 30.0
        window_idx = int(active_time // 5.0)
        sub_time = active_time % 5.0

        if window_idx == 0:
            mode = "INTERACTION %"
            data = current_frame.get("interaction_shares", {})
            formatter = lambda val: f"{val:5.1f}%"
        elif window_idx == 1:
            mode = "SHOTS LEADERS"
            data = current_frame.get("shots_ranked", {})
            formatter = lambda val: f"{val} Shots"
        else:
            mode = "PASSES LEADERS"
            data = current_frame.get("passes_ranked", {})
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
            table_w, table_h = 360, 200
            table_surf = pygame.Surface((table_w, table_h), pygame.SRCALPHA)
            table_surf.fill((10, 16, 28, 240))

            header_txt = font_sm.render(f"TOP {mode}", True, sim.GOLD_NEON)
            table_surf.blit(header_txt, (14, 12))
            pygame.draw.line(table_surf, sim.CYAN_NEON, (14, 34), (table_w - 14, 34), 2)

            y_offset = 44
            count = 0
            for (jersey, name), val in data.items():
                if count >= 5:
                    break
                display_str = f"#{jersey} {name}"
                row_str = f"{display_str:<26} {formatter(val)}"
                row_txt = font_sm.render(row_str, True, sim.WHITE)
                table_surf.blit(row_txt, (14, y_offset))
                y_offset += 22
                count += 1

            pygame.draw.rect(table_surf, sim.CYAN_NEON, pygame.Rect(0, 0, table_w, table_h), 2, border_radius=6)

            target_x = 30
            start_x = -table_w - 30
            current_x = int(start_x + (target_x - start_x) * anim_progress)
            screen_surf.blit(table_surf, (current_x, hud_height + 15))

    # Convert to PIL Image for Streamlit
    view = pygame.surfarray.array3d(screen_surf)
    return Image.fromarray(np.transpose(view, (1, 0, 2)))


# ---------------------------------------------------------------------------
# Frontend Tabs Implementation
# ---------------------------------------------------------------------------
st.title("🏒 Pro Hockey Analytics Suite")

tab1, tab2, tab3 = st.tabs([
    "Simulate Game",
    "Player Stat Comparison",
    "Highest Stat Prediction"
])

with tab1:
    st.subheader("Live Match Replay & F1 Broadcast Simulation")
    master_frames = load_data_from_simulation()

    if not master_frames:
        st.error("Could not load simulation timeline. Check file paths.")
    else:
        total_frames = len(master_frames)

        # Initialize session state for real-time play loop
        if "frame_idx" not in st.session_state:
            st.session_state.frame_idx = 0
        if "is_playing" not in st.session_state:
            st.session_state.is_playing = False

        col1, col2, col3 = st.columns([2, 6, 2])
        with col1:
            st.session_state.is_playing = st.toggle("▶ Play / Pause Simulation", value=st.session_state.is_playing)
        with col2:
            st.session_state.frame_idx = st.slider(
                "Timeline Scrubber", 
                0, 
                total_frames - 1, 
                int(st.session_state.frame_idx), 
                1
            )
        with col3:
            playback_speed = st.selectbox("Speed", [1, 2, 4], index=0)

        rink_surface = pygame.Surface((sim.VIRTUAL_WIDTH, sim.VIRTUAL_HEIGHT))
        sim.draw_master_rink(rink_surface)

        font_sm = pygame.font.SysFont("Segoe UI", 13, bold=True)
        font_md = pygame.font.SysFont("Segoe UI", 15, bold=True)
        font_title = pygame.font.SysFont("Segoe UI", 24, bold=True)

        current_idx = int(st.session_state.frame_idx)
        sim_elapsed_real = current_idx / sim.TARGET_FPS
        current_frame = master_frames[current_idx]

        img = render_simulation_frame_for_web(
            current_frame,
            rink_surface,
            font_sm,
            font_md,
            font_title,
            cycle_time=sim_elapsed_real
        )

        st.image(img, width="stretch")
        st.markdown(f"**Match Clock:** `{current_frame['match_clock']}` | **Event Type:** `{current_frame['event_type']}` | **Score:** Home `{current_frame['home_score']}` - `{current_frame['away_score']}` Away")

        # Automated real-time streaming loop driver
        if st.session_state.is_playing:
            st.session_state.frame_idx = (current_idx + int(playback_speed)) % total_frames
            time.sleep(1.0 / (sim.TARGET_FPS * playback_speed))
            st.rerun()

with tab2:
    st.subheader("Player Stat Comparison")
    st.info("Empty placeholder tab.")

with tab3:
    st.subheader("Highest Stat Prediction")
    st.info("Empty placeholder tab.")