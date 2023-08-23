import pygame
import random
import math

# Constants
WIDTH, HEIGHT = 1000, 1000
PARTICLE_COUNT = 100
GRAVITY = 0.5
ABSORPTION_RATE = 0.1  # New constant to control the rate of absorption
EXPLOSION_FORCE = 10  # New constant to control the explosion force

# Particle class
class Particle:
    def __init__(self, x, y, type='normal'):
        self.x = x
        self.y = y
        self.mass = random.uniform(1, 5)
        self.radius = self.mass * 2
        self.dx = random.uniform(-1, 1)
        self.dy = random.uniform(-1, 1)
        self.type = type  # 'normal', 'repel', 'explode', 'elastic'

    def move(self, particles):
        for particle in particles:
            if particle != self:
                distance = math.sqrt((self.x - particle.x)**2 + (self.y - particle.y)**2)
                # Check for collision
                if distance < self.radius + particle.radius:
                    # Explode if particle type is 'explode'
                    if self.type == 'explode' or particle.type == 'explode':
                        self.dx += random.uniform(-EXPLOSION_FORCE, EXPLOSION_FORCE)
                        self.dy += random.uniform(-EXPLOSION_FORCE, EXPLOSION_FORCE)
                        particle.dx += random.uniform(-EXPLOSION_FORCE, EXPLOSION_FORCE)
                        particle.dy += random.uniform(-EXPLOSION_FORCE, EXPLOSION_FORCE)
                        continue
                    # Absorb smaller particle if this particle is larger
                    if self.mass > particle.mass:
                        self.mass += ABSORPTION_RATE * particle.mass
                        self.radius = self.mass * 2
                        particles.remove(particle)
                    elif self.mass < particle.mass:
                        particle.mass += ABSORPTION_RATE * self.mass
                        particle.radius = particle.mass * 2
                        particles.remove(self)
                    continue
                force = GRAVITY * (self.mass * particle.mass) / (distance**2)
                dx = (particle.x - self.x) / distance
                dy = (particle.y - self.y) / distance
                # If particle type is 'repel', reverse the force direction
                if self.type == 'repel' or particle.type == 'repel':
                    self.dx -= dx * force
                    self.dy -= dy * force
                else:
                    self.dx += dx * force
                    self.dy += dy * force

        self.x += self.dx
        self.y += self.dy

        if self.x < 0 or self.x > WIDTH:
            self.dx *= -1
        if self.y < 0 or self.y > HEIGHT:
            self.dy *= -1

    def draw(self, screen):
        color = (255, 0, 0) if self.type == 'repel' else (255, 255, 255)
        pygame.draw.circle(screen, color, (int(self.x), int(self.y)), int(self.radius))

# Initialize pygame
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))

# Create particles
particles = [Particle(random.uniform(0, WIDTH), random.uniform(0, HEIGHT), 'repel' if random.random() < 0.2 else 'normal') for _ in range(PARTICLE_COUNT)]

# Main loop
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            x, y = pygame.mouse.get_pos()
            type = 'explode' if random.random() < 0.2 else 'normal'
            particles.append(Particle(x, y, type))
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                GRAVITY += 0.1
            elif event.key == pygame.K_DOWN:
                GRAVITY -= 0.1

    screen.fill((0, 0, 0))

    for particle in particles:
        particle.move(particles)
        particle.draw(screen)

    pygame.display.flip()

pygame.quit()