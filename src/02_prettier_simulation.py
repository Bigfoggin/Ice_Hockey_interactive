import sys
import math
import time
import pandas as pd
import pygame

# ---------------------------------------------------------------------------
# Configuration (Persona 3 Reload Stylized Broadcast Palette)
# ---------------------------------------------------------------------------
VIRTUAL_WIDTH, VIRTUAL_HEIGHT = 1500, 800
TARGET_FPS = 30
FRAMES_PER_STEP = 15

# Palette: Midnight Arena, Deep Glass Ice, Electric Cyan, Neon Gold, Azure & Crimson Teams
ARENA_BG = (6, 10, 18)
ICE_BASE = (14, 24, 42)
ICE_GLOW = (22, 38, 66)
BOARD_BORDER = (0, 210, 255)    # Electric Cyan
WHITE = (255, 255, 255)
CYAN_NEON = (0, 240, 255)
GOLD_NEON = (255, 190, 30)
PANEL_BG = (10, 16, 28, 230)
LINE_RED = (235, 45, 65)
LINE_BLUE = (0, 130, 210)

# Professional Broadcast Team Colors
HOME_TEAM = (40, 130, 255)   # Electric Azure
AWAY_TEAM = (255, 45, 95)    # Neon Crimson

CAMERA_ZOOM_WIDTH = 920
CAMERA_ZOOM_HEIGHT = 490
CAMERA_MORPH_FACTOR = 0.2
PIP_WIDTH_RATIO = 0.24
PIP_HEIGHT_RATIO = 0.22

pygame.init()
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
ACTUAL_WIDTH, ACTUAL_HEIGHT = screen.get_size()
pygame.display.set_caption("Pro Hockey Analytics — Persona 3 Reload Stylized Edition")
clock = pygame.time.Clock()

# Fonts
try:
    FONT_SM = pygame.font.SysFont("Segoe UI", 14, bold=True)
    FONT_MD = pygame.font.SysFont("Segoe UI", 16, bold=True)
    FONT_LG = pygame.font.SysFont("Segoe UI", 22, bold=True)
    FONT_TITLE = pygame.font.SysFont("Segoe UI", 26, bold=True)
except Exception:
    FONT_SM = pygame.font.Font(None, 18)
    FONT_MD = pygame.font.Font(None, 22)
    FONT_LG = pygame.font.Font(None, 28)
    FONT_TITLE = pygame.font.Font(None, 34)


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


