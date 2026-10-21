import sys
import math
import time
import pandas as pd
import pygame

# ---------------------------------------------------------------------------
# Configuration (Persona 3 Reload / F1 Broadcast Palette)
# ---------------------------------------------------------------------------
VIRTUAL_WIDTH, VIRTUAL_HEIGHT = 1500, 800
TARGET_FPS = 30
FRAMES_PER_STEP = 15  # Fallback for rows without usable timestamps

ARENA_BG = (6, 10, 18)
ICE_BASE = (14, 24, 42)
BOARD_BORDER = (0, 210, 255)
WHITE = (255, 255, 255)
CYAN_NEON = (0, 240, 255)
GOLD_NEON = (255, 190, 30)
PANEL_BG = (10, 16, 28, 240)
LINE_RED = (235, 45, 65)
LINE_BLUE = (0, 130, 210)

HOME_TEAM = (40, 130, 255)
AWAY_TEAM = (255, 45, 95)

# Persona 3 Reload Palette Accents
P3_BLUE = (10, 30, 80)
P3_CYAN = (0, 230, 255)
P3_YELLOW = (255, 230, 0)
P3_RED = (255, 20, 60)

CAMERA_ZOOM_WIDTH = 920
CAMERA_ZOOM_HEIGHT = 490

# --- CAMERA DYNAMICS ---
CAMERA_SMOOTH_SPEED = 0.04  # Controlled per-frame exponential smoothing speed

PIP_WIDTH_RATIO = 0.24
PIP_HEIGHT_RATIO = 0.22

# Zoom Tolerance Buffer (in seconds)
ZOOM_TOLERANCE_SECONDS = 5.0
POPUP_DURATION_SECONDS = 2.5

pygame.init()
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
ACTUAL_WIDTH, ACTUAL_HEIGHT = screen.get_size()
pygame.display.set_caption("Pro Hockey Analytics — Dynamic Smooth Zoom")
clock = pygame.time.Clock()

try:
    FONT_SM = pygame.font.SysFont("Segoe UI", 12, bold=True)
    FONT_MD = pygame.font.SysFont("Segoe UI", 15, bold=True)
    FONT_LG = pygame.font.SysFont("Segoe UI", 20, bold=True)
    FONT_TITLE = pygame.font.SysFont("Segoe UI", 28, bold=True)
    FONT_HUGE = pygame.font.SysFont("Segoe UI", 30, bold=True)
    FONT_BANNER = pygame.font.SysFont("Segoe UI", 24, bold=True)
    FONT_SMALL_BANNER = pygame.font.SysFont("Segoe UI", 13, bold=True)
except Exception:
    FONT_SM = pygame.font.Font(None, 16)
    FONT_MD = pygame.font.Font(None, 22)
    FONT_LG = pygame.font.Font(None, 26)
    FONT_TITLE = pygame.font.Font(None, 32)
    FONT_HUGE = pygame.font.Font(None, 36)
    FONT_BANNER = pygame.font.Font(None, 28)
    FONT_SMALL_BANNER = pygame.font.Font(None, 16)


def scale_coordinates(x, y):
    return (
        int(VIRTUAL_WIDTH / 2 + x * 17.5),
        int(VIRTUAL_HEIGHT / 2 + y * 17.5),
    )


def parse_coord_str(coord_str):
    if pd.isna(coord_str) or not isinstance(coord_str, str):
        return None
    try:
        parts = coord_str.split(",")
        if len(parts) < 2:
            return None
        return float(parts[0]), float(parts[1])
    except (ValueError, TypeError):
        return None


def lerp_coord(coord_a, coord_b, t):
    if coord_a is None:
        return coord_b
    if coord_b is None:
        return coord_a
    return (
        coord_a[0] + (coord_b[0] - coord_a[0]) * t,
        coord_a[1] + (coord_b[1] - coord_a[1]) * t,
    )


