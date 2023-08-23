import pygame
import sys
import random

# Initialize Pygame
pygame.init()

# Set up some constants
WIDTH, HEIGHT = 640, 480
SIZE = (WIDTH, HEIGHT)
FPS = 30  # Decreased the FPS to slow down the game

# Colors
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)

# Set up the display
screen = pygame.display.set_mode(SIZE)

# Set up the clock
clock = pygame.time.Clock()

# Snake
snake_pos = [[100, 50], [90, 50], [80, 50]]
snake_speed = [0, 10]

# Apple
apple_pos = [random.randrange(1, WIDTH//10)*10, random.randrange(1, HEIGHT//10)*10]
apple_present = True

# Obstacles
obstacles = []
for _ in range(10):
    obstacle_pos = [random.randrange(1, WIDTH//10)*10, random.randrange(1, HEIGHT//10)*10]
    while obstacle_pos in snake_pos or obstacle_pos == apple_pos:
        obstacle_pos = [random.randrange(1, WIDTH//10)*10, random.randrange(1, HEIGHT//10)*10]
    obstacles.append(obstacle_pos)

# Score
score = 0

# Font
font = pygame.font.Font(None, 36)

def draw_snake():
    for pos in snake_pos:
        pygame.draw.rect(screen, GREEN, pygame.Rect(pos[0], pos[1], 10, 10))

def draw_apple():
    pygame.draw.rect(screen, RED, pygame.Rect(apple_pos[0], apple_pos[1], 10, 10))

def draw_obstacles():
    for pos in obstacles:
        pygame.draw.rect(screen, BLUE, pygame.Rect(pos[0], pos[1], 10, 10))

def move_snake():
    global score
    global apple_present

    # Move the snake by adding a new head and removing the tail
    new_head = [snake_pos[0][0] + snake_speed[0], snake_pos[0][1] + snake_speed[1]]
    snake_pos.insert(0, new_head)

    # Check if the snake has eaten the apple
    if snake_pos[0] == apple_pos:
        score += 1
        apple_present = False
    else:
        # If not, remove the tail of the snake
        snake_pos.pop()

    # Check if the snake is out of bounds
    if snake_pos[0][0] >= WIDTH:
        snake_pos[0][0] = 0
    elif snake_pos[0][0] < 0:
        snake_pos[0][0] = WIDTH - 10
    if snake_pos[0][1] >= HEIGHT:
        snake_pos[0][1] = 0
    elif snake_pos[0][1] < 0:
        snake_pos[0][1] = HEIGHT - 10

    # Check if the snake has hit an obstacle
    if snake_pos[0] in obstacles:
        pygame.quit()
        sys.exit()

    # Generate a new apple if there isn't one
    if not apple_present:
        apple_pos[0] = random.randrange(1, WIDTH//10)*10
        apple_pos[1] = random.randrange(1, HEIGHT//10)*10
        apple_present = True

def draw_score():
    # Render the score as a string
    score_text = font.render("Score: " + str(score), True, (0, 0, 0))
    screen.blit(score_text, (10, 10))

# Game loop
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        # Add keyboard event handler
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                snake_speed = [0, -10]
            elif event.key == pygame.K_DOWN:
                snake_speed = [0, 10]
            elif event.key == pygame.K_LEFT:
                snake_speed = [-10, 0]
            elif event.key == pygame.K_RIGHT:
                snake_speed = [10, 0]

    screen.fill(WHITE)

    draw_snake()
    draw_apple()
    draw_obstacles()
    move_snake()
    draw_score()

    pygame.display.flip()
    clock.tick(FPS)