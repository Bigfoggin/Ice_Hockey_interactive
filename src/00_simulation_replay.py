import sys
import pandas as pd
import pygame

# Initialize Pygame
pygame.init()

# Constants
WIDTH, HEIGHT = 1200, 600
TARGET_FPS = 30

# Colors
ICE_BLUE = (230, 242, 255)
WHITE = (255, 255, 255)
RED = (220, 50, 50)
BLUE = (50, 100, 220)
BLACK = (20, 20, 20)
LINE_RED = (200, 50, 50)
LINE_BLUE = (50, 100, 200)

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Hockey Match Interpolated Replay (30 FPS)")
clock = pygame.time.Clock()


def scale_coordinates(x, y):
  """Converts real-world Wisehockey meters ((0,0) at center ice)

  to Pygame window pixels.
  """
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
  """Linearly interpolates between two (x, y) coordinates.

  t is a float between 0.0 and 1.0.
  """
  if coord_a is None or coord_b is None:
    return coord_a or coord_b
  x = coord_a[0] + (coord_b[0] - coord_a[0]) * t
  y = coord_a[1] + (coord_b[1] - coord_a[1]) * t
  return (x, y)


def extract_players(row):
  """Extracts player dictionary: {player_id: {'coord': (x, y), 'team':

  'Home'/'Away'}}
  """
  players = {}
  for i in range(1, 13):
    p_id = row.get(f"StartPlayerId{i}")
    coord = parse_coord_str(row.get(f"StartPlayerCoordinates{i}"))
    team = row.get(f"StartPlayerTeam{i}")

    if pd.notna(p_id) and coord is not None:
      players[p_id] = {"coord": coord, "team": str(team)}
  return players


def draw_rink(surface):
  surface.fill(ICE_BLUE)
  rink_rect = pygame.Rect(60, 40, WIDTH - 120, HEIGHT - 80)
  pygame.draw.rect(surface, WHITE, rink_rect, 4, border_radius=40)
  pygame.draw.rect(surface, (180, 210, 240), rink_rect, 4, border_radius=40)

  # Center Red Line & Circle
  pygame.draw.line(surface, LINE_RED, (WIDTH // 2, 40), (WIDTH // 2, HEIGHT - 40), 4)
  pygame.draw.circle(surface, LINE_RED, (WIDTH // 2, HEIGHT // 2), 60, 3)
  pygame.draw.circle(surface, LINE_RED, (WIDTH // 2, HEIGHT // 2), 6)

  # Blue Lines
  pygame.draw.line(
      surface, LINE_BLUE, (WIDTH * 0.35, 40), (WIDTH * 0.35, HEIGHT - 40), 4
  )
  pygame.draw.line(
      surface, LINE_BLUE, (WIDTH * 0.65, 40), (WIDTH * 0.65, HEIGHT - 40), 4
  )


def main():
  csv_file = "data/match_data/event_data_sample_Match_events.csv"

  try:
    df = pd.read_csv(csv_file)
  except FileNotFoundError:
    print(f"Error: Could not find '{csv_file}'.")
    pygame.quit()
    sys.exit()

  current_row_idx = 0
  total_rows = len(df)
  paused = False

  # Progress t between current_row_idx and next_row_idx (0.0 to 1.0)
  t = 0.0
  # Duration in seconds to transition between sparse event rows
  event_duration = 0.8

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
          current_row_idx = min(total_rows - 1, current_row_idx + 1)
          t = 0.0
        elif event.key == pygame.K_LEFT:
          current_row_idx = max(0, current_row_idx - 1)
          t = 0.0

    if not paused and total_rows > 1:
      t += dt / event_duration
      if t >= 1.0:
        t = 0.0
        current_row_idx = (current_row_idx + 1) % total_rows

    # Get current and next event rows
    row_a = df.iloc[current_row_idx]
    next_idx = (current_row_idx + 1) % total_rows
    row_b = df.iloc[next_idx]

    # Draw Rink Background
    draw_rink(screen)

    # 1. Interpolate Puck Position
    puck_a = parse_coord_str(row_a.get("EventStartCoordinate"))
    puck_b = parse_coord_str(row_b.get("EventStartCoordinate"))
    puck_interp = lerp_coord(puck_a, puck_b, t)

    if puck_interp:
      px, py = scale_coordinates(puck_interp[0], puck_interp[1])
      pygame.draw.circle(screen, BLACK, (px, py), 8)

    # 2. Interpolate Player Positions (Matching by Player ID)
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
        color = RED if team.lower() == "home" else BLUE
        pygame.draw.circle(screen, color, (px, py), 12)
        pygame.draw.circle(screen, WHITE, (px, py), 12, 2)

    # Display event info text overlay
    font = pygame.font.SysFont(None, 22)
    info_text = (
        f"30 FPS Interpolated | Event {current_row_idx+1}/{total_rows} | Time:"
        f" {row_a.get('MatchClock (mm:ss)')} | Type: {row_a.get('EventType')}"
    )
    text_surface = font.render(info_text, True, BLACK)
    screen.blit(text_surface, (70, 15))

    pygame.display.flip()


if __name__ == "__main__":
  main()