def extract_players(row):
    players = {}
    for i in range(1, 13):
        p_id = row.get(f"StartPlayerId{i}")
        coord = parse_coord_str(row.get(f"StartPlayerCoordinates{i}"))
        team = row.get(f"StartPlayerTeam{i}")
        name = row.get(f"StartPlayerName{i}")

        if pd.notna(p_id) and coord is not None:
            jersey = ""
            p_name = "Unknown"
            if pd.notna(name) and isinstance(name, str):
                parts = name.split()
                if parts and parts[0].startswith("#"):
                    jersey = parts[0][1:]
                    p_name = " ".join(parts[1:])
            players[p_id] = {
                "coord": coord,
                "team": str(team) if pd.notna(team) else "",
                "jersey": jersey,
                "name": p_name,
            }
    return players


def precompute_replay_timeline(df):
    master_frames = []
    if len(df) < 2:
        return master_frames

    home_score = 0
    away_score = 0

    player_interactions = {}
    player_shots = {}
    player_passes = {}
    total_interactions = 0

    last_zoom_state_change_time = -999.0
    current_simulated_time = 0.0
    currently_zoomed = False

    print("Precomputing replay timeline and camera targets...")
    for i in range(len(df) - 1):
        row_a = df.iloc[i]
        row_b = df.iloc[i + 1]

        players_a = extract_players(row_a)
        players_b = extract_players(row_b)
        puck_a = parse_coord_str(row_a.get("EventStartCoordinate"))
        puck_b = parse_coord_str(row_b.get("EventStartCoordinate"))

        event_type = str(row_a.get("EventType", ""))
        event_lower = event_type.lower()
        raw_is_zoom_event = event_type in ("Shot", "Goal", "Pass", "PuckControl")

        duration = 0.75
        interpolation_frames = max(1, int(round(duration * TARGET_FPS)))

        if raw_is_zoom_event != currently_zoomed:
            if (current_simulated_time - last_zoom_state_change_time) < ZOOM_TOLERANCE_SECONDS:
                is_zoom_event = currently_zoomed
            else:
                is_zoom_event = raw_is_zoom_event
                currently_zoomed = raw_is_zoom_event
                last_zoom_state_change_time = current_simulated_time
        else:
            is_zoom_event = raw_is_zoom_event

        banner_text = None
        banner_color = P3_YELLOW

        if "goal" in event_lower or str(row_a.get("ShotResult")) == "Goal":
            banner_text = "GOAL!!!"
            banner_color = P3_RED
        elif event_type == "Shot":
            shot_res = str(row_a.get("ShotResult"))
            if shot_res == "Saved":
                banner_text = "GREAT SAVE!"
                banner_color = P3_CYAN
            elif shot_res in ("Goal", "Blocked"):
                pass
            else:
                banner_text = "SHOT ON TARGET!"
                banner_color = P3_YELLOW
        elif event_type == "Pass" and str(row_a.get("PassResult")) == "Successful":
            banner_text = "CLEAN PASS!"
            banner_color = (50, 255, 150)
        elif event_type == "BluelineCrossing" and str(row_a.get("BluelineCrossingResult")) in ("PossessionMaintained", "PuckDumpedIn"):
            banner_text = "ZONE ENTRY!"
            banner_color = P3_CYAN

        primary_name = row_a.get("EventPrimaryPlayerName")

        if "goal" in event_lower:
            left_count = 0
            right_count = 0
            lookback = min(3, i)
            for lb in range(lookback, 0, -1):
                prev_row = df.iloc[i - lb]
                prev_puck = parse_coord_str(prev_row.get("EventStartCoordinate"))
                if prev_puck is not None:
                    if prev_puck[0] < 0:
                        left_count += 1
                    else:
                        right_count += 1

            if left_count == 0 and right_count == 0 and puck_a is not None:
                if puck_a[0] < 0:
                    left_count = 1
                else:
                    right_count = 1

            if left_count > right_count:
                away_score += 1
            else:
                home_score += 1

        if pd.notna(primary_name) and isinstance(primary_name, str):
            parts = primary_name.split()
            if parts and parts[0].startswith("#"):
                j_num = parts[0][1:]
                clean_name = " ".join(parts[1:])
                p_team = ""
                for p_data in players_a.values():
                    if p_data.get("jersey") == j_num:
                        p_team = p_data.get("team", "")
                        break
                player_info = (j_num, clean_name, p_team)

                if event_type in ("Shot", "Goal"):
                    player_shots[player_info] = player_shots.get(player_info, 0) + 1
                elif event_type == "Pass":
                    player_passes[player_info] = player_passes.get(player_info, 0) + 1

        if puck_a is not None:
            for p_data in players_a.values():
                j = p_data.get("jersey")
                p_name = p_data.get("name", "Unknown")
                p_team = p_data.get("team", "")
                if j:
                    dist = math.hypot(p_data["coord"][0] - puck_a[0], p_data["coord"][1] - puck_a[1])
                    if dist <= 3.5 or is_zoom_event:
                        weight = 2 if is_zoom_event and dist <= 2.0 else 1
                        player_interactions[(j, p_name, p_team)] = player_interactions.get((j, p_name, p_team), 0) + weight
                        total_interactions += weight

        interaction_shares = {}
        if total_interactions > 0:
            for (j, name, team), count in sorted(player_interactions.items(), key=lambda x: x[1], reverse=True):
                interaction_shares[(j, name, team)] = (count / total_interactions) * 100.0

        shots_ranked = dict(sorted(player_shots.items(), key=lambda x: x[1], reverse=True))
        passes_ranked = dict(sorted(player_passes.items(), key=lambda x: x[1], reverse=True))

        if puck_a is not None and puck_b is not None:
            dist_meters = math.hypot(puck_b[0] - puck_a[0], puck_b[1] - puck_a[1])
        else:
            dist_meters = 1.0

        base_speed_kmh = dist_meters / max(0.1, duration) * 3.6
        all_ids = set(players_a) | set(players_b)

        previous_speed = 0.0
        for f in range(interpolation_frames):
            t = f / interpolation_frames
            puck_interp = lerp_coord(puck_a, puck_b, t)

            if is_zoom_event:
                speed_kmh = max(0.0, base_speed_kmh + math.sin(f * 0.5) * 8.0)
            else:
                speed_kmh = max(0.0, base_speed_kmh * 0.5)

            if f == 0:
                accelerating = True
            else:
                accelerating = speed_kmh >= previous_speed
            previous_speed = speed_kmh

            interp_players = {}
            for p_id in all_ids:
                p_a = players_a.get(p_id)
                p_b = players_b.get(p_id)
                source = p_a or p_b
                pos = lerp_coord(
                    p_a["coord"] if p_a else None,
                    p_b["coord"] if p_b else None,
                    t,
                )
                if pos is not None:
                    interp_players[p_id] = {
                        "coord": pos,
                        "team": source["team"],
                        "jersey": source.get("jersey", ""),
                        "name": source.get("name", ""),
                    }

            if puck_interp is not None:
                pk_x, pk_y = scale_coordinates(*puck_interp)
            else:
                pk_x, pk_y = VIRTUAL_WIDTH // 2, VIRTUAL_HEIGHT // 2

            target_w = float(CAMERA_ZOOM_WIDTH) if is_zoom_event else float(VIRTUAL_WIDTH)
            target_h = float(CAMERA_ZOOM_HEIGHT) if is_zoom_event else float(VIRTUAL_HEIGHT)
            target_x = pk_x - target_w / 2.0
            target_y = pk_y - target_h / 2.0

            master_frames.append({
                "match_clock": row_a.get("MatchClock (mm:ss)", "00:00"),
                "event_type": event_type,
                "is_zoom": is_zoom_event,
                "event_idx": i + 1,
                "puck": puck_interp,
                "speed": speed_kmh,
                "accelerating": accelerating,
                "players": interp_players,
                "home_score": home_score,
                "away_score": away_score,
                "target_x": target_x,
                "target_y": target_y,
                "target_w": target_w,
                "target_h": target_h,
                "interaction_shares": interaction_shares,
                "shots_ranked": shots_ranked,
                "passes_ranked": passes_ranked,
                "banner_text": banner_text,
                "banner_color": banner_color,
                "banner_anchor": puck_a if banner_text and puck_a is not None else None,
            })

        current_simulated_time += duration

    print(f"Precomputation complete: {len(master_frames):,} raw frames.")
    return master_frames


