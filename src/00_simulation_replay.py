import sys
import pandas as pd
import pygame

# Initialize Pygame
pygame.init()

# Constants
WIDTH, HEIGHT = 1200, 600
TARGET_FPS = 30

# Broadcast Ice Palette (Authentic grey-white metallic ice)
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

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption(
    "Pro Hockey Analytics Replay — Uniform 30 FPS Timeline"
)
clock = pygame.time.Clock()

# Fonts
try:
  FONT_SM = pygame.font.SysFont("Arial", 13, bold=True)
  FONT_MD = pygame.font.SysFont("Arial", 15, bold=True)
except Exception:
  FONT_SM = pygame.font.Font(None, 18)
  FONT_MD = pygame.font.Font(None, 22)


def scale_coordinates(x, y):
  """Converts Wisehockey real-world meters ((0,0) at center ice)

  to Pygame window pixels.
  """
  pixel_x = (WIDTH / 2) + (x * 17.5)
  pixel_y = (HEIGHT / 2) + (y * 17.5)
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
  """Converts 'mm:ss' or numeric match clock into total float seconds."""
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
  """Pre-computes a master list of frames where 1 second of match time = 30 frames."""
  master_frames = []
  total_rows = len(df)

  if total_rows < 2:
    return master_frames

  print("Building uniform 30 FPS interpolation timeline...")

  for i in range(total_rows - 1):
    row_a = df.iloc[i]
    row_b = df.iloc[i + 1]

    clock_a = parse_match_clock(row_a.get("MatchClock (mm:ss)"))
    clock_b = parse_match_clock(row_b.get("MatchClock (mm:ss)"))

    # Calculate time difference in seconds (clamp between 0.1 and 5.0 seconds to avoid anomalies)
    time_diff = clock_b - clock_a
    if time_diff <= 0 or time_diff > 10.0:
      time_diff = 1.0  # Default fallback step if clocks wrap or skip wildly

    num_frames = int(time_diff * TARGET_FPS)
    num_frames = max(1, num_frames)  # At least 1 frame

    players_a = extract_players(row_a)
    players_b = extract_players(row_b)
    puck_a = parse_coord_str(row_a.get("EventStartCoordinate"))
    puck_b = parse_coord_str(row_b.get("EventStartCoordinate"))

    for f in range(num_frames):
      t = f / num_frames

      # Interpolate puck
      puck_interp = lerp_coord(puck_a, puck_b, t)

      # Interpolate players
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
          "event_type": row_a.get("EventType"),
          "event_idx": i + 1,
          "puck": puck_interp,
          "players": interp_players,
      })

  print(
      f"✔ Timeline built successfully: {len(master_frames)} total frames"
      " generated."
  )
  return master_frames


