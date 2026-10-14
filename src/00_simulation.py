import math
import random
import sys
import pygame

# Initialize Pygame
pygame.init()

# Constants
WIDTH, HEIGHT = 1200, 600
FPS = 60

# Colors
ICE_BLUE = (230, 242, 255)
WHITE = (255, 255, 255)
RED = (220, 50, 50)
BLUE = (50, 100, 220)
BLACK = (20, 20, 20)
LINE_RED = (200, 50, 50)
LINE_BLUE = (50, 100, 200)

# Screen setup
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Hockey Simulation")
clock = pygame.time.Clock()


class Puck:

  def __init__(self, x, y):
    self.x = x
    self.y = y
    self.vx = 0
    self.vy = 0
    self.radius = 8
    self.friction = 0.985

  def update(self):
    self.x += self.vx
    self.y += self.vy
    self.vx *= self.friction
    self.vy *= self.friction

    # Wall collisions with bouncing
    rink_left = 60
    rink_right = WIDTH - 60
    rink_top = 40
    rink_bottom = HEIGHT - 40

    if self.x - self.radius < rink_left:
      self.x = rink_left + self.radius
      self.vx *= -0.8
    elif self.x + self.radius > rink_right:
      self.x = rink_right - self.radius
      self.vx *= -0.8

    if self.y - self.radius < rink_top:
      self.y = rink_top + self.radius
      self.vy *= -0.8
    elif self.y + self.radius > rink_bottom:
      self.y = rink_bottom - self.radius
      self.vy *= -0.8

  def draw(self, surface):
    pygame.draw.circle(
        surface, BLACK, (int(self.x), int(self.y)), self.radius
    )


class Player:

  def __init__(self, x, y, team):
    self.x = x
    self.y = y
    self.vx = 0
    self.vy = 0
    self.team = team  # 'RED' or 'BLUE'
    self.radius = 15
    self.max_speed = 3.5 if team == "RED" else 3.3

  def update(self, puck):
    # Simple AI: Move toward the puck with a bit of offset based on team
    dx = puck.x - self.x
    dy = puck.y - self.y
    dist = math.hypot(dx, dy)

    if dist > 1:
      dx /= dist
      dy /= dist
      # Accelerate towards puck
      self.vx += dx * 0.3
      self.vy += dy * 0.3

    # Speed limit
    speed = math.hypot(self.vx, self.vy)
    if speed > self.max_speed:
      self.vx = (self.vx / speed) * self.max_speed
      self.vy = (self.vy / speed) * self.max_speed

    self.x += self.vx
    self.y += self.vy

    # Friction / damping for players
    self.vx *= 0.92
    self.vy *= 0.92

    # Keep players inside the rink boundaries
    rink_left = 75
    rink_right = WIDTH - 75
    rink_top = 55
    rink_bottom = HEIGHT - 55

    self.x = max(rink_left, min(rink_right, self.x))
    self.y = max(rink_top, min(rink_bottom, self.y))

  def draw(self, surface):
    color = RED if self.team == "RED" else BLUE
    pygame.draw.circle(
        surface, color, (int(self.x), int(self.y)), self.radius
    )
    # Draw player number indicator outline
    pygame.draw.circle(
        surface, WHITE, (int(self.x), int(self.y)), self.radius, 2
    )


def draw_rink(surface):
  surface.fill(ICE_BLUE)

  # Rink outer boundary (rounded corners simulated with rects/circles)
  rink_rect = pygame.Rect(60, 40, WIDTH - 120, HEIGHT - 80)
  pygame.draw.rect(surface, WHITE, rink_rect, 4, border_radius=40)
  pygame.draw.rect(surface, ICE_BLUE, rink_rect, border_radius=40)
  # Rink border outline
  pygame.draw.rect(surface, (180, 210, 240), rink_rect, 4, border_radius=40)

  # Center Red Line
  pygame.draw.line(surface, LINE_RED, (WIDTH // 2, 40), (WIDTH // 2, HEIGHT - 40), 4)

  # Center Ice Circle and Dot
  pygame.draw.circle(surface, LINE_RED, (WIDTH // 2, HEIGHT // 2), 60, 3)
  pygame.draw.circle(surface, LINE_RED, (WIDTH // 2, HEIGHT // 2), 6)

  # Blue Lines
  pygame.draw.line(surface, LINE_BLUE, (WIDTH * 0.35, 40), (WIDTH * 0.35, HEIGHT - 40), 4)
  pygame.draw.line(surface, LINE_BLUE, (WIDTH * 0.65, 40), (WIDTH * 0.65, HEIGHT - 40), 4)

  # Goal Creases & Nets
  # Left Goal
  pygame.draw.arc(
      surface,
      LINE_RED,
      (WIDTH * 0.1 - 20, HEIGHT // 2 - 30, 40, 60),
      -math.pi / 2,
      math.pi / 2,
      3,
  )
  pygame.draw.rect(surface, (100, 100, 100), (WIDTH * 0.08 - 15, HEIGHT // 2 - 25, 15, 50))

  # Right Goal
  pygame.draw.arc(
      surface,
      LINE_RED,
      (WIDTH * 0.9 - 20, HEIGHT // 2 - 30, 40, 60),
      math.pi / 2,
      3 * math.pi / 2,
      3,
  )
  pygame.draw.rect(surface, (100, 100, 100), (WIDTH * 0.92, HEIGHT // 2 - 25, 15, 50))


def main():
  puck = Puck(WIDTH // 2, HEIGHT // 2)

  # Create players for two teams (Red vs Blue)
  players = [
      # Red Team
      Player(WIDTH * 0.4, HEIGHT * 0.3, "RED"),
      Player(WIDTH * 0.4, HEIGHT * 0.7, "RED"),
      Player(WIDTH * 0.25, HEIGHT * 0.5, "RED"),
      # Blue Team
      Player(WIDTH * 0.6, HEIGHT * 0.3, "BLUE"),
      Player(WIDTH * 0.6, HEIGHT * 0.7, "BLUE"),
      Player(WIDTH * 0.75, HEIGHT * 0.5, "BLUE"),
  ]

  while True:
    for event in pygame.event.get():
      if event.type == pygame.QUIT:
        pygame.quit()
        sys.exit()
      elif event.type == pygame.KEYDOWN:
        if event.key == pygame.K_SPACE:
          # Give the puck a random whack when spacebar is pressed
          puck.vx = random.choice([-12, 12])
          puck.vy = random.uniform(-6, 6)

    # Updates
    puck.update()
    for player in players:
      player.update(puck)

      # Simple collision between players and puck
      dist = math.hypot(player.x - puck.x, player.y - puck.y)
      if dist < player.radius + puck.radius:
        # Kick/hit puck away from player
        angle = math.atan2(puck.y - player.y, puck.x - player.x)
        puck.vx = math.cos(angle) * 8 + player.vx * 0.5
        puck.vy = math.sin(angle) * 8 + player.vy * 0.5

    # Drawing
    draw_rink(screen)
    puck.draw(screen)
    for player in players:
      player.draw(screen)

    pygame.display.flip()
    clock.tick(FPS)


if __name__ == "__main__":
  main()