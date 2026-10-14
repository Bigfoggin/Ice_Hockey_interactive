import os
import sys
from pathlib import Path
import cv2
import numpy as np
import pandas as pd
import pygame

# Set Pygame to run headless (no display window will open)
os.environ["SDL_VIDEODRIVER"] = "dummy"

pygame.init()

# Video & Canvas Constants
WIDTH, HEIGHT = 1200, 600
TARGET_FPS = 30
VIDEO_DURATION_SEC = 20
TOTAL_FRAMES = TARGET_FPS * VIDEO_DURATION_SEC  # 600 frames total

# Colors
ICE_BLUE = (230, 242, 255)
WHITE = (255, 255, 255)
BLACK = (20, 20, 20)
LINE_RED = (200, 50, 50)
LINE_BLUE = (50, 100, 200)

# Updated Team Colors
PURPLE = (130, 40, 180)  # Formerly Red (Home Team)
YELLOW = (240, 200, 30)  # Formerly Blue (Away Team)

# Create off-screen rendering surface
surface = pygame.Surface((WIDTH, HEIGHT))


def scale_coordinates(x, y):
  """Converts real-world Wisehockey meters ((0,0) at center ice) to pixels."""
  pixel_x = (WIDTH / 2) + (x * 17.5)
  pixel_y = (HEIGHT / 2) + (y * 17.5)
  return int(pixel_x), int(pixel_y)


def parse_coord_str(coord_str):
  """Parses 'x,y' string into (float_x, float_y) tuple."""
  if pd.isna(coord_str) or not isinstance(coord_str, str):
    return None
  try:
    parts = coord_str.split(",")
    return (float(parts[0]), float(parts[1]))
  except Exception:
    return None


def lerp_coord(coord_a, coord_b, t):
  """Linearly interpolates between two (x, y) coordinates."""
  if coord_a is None or coord_b is None:
    return coord_a or coord_b
  x = coord_a[0] + (coord_b[0] - coord_a[0]) * t
  y = coord_a[1] + (coord_b[1] - coord_a[1]) * t
  return (x, y)


def extract_players(row):
  """Extracts player dictionary: {player_id: {'coord': (x, y), 'team': 'Home'/'Away'}}."""
  players = {}
  for i in range(1, 13):
    p_id = row.get(f"StartPlayerId{i}")
    coord = parse_coord_str(row.get(f"StartPlayerCoordinates{i}"))
    team = row.get(f"StartPlayerTeam{i}")

    if pd.notna(p_id) and coord is not None:
      players[p_id] = {"coord": coord, "team": str(team)}
  return players