def parse_match_clock(clock_str):
    if pd.isna(clock_str):
        return 0.0
    if isinstance(clock_str, (int, float)):
        return float(clock_str)
    if isinstance(clock_str, str) and ":" in clock_str:
        try:
            parts = clock_str.split(":")
            return int(parts[0]) * 60 + float(parts[1])
        except (ValueError, TypeError):
            return 0.0
    try:
        return float(clock_str)
    except (ValueError, TypeError):
        return 0.0


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
            if pd.notna(name) and isinstance(name, str):
                parts = name.split()
                if parts and parts[0].startswith("#"):
                    jersey = parts[0][1:]
            players[p_id] = {
                "coord": coord,
                "team": str(team) if pd.notna(team) else "",
                "jersey": jersey,
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

    player_interaction_counts = {}
    total_interactions = 0

    print("Precomputing stylized timeline...")
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

        if "goal" in event_lower:
            puck_x = puck_a[0] if puck_a is not None else 20.0
            if puck_x < 0:
                home_score += 1
            else:
                away_score += 1

        if puck_a is not None:
            for p_data in players_a.values():
                j = p_data.get("jersey")
                if j:
                    dist_to_puck = math.hypot(p_data["coord"][0] - puck_a[0], p_data["coord"][1] - puck_a[1])
                    if dist_to_puck <= 3.5 or is_zoom_event:
                        weight = 2 if is_zoom_event and dist_to_puck <= 2.0 else 1
                        player_interaction_counts[j] = player_interaction_counts.get(j, 0) + weight
                        total_interactions += weight

        current_percentages = {}
        if total_interactions > 0:
            for j, count in player_interaction_counts.items():
                current_percentages[j] = (count / total_interactions) * 100.0
            current_percentages = dict(sorted(current_percentages.items(), key=lambda item: item[1], reverse=True))

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
                "interaction_shares": current_percentages,
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


def draw_player(surface, p_data):
    px, py = scale_coordinates(*p_data["coord"])
    is_home = p_data["team"].lower() == "home"
    primary_color = HOME_TEAM if is_home else AWAY_TEAM

    # Clean multi-layered broadcast node (white highlight circle removed)
    # 1. Drop shadow
    pygame.draw.circle(surface, (0, 0, 0, 160), (px + 2, py + 3), 16)
    # 2. Dark metallic bezel ring
    pygame.draw.circle(surface, (15, 22, 36), (px, py), 16)
    # 3. Vibrant team color ring
    pygame.draw.circle(surface, primary_color, (px, py), 14)
    # 4. Neon Cyan rim accent
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


def blit_camera_view(source, destination, frame, crop_surface):
    cam_w = max(10, min(float(VIRTUAL_WIDTH), frame["cam_w"]))
    cam_h = max(10, min(float(VIRTUAL_HEIGHT), frame["cam_h"]))
    cam_x = max(0.0, min(float(VIRTUAL_WIDTH) - cam_w, frame["cam_x"]))
    cam_y = max(0.0, min(float(VIRTUAL_HEIGHT) - cam_h, frame["cam_y"]))

    crop_w, crop_h = max(10, int(cam_w)), max(10, int(cam_h))
    crop_surface.fill(ARENA_BG)
    crop_surface.blit(source, ( -int(cam_x), -int(cam_y)))

    crop_view = crop_surface.subsurface((0, 0, crop_w, crop_h))
    scaled = pygame.transform.scale(crop_view, (ACTUAL_WIDTH, ACTUAL_HEIGHT))
    destination.blit(scaled, (0, 0))
    return cam_x, cam_y, cam_w, cam_h


def main():
    csv_file = "data/match_data/event_data_sample_Match_events.csv"
    try:
        df = pd.read_csv(csv_file)
    except FileNotFoundError:
        print(f"Error: Could not find '{csv_file}'.")
        pygame.quit()
        sys.exit(1)

    master_frames = precompute_replay_timeline(df)
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

    rink_surface = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT)).convert()
    draw_master_rink(rink_surface)
    master_surface = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT)).convert()
    crop_surface = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT)).convert()

    pip_w = max(1, int(ACTUAL_WIDTH * PIP_WIDTH_RATIO))
    pip_h = max(1, int(ACTUAL_HEIGHT * PIP_HEIGHT_RATIO))
    pip_background = pygame.transform.scale(rink_surface, (pip_w, pip_h)).convert()
    pip_surface = pygame.Surface((pip_w, pip_h)).convert()

    hud_height = max(1, int(ACTUAL_HEIGHT * 0.07))
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

        current_frame = master_frames[int(frame_idx)]

        master_surface.blit(rink_surface, (0, 0))
        for p_data in current_frame["players"].values():
            draw_player(master_surface, p_data)
        draw_puck(master_surface, current_frame)

        cam_x, cam_y, cam_w, cam_h = blit_camera_view(
            master_surface, screen, current_frame, crop_surface
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

        score_text = f"HOME  {current_frame['home_score']}  -  {current_frame['away_score']}  AWAY"
        txt_score = cached_text(FONT_TITLE, score_text, GOLD_NEON)
        screen.blit(txt_score, txt_score.get_rect(center=(ACTUAL_WIDTH // 2, hud_height // 2)))

        info_text = (
            f"Speed: {playback_speed:.1f}x  |  Clock: {current_frame['match_clock']}  "
            f"|  Type: {current_frame['event_type']}"
        )
        txt_info = cached_text(FONT_MD, info_text, WHITE)
        screen.blit(txt_info, txt_info.get_rect(right=ACTUAL_WIDTH - 30, centery=hud_height // 2))

        # ---------------------------------------------------------------------------
        # Stylized Interaction Percentage Table (Top Left)
        # ---------------------------------------------------------------------------
        match_secs = parse_match_clock(current_frame["match_clock"])
        if (match_secs % 30.0) <= 5.0:
            shares = current_frame.get("interaction_shares", {})
            if shares:
                table_w, table_h = 240, 190
                table_surf = pygame.Surface((table_w, table_h), pygame.SRCALPHA)
                table_surf.fill((10, 16, 28, 235))
                
                header_txt = cached_text(FONT_SM, "PLAYER INTERACTION %", GOLD_NEON)
                table_surf.blit(header_txt, (14, 12))
                pygame.draw.line(table_surf, CYAN_NEON, (14, 34), (table_w - 14, 34), 2)

                y_offset = 44
                count = 0
                for jersey, pct in shares.items():
                    if count >= 6:
                        break
                    row_str = f"NO. {jersey:<3}  {pct:5.1f}%"
                    row_txt = cached_text(FONT_MD, row_str, WHITE)
                    table_surf.blit(row_txt, (16, y_offset))
                    y_offset += 22
                    count += 1

                pygame.draw.rect(table_surf, CYAN_NEON, table_surf.get_rect(), 2, border_radius=6)
                screen.blit(table_surf, (30, hud_height + 15))

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