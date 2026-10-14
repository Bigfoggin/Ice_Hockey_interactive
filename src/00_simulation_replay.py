import sys
import pandas as pd
import pygame

# Initialize Pygame
pygame.init()

# Constants (HD Broadcast Window - used as our virtual render resolution)
VIRTUAL_WIDTH, VIRTUAL_HEIGHT = 1500, 800
TARGET_FPS = 30

# Broadcast Ice Palette
ICE_BASE = (228, 234, 240)
ICE_SHADOW = (205, 215, 225)
BOARD_BORDER = (140, 165, 195)
WHITE = (255, 255, 255)
BLACK = (20, 20, 20)
UNIFORM_BORDER = (40, 40, 40)
DARK_PANEL = (20, 24, 30, 235)
LINE_RED = (195, 40, 40)
LINE_BLUE = (30, 85, 190)

# Team Branding Colors
PURPLE = (95, 25, 145)
YELLOW = (235, 180, 15)

# Initialize in Fullscreen Mode (adapts to display resolution)
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
ACTUAL_WIDTH, ACTUAL_HEIGHT = screen.get_size()
pygame.display.set_caption(
    "Pro Hockey Analytics — Fullscreen Broadcast Edition"
)
clock = pygame.time.Clock()

# Fonts
try:
  FONT_SM = pygame.font.SysFont("Arial", 13, bold=True)
  FONT_MD = pygame.font.SysFont("Arial", 15, bold=True)
  FONT_LG = pygame.font.SysFont("Arial", 18, bold=True)
except Exception:
  FONT_SM = pygame.font.Font(None, 18)
  FONT_MD = pygame.font.Font(None, 22)
  FONT_LG = pygame.font.Font(None, 26)


def scale_coordinates(x, y):
  """Converts real-world Wisehockey meters ((0,0) at center ice)

  to virtual master rink pixels (1500x800).
  """
  pixel_x = (VIRTUAL_WIDTH / 2) + (x * 17.5)
  pixel_y = (VIRTUAL_HEIGHT / 2) + (y * 17.5)
  return int(pixel_x), int(pixel_y)


def parse_coord_str(coord_str):
  if pd.isna(coord_str) or not isinstance(coord_str, str):
    return None
  try:
    parts = coord_str.split(",")
    return (float(parts[0]), float(parts[1]))
  except Exception:
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
    except Exception:
      return 0.0
  try:
    return float(clock_str)
  except Exception:
    return 0.0


def lerp_coord(coord_a, coord_b, t):
  if coord_a is None or coord_b is None:
    return coord_a or coord_b
  x = coord_a[0] + (coord_b[0] - coord_a[0]) * t
  y = coord_a[1] + (coord_b[1] - coord_a[1]) * t
  return (x, y)


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
          jersey = parts[0].replace("#", "")
      players[p_id] = {"coord": coord, "team": str(team), "jersey": jersey}
  return players


def build_uniform_timeline(df):
  master_frames = []
  total_rows = len(df)
  if total_rows < 2:
    return master_frames

  home_score = 0
  away_score = 0

  print("Building uniform 30 FPS timeline with score tracking...")
  for i in range(total_rows - 1):
    row_a = df.iloc[i]
    row_b = df.iloc[i + 1]

    clock_a = parse_match_clock(row_a.get("MatchClock (mm:ss)"))
    clock_b = parse_match_clock(row_b.get("MatchClock (mm:ss)"))

    time_diff = clock_b - clock_a
    if time_diff <= 0 or time_diff > 10.0:
      time_diff = 1.0

    num_frames = int(time_diff * TARGET_FPS)
    num_frames = max(1, num_frames)

    players_a = extract_players(row_a)
    players_b = extract_players(row_b)
    puck_a = parse_coord_str(row_a.get("EventStartCoordinate"))
    puck_b = parse_coord_str(row_b.get("EventStartCoordinate"))

    event_type = str(row_a.get("EventType", ""))
    is_zoom_event = event_type in ["Shot", "Goal", "Pass", "PuckControl"]

    if event_type.lower() == "goal":
      scoring_team = str(row_a.get("EventTeam", "home")).lower()
      if "away" in scoring_team:
        away_score += 1
      else:
        home_score += 1

    for f in range(num_frames):
      t = f / num_frames
      puck_interp = lerp_coord(puck_a, puck_b, t)

      interp_players = {}
      all_ids = set(players_a.keys()).union(set(players_b.keys()))
      for p_id in all_ids:
        p_a = players_a.get(p_id)
        p_b = players_b.get(p_id)
        c_a = p_a["coord"] if p_a else None
        c_b = p_b["coord"] if p_b else None
        team = (p_a or p_b)["team"]
        jersey = (p_a or p_b).get("jersey", "")
        pos = lerp_coord(c_a, c_b, t)
        if pos:
          interp_players[p_id] = {
              "coord": pos,
              "team": team,
              "jersey": jersey,
          }

      master_frames.append({
          "match_clock": row_a.get("MatchClock (mm:ss)"),
          "event_type": event_type,
          "is_zoom": is_zoom_event,
          "event_idx": i + 1,
          "puck": puck_interp,
          "players": interp_players,
          "home_score": home_score,
          "away_score": away_score,
      })

  print(f"✔ Timeline ready: {len(master_frames)} frames.")
  return master_frames