def optimize_stagnant_frames(master_frames, movement_radius=0.05, fps=30):
    if not master_frames:
        return master_frames

    optimized_frames = [master_frames[0]]
    skip_cooldown_frames = 0  # 1-second grace period counter
    
    i = 1
    while i < len(master_frames):
        current = master_frames[i]
        prev = optimized_frames[-1]

        event_type = str(current.get("event_type", "")).lower()
        banner_text = current.get("banner_text")
        
        is_major_event = (
            "goal" in event_type or 
            banner_text is not None or 
            "faceoff" in event_type or 
            "period" in event_type
        )

        if is_major_event:
            # Enforce 1-second retention window (no frame-skipping right when goal/restart occurs)
            skip_cooldown_frames = fps

        if skip_cooldown_frames > 0:
            optimized_frames.append(current)
            skip_cooldown_frames -= 1
            i += 1
            continue

        puck_a = prev.get("puck")
        puck_b = current.get("puck")
        
        puck_moved = False
        if puck_a is not None and puck_b is not None:
            if math.hypot(puck_b[0] - puck_a[0], puck_b[1] - puck_a[1]) > movement_radius:
                puck_moved = True

        players_moved = False
        players_a = prev.get("players", {})
        players_b = current.get("players", {})

        for p_id, p_data_b in players_b.items():
            if p_id in players_a:
                p_data_a = players_a[p_id]
                dist = math.hypot(p_data_b["coord"][0] - p_data_a["coord"][0],
                                  p_data_b["coord"][1] - p_data_a["coord"][1])
                if dist > movement_radius:
                    players_moved = True
                    break
            else:
                players_moved = True
                break

        if not puck_moved and not players_moved:
            i += 1
            continue

        optimized_frames.append(current)
        i += 1

    print(f"Post-processing optimization with grace period: compressed down to {len(optimized_frames):,} frames.")
    return optimized_frames