def draw_rink(surface):
  surface.fill(ICE_BASE)

  # Outer Rink Board
  rink_rect = pygame.Rect(40, 60, WIDTH - 80, HEIGHT - 100)
  pygame.draw.rect(
      surface, ICE_SHADOW, rink_rect.inflate(12, 12), 0, border_radius=46
  )
  pygame.draw.rect(surface, WHITE, rink_rect, 0, border_radius=40)
  pygame.draw.rect(surface, BOARD_BORDER, rink_rect, 5, border_radius=40)

  # Spotlight Glare
  glare_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
  pygame.draw.circle(
      glare_surf, (255, 255, 255, 45), (int(WIDTH * 0.30), int(HEIGHT * 0.4)), 160
  )
  pygame.draw.circle(
      glare_surf, (255, 255, 255, 40), (int(WIDTH * 0.70), int(HEIGHT * 0.6)), 180
  )
  pygame.draw.circle(
      glare_surf, (255, 255, 255, 25), (int(WIDTH * 0.50), int(HEIGHT * 0.5)), 220
  )
  surface.blit(glare_surf, (0, 0))

  # Subtle Under-Ice Logos
  logo_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
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
  pygame.draw.line(surface, LINE_RED, (WIDTH // 2, 60), (WIDTH // 2, HEIGHT - 40), 4)
  pygame.draw.circle(surface, LINE_RED, (WIDTH // 2, HEIGHT // 2 + 10), 65, 3)
  pygame.draw.circle(surface, LINE_RED, (WIDTH // 2, HEIGHT // 2 + 10), 6)

  # Blue Lines
  blue_x_left = int(scale_coordinates(-8.5, 0)[0])
  blue_x_right = int(scale_coordinates(8.5, 0)[0])
  pygame.draw.line(
      surface, LINE_BLUE, (blue_x_left, 60), (blue_x_left, HEIGHT - 40), 4
  )
  pygame.draw.line(
      surface, LINE_BLUE, (blue_x_right, 60), (blue_x_right, HEIGHT - 40), 4
  )

  # Goal Lines & Nets
  left_goal_x = scale_coordinates(-26, 0)[0]
  right_goal_x = scale_coordinates(26, 0)[0]

  pygame.draw.line(
      surface, LINE_RED, (left_goal_x, 70), (left_goal_x, HEIGHT - 50), 2
  )
  pygame.draw.line(
      surface, LINE_RED, (right_goal_x, 70), (right_goal_x, HEIGHT - 50), 2
  )

  # Goal Creases
  crease_color = (200, 220, 245)
  pygame.draw.circle(
      surface, crease_color, (left_goal_x, HEIGHT // 2 + 10), 20
  )
  pygame.draw.circle(
      surface, LINE_RED, (left_goal_x, HEIGHT // 2 + 10), 20, 2
  )
  pygame.draw.circle(
      surface, crease_color, (right_goal_x, HEIGHT // 2 + 10), 20
  )
  pygame.draw.circle(
      surface, LINE_RED, (right_goal_x, HEIGHT // 2 + 10), 20, 2
  )

  # Goal Nets
  net_w, net_h = 14, 24
  pygame.draw.rect(
      surface,
      (210, 160, 160),
      pygame.Rect(
          left_goal_x - net_w, (HEIGHT // 2 + 10) - (net_h // 2), net_w, net_h
      ),
  )
  pygame.draw.rect(
      surface,
      LINE_RED,
      pygame.Rect(
          left_goal_x - net_w, (HEIGHT // 2 + 10) - (net_h // 2), net_w, net_h
      ),
      2,
  )

  pygame.draw.rect(
      surface,
      (210, 160, 160),
      pygame.Rect(
          right_goal_x, (HEIGHT // 2 + 10) - (net_h // 2), net_w, net_h
      ),
  )
  pygame.draw.rect(
      surface,
      LINE_RED,
      pygame.Rect(
          right_goal_x, (HEIGHT // 2 + 10) - (net_h // 2), net_w, net_h
      ),
      2,
  )

  # Faceoff Dots & Circles
  endzone_dots = [(-20, -6), (-20, 6), (20, -6), (20, 6)]
  for dot_x, dot_y in endzone_dots:
    px, py = scale_coordinates(dot_x, dot_y)
    py += 10
    pygame.draw.circle(surface, LINE_RED, (px, py), 45, 2)
    pygame.draw.circle(surface, LINE_RED, (px, py), 5)

  neutral_dots = [(-6, -6), (-6, 6), (6, -6), (6, 6)]
  for dot_x, dot_y in neutral_dots:
    px, py = scale_coordinates(dot_x, dot_y)
    py += 10
    pygame.draw.circle(surface, LINE_RED, (px, py), 5)


def main():
  csv_file = "data/match_data/event_data_sample_Match_events.csv"

  try:
    df = pd.read_csv(csv_file)
  except FileNotFoundError:
    print(f"Error: Could not find '{csv_file}'.")
    pygame.quit()
    sys.exit()

  # Build master uniform frame sequence
  master_frames = build_uniform_timeline(df)
  if not master_frames:
    print("Error: Could not generate timeline frames.")
    pygame.quit()
    sys.exit()

  frame_idx = 0
  total_frames = len(master_frames)
  paused = False
  playback_speed = 1.0  # multiplier for playback rate

  while True:
    dt = clock.tick(TARGET_FPS) / 1000.0

    for event in pygame.event.get():
      if event.type == pygame.QUIT:
        pygame.quit()
        sys.exit()
      elif event.type == pygame.KEYDOWN:
        if event.key == pygame.K_SPACE:
          paused = not paused
        elif event.key == pygame.K_RIGHT:
          frame_idx = min(total_frames - 1, frame_idx + int(TARGET_FPS))  
          # skip 1 second forward
        elif event.key == pygame.K_LEFT:
          frame_idx = max(0, frame_idx - int(TARGET_FPS))  
          # skip 1 second backward
        elif event.key == pygame.K_UP:
          playback_speed = min(4.0, playback_speed + 0.5)
        elif event.key == pygame.K_DOWN:
          playback_speed = max(0.5, playback_speed - 0.5)

    if not paused:
      frame_idx += playback_speed
      if frame_idx >= total_frames:
        frame_idx = 0  # Loop back to start

    current_frame = master_frames[int(frame_idx)]

    # Draw Rink
    draw_rink(screen)

    # 1. Render Puck
    puck_coord = current_frame["puck"]
    if puck_coord:
      px, py = scale_coordinates(puck_coord[0], puck_coord[1])
      py += 10
      pygame.draw.circle(screen, (120, 135, 150), (px + 2, py + 2), 7)
      pygame.draw.circle(screen, (25, 25, 25), (px, py), 7)
      pygame.draw.circle(screen, (110, 110, 110), (px, py), 7, 1)

    # 2. Render Players
    for p_id, p_data in current_frame["players"].items():
      pos = p_data["coord"]
      team = p_data["team"]
      jersey = p_data["jersey"]

      px, py = scale_coordinates(pos[0], pos[1])
      py += 10

      is_home = team.lower() == "home"
      primary_color = PURPLE if is_home else YELLOW

      pygame.draw.circle(screen, (140, 155, 175), (px + 2, py + 2), 14)
      pygame.draw.circle(screen, primary_color, (px, py), 14)
      pygame.draw.circle(screen, UNIFORM_BORDER, (px, py), 14, 2)

      if jersey:
        text_color = WHITE if is_home else (30, 30, 30)
        txt = FONT_SM.render(jersey, True, text_color)
        txt_rect = txt.get_rect(center=(px, py))
        screen.blit(txt, txt_rect)

    # 3. Modern Glassmorphic HUD Bar
    hud_surface = pygame.Surface((WIDTH, 48), pygame.SRCALPHA)
    hud_surface.fill(DARK_PANEL)
    screen.blit(hud_surface, (0, 0))

    status_label = "PAUSED" if paused else "PLAYING"
    status_color = (255, 90, 90) if paused else (80, 255, 130)

    stat_text_1 = FONT_MD.render(f"[{status_label}]", True, status_color)
    stat_text_2 = FONT_MD.render(
        f"Speed: {playback_speed}x | Frame: {int(frame_idx)+1}/{total_frames} |"
        f" Clock: {current_frame['match_clock']} | Type:"
        f" {current_frame['event_type']}",
        True,
        WHITE,
    )

    screen.blit(stat_text_1, (20, 13))
    screen.blit(stat_text_2, (150, 13))

    pygame.display.flip()


if __name__ == "__main__":
  main()