def draw_master_rink(surface):
  surface.fill(ICE_BASE)

  x_min, y_min = scale_coordinates(-30.8, -14.85)
  x_max, y_max = scale_coordinates(30.8, 14.85)
  rink_rect = pygame.Rect(x_min, y_min, x_max - x_min, y_max - y_min)

  pygame.draw.rect(
      surface, ICE_SHADOW, rink_rect.inflate(14, 14), 0, border_radius=46
  )
  pygame.draw.rect(surface, WHITE, rink_rect, 0, border_radius=40)
  pygame.draw.rect(surface, BOARD_BORDER, rink_rect, 5, border_radius=40)

  # Spotlight Glare
  glare_surf = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT), pygame.SRCALPHA)
  pygame.draw.circle(
      glare_surf,
      (255, 255, 255, 45),
      (int(VIRTUAL_WIDTH * 0.30), int(VIRTUAL_HEIGHT * 0.4)),
      180,
  )
  pygame.draw.circle(
      glare_surf,
      (255, 255, 255, 40),
      (int(VIRTUAL_WIDTH * 0.70), int(VIRTUAL_HEIGHT * 0.6)),
      200,
  )
  pygame.draw.circle(
      glare_surf,
      (255, 255, 255, 25),
      (int(VIRTUAL_WIDTH * 0.50), int(VIRTUAL_HEIGHT * 0.5)),
      250,
  )
  surface.blit(glare_surf, (0, 0))

  # Under-Ice Logos
  logo_surf = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT), pygame.SRCALPHA)
  pygame.draw.circle(
      logo_surf, (160, 185, 210, 35), scale_coordinates(-17, 0), 55
  )
  pygame.draw.circle(
      logo_surf, (130, 155, 185, 60), scale_coordinates(-17, 0), 55, 2
  )
  pygame.draw.circle(
      logo_surf, (160, 185, 210, 35), scale_coordinates(17, 0), 55
  )
  pygame.draw.circle(
      logo_surf, (130, 155, 185, 60), scale_coordinates(17, 0), 55, 2
  )
  surface.blit(logo_surf, (0, 0))

  # Center Red Line & Circle
  pygame.draw.line(
      surface, LINE_RED, (VIRTUAL_WIDTH // 2, y_min), (VIRTUAL_WIDTH // 2, y_max), 4
  )
  pygame.draw.circle(
      surface, LINE_RED, (VIRTUAL_WIDTH // 2, VIRTUAL_HEIGHT // 2), 65, 3
  )
  pygame.draw.circle(
      surface, LINE_RED, (VIRTUAL_WIDTH // 2, VIRTUAL_HEIGHT // 2), 6
  )

  # Blue Lines
  blue_x_left = int(scale_coordinates(-8.5, 0)[0])
  blue_x_right = int(scale_coordinates(8.5, 0)[0])
  pygame.draw.line(
      surface, LINE_BLUE, (blue_x_left, y_min), (blue_x_left, y_max), 4
  )
  pygame.draw.line(
      surface, LINE_BLUE, (blue_x_right, y_min), (blue_x_right, y_max), 4
  )

  # Goal Lines & Nets
  left_goal_x = scale_coordinates(-26, 0)[0]
  right_goal_x = scale_coordinates(26, 0)[0]

  pygame.draw.line(
      surface, LINE_RED, (left_goal_x, y_min + 10), (left_goal_x, y_max - 10), 2
  )
  pygame.draw.line(
      surface, LINE_RED, (right_goal_x, y_min + 10), (right_goal_x, y_max - 10), 2
  )

  # Creases
  crease_color = (200, 220, 245)
  pygame.draw.circle(
      surface, crease_color, (left_goal_x, VIRTUAL_HEIGHT // 2), 20
  )
  pygame.draw.circle(
      surface, LINE_RED, (left_goal_x, VIRTUAL_HEIGHT // 2), 20, 2
  )
  pygame.draw.circle(
      surface, crease_color, (right_goal_x, VIRTUAL_HEIGHT // 2), 20
  )
  pygame.draw.circle(
      surface, LINE_RED, (right_goal_x, VIRTUAL_HEIGHT // 2), 20, 2
  )

  # Nets
  net_w, net_h = 14, 24
  pygame.draw.rect(
      surface,
      (210, 160, 160),
      pygame.Rect(
          left_goal_x - net_w,
          (VIRTUAL_HEIGHT // 2) - (net_h // 2),
          net_w,
          net_h,
      ),
  )
  pygame.draw.rect(
      surface,
      LINE_RED,
      pygame.Rect(
          left_goal_x - net_w,
          (VIRTUAL_HEIGHT // 2) - (net_h // 2),
          net_w,
          net_h,
      ),
      2,
  )

  pygame.draw.rect(
      surface,
      (210, 160, 160),
      pygame.Rect(
          right_goal_x,
          (VIRTUAL_HEIGHT // 2) - (net_h // 2),
          net_w,
          net_h,
      ),
  )
  pygame.draw.rect(
      surface,
      LINE_RED,
      pygame.Rect(
          right_goal_x,
          (VIRTUAL_HEIGHT // 2) - (net_h // 2),
          net_w,
          net_h,
      ),
      2,
  )

  # Faceoff Dots
  endzone_dots = [(-20, -6), (-20, 6), (20, -6), (20, 6)]
  for dot_x, dot_y in endzone_dots:
    px, py = scale_coordinates(dot_x, dot_y)
    pygame.draw.circle(surface, LINE_RED, (px, py), 45, 2)
    pygame.draw.circle(surface, LINE_RED, (px, py), 5)

  neutral_dots = [(-6, -6), (-6, 6), (6, -6), (6, 6)]
  for dot_x, dot_y in neutral_dots:
    px, py = scale_coordinates(dot_x, dot_y)
    pygame.draw.circle(surface, LINE_RED, (px, py), 5)


def main():
  csv_file = "data/match_data/event_data_sample_Match_events.csv"
  try:
    df = pd.read_csv(csv_file)
  except FileNotFoundError:
    print(f"Error: Could not find '{csv_file}'.")
    pygame.quit()
    sys.exit()

  master_frames = build_uniform_timeline(df)
  if not master_frames:
    pygame.quit()
    sys.exit()

  frame_idx = 0
  total_frames = len(master_frames)
  paused = False
  playback_speed = 1.0

  master_surface = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT))

  # Persistent Camera Viewport State for Smooth Morphing
  cam_x, cam_y = 0.0, 0.0
  cam_w, cam_h = float(VIRTUAL_WIDTH), float(VIRTUAL_HEIGHT)
  morph_speed = 0.12

  while True:
    dt = clock.tick(TARGET_FPS) / 1000.0

    for event in pygame.event.get():
      if event.type == pygame.QUIT:
        pygame.quit()
        sys.exit()
      elif event.type == pygame.KEYDOWN:
        if event.key == pygame.K_ESCAPE:  # Press ESC to exit fullscreen
          pygame.quit()
          sys.exit()
        elif event.key == pygame.K_SPACE:
          paused = not paused
        elif event.key == pygame.K_RIGHT:
          frame_idx = min(total_frames - 1, frame_idx + TARGET_FPS)
        elif event.key == pygame.K_LEFT:
          frame_idx = max(0, frame_idx - TARGET_FPS)
        elif event.key == pygame.K_UP:
          playback_speed = min(4.0, playback_speed + 0.5)
        elif event.key == pygame.K_DOWN:
          playback_speed = max(0.5, playback_speed - 0.5)

    if not paused:
      frame_idx += playback_speed
      if frame_idx >= total_frames:
        frame_idx = 0

    current_frame = master_frames[int(frame_idx)]

    # 1. Draw full rink and entities onto master surface
    draw_master_rink(master_surface)

    # Render Puck
    puck_coord = current_frame["puck"]
    pk_x, pk_y = 0, 0
    if puck_coord:
      pk_x, pk_y = scale_coordinates(puck_coord[0], puck_coord[1])
      pygame.draw.circle(master_surface, (120, 135, 150), (pk_x + 2, pk_y + 2), 7)
      pygame.draw.circle(master_surface, (25, 25, 25), (pk_x, pk_y), 7)
      pygame.draw.circle(master_surface, (110, 110, 110), (pk_x, pk_y), 7, 1)

    # Render Players
    for p_id, p_data in current_frame["players"].items():
      pos = p_data["coord"]
      team = p_data["team"]
      jersey = p_data["jersey"]

      px, py = scale_coordinates(pos[0], pos[1])

      is_home = team.lower() == "home"
      primary_color = PURPLE if is_home else YELLOW

      pygame.draw.circle(master_surface, (140, 155, 175), (px + 2, py + 2), 14)
      pygame.draw.circle(master_surface, primary_color, (px, py), 14)
      pygame.draw.circle(master_surface, UNIFORM_BORDER, (px, py), 14, 2)

      if jersey:
        text_color = WHITE if is_home else (30, 30, 30)
        txt = FONT_SM.render(jersey, True, text_color)
        txt_rect = txt.get_rect(center=(px, py))
        master_surface.blit(txt, txt_rect)

    # 2. Determine Target Camera State for Morphing (Free Panning)
    if current_frame["is_zoom"] and puck_coord:
      target_w, target_h = 700.0, 420.0
      target_x = pk_x - target_w / 2.0
      target_y = pk_y - target_h / 2.0
    else:
      target_x, target_y = 0.0, 0.0
      target_w, target_h = float(VIRTUAL_WIDTH), float(VIRTUAL_HEIGHT)

    cam_x += (target_x - cam_x) * morph_speed
    cam_y += (target_y - cam_y) * morph_speed
    cam_w += (target_w - cam_w) * morph_speed
    cam_h += (target_h - cam_h) * morph_speed

    # Render Active Camera View to Canvas
    crop_w, crop_h = max(10, int(cam_w)), max(10, int(cam_h))
    zoom_canvas = pygame.Surface((crop_w, crop_h))
    zoom_canvas.fill(ICE_BASE)
    zoom_canvas.blit(master_surface, (-int(cam_x), -int(cam_y)))

    # Smooth scale the final view to fill the native fullscreen display
    scaled_zoom = pygame.transform.smoothscale(
        zoom_canvas, (ACTUAL_WIDTH, ACTUAL_HEIGHT)
    )
    screen.blit(scaled_zoom, (0, 0))

    # 3. Draw PiP Mini-Map in Upper Right (Scaled proportionally to actual screen)
    if cam_w < float(VIRTUAL_WIDTH) - 50:
      pip_w, pip_h = int(ACTUAL_WIDTH * 0.24), int(ACTUAL_HEIGHT * 0.22)
      pip_surface = pygame.transform.smoothscale(master_surface, (pip_w, pip_h))
      pip_rect = pygame.Rect(ACTUAL_WIDTH - pip_w - 30, 70, pip_w, pip_h)
      screen.blit(pip_surface, pip_rect)
      pygame.draw.rect(screen, WHITE, pip_rect, 3, border_radius=6)

      view_box = pygame.Rect(
          int(cam_x * (pip_w / VIRTUAL_WIDTH)),
          int(cam_y * (pip_h / VIRTUAL_HEIGHT)),
          int(cam_w * (pip_w / VIRTUAL_WIDTH)),
          int(cam_h * (pip_h / VIRTUAL_HEIGHT)),
      )
      pygame.draw.rect(screen, (255, 80, 80), view_box, 2)

    # 4. Modern Glassmorphic HUD Bar (Stretched dynamically across full screen width)
    hud_height = int(ACTUAL_HEIGHT * 0.065)
    hud_surface = pygame.Surface((ACTUAL_WIDTH, hud_height), pygame.SRCALPHA)
    hud_surface.fill(DARK_PANEL)
    screen.blit(hud_surface, (0, 0))

    status_label = "PAUSED" if paused else "PLAYING"
    status_color = (255, 90, 90) if paused else (80, 255, 130)
    mode_str = (
        "🔍 [MORPH ZOOM]"
        if cam_w < float(VIRTUAL_WIDTH) - 100
        else "🏟️ [FULL VIEW]"
    )

    # Left Section: Status & Mode
    txt_status = FONT_MD.render(f"[{status_label}] {mode_str}", True, status_color)
    screen.blit(txt_status, (30, hud_height // 2 - txt_status.get_height() // 2))

    # Center Section: Scoreboard
    h_score = current_frame["home_score"]
    a_score = current_frame["away_score"]
    txt_score = FONT_LG.render(
        f"PURPLE  {h_score}  -  {a_score}  YELLOW", True, WHITE
    )
    score_rect = txt_score.get_rect(
        center=(ACTUAL_WIDTH // 2, hud_height // 2)
    )
    screen.blit(txt_score, score_rect)

    # Right Section: Clock & Match Data
    info_str = (
        f"Speed: {playback_speed}x  |  Clock: {current_frame['match_clock']}"
        f"  |  Type: {current_frame['event_type']}"
    )
    txt_info = FONT_MD.render(info_str, True, WHITE)
    info_rect = txt_info.get_rect(
        right=ACTUAL_WIDTH - 30, centery=hud_height // 2
    )
    screen.blit(txt_info, info_rect)

    pygame.display.flip()


if __name__ == "__main__":
  main()