def draw_world_event_banner(surface, popup, is_underlayer=False):
    text = popup["text"]
    color = popup["color"]
    anchor = popup["anchor"]
    wall_elapsed = time.time() - popup["start_time"]
    progress = wall_elapsed / POPUP_DURATION_SECONDS

    if not text or anchor is None or progress >= 1.0:
        return

    anchor_x, anchor_y = scale_coordinates(*anchor)
    intro = min(1.0, max(0.0, progress / 0.12))
    outro = min(1.0, max(0.0, (1.0 - progress) / 0.12))
    visibility = min(intro, outro)
    
    max_opacity_factor = 0.7
    if is_underlayer:
        visibility *= 0.55
    
    eased = 1.0 - math.pow(1.0 - intro, 3)
    base_scale = 0.6 + 0.4 * eased
    scale = base_scale * (0.85 if is_underlayer else 1.0)
    
    shake_strength = (1.0 - min(1.0, wall_elapsed / 0.5)) * (2.0 if is_underlayer else 3.0)
    shake_x = math.sin(wall_elapsed * 52.0) * shake_strength
    shake_y = math.cos(wall_elapsed * 43.0) * shake_strength * 0.45

    font = FONT_BANNER if scale > 0.8 else FONT_SMALL_BANNER
    text_surf = font.render(text, True, color)
    
    box_w = max(130, text_surf.get_width() + 24)
    box_h = text_surf.get_height() + 12
    box_w = max(1, int(box_w * scale))
    box_h = max(1, int(box_h * scale))

    panel = pygame.Surface((box_w + 10, box_h + 10), pygame.SRCALPHA)
    
    alpha = max(0, min(178, int(235 * visibility * max_opacity_factor)))
    rect = pygame.Rect(5, 5, box_w, box_h)
    radius = max(3, int(6 * scale))

    pygame.draw.rect(panel, (*color, int(alpha * 0.15)), rect.inflate(6, 6), border_radius=radius)
    pygame.draw.rect(panel, (5, 10, 22, int(alpha * 0.96)), rect, border_radius=radius)
    pygame.draw.rect(panel, (*color, alpha), rect, width=max(1, int(1.5 * scale)), border_radius=radius)

    scaled_text = pygame.transform.smoothscale(
        text_surf,
        (max(1, int(text_surf.get_width() * scale)),
         max(1, int(text_surf.get_height() * scale)))
    )
    text_alpha = pygame.Surface(scaled_text.get_size(), pygame.SRCALPHA)
    text_alpha.blit(scaled_text, (0, 0))
    text_alpha.set_alpha(alpha)
    panel.blit(text_alpha, text_alpha.get_rect(center=rect.center))

    y_shift = 18 if is_underlayer else 0
    dest = panel.get_rect(center=(int(anchor_x + shake_x),
                                  int(anchor_y - 32 * scale - y_shift + shake_y)))
    surface.blit(panel, dest)


def draw_master_rink(surface):
    surface.fill(ARENA_BG)

    x_min, y_min = scale_coordinates(-30.8, -14.85)
    x_max, y_max = scale_coordinates(30.8, 14.85)
    rink_rect = pygame.Rect(x_min, y_min, x_max - x_min, y_max - y_min)

    pygame.draw.rect(surface, (4, 7, 12), rink_rect.inflate(20, 20), 0, border_radius=50)
    pygame.draw.rect(surface, ICE_BASE, rink_rect, 0, border_radius=40)

    glow_surf = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT), pygame.SRCALPHA)
    pygame.draw.circle(glow_surf, (0, 180, 255, 12), (VIRTUAL_WIDTH // 2, VIRTUAL_HEIGHT // 2), 350)
    surface.blit(glow_surf, (0, 0))

    pygame.draw.rect(surface, BOARD_BORDER, rink_rect, 4, border_radius=40)

    center_x, center_y = VIRTUAL_WIDTH // 2, VIRTUAL_HEIGHT // 2
    pygame.draw.line(surface, LINE_RED, (center_x, y_min), (center_x, y_max), 3)
    pygame.draw.circle(surface, CYAN_NEON, (center_x, center_y), 65, 2)
    pygame.draw.circle(surface, LINE_RED, (center_x, center_y), 6)

    blue_x_left = scale_coordinates(-8.5, 0)[0]
    blue_x_right = scale_coordinates(8.5, 0)[0]
    pygame.draw.line(surface, LINE_BLUE, (blue_x_left, y_min), (blue_x_left, y_max), 3)
    pygame.draw.line(surface, LINE_BLUE, (blue_x_right, y_min), (blue_x_right, y_max), 3)

    left_goal_x = scale_coordinates(-26, 0)[0]
    right_goal_x = scale_coordinates(26, 0)[0]
    pygame.draw.line(surface, LINE_RED, (left_goal_x, y_min + 10), (left_goal_x, y_max - 10), 2)
    pygame.draw.line(surface, LINE_RED, (right_goal_x, y_min + 10), (right_goal_x, y_max - 10), 2)

    crease_color = (15, 50, 90)
    for gx in (left_goal_x, right_goal_x):
        pygame.draw.circle(surface, crease_color, (gx, center_y), 20)
        pygame.draw.circle(surface, CYAN_NEON, (gx, center_y), 20, 2)

    net_w, net_h = 14, 24
    pygame.draw.rect(surface, (60, 20, 20), (left_goal_x - net_w, center_y - net_h // 2, net_w, net_h))
    pygame.draw.rect(surface, LINE_RED, (left_goal_x - net_w, center_y - net_h // 2, net_w, net_h), 2)
    pygame.draw.rect(surface, (60, 20, 20), (right_goal_x, center_y - net_h // 2, net_w, net_h))
    pygame.draw.rect(surface, LINE_RED, (right_goal_x, center_y - net_h // 2, net_w, net_h), 2)

    for dot_x, dot_y in [(-20, -6), (-20, 6), (20, -6), (20, 6)]:
        px, py = scale_coordinates(dot_x, dot_y)
        pygame.draw.circle(surface, CYAN_NEON, (px, py), 45, 1)
        pygame.draw.circle(surface, CYAN_NEON, (px, py), 4)

    for dot_x, dot_y in [(-6, -6), (-6, 6), (6, -6), (6, 6)]:
        pygame.draw.circle(surface, CYAN_NEON, scale_coordinates(dot_x, dot_y), 4)


def draw_player(surface, p_data):
    px, py = scale_coordinates(*p_data["coord"])
    is_home = p_data["team"].lower() == "home"
    primary_color = HOME_TEAM if is_home else AWAY_TEAM

    pygame.draw.circle(surface, (0, 0, 0, 160), (px + 2, py + 3), 16)
    pygame.draw.circle(surface, (15, 22, 36), (px, py), 16)
    pygame.draw.circle(surface, primary_color, (px, py), 14)
    pygame.draw.circle(surface, CYAN_NEON, (px, py), 16, 2)

    jersey = p_data.get("jersey", "")
    if jersey:
        txt_shadow = FONT_MD.render(jersey, True, (0, 0, 0))
        txt = FONT_MD.render(jersey, True, WHITE)
        surface.blit(txt_shadow, txt_shadow.get_rect(center=(px + 1, py + 1)))
        surface.blit(txt, txt.get_rect(center=(px, py)))


def draw_puck(surface, frame):
    puck_coord = frame["puck"]
    if puck_coord is None:
        return
    pk_x, pk_y = scale_coordinates(*puck_coord)
    pygame.draw.circle(surface, (0, 0, 0), (pk_x + 2, pk_y + 2), 7)
    pygame.draw.circle(surface, (15, 15, 20), (pk_x, pk_y), 7)
    pygame.draw.circle(surface, CYAN_NEON, (pk_x, pk_y), 7, 2)

    if frame["is_zoom"]:
        speed_color = (0, 255, 180) if frame["accelerating"] else (255, 90, 110)
        speed_surf = FONT_MD.render(f'{int(frame["speed"])} km/h', True, speed_color)
        surface.blit(speed_surf, speed_surf.get_rect(center=(pk_x, pk_y + 18)))


def blit_camera_view(source, destination, cur_cam_x, cur_cam_y, cur_cam_w, cur_cam_h, crop_surface):
    cam_w = max(10, min(float(VIRTUAL_WIDTH), cur_cam_w))
    cam_h = max(10, min(float(VIRTUAL_HEIGHT), cur_cam_h))
    cam_x = max(0.0, min(float(VIRTUAL_WIDTH) - cam_w, cur_cam_x))
    cam_y = max(0.0, min(float(VIRTUAL_HEIGHT) - cam_h, cur_cam_y))

    crop_w, crop_h = max(10, int(cam_w)), max(10, int(cam_h))
    crop_surface.fill(ARENA_BG)
    crop_surface.blit(source, (-int(cam_x), -int(cam_y)))

    crop_view = crop_surface.subsurface((0, 0, crop_w, crop_h))

    target_aspect = ACTUAL_WIDTH / ACTUAL_HEIGHT
    crop_aspect = crop_w / crop_h

    if crop_aspect > target_aspect:
        scaled_w = ACTUAL_WIDTH
        scaled_h = int(ACTUAL_WIDTH / crop_aspect)
    else:
        scaled_h = ACTUAL_HEIGHT
        scaled_w = int(ACTUAL_HEIGHT * crop_aspect)

    scaled = pygame.transform.smoothscale(crop_view, (scaled_w, scaled_h))
    dest_x = (ACTUAL_WIDTH - scaled_w) // 2
    dest_y = (ACTUAL_HEIGHT - scaled_h) // 2

    destination.fill(ARENA_BG)
    destination.blit(scaled, (dest_x, dest_y))
    return cam_x, cam_y, cam_w, cam_h


def main():
    csv_file = "data/match_data/event_data_sample_Match_events.csv"
    try:
        df = pd.read_csv(csv_file)
    except FileNotFoundError:
        print(f"Error: Could not find '{csv_file}'.")
        pygame.quit()
        sys.exit(1)

    home_team_name = "EV Zug"
    away_team_name = "HC Davos"
    for _, row in df.iterrows():
        p1 = str(row.get("StartPlayerName1", ""))
        p7 = str(row.get("StartPlayerName7", ""))
        if "Aeschlimann" in p1 or "Stransky" in p1:
            away_team_name = "HC Davos"
        if "Gajan" in p7 or "Finley" in p7:
            home_team_name = "EV Zug"

    raw_frames = precompute_replay_timeline(df)
    master_frames = optimize_stagnant_frames(raw_frames, movement_radius=0.15, fps=TARGET_FPS)

    if not master_frames:
        print("Not enough rows to create a replay timeline.")
        pygame.quit()
        sys.exit(1)

    total_frames = len(master_frames)
    frame_idx = 0.0
    paused = False
    playback_speed = 1.0
    show_performance = False
    last_frame_ms = 0.0

    cur_cam_x = 0.0
    cur_cam_y = 0.0
    cur_cam_w = float(VIRTUAL_WIDTH)
    cur_cam_h = float(VIRTUAL_HEIGHT)

    rink_surface = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT)).convert()
    draw_master_rink(rink_surface)
    master_surface = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT)).convert()
    crop_surface = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT)).convert()

    pip_w = max(1, int(ACTUAL_WIDTH * PIP_WIDTH_RATIO))
    pip_h = max(1, int(ACTUAL_HEIGHT * PIP_HEIGHT_RATIO))
    pip_background = pygame.transform.smoothscale(rink_surface, (pip_w, pip_h)).convert()
    pip_surface = pygame.Surface((pip_w, pip_h)).convert()

    hud_height = max(1, int(ACTUAL_HEIGHT * 0.085))
    hud_surface = pygame.Surface((ACTUAL_WIDTH, hud_height), pygame.SRCALPHA)
    hud_surface.fill(PANEL_BG)

    text_cache = {}

    def cached_text(font, text, color):
        key = (id(font), text, color)
        result = text_cache.get(key)
        if result is None:
            result = font.render(text, True, color)
            text_cache[key] = result
        return result

    overlay_start_time = time.time()
    active_celebration_idx = -1
    active_popups = []

    print("Replay running. Controls: Space pause, arrows seek/speed, F3 performance, Esc quit.")

    running = True
    while running:
        frame_start = time.perf_counter()
        dt = clock.tick(TARGET_FPS) / 1000.0
        dt = min(dt, 0.25)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_RIGHT:
                    frame_idx = min(total_frames - 1, frame_idx + TARGET_FPS)
                elif event.key == pygame.K_LEFT:
                    frame_idx = max(0.0, frame_idx - TARGET_FPS)
                elif event.key == pygame.K_UP:
                    playback_speed = min(4.0, playback_speed + 0.5)
                elif event.key == pygame.K_DOWN:
                    playback_speed = max(0.5, playback_speed - 0.5)
                elif event.key == pygame.K_F3:
                    show_performance = not show_performance

        if not paused:
            frame_idx += playback_speed * TARGET_FPS * dt
            if frame_idx >= total_frames:
                frame_idx %= total_frames

        current_int_frame = int(frame_idx)
        current_frame = master_frames[current_int_frame]

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
                    "color": current_frame.get("banner_color", P3_YELLOW),
                    "anchor": current_frame.get("banner_anchor"),
                    "start_time": time.time(),
                    "event_idx": active_celebration_idx
                })

        now = time.time()
        active_popups = [p for p in active_popups if (now - p["start_time"]) < POPUP_DURATION_SECONDS]

        master_surface.blit(rink_surface, (0, 0))
        
        for i, popup in enumerate(active_popups):
            is_underlayer = (i < len(active_popups) - 1)
            draw_world_event_banner(master_surface, popup, is_underlayer=is_underlayer)

        for p_data in current_frame["players"].values():
            draw_player(master_surface, p_data)
        draw_puck(master_surface, current_frame)
        
        cam_x, cam_y, cam_w, cam_h = blit_camera_view(
            master_surface, screen, cur_cam_x, cur_cam_y, cur_cam_w, cur_cam_h, crop_surface
        )

        if cam_w < float(VIRTUAL_WIDTH) - 50:
            pip_surface.blit(pip_background, (0, 0))
            for p_data in current_frame["players"].values():
                mx, my = scale_coordinates(*p_data["coord"])
                mx = int(mx * pip_w / VIRTUAL_WIDTH)
                my = int(my * pip_h / VIRTUAL_HEIGHT)
                color = HOME_TEAM if p_data["team"].lower() == "home" else AWAY_TEAM
                pygame.draw.circle(pip_surface, color, (mx, my), 3)

            if current_frame["puck"] is not None:
                mx, my = scale_coordinates(*current_frame["puck"])
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

        status_label = "PAUSED" if paused else "PLAYING"
        status_color = (255, 90, 110) if paused else (0, 255, 180)
        mode_str = "[MORPH ZOOM]" if cam_w < float(VIRTUAL_WIDTH) - 100 else "[FULL VIEW]"
        txt_status = cached_text(FONT_MD, f"[{status_label}] {mode_str}", status_color)
        screen.blit(txt_status, (30, hud_height // 2 - txt_status.get_height() // 2))

        txt_home_label = cached_text(FONT_SM, "HOME", (180, 190, 210))
        txt_away_label = cached_text(FONT_SM, "AWAY", (180, 190, 210))
        txt_home_name = cached_text(FONT_HUGE, home_team_name, HOME_TEAM)
        txt_home_score = cached_text(FONT_HUGE, f" {current_frame['home_score']} ", GOLD_NEON)
        txt_dash = cached_text(FONT_HUGE, " - ", WHITE)
        txt_away_score = cached_text(FONT_HUGE, f" {current_frame['away_score']} ", GOLD_NEON)
        txt_away_name = cached_text(FONT_HUGE, away_team_name, AWAY_TEAM)

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

        info_text = (
            f"Speed: {playback_speed:.1f}x  |  Clock: {current_frame['match_clock']}  "
            f"|  Type: {current_frame['event_type']}"
        )
        txt_info = cached_text(FONT_MD, info_text, WHITE)
        screen.blit(txt_info, txt_info.get_rect(right=ACTUAL_WIDTH - 30, centery=hud_height // 2))

        # Leaderboard State Machine
        cycle_duration = 45.0
        elapsed_real = time.time() - overlay_start_time
        cycle_time = elapsed_real % cycle_duration

        if cycle_time >= 30.0:
            active_time = cycle_time - 30.0
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
                table_w, table_h = 420, 240
                table_surf = pygame.Surface((table_w, table_h), pygame.SRCALPHA)
                table_surf.fill((10, 16, 28, 240))

                header_txt = cached_text(FONT_MD, f"TOP {mode}", GOLD_NEON)
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

                    txt_hash = cached_text(FONT_MD, "#", WHITE)
                    txt_jersey = cached_text(FONT_MD, str(jersey), jersey_color)
                    txt_rest = cached_text(FONT_MD, f" {name:<20} {formatter(val)}", WHITE)

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

        if show_performance:
            perf_text = (
                f"FPS: {clock.get_fps():.1f} | Frame: {last_frame_ms:.1f} ms | "
                f"Replay: {int(frame_idx)}/{total_frames}"
            )
            perf_surf = cached_text(FONT_MD, perf_text, WHITE)
            panel = pygame.Surface((perf_surf.get_width() + 20, perf_surf.get_height() + 12),
                                   pygame.SRCALPHA)
            panel.fill((10, 16, 28, 240))
            screen.blit(panel, (20, hud_height + 15))
            screen.blit(perf_surf, (30, hud_height + 21))

        pygame.display.flip()
        last_frame_ms = (time.perf_counter() - frame_start) * 1000.0

    pygame.quit()


if __name__ == "__main__":
    main()