def draw_rink(target_surface):
  """Renders a complete ice hockey rink layout with goals, creases, and faceoff dots."""
  target_surface.fill(ICE_BLUE)

  # Outer Rink Board
  rink_rect = pygame.Rect(60, 40, WIDTH - 120, HEIGHT - 80)
  pygame.draw.rect(target_surface, WHITE, rink_rect, 4, border_radius=40)
  pygame.draw.rect(
      target_surface, (180, 210, 240), rink_rect, 4, border_radius=40
  )

  # Center Red Line & Center Circle
  pygame.draw.line(
      target_surface, LINE_RED, (WIDTH // 2, 40), (WIDTH // 2, HEIGHT - 40), 4
  )
  pygame.draw.circle(
      target_surface, LINE_RED, (WIDTH // 2, HEIGHT // 2), 60, 3
  )
  pygame.draw.circle(target_surface, LINE_RED, (WIDTH // 2, HEIGHT // 2), 6)

  # Blue Lines
  blue_x_left = int(scale_coordinates(-8.5, 0)[0])
  blue_x_right = int(scale_coordinates(8.5, 0)[0])
  pygame.draw.line(
      target_surface, LINE_BLUE, (blue_x_left, 40), (blue_x_left, HEIGHT - 40), 4
  )
  pygame.draw.line(
      target_surface,
      LINE_BLUE,
      (blue_x_right, 40),
      (blue_x_right, HEIGHT - 40),
      4,
  )

  # Goal Line Positions (Wisehockey ~ +/-26 meters)
  left_goal_x = scale_coordinates(-26, 0)[0]
  right_goal_x = scale_coordinates(26, 0)[0]

  # Goal Lines (Red)
  pygame.draw.line(
      target_surface,
      LINE_RED,
      (left_goal_x, 50),
      (left_goal_x, HEIGHT - 50),
      2,
  )
  pygame.draw.line(
      target_surface,
      LINE_RED,
      (right_goal_x, 50),
      (right_goal_x, HEIGHT - 50),
      2,
  )

  # Goal Creases
  crease_color = (160, 210, 255)
  pygame.draw.circle(
      target_surface, crease_color, (left_goal_x, HEIGHT // 2), 18
  )
  pygame.draw.circle(
      target_surface, LINE_RED, (left_goal_x, HEIGHT // 2), 18, 2
  )

  pygame.draw.circle(
      target_surface, crease_color, (right_goal_x, HEIGHT // 2), 18
  )
  pygame.draw.circle(
      target_surface, LINE_RED, (right_goal_x, HEIGHT // 2), 18, 2
  )

  # Goal Nets (Red Rectangles)
  pygame.draw.rect(
      target_surface,
      LINE_RED,
      pygame.Rect(left_goal_x - 12, (HEIGHT // 2) - 10, 12, 20),
      2,
  )
  pygame.draw.rect(
      target_surface,
      LINE_RED,
      pygame.Rect(right_goal_x, (HEIGHT // 2) - 10, 12, 20),
      2,
  )

  # Faceoff Circles & Dots (End Zones)
  endzone_dots = [(-20, -6), (-20, 6), (20, -6), (20, 6)]
  for dot_x, dot_y in endzone_dots:
    px, py = scale_coordinates(dot_x, dot_y)
    pygame.draw.circle(target_surface, LINE_RED, (px, py), 50, 2)
    pygame.draw.circle(target_surface, LINE_RED, (px, py), 5)

  # Neutral Zone Dots
  neutral_dots = [(-6, -6), (-6, 6), (6, -6), (6, 6)]
  for dot_x, dot_y in neutral_dots:
    px, py = scale_coordinates(dot_x, dot_y)
    pygame.draw.circle(target_surface, LINE_RED, (px, py), 5)


def generate_video():
  csv_file = "data/match_data/event_data_sample_Match_events.csv"
  output_video_path = "output_simulation.mp4"

  try:
    df = pd.read_csv(csv_file)
  except FileNotFoundError:
    print(f"Error: Could not find '{csv_file}'. Check file path.")
    sys.exit(1)

  total_rows = len(df)
  if total_rows == 0:
    print("CSV file is empty.")
    sys.exit(1)

  # Setup OpenCV VideoWriter
  fourcc = cv2.VideoWriter_fourcc(*"mp4v")
  out = cv2.VideoWriter(output_video_path, fourcc, TARGET_FPS, (WIDTH, HEIGHT))

  current_row_idx = 0
  t = 0.0
  event_duration = 0.8
  dt = 1.0 / TARGET_FPS

  font = pygame.font.SysFont(None, 24)

  print(
      f"Generating {VIDEO_DURATION_SEC}-second video ({TOTAL_FRAMES} frames) with"
      " Purple & Yellow teams..."
  )

  for frame_num in range(TOTAL_FRAMES):
    t += dt / event_duration
    if t >= 1.0:
      t = 0.0
      current_row_idx = (current_row_idx + 1) % total_rows

    row_a = df.iloc[current_row_idx]
    next_idx = (current_row_idx + 1) % total_rows
    row_b = df.iloc[next_idx]

    # Draw Rink Background
    draw_rink(surface)

    # 1. Interpolate Puck Position
    puck_a = parse_coord_str(row_a.get("EventStartCoordinate"))
    puck_b = parse_coord_str(row_b.get("EventStartCoordinate"))
    puck_interp = lerp_coord(puck_a, puck_b, t)

    if puck_interp:
      px, py = scale_coordinates(puck_interp[0], puck_interp[1])
      pygame.draw.circle(surface, BLACK, (px, py), 8)

    # 2. Interpolate Player Positions
    players_a = extract_players(row_a)
    players_b = extract_players(row_b)
    all_player_ids = set(players_a.keys()).union(set(players_b.keys()))

    for p_id in all_player_ids:
      p_data_a = players_a.get(p_id)
      p_data_b = players_b.get(p_id)

      coord_a = p_data_a["coord"] if p_data_a else None
      coord_b = p_data_b["coord"] if p_data_b else None
      team = (p_data_a or p_data_b)["team"]

      pos = lerp_coord(coord_a, coord_b, t)
      if pos:
        px, py = scale_coordinates(pos[0], pos[1])
        # Home = Purple, Away = Yellow
        color = PURPLE if team.lower() == "home" else YELLOW
        pygame.draw.circle(surface, color, (px, py), 12)
        pygame.draw.circle(surface, WHITE if color == PURPLE else BLACK, (px, py), 12, 2)

    # Overlay Info
    current_time_sec = frame_num / TARGET_FPS
    info_text = (
        f"Video Time: {current_time_sec:.1f}s / {VIDEO_DURATION_SEC}s | Event"
        f" {current_row_idx+1}/{total_rows} | Clock:"
        f" {row_a.get('MatchClock (mm:ss)')} | Type: {row_a.get('EventType')}"
    )
    text_surface = font.render(info_text, True, BLACK)
    surface.blit(text_surface, (70, 15))

    # Convert Surface -> Video Frame
    view = pygame.surfarray.array3d(surface)
    frame_rgb = np.transpose(view, (1, 0, 2))
    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

    out.write(frame_bgr)

    if (frame_num + 1) % 60 == 0 or (frame_num + 1) == TOTAL_FRAMES:
      print(f" Progress: {frame_num + 1}/{TOTAL_FRAMES} frames rendered.")

  out.release()
  pygame.quit()
  print(f"\n✔ Video successfully saved to '{output_video_path}'!")


if __name__ == "__main__":
  generate_video()