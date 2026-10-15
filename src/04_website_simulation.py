import sys
import math
import time
import os
import pandas as pd
import pygame

# ---------------------------------------------------------------------------
# Configuration (Persona 3 Reload / F1 Broadcast Palette)
# ---------------------------------------------------------------------------
VIRTUAL_WIDTH, VIRTUAL_HEIGHT = 1500, 800
TARGET_FPS = 30
FRAMES_PER_STEP = 15

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

CAMERA_ZOOM_WIDTH = 920
CAMERA_ZOOM_HEIGHT = 490
CAMERA_MORPH_FACTOR = 0.2
PIP_WIDTH_RATIO = 0.24
PIP_HEIGHT_RATIO = 0.22


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
    cam_x, cam_y = 0.0, 0.0
    cam_w, cam_h = float(VIRTUAL_WIDTH), float(VIRTUAL_HEIGHT)

    player_interactions = {}
    player_shots = {}
    player_passes = {}
    total_interactions = 0

    print("Precomputing multi-stat timelines...")
    for i in range(len(df) - 1):
        row_a = df.iloc[i]
        row_b = df.iloc[i + 1]

        players_a = extract_players(row_a)
        players_b = extract_players(row_b)
        puck_a = parse_coord_str(row_a.get("EventStartCoordinate"))
        puck_b = parse_coord_str(row_b.get("EventStartCoordinate"))

        event_type = str(row_a.get("EventType", ""))
        event_lower = event_type.lower()
        is_zoom_event = event_type in ("Shot", "Goal", "Pass", "PuckControl")

        primary_name = row_a.get("EventPrimaryPlayerName")

        if "goal" in event_lower:
            puck_x = puck_a[0] if puck_a is not None else 20.0
            if puck_x < 0:
                home_score += 1
            else:
                away_score += 1

        if pd.notna(primary_name) and isinstance(primary_name, str):
            parts = primary_name.split()
            if parts and parts[0].startswith("#"):
                j_num = parts[0][1:]
                clean_name = " ".join(parts[1:])
                player_info = (j_num, clean_name)

                if event_type in ("Shot", "Goal"):
                    player_shots[player_info] = player_shots.get(player_info, 0) + 1
                elif event_type == "Pass":
                    player_passes[player_info] = player_passes.get(player_info, 0) + 1

        if puck_a is not None:
            for p_data in players_a.values():
                j = p_data.get("jersey")
                p_name = p_data.get("name", "Unknown")
                if j:
                    dist = math.hypot(p_data["coord"][0] - puck_a[0], p_data["coord"][1] - puck_a[1])
                    if dist <= 3.5 or is_zoom_event:
                        weight = 2 if is_zoom_event and dist <= 2.0 else 1
                        player_interactions[(j, p_name)] = player_interactions.get((j, p_name), 0) + weight
                        total_interactions += weight

        interaction_shares = {}
        if total_interactions > 0:
            for (j, name), count in sorted(player_interactions.items(), key=lambda x: x[1], reverse=True):
                interaction_shares[(j, name)] = (count / total_interactions) * 100.0

        shots_ranked = dict(sorted(player_shots.items(), key=lambda x: x[1], reverse=True))
        passes_ranked = dict(sorted(player_passes.items(), key=lambda x: x[1], reverse=True))

        if puck_a is not None and puck_b is not None:
            dist_meters = math.hypot(puck_b[0] - puck_a[0], puck_b[1] - puck_a[1])
        else:
            dist_meters = 1.0

        duration = FRAMES_PER_STEP / TARGET_FPS
        base_speed_kmh = dist_meters / max(0.1, duration) * 3.6
        all_ids = set(players_a) | set(players_b)

        previous_speed = 0.0
        for f in range(FRAMES_PER_STEP):
            t = f / FRAMES_PER_STEP
            puck_interp = lerp_coord(puck_a, puck_b, t)

            if is_zoom_event:
                speed_kmh = max(0.0, base_speed_kmh + math.sin(f * 0.5) * 8.0)
            else:
                speed_kmh = max(0.0, base_speed_kmh * 0.5)

            accelerating = True if f == 0 else (speed_kmh >= previous_speed)
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

            if is_zoom_event and puck_interp is not None:
                target_w = float(CAMERA_ZOOM_WIDTH)
                target_h = float(CAMERA_ZOOM_HEIGHT)
                target_x = pk_x - target_w / 2.0
                target_y = pk_y - target_h / 2.0
            else:
                target_x, target_y = 0.0, 0.0
                target_w, target_h = float(VIRTUAL_WIDTH), float(VIRTUAL_HEIGHT)

            cam_x += (target_x - cam_x) * CAMERA_MORPH_FACTOR
            cam_y += (target_y - cam_y) * CAMERA_MORPH_FACTOR
            cam_w += (target_w - cam_w) * CAMERA_MORPH_FACTOR
            cam_h += (target_h - cam_h) * CAMERA_MORPH_FACTOR

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
                "cam_x": cam_x,
                "cam_y": cam_y,
                "cam_w": cam_w,
                "cam_h": cam_h,
                "interaction_shares": interaction_shares,
                "shots_ranked": shots_ranked,
                "passes_ranked": passes_ranked,
            })

    print(f"Precomputation complete: {len(master_frames):,} frames.")
    return master_frames


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


def draw_player(surface, p_data, font_md):
    px, py = scale_coordinates(*p_data["coord"])
    is_home = p_data["team"].lower() == "home"
    primary_color = HOME_TEAM if is_home else AWAY_TEAM

    pygame.draw.circle(surface, (0, 0, 0, 160), (px + 2, py + 3), 16)
    pygame.draw.circle(surface, (15, 22, 36), (px, py), 16)
    pygame.draw.circle(surface, primary_color, (px, py), 14)
    pygame.draw.circle(surface, CYAN_NEON, (px, py), 16, 2)

    jersey = p_data.get("jersey", "")
    if jersey:
        txt_shadow = font_md.render(jersey, True, (0, 0, 0))
        txt = font_md.render(jersey, True, WHITE)
        surface.blit(txt_shadow, txt_shadow.get_rect(center=(px + 1, py + 1)))
        surface.blit(txt, txt.get_rect(center=(px, py)))


def draw_puck(surface, frame, font_md):
    puck_coord = frame["puck"]
    if puck_coord is None:
        return
    pk_x, pk_y = scale_coordinates(*puck_coord)
    pygame.draw.circle(surface, (0, 0, 0), (pk_x + 2, pk_y + 2), 7)
    pygame.draw.circle(surface, (15, 15, 20), (pk_x, pk_y), 7)
    pygame.draw.circle(surface, CYAN_NEON, (pk_x, pk_y), 7, 2)

    if frame["is_zoom"]:
        speed_color = (0, 255, 180) if frame["accelerating"] else (255, 90, 110)
        speed_surf = font_md.render(f'{int(frame["speed"])} km/h', True, speed_color)
        surface.blit(speed_surf, speed_surf.get_rect(center=(pk_x, pk_y + 18)))


def main():
    # Local standalone execution loop
    pygame.init()
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    ACTUAL_WIDTH, ACTUAL_HEIGHT = screen.get_size()
    pygame.display.set_caption("Pro Hockey Analytics — F1 Style Leaderboard Edition")
    clock = pygame.time.Clock()

    FONT_SM = pygame.font.SysFont("Segoe UI", 13, bold=True)
    FONT_MD = pygame.font.SysFont("Segoe UI", 15, bold=True)
    FONT_TITLE = pygame.font.SysFont("Segoe UI", 24, bold=True)

    csv_file = "data/match_data/event_data_sample_Match_events.csv"
    df = pd.read_csv(csv_file)
    master_frames = precompute_replay_timeline(df)

    # ... standard local execution loop can remain here ...
    pygame.quit()


if __name__ == "__main__":
    main()