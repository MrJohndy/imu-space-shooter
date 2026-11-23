import serial
import pygame
import random
import math
import time

# ============================================================
# IMU SPACE SHOOTER
# Procedural graphics: no external image assets required.
# ============================================================

# SERIAL (preview mode can run even when the Arduino is disconnected)
try:
    ser = serial.Serial("COM6", 115200, timeout=0.01)
    time.sleep(2)
except serial.SerialException:
    ser = None

# GAME SETTINGS
WIDTH, HEIGHT = 900, 650
FPS = 60
ROLL_DIRECTION = -1
PITCH_DIRECTION = 1
MAX_TILT = 25
DEADZONE = 2
FOLLOW_SPEED = 8

# GAMEPLAY
PLAYER_MAX_HEALTH = 100
PLAYER_SPEED = 1.0
AUTO_FIRE_INTERVAL = 0.24
BOSS_INTERVAL = 60.0
POWERUP_DURATION = 9.0

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("IMU SPACE SHOOTER")
clock = pygame.time.Clock()

font = pygame.font.SysFont("Arial", 25, bold=True)
small_font = pygame.font.SysFont("Arial", 17)
tiny_font = pygame.font.SysFont("Arial", 13)
big_font = pygame.font.SysFont("Arial", 56, bold=True)

# COLORS
BLACK = (4, 6, 18)
WHITE = (235, 245, 255)
CYAN = (40, 220, 255)
BLUE = (55, 110, 255)
GREEN = (60, 255, 160)
RED = (255, 65, 85)
ORANGE = (255, 155, 55)
PURPLE = (185, 90, 255)
GOLD = (255, 215, 75)
MUTED = (115, 140, 175)

# IMU DATA
roll = pitch = yaw = 0.0
neutral_roll = neutral_pitch = None
imu_ready = False
calibration_progress = 0
calibration_status = "Waiting for Arduino..."

# WORLD / PLAYER
player_x, player_y = WIDTH // 2, HEIGHT - 100
player_health = PLAYER_MAX_HEALTH
player_invulnerable = 0.0
player_bullets = []
enemy_bullets = []
asteroids = []
aliens = []
powerups = []
particles = []
stars = []
score = 0
game_over = False
spawn_timer = 0.0
alien_spawn_timer = 8.0
fire_timer = 0.0
boss = None
bosses_defeated = 0
next_boss_index = 0
boss_spawn_timer = BOSS_INTERVAL
asteroids_destroyed = 0
difficulty_level = 0
boss_perks = set()
perk_stacks = {"destroyer": 0, "hive": 0, "overlord": 0, "omega": 0}
cannon_count = 0
drone_count = 0
armor_layers = 0
perk_drone_timer = 0.0
powerups_awarded = 0
powerup_effects = {"rapid": 0.0, "triple": 0.0, "shield": 0.0}
screen_shake = 0.0
elapsed = 0.0

# BACKGROUND STAR LAYERS
for layer, count in [(1, 55), (2, 35), (3, 18)]:
    for _ in range(count):
        stars.append({
            "x": random.randrange(WIDTH),
            "y": random.randrange(HEIGHT),
            "speed": layer * random.uniform(22, 48),
            "size": layer,
            "phase": random.random() * math.tau
        })


def clamp(value, low, high):
    return max(low, min(high, value))


def draw_text(text, x, y, color=WHITE, selected_font=font):
    image = selected_font.render(str(text), True, color)
    screen.blit(image, (int(x), int(y)))


def draw_centered(text, y, color=WHITE, selected_font=font):
    image = selected_font.render(str(text), True, color)
    screen.blit(image, (WIDTH // 2 - image.get_width() // 2, y))


def add_burst(x, y, color, amount=16, force=180):
    for _ in range(amount):
        angle = random.random() * math.tau
        speed = random.uniform(force * 0.25, force)
        particles.append({
            "x": float(x), "y": float(y),
            "vx": math.cos(angle) * speed,
            "vy": math.sin(angle) * speed,
            "life": random.uniform(0.25, 0.75),
            "max_life": 0.75,
            "size": random.randint(2, 5),
            "color": color
        })


def draw_planet(cx, cy, radius, base, light, dark, seed, ring=False, gas_giant=False):
    """Draw a shaded, textured planet using procedural shapes."""
    rng = random.Random(seed)
    # Atmospheric halo, then rings behind the planet.
    halo = pygame.Surface((radius * 2 + 34, radius * 2 + 34), pygame.SRCALPHA)
    pygame.draw.circle(halo, (*light, 18), (radius + 17, radius + 17), radius + 14, 13)
    screen.blit(halo, (cx - radius - 17, cy - radius - 17), special_flags=pygame.BLEND_RGBA_ADD)

    if ring:
        ring_layer = pygame.Surface((radius * 3, radius * 2), pygame.SRCALPHA)
        rc = (radius * 3 // 2, radius)
        pygame.draw.ellipse(ring_layer, (*light, 75), (0, radius // 2, radius * 3, radius), 7)
        pygame.draw.ellipse(ring_layer, (*dark, 110), (8, radius // 2 + 8, radius * 3 - 16, radius - 16), 3)
        screen.blit(ring_layer, (cx - radius * 3 // 2, cy - radius))

    size = radius * 2 + 4
    planet = pygame.Surface((size, size), pygame.SRCALPHA)
    c = radius + 2
    # Layered offset circles create a soft spherical light-to-dark gradient.
    for i in range(28, -1, -1):
        t = i / 28
        col = tuple(int(dark[k] * (1 - t) + base[k] * t) for k in range(3))
        rr = int(radius * (0.52 + 0.48 * (i / 28)))
        pygame.draw.circle(planet, (*col, 255), (c - int(radius * 0.12), c - int(radius * 0.15)), rr)

    # Surface detail: bands for gas planets, continents and craters for rocky ones.
    if gas_giant:
        for j in range(9):
            yy = int(radius * 0.38 + j * radius * 0.15)
            band_col = light if j % 2 == 0 else dark
            band = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.ellipse(band, (*band_col, rng.randint(25, 55)),
                                (-radius // 3, yy, radius * 2 + radius // 2, max(8, radius // 5)))
            planet.blit(band, (0, 0))
        for _ in range(18):
            x = rng.randint(int(radius * .25), int(radius * 1.75))
            y = rng.randint(int(radius * .35), int(radius * 1.65))
            pygame.draw.ellipse(planet, (*light, 35), (x, y, rng.randint(12, 34), rng.randint(4, 10)), 1)
    else:
        for _ in range(8):
            angle = rng.random() * math.tau
            dist = rng.uniform(0.15, 0.68) * radius
            x = int(c + math.cos(angle) * dist)
            y = int(c + math.sin(angle) * dist)
            w = rng.randint(max(12, radius // 9), max(18, radius // 4))
            h = rng.randint(max(8, radius // 12), max(12, radius // 7))
            pts = [(x - w, y), (x - w // 2, y - h), (x + w // 2, y - h // 2),
                   (x + w, y + h // 3), (x, y + h), (x - w // 2, y + h // 2)]
            pygame.draw.polygon(planet, (*light, 65), pts)
            pygame.draw.lines(planet, (*dark, 95), True, pts, 2)
        for _ in range(15):
            angle = rng.random() * math.tau
            dist = rng.uniform(0.12, 0.72) * radius
            x, y = int(c + math.cos(angle) * dist), int(c + math.sin(angle) * dist)
            r = rng.randint(3, max(4, radius // 22))
            pygame.draw.circle(planet, (*dark, 105), (x, y), r)
            pygame.draw.circle(planet, (*light, 100), (x - 2, y - 2), max(1, r - 2), 1)

    # Clip all surface detail to the spherical silhouette and add a dark limb.
    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (c, c), radius)
    planet.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    pygame.draw.circle(planet, (*light, 190), (c, c), radius, 2)
    shadow = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 12, 95), (c - radius // 3, c - radius // 2,
                                                    radius * 2, radius * 2))
    planet.blit(shadow, (0, 0))
    screen.blit(planet, (cx - c, cy - c))


# Render the planets once so the animated game loop only blits a cached layer.
_planet_screen = screen
planet_layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
screen = planet_layer
draw_planet(145, 245, 225, (73, 57, 145), (145, 126, 220), (25, 20, 65),
            seed=21, ring=True, gas_giant=False)
draw_planet(900, 525, 285, (42, 105, 155), (105, 190, 220), (8, 30, 70),
            seed=84, ring=False, gas_giant=True)
screen = _planet_screen


def draw_background(dt):
    screen.fill(BLACK)
    screen.blit(planet_layer, (0, 0))

    for star in stars:
        star["y"] += star["speed"] * dt
        if star["y"] > HEIGHT:
            star["y"] = -4
            star["x"] = random.randrange(WIDTH)
        pulse = 0.65 + 0.35 * math.sin(elapsed * 2 + star["phase"])
        shade = int(100 + 150 * pulse)
        pygame.draw.circle(screen, (shade, shade, min(255, shade + 20)),
                           (int(star["x"]), int(star["y"])), star["size"])


def draw_health_bar(x, y, width, height, ratio, color, back=(35, 40, 58)):
    ratio = clamp(ratio, 0, 1)
    pygame.draw.rect(screen, back, (int(x), int(y), int(width), int(height)), border_radius=4)
    if ratio > 0:
        pygame.draw.rect(screen, color,
                         (int(x), int(y), int(width * ratio), int(height)), border_radius=4)
    pygame.draw.rect(screen, (170, 190, 220), (int(x), int(y), int(width), int(height)), 1, border_radius=4)


def make_asteroid(force_type=None, x=None, y=None, radius=None, fragment=False):
    level = int(elapsed // 30)
    kinds = ["rock", "armored", "fast", "splitter", "crystal"]
    weights = [max(18, 55 - level * 3), min(30, 15 + level * 2),
               min(25, 12 + level), min(22, 10 + level), min(20, 8 + level)]
    kind = force_type or random.choices(kinds, weights=weights)[0]
    radius = radius or random.randint(17, 34)
    vertices = []
    count = random.randint(9, 13)
    for i in range(count):
        angle = math.tau * i / count
        r = radius * random.uniform(0.72, 1.15)
        vertices.append((math.cos(angle) * r, math.sin(angle) * r))
    hp_base = {"rock": 1 if radius < 24 else 2, "armored": 4,
               "fast": 1, "splitter": 2, "crystal": 3}[kind]
    hp = 1 if fragment else hp_base + min(level, 8) + (1 if kind in ("armored", "crystal") else 0)
    speed_base = {"rock": (145, 230), "armored": (95, 145),
                  "fast": (250, 340), "splitter": (125, 185),
                  "crystal": (165, 220)}[kind]
    speed = random.randint(*speed_base) + min(level * 16, 210)
    return {
        "x": x if x is not None else random.randint(radius, WIDTH - radius),
        "y": y if y is not None else -radius,
        "radius": radius, "speed": speed, "hp": hp, "max_hp": hp,
        "kind": kind, "angle": random.random() * math.tau,
        "spin": random.uniform(-1.2, 1.2), "vx": 0.0, "target_x": None, "vertices": vertices,
        "seed": random.randint(0, 99999)
    }


def make_alien():
    # Scout appearance and weapon are themed around the next boss.
    theme = next_boss_index % 4
    palette = [ORANGE, PURPLE, RED, GOLD]
    return {"x": random.randint(65, WIDTH - 65), "y": -35,
            "vx": random.choice([-1, 1]) * random.uniform(35, 85),
            "phase": random.random() * math.tau, "theme": theme,
            "hp": 2 + min(difficulty_level // 2, 4), "fire": random.uniform(0.8, 1.8),
            "color": palette[theme]}


def draw_alien(a):
    x, y, c = int(a["x"]), int(a["y"]), a["color"]
    # Small flying saucer with twin glowing eyes and swept wings.
    pygame.draw.polygon(screen, tuple(v // 2 for v in c),
                        [(x-24,y+2),(x-12,y-9),(x+12,y-9),(x+24,y+2),(x+12,y+8),(x-12,y+8)])
    pygame.draw.ellipse(screen, c, (x-17,y-8,34,17))
    pygame.draw.ellipse(screen, WHITE, (x-9,y-4,6,7))
    pygame.draw.ellipse(screen, WHITE, (x+3,y-4,6,7))
    pygame.draw.arc(screen, c, (x-24,y-13,48,27), math.pi, math.tau, 2)


def alien_fire(a):
    theme = a["theme"]
    if theme == 0:  # Destroyer: quick aimed bolts
        for offset in (-0.10, 0.10):
            dx, dy = player_x - a["x"] + offset * 180, player_y - a["y"]
            length = max(1, math.hypot(dx, dy))
            enemy_bullets.append({"x":a["x"],"y":a["y"]+8,"vx":dx/length*230,"vy":dy/length*230,"r":5,"color":ORANGE})
    elif theme == 1:  # Hive: three-way fan
        for angle in (-0.30, 0, 0.30):
            enemy_bullets.append({"x":a["x"],"y":a["y"]+8,"vx":math.sin(angle)*190,"vy":175,"r":5,"color":PURPLE})
    elif theme == 2:  # Overlord: slow lane-seeking plasma
        dx = clamp((player_x-a["x"])*0.45, -100, 100)
        enemy_bullets.append({"x":a["x"],"y":a["y"]+8,"vx":dx,"vy":175,"r":8,"color":RED})
    else:  # Omega: rotating three-orb burst
        for i in range(3):
            angle = a["phase"] + i * math.tau/3
            enemy_bullets.append({"x":a["x"],"y":a["y"]+8,"vx":math.cos(angle)*145,"vy":115+math.sin(angle)*75,"r":6,"color":GOLD})


def asteroid_points(obj):
    pts = []
    ca, sa = math.cos(obj["angle"]), math.sin(obj["angle"])
    for vx, vy in obj["vertices"]:
        pts.append((obj["x"] + vx * ca - vy * sa,
                    obj["y"] + vx * sa + vy * ca))
    return pts


def draw_asteroid(obj):
    pts = asteroid_points(obj)
    palettes = {
        "rock": ((76, 83, 105), (155, 165, 185)),
        "armored": ((55, 65, 82), (180, 195, 215)),
        "fast": ((95, 65, 58), (255, 150, 95)),
        "splitter": ((75, 65, 105), (190, 145, 255)),
        "crystal": ((35, 95, 115), (100, 240, 255))
    }
    fill, edge = palettes.get(obj.get("kind", "rock"), palettes["rock"])
    pygame.draw.polygon(screen, fill, pts)
    pygame.draw.polygon(screen, edge, pts, 2)
    cx, cy = int(obj["x"]), int(obj["y"])
    for i in range(4):
        ox = math.sin(obj["seed"] * 0.01 + i * 2.1) * obj["radius"] * 0.34
        oy = math.cos(obj["seed"] * 0.02 + i * 1.7) * obj["radius"] * 0.30
        rr = max(2, obj["radius"] // (5 + (i % 2)))
        pygame.draw.circle(screen, edge, (int(cx + ox), int(cy + oy)), rr, 1)
    if obj.get("kind") == "armored":
        pygame.draw.polygon(screen, (205, 215, 230), pts, 4)
    elif obj.get("kind") == "fast":
        pygame.draw.line(screen, ORANGE, (cx-obj["radius"], cy), (cx+obj["radius"], cy), 2)
    elif obj.get("kind") == "splitter":
        pygame.draw.circle(screen, PURPLE, (cx, cy), max(4, obj["radius"]//3), 2)
    elif obj.get("kind") == "crystal":
        pygame.draw.polygon(screen, WHITE, [(cx,cy-obj["radius"]//2),(cx+obj["radius"]//3,cy),(cx,cy+obj["radius"]//2),(cx-obj["radius"]//3,cy)], 2)
    if obj["hp"] < obj["max_hp"]:
        draw_health_bar(cx - obj["radius"], cy - obj["radius"] - 10,
                        obj["radius"] * 2, 5, obj["hp"] / obj["max_hp"], ORANGE)



def draw_player(x, y):
    x, y = int(x), int(y)
    # Engine glow
    glow = pygame.Surface((90, 100), pygame.SRCALPHA)
    pygame.draw.ellipse(glow, (20, 160, 255, 45), (20, 10, 50, 80))
    screen.blit(glow, (x - 45, y + 4))
    flame_len = random.randint(15, 27)
    pygame.draw.polygon(screen, ORANGE, [(x - 9, y + 19), (x, y + 19 + flame_len),
                                         (x + 9, y + 19)])
    pygame.draw.polygon(screen, CYAN, [(x - 5, y + 19), (x, y + 19 + flame_len // 2),
                                        (x + 5, y + 19)])
    hull = [(x, y - 30), (x - 12, y - 5), (x - 29, y + 17),
            (x - 12, y + 13), (x, y + 22), (x + 12, y + 13),
            (x + 29, y + 17), (x + 12, y - 5)]
    pygame.draw.polygon(screen, (25, 105, 165), hull)
    pygame.draw.polygon(screen, CYAN, hull, 2)
    pygame.draw.polygon(screen, (160, 245, 255),
                        [(x, y - 21), (x - 6, y + 3), (x, y + 9), (x + 6, y + 3)])
    pygame.draw.line(screen, WHITE, (x, y - 20), (x, y + 10), 1)
    # Cannon upgrades visibly expand the ship's weapon wings and add barrels.
    if cannon_count > 0:
        for i in range(cannon_count):
            side = -1 if i % 2 == 0 else 1
            tier = i // 2
            cx = x + side * (22 + tier * 13)
            cy = y + 5 + tier * 3
            pygame.draw.polygon(screen, (35, 75, 125),
                                [(cx, cy - 15), (cx - 6, cy + 10), (cx + 6, cy + 10)])
            pygame.draw.polygon(screen, GOLD if tier else CYAN,
                                [(cx, cy - 15), (cx - 6, cy + 10), (cx + 6, cy + 10)], 2)
            pygame.draw.line(screen, WHITE, (cx, cy - 13), (cx, cy - 5), 2)
    # Reinforced hull is shown as layered armor plating around the fuselage.
    for layer in range(min(armor_layers, 5)):
        inset = 3 + layer * 3
        pygame.draw.lines(screen, (150 + layer * 15, 175 + layer * 10, 205), False,
                          [(x - 13 - inset, y + 8 + layer * 2), (x, y + 17 + layer * 2),
                           (x + 13 + inset, y + 8 + layer * 2)], 2)
    if powerup_effects["shield"] > 0 or player_invulnerable > 0:
        pygame.draw.circle(screen, (70, 210, 255), (x, y), 39, 2)
        pygame.draw.circle(screen, (70, 210, 255), (x, y), 43, 1)



def drone_positions(x, y):
    """Stable orbit slots: drones fill both flanks, then upper/lower orbit slots."""
    positions = []
    for i in range(min(drone_count, 12)):
        angle = -math.pi / 2 + i * (math.tau / max(1, min(drone_count, 12)))
        # First pair is deliberately placed on left and right for visibility.
        if i == 0:
            angle = math.pi
        elif i == 1:
            angle = 0
        elif i == 2:
            angle = -math.pi / 2
        elif i == 3:
            angle = math.pi / 2
        else:
            angle = -math.pi / 2 + (i - 4) * math.tau / max(1, min(drone_count, 12) - 4)
        radius = 54 if i < 4 else 82 + (i // 8) * 16
        positions.append((x + math.cos(angle) * radius, y + math.sin(angle) * radius * 0.72))
    return positions


def draw_companion_drones(x, y):
    for dx, dy in drone_positions(x, y):
        px, py = int(dx), int(dy)
        pygame.draw.circle(screen, (20, 85, 115), (px, py), 10)
        pygame.draw.circle(screen, CYAN, (px, py), 10, 2)
        pygame.draw.circle(screen, WHITE, (px, py), 3)
        pygame.draw.line(screen, (80, 180, 220), (px, py + 8), (px, py + 13), 2)


def draw_bullet(b):
    pygame.draw.line(screen, (70, 180, 255), (int(b["x"]), int(b["y"] + 12)),
                     (int(b["x"]), int(b["y"] - 8)), 7)
    pygame.draw.line(screen, WHITE, (int(b["x"]), int(b["y"] + 8)),
                     (int(b["x"]), int(b["y"] - 8)), 2)


def draw_enemy_bullet(b):
    pygame.draw.circle(screen, (*b["color"], 90), (int(b["x"]), int(b["y"])), b["r"] + 5)
    pygame.draw.circle(screen, b["color"], (int(b["x"]), int(b["y"])), b["r"])
    pygame.draw.circle(screen, WHITE, (int(b["x"] - 2), int(b["y"] - 2)), max(1, b["r"] // 3))


def spawn_powerup(x, y, kind=None):
    if kind is None:
        kind = ["health", "rapid", "triple", "shield"][powerups_awarded % 4]
    powerups.append({"x": x, "y": y, "kind": kind, "speed": 105, "phase": 0.0})


def draw_powerup(p):
    colors = {"health": GREEN, "rapid": GOLD, "triple": PURPLE, "shield": CYAN}
    symbols = {"health": "+", "rapid": "R", "triple": "3", "shield": "S"}
    color = colors[p["kind"]]
    x, y = int(p["x"]), int(p["y"])
    pygame.draw.circle(screen, (*color,), (x, y), 17, 2)
    pygame.draw.circle(screen, (color[0] // 3, color[1] // 3, color[2] // 3), (x, y), 13)
    label = font.render(symbols[p["kind"]], True, WHITE)
    screen.blit(label, (x - label.get_width() // 2, y - label.get_height() // 2 - 2))


def create_boss(index):
    design = index % 4
    names = ["THE DESTROYER", "THE HIVE", "THE OVERLORD", "THE OMEGA CORE"]
    hp_values = [650, 1050, 1550, 2200]
    scale = 1.0 + (index // 4) * 0.28
    hp = int(hp_values[design] * scale)
    return {
        "name": names[design], "x": WIDTH / 2, "y": -115, "target_y": 115,
        "hp": hp, "max_hp": hp, "phase": 0.0, "attack_timer": 1.0,
        "special_timer": 4.0, "laser_warning": 0.0, "laser_active": 0.0,
        "summon_timer": 6.0, "index": design, "cycle": index,
        "direction": 1, "special_variant": 0
    }



def boss_fire_spread(b, count=5, speed=125):
    for i in range(count):
        angle = math.radians(35 + i * (110 / max(1, count - 1)))
        # Fan points downward from boss
        enemy_bullets.append({
            "x": b["x"], "y": b["y"] + 35,
            "vx": math.cos(angle) * speed * 0.55,
            "vy": math.sin(angle) * speed,
            "r": 6, "color": RED
        })


def boss_targeted_burst(b):
    dx, dy = player_x - b["x"], player_y - (b["y"] + 25)
    length = max(1, math.hypot(dx, dy))
    for offset in [-0.12, 0, 0.12]:
        angle = math.atan2(dy, dx) + offset
        enemy_bullets.append({
            "x": b["x"], "y": b["y"] + 25,
            "vx": math.cos(angle) * 155,
            "vy": math.sin(angle) * 155,
            "r": 6, "color": ORANGE
        })


def update_boss(dt):
    global boss, score, bosses_defeated, next_boss_index, player_health, game_over, screen_shake, boss_spawn_timer
    global cannon_count, drone_count, armor_layers
    if boss is None:
        return

    b = boss
    b["phase"] += dt
    b["y"] += (b["target_y"] - b["y"]) * min(1, 2.2 * dt)
    b["x"] = WIDTH / 2 + math.sin(b["phase"] * 0.75) * 245
    if b["y"] < b["target_y"] - 1:
        return

    b["attack_timer"] -= dt
    b["special_timer"] -= dt
    b["summon_timer"] -= dt

    # Each boss escalates its attacks as its health falls.
    enraged = b["hp"] <= b["max_hp"] * 0.35
    if b["attack_timer"] <= 0:
        boss_fire_spread(b, 6 if enraged else 5, 150 if enraged else 125)
        b["attack_timer"] = 1.45 if enraged else 2.0

    if b["special_timer"] <= 0:
        if b["index"] == 0:
            # Destroyer: aimed missile-like burst
            boss_targeted_burst(b)
            b["special_timer"] = 3.0
        elif b["index"] == 1:
            # Hive: radial orb ring
            for i in range(8):
                a = math.tau * i / 8
                enemy_bullets.append({"x": b["x"], "y": b["y"],
                                      "vx": math.cos(a) * 100, "vy": math.sin(a) * 100,
                                      "r": 6, "color": PURPLE})
            b["special_timer"] = 4.6
        elif b["index"] == 2:
            # Overlord: charge then laser beam
            b["laser_warning"] = 1.1
            b["special_timer"] = 5.2
        else:
            # Omega: twin aimed bursts plus radial pattern
            boss_targeted_burst(b)
            for i in range(8):
                a = math.tau * i / 8 + b["phase"]
                enemy_bullets.append({"x": b["x"], "y": b["y"],
                                      "vx": math.cos(a) * 115, "vy": math.sin(a) * 115,
                                      "r": 6, "color": GOLD})
            b["special_timer"] = 4.2
        # Every second special cycle adds a distinct secondary pattern.
        b["special_variant"] += 1
        if b["special_variant"] % 2 == 0:
            if b["index"] == 0:
                # Destroyer: slow heavy shells aimed at the player's current lane.
                for offset in (-42, 0, 42):
                    enemy_bullets.append({"x": b["x"] + offset, "y": b["y"] + 35,
                                          "vx": (player_x - (b["x"] + offset)) * 0.18,
                                          "vy": 155, "r": 9, "color": ORANGE})
            elif b["index"] == 1:
                # Hive: paired drifting mines.
                for side in (-1, 1):
                    enemy_bullets.append({"x": b["x"] + side*65, "y": b["y"]+20,
                                          "vx": side*45, "vy": 95, "r": 10, "color": PURPLE})
            elif b["index"] == 2:
                # Overlord: three staggered laser lanes with a clear warning window.
                b["laser_warning"] = 1.6
                b["laser_multi"] = [b["x"]-90, b["x"], b["x"]+90]
            else:
                # Omega: rotating spiral stream.
                for i in range(10):
                    a = b["phase"] + i * math.tau / 10
                    enemy_bullets.append({"x": b["x"], "y": b["y"],
                                          "vx": math.cos(a)*95, "vy": math.sin(a)*95+35,
                                          "r": 5, "color": GOLD})

    if b["index"] == 1 and b["summon_timer"] <= 0:
        # Hive summons falling drones (represented as fast enemy shots)
        for side in [-1, 1]:
            enemy_bullets.append({"x": b["x"] + side * 42, "y": b["y"] + 25,
                                  "vx": side * 22, "vy": 145, "r": 8, "color": PURPLE})
        b["summon_timer"] = 6.5

    if b["laser_warning"] > 0:
        b["laser_warning"] -= dt
        if b["laser_warning"] <= 0:
            b["laser_active"] = 0.65
    elif b["laser_active"] > 0:
        b["laser_active"] -= dt
        # One or three vertical columns; the warning and damage lanes match.
        lanes = b.get("laser_multi") or [b["x"]]
        if any(abs(player_x - lane_x) < 35 for lane_x in lanes) and abs(player_y - (b["y"] + 230)) < 290:
            if player_invulnerable <= 0 and powerup_effects["shield"] <= 0:
                damage_player(35)
        if b["laser_active"] <= 0:
            b.pop("laser_multi", None)

    # Draw laser warning/beam on the exact lanes used for collision.
    lanes = b.get("laser_multi") or [b["x"]]
    if b["laser_warning"] > 0:
        for lane_x in lanes:
            pygame.draw.line(screen, (255, 100, 100), (int(lane_x), int(b["y"] + 30)),
                             (int(lane_x), HEIGHT), 3)
        draw_text("LASER LOCK", b["x"] - 55, b["y"] + 45, RED, tiny_font)
    if b["laser_active"] > 0:
        beam = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for lane_x in lanes:
            pygame.draw.rect(beam, (255, 35, 65, 85), (int(lane_x - 34), 0, 68, HEIGHT))
            pygame.draw.rect(beam, (255, 170, 190, 210), (int(lane_x - 5), 0, 10, HEIGHT))
        screen.blit(beam, (0, 0))

    # Boss damage / defeat
    if b["hp"] <= 0:
        add_burst(b["x"], b["y"], GOLD, 90, 360)
        score += 250
        bosses_defeated += 1
        next_boss_index += 1
        boss_spawn_timer = BOSS_INTERVAL
        perk_names = ["destroyer", "hive", "overlord", "omega"]
        reward = perk_names[b["index"]]
        boss_perks.add(reward)
        perk_stacks[reward] += 1
        if reward == "destroyer":
            cannon_count = min(10, cannon_count + 2)
        elif reward == "hive":
            drone_count = min(12, drone_count + 2)
        elif reward == "overlord":
            armor_layers = min(5, armor_layers + 1)
        boss = None
        enemy_bullets.clear()


def draw_boss(b, show_hud=True):
    x, y = int(b["x"]), int(b["y"])
    idx = b["index"]

    # Each boss has its own silhouette, palette, and core design.
    if idx == 0:  # THE DESTROYER: heavy angular battleship
        color, dark, glow = RED, (75, 24, 48), (255, 55, 90, 35)
        aura = pygame.Surface((390, 170), pygame.SRCALPHA)
        pygame.draw.ellipse(aura, glow, (10, 15, 370, 135))
        screen.blit(aura, (x - 195, y - 65))
        hull = [(x-165,y-5),(x-115,y-58),(x-45,y-42),(x,y-76),
                (x+45,y-42),(x+115,y-58),(x+165,y-5),(x+112,y+48),
                (x+35,y+38),(x,y+58),(x-35,y+38),(x-112,y+48)]
        pygame.draw.polygon(screen, dark, hull)
        pygame.draw.polygon(screen, color, hull, 4)
        for side in (-1, 1):
            pygame.draw.polygon(screen, (145, 45, 65),
                [(x+side*105,y-25),(x+side*178,y+12),(x+side*105,y+28)])
            pygame.draw.circle(screen, ORANGE, (x+side*115,y+8), 11)
        pygame.draw.circle(screen, (255, 70, 95), (x,y-5), 25)
        pygame.draw.circle(screen, WHITE, (x,y-5), 8)
    elif idx == 1:  # THE HIVE: organic queen with orbiting pods
        color, dark = PURPLE, (48, 25, 85)
        for a in range(6):
            ang = b["phase"] * 0.45 + math.tau*a/6
            px, py = int(x+math.cos(ang)*105), int(y+math.sin(ang)*38)
            pygame.draw.circle(screen, (115,55,180), (px,py), 23, 3)
            pygame.draw.circle(screen, (205,135,255), (px,py), 9)
        shell = [(x,y-68),(x+76,y-35),(x+92,y+25),(x+42,y+62),
                 (x-42,y+62),(x-92,y+25),(x-76,y-35)]
        pygame.draw.polygon(screen, dark, shell)
        pygame.draw.polygon(screen, color, shell, 4)
        pygame.draw.circle(screen, (210,135,255), (x,y), 34)
        pygame.draw.circle(screen, (65,20,110), (x,y), 23)
        pygame.draw.circle(screen, WHITE, (x,y), 9)
        for side in (-1,1):
            pygame.draw.line(screen, color, (x+side*55,y+5),(x+side*120,y+35),7)
    elif idx == 2:  # THE OVERLORD: tall armored sentinel
        color, dark = (70,235,190), (18,65,75)
        hull = [(x,y-82),(x+48,y-48),(x+38,y+48),(x,y+67),
                (x-38,y+48),(x-48,y-48)]
        pygame.draw.polygon(screen, dark, hull)
        pygame.draw.polygon(screen, color, hull, 4)
        for side in (-1,1):
            wing = [(x+side*35,y-30),(x+side*150,y-65),
                    (x+side*115,y+5),(x+side*42,y+25)]
            pygame.draw.polygon(screen, (25,105,110), wing)
            pygame.draw.polygon(screen, color, wing, 3)
            pygame.draw.circle(screen, WHITE, (x+side*82,y-20), 7)
        pygame.draw.rect(screen, (20,180,170), (x-13,y-42,26,80), border_radius=8)
        pygame.draw.circle(screen, WHITE, (x,y-12), 10)
    else:  # THE OMEGA CORE: floating reactor with concentric rings
        color, dark = GOLD, (80,55,18)
        for radius, width in ((90,5),(65,3),(40,2)):
            pygame.draw.circle(screen, (190,145,45), (x,y), radius, width)
        for a in range(4):
            ang = b["phase"]*0.65 + math.tau*a/4
            px, py = int(x+math.cos(ang)*90), int(y+math.sin(ang)*90)
            pygame.draw.circle(screen, (255,170,45), (px,py), 13)
            pygame.draw.circle(screen, WHITE, (px,py), 5)
        pygame.draw.polygon(screen, dark, [(x,y-54),(x+48,y),(x,y+54),(x-48,y)])
        pygame.draw.polygon(screen, color, [(x,y-54),(x+48,y),(x,y+54),(x-48,y)], 4)
        pygame.draw.circle(screen, (255,235,145), (x,y), 25)
        pygame.draw.circle(screen, WHITE, (x,y), 10)

    if show_hud:
        draw_text(b["name"], x - 90, y - 105, color, small_font)
        draw_health_bar(WIDTH // 2 - 230, 22, 460, 16, b["hp"] / b["max_hp"], color)
        draw_centered(f"BOSS HP  {int(b['hp'])}/{b['max_hp']}", 42, WHITE, tiny_font)
    else:
        draw_text(b["name"], x - 90, y - 105, color, small_font)


def damage_player(amount):
    global player_health, player_invulnerable, game_over, screen_shake
    if player_invulnerable > 0 or powerup_effects["shield"] > 0:
        return
    if armor_layers > 0:
        amount = max(1, int(amount * max(0.35, 0.82 ** armor_layers)))
    player_health = max(0, player_health - amount)
    player_invulnerable = 0.8
    screen_shake = 0.22
    add_burst(player_x, player_y, RED, 12, 130)
    if player_health <= 0:
        game_over = True


def reset_game():
    global player_x, player_y, player_health, player_invulnerable
    global player_bullets, enemy_bullets, asteroids, aliens, powerups, particles
    global score, game_over, spawn_timer, fire_timer, boss, bosses_defeated
    global next_boss_index, powerup_effects, screen_shake, elapsed, alien_spawn_timer
    global boss_spawn_timer, asteroids_destroyed, difficulty_level, boss_perks, perk_drone_timer, powerups_awarded
    global perk_stacks, cannon_count, drone_count, armor_layers
    player_x, player_y = WIDTH // 2, HEIGHT - 100
    player_health = PLAYER_MAX_HEALTH
    player_invulnerable = 0
    player_bullets, enemy_bullets, asteroids, aliens, powerups, particles = [], [], [], [], [], []
    score = 0
    game_over = False
    spawn_timer = fire_timer = 0
    alien_spawn_timer = 8.0
    boss = None
    bosses_defeated = 0
    next_boss_index = 0
    boss_spawn_timer = BOSS_INTERVAL
    asteroids_destroyed = 0
    difficulty_level = 0
    boss_perks = set()
    perk_stacks = {"destroyer": 0, "hive": 0, "overlord": 0, "omega": 0}
    cannon_count = drone_count = armor_layers = 0
    perk_drone_timer = 0.0
    powerups_awarded = 0
    powerup_effects = {"rapid": 0.0, "triple": 0.0, "shield": 0.0}
    screen_shake = 0
    elapsed = 0


def read_imu():
    global roll, pitch, yaw, neutral_roll, neutral_pitch, imu_ready
    global calibration_progress, calibration_status
    if ser is None:
        calibration_status = "Arduino not connected - press P for drawing preview"
        return
    while ser.in_waiting:
        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            if line.startswith("STATUS,"):
                calibration_status = line.split(",", 1)[1]
            elif line.startswith("CAL,"):
                calibration_progress = int(float(line.split(",", 1)[1]))
                calibration_progress = int(clamp(calibration_progress, 0, 100))
            elif line == "READY":
                calibration_progress = 100
                calibration_status = "Calibration complete"
                imu_ready = True
            elif line.startswith("ERROR,"):
                calibration_status = line.split(",", 1)[1]
            else:
                values = line.split(",")
                if len(values) == 3:
                    roll, pitch, yaw = map(float, values)
                    if neutral_roll is None:
                        neutral_roll, neutral_pitch = roll, pitch
        except (ValueError, UnicodeDecodeError):
            pass


def draw_calibration_screen():
    screen.fill(BLACK)
    draw_centered("IMU SPACE SHOOTER", 190, GREEN, big_font)
    draw_centered(calibration_status, 280, WHITE, font)
    bar_w, bar_h = 400, 25
    bar_x, bar_y = (WIDTH - bar_w) // 2, 350
    pygame.draw.rect(screen, MUTED, (bar_x, bar_y, bar_w, bar_h), 2, border_radius=5)
    fill_w = int(bar_w * calibration_progress / 100)
    if fill_w > 4:
        pygame.draw.rect(screen, GREEN, (bar_x + 2, bar_y + 2, fill_w - 4, bar_h - 4),
                         border_radius=4)
    draw_centered(f"{calibration_progress}%", 395, GREEN, font)
    draw_centered("Keep the sensor still", 450, MUTED, small_font)


def fire_player_weapon():
    # Each Destroyer reward adds two cannons; triple-shot temporarily adds side fire.
    base_count = 1 + cannon_count
    if powerup_effects["triple"] > 0:
        base_count += 2
    base_count = min(base_count, 13)
    spacing = 14
    first = -(base_count - 1) * spacing / 2
    for i in range(base_count):
        player_bullets.append({
            "x": player_x + first + i * spacing,
            "y": player_y - 24,
            "speed": 620,
            "damage": 12,
            "pierce": min(4, perk_stacks.get("omega", 0))
        })


def apply_powerup(kind):
    global player_health
    if kind == "health":
        player_health = min(PLAYER_MAX_HEALTH, player_health + 30)
    elif kind == "rapid":
        powerup_effects["rapid"] = POWERUP_DURATION
    elif kind == "triple":
        powerup_effects["triple"] = POWERUP_DURATION
    elif kind == "shield":
        powerup_effects["shield"] = POWERUP_DURATION


def update_particles(dt):
    for p in particles[:]:
        p["x"] += p["vx"] * dt
        p["y"] += p["vy"] * dt
        p["life"] -= dt
        p["vx"] *= 0.985
        p["vy"] *= 0.985
        if p["life"] <= 0:
            particles.remove(p)
        else:
            radius = max(1, int(p["size"] * p["life"] / p["max_life"]))
            pygame.draw.circle(screen, p["color"], (int(p["x"]), int(p["y"])), radius)


def update_hud():
    draw_text(f"SCORE  {score:06d}", 18, 16, GREEN)
    draw_text(f"BOSSES  {bosses_defeated}", 18, 48, CYAN, small_font)
    draw_text(f"THREAT LVL {difficulty_level + 1}", 18, 88, ORANGE, tiny_font)
    draw_text("HULL", WIDTH - 190, 18, WHITE, small_font)
    if boss is None:
        draw_text(f"NEXT BOSS {max(0, boss_spawn_timer):04.1f}s", WIDTH // 2 - 75, 16, GOLD, tiny_font)
    perk_labels = {"destroyer":"TWIN CANNONS", "hive":"DRONE ALLY", "overlord":"REINFORCED HULL", "omega":"PIERCING SHOTS"}
    if boss_perks:
        perk_text = f"CANNONS x{cannon_count + 1}  DRONES x{drone_count}  ARMOR x{armor_layers}  PIERCING x{perk_stacks.get('omega', 0)}"
        draw_text(perk_text, 18, 72, GOLD, tiny_font)
    draw_health_bar(WIDTH - 130, 20, 110, 14, player_health / PLAYER_MAX_HEALTH,
                    GREEN if player_health > 35 else RED)
    active = []
    labels = {"rapid": "RAPID FIRE", "triple": "TRIPLE SHOT", "shield": "SHIELD"}
    for key, label in labels.items():
        if powerup_effects[key] > 0:
            active.append(f"{label} {powerup_effects[key]:.0f}s")
    for i, label in enumerate(active):
        draw_text(label, WIDTH - 190, 48 + i * 20, GOLD, tiny_font)


def draw_preview_screen(preview_boss, preview_index, laser_mode):
    """Static art preview; does not require IMU input or advance gameplay."""
    draw_background(0)

    # Dedicated header area: no boss HUD is drawn over these instructions.
    pygame.draw.rect(screen, (8, 13, 32), (0, 0, WIDTH, 104))
    draw_centered("DRAWING PREVIEW", 8, GREEN, font)
    draw_centered("LEFT / RIGHT: change boss     UP / DOWN: move vertically", 42, WHITE, tiny_font)
    draw_centered("Q / E or [ / ]: move horizontally     L: cycle laser     P / ESC: exit", 62, WHITE, tiny_font)
    draw_health_bar(WIDTH // 2 - 150, 84, 300, 8,
                    preview_boss["hp"] / preview_boss["max_hp"],
                    (RED, PURPLE, (70, 235, 190), GOLD)[preview_index])

    draw_boss(preview_boss, show_hud=False)

    # Example asteroid and player ship remain visible for scale comparison.
    sample = {"x": 125, "y": 525, "radius": 30, "angle": 0.35,
              "vertices": [(math.cos(math.tau*i/10)*30, math.sin(math.tau*i/10)*27) for i in range(10)],
              "seed": 1234, "hp": 2, "max_hp": 2}
    draw_asteroid(sample)
    draw_player(WIDTH // 2, HEIGHT - 85)

    if laser_mode:
        lx = int(preview_boss["x"])
        laser_start = int(preview_boss["y"] + 65)
        if laser_mode == 1:
            # Dashed lock-on guide makes the danger lane visible without hiding the ship.
            for yy in range(laser_start, HEIGHT, 22):
                pygame.draw.line(screen, (255, 95, 110), (lx, yy),
                                 (lx, min(yy + 11, HEIGHT)), 3)
            tag = tiny_font.render("LASER LOCK WARNING", True, RED)
            tag_bg = pygame.Rect(min(WIDTH - tag.get_width() - 24, max(8, lx + 12)),
                                 min(HEIGHT - 30, laser_start + 8), tag.get_width() + 12, 22)
            pygame.draw.rect(screen, (20, 8, 20), tag_bg, border_radius=5)
            screen.blit(tag, (tag_bg.x + 6, tag_bg.y + 4))
        else:
            beam = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pygame.draw.rect(beam, (255, 35, 65, 65), (lx - 34, laser_start, 68, HEIGHT - laser_start))
            pygame.draw.rect(beam, (255, 170, 190, 190), (lx - 5, laser_start, 10, HEIGHT - laser_start))
            screen.blit(beam, (0, 0))
            draw_text("ACTIVE LASER PREVIEW", 18, HEIGHT - 28, RED, tiny_font)

    draw_centered(f"{preview_index + 1}/4  -  {preview_boss['name']}", HEIGHT - 28, CYAN, small_font)


def main():
    global running, elapsed, player_x, player_y, spawn_timer, fire_timer, alien_spawn_timer
    global game_over, player_invulnerable, screen_shake, score, boss
    global boss_spawn_timer, difficulty_level, perk_drone_timer, asteroids_destroyed, powerups_awarded

    preview_mode = False
    preview_index = 0
    preview_boss = create_boss(preview_index)
    preview_boss["x"], preview_boss["y"] = WIDTH // 2, 245
    laser_mode = 0
    running = True
    try:
        while running:
            dt = min(clock.tick(FPS) / 1000.0, 0.05)
            read_imu()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if preview_mode:
                            preview_mode = False
                        else:
                            running = False
                    elif event.key == pygame.K_p:
                        preview_mode = not preview_mode
                    elif preview_mode:
                        if event.key in (pygame.K_RIGHT, pygame.K_d):
                            preview_index = (preview_index + 1) % 4
                            preview_boss = create_boss(preview_index)
                            preview_boss["x"], preview_boss["y"] = WIDTH // 2, 245
                        elif event.key in (pygame.K_LEFT, pygame.K_a):
                            preview_index = (preview_index - 1) % 4
                            preview_boss = create_boss(preview_index)
                            preview_boss["x"], preview_boss["y"] = WIDTH // 2, 245
                        elif event.key == pygame.K_UP:
                            preview_boss["y"] = max(125, preview_boss["y"] - 10)
                        elif event.key == pygame.K_DOWN:
                            preview_boss["y"] = min(HEIGHT - 150, preview_boss["y"] + 10)
                        elif event.key in (pygame.K_LEFTBRACKET, pygame.K_q):
                            preview_boss["x"] = max(190, preview_boss["x"] - 20)
                        elif event.key in (pygame.K_RIGHTBRACKET, pygame.K_e):
                            preview_boss["x"] = min(WIDTH - 190, preview_boss["x"] + 20)
                        elif event.key == pygame.K_l:
                            laser_mode = (laser_mode + 1) % 3
                    elif event.key == pygame.K_r and game_over:
                        reset_game()

            if preview_mode:
                preview_boss["phase"] += dt
                draw_preview_screen(preview_boss, preview_index, laser_mode)
                pygame.display.flip()
                continue

            # READY can arrive before the first orientation packet.
            # Wait until read_imu() has captured a real neutral position.
            if not imu_ready or neutral_roll is None or neutral_pitch is None:
                if imu_ready:
                    calibration_status = "Waiting for first orientation sample..."
                    calibration_progress = 100
                draw_calibration_screen()
                pygame.display.flip()
                continue

            if not game_over:
                elapsed += dt
            draw_background(dt)

            if not game_over:
                # IMU MOVEMENT
                roll_delta = (roll - neutral_roll) * ROLL_DIRECTION
                pitch_delta = (pitch - neutral_pitch) * PITCH_DIRECTION
                if abs(roll_delta) < DEADZONE:
                    roll_delta = 0
                if abs(pitch_delta) < DEADZONE:
                    pitch_delta = 0
                roll_delta = clamp(roll_delta, -MAX_TILT, MAX_TILT)
                pitch_delta = clamp(pitch_delta, -MAX_TILT, MAX_TILT)
                target_x = WIDTH / 2 + (roll_delta / MAX_TILT) * (WIDTH * 0.42)
                target_y = HEIGHT / 2 + (pitch_delta / MAX_TILT) * (HEIGHT * 0.38)
                player_x += (target_x - player_x) * min(1, FOLLOW_SPEED * dt)
                player_y += (target_y - player_y) * min(1, FOLLOW_SPEED * dt)
                player_x = clamp(player_x, 35, WIDTH - 35)
                player_y = clamp(player_y, 55, HEIGHT - 45)

                player_invulnerable = max(0, player_invulnerable - dt)
                for key in powerup_effects:
                    powerup_effects[key] = max(0, powerup_effects[key] - dt)

                # AUTOMATIC FIRE
                fire_timer -= dt
                fire_interval = 0.105 if powerup_effects["rapid"] > 0 else AUTO_FIRE_INTERVAL
                if fire_timer <= 0:
                    fire_player_weapon()
                    fire_timer = fire_interval

                # Every Hive victory adds two visible, independently firing drones.
                if drone_count > 0:
                    perk_drone_timer -= dt
                    if perk_drone_timer <= 0:
                        for dx, dy in drone_positions(player_x, player_y):
                            player_bullets.append({"x": dx, "y": dy - 10, "speed": 570,
                                                   "damage": 7, "pierce": min(4, perk_stacks.get("omega", 0))})
                        perk_drone_timer = max(0.22, 0.82 - drone_count * 0.035)
                # ASTEROID SPAWNING / BOSS TIMING
                spawn_timer += dt
                difficulty_level = int(elapsed // 30)
                spawn_interval = max(0.12, 0.68 - difficulty_level * 0.085)
                if boss is None:
                    boss_spawn_timer -= dt
                    if boss_spawn_timer <= 0:
                        boss = create_boss(next_boss_index)
                        enemy_bullets.clear()
                        boss_spawn_timer = 0
                    elif spawn_timer >= spawn_interval:
                        spawn_timer = 0
                        # Threats are deliberately sent into the player's forward lane,
                        # with a small offset so the player must actively dodge.
                        # All rocks enter from the top edge. Most fall naturally;
                        # a minority steer toward the player's lane for variety.
                        threat_x = random.randint(35, WIDTH - 35)
                        threat_radius = random.randint(20, 38)
                        asteroid = make_asteroid(x=threat_x, y=-threat_radius, radius=threat_radius)
                        if random.random() < min(0.22 + difficulty_level * 0.025, 0.42):
                            asteroid["target_x"] = clamp(player_x + random.randint(-55, 55), 35, WIDTH - 35)
                            asteroid["vx"] = clamp((asteroid["target_x"] - threat_x) * 0.48, -125, 125)
                            asteroid["tracking"] = 0.10 + min(difficulty_level * 0.01, 0.07)
                        asteroids.append(asteroid)

                # Small alien scouts arrive in waves, themed to the next boss.
                alien_spawn_timer -= dt
                if boss is None and alien_spawn_timer <= 0:
                    aliens.append(make_alien())
                    if difficulty_level >= 2 and random.random() < 0.35:
                        aliens.append(make_alien())
                    alien_spawn_timer = max(3.8, 9.0 - difficulty_level * 0.45)

                # PLAYER BULLETS
                for bullet in player_bullets[:]:
                    bullet["y"] -= bullet["speed"] * dt
                    if bullet["y"] < -25:
                        player_bullets.remove(bullet)
                        continue
                    hit = False
                    for alien in aliens[:]:
                        if math.hypot(bullet["x"]-alien["x"], bullet["y"]-alien["y"]) < 22:
                            alien["hp"] -= bullet.get("damage", 12) / 12
                            add_burst(alien["x"], alien["y"], alien["color"], 4, 70)
                            hit = True
                            if alien["hp"] <= 0:
                                score += 35
                                add_burst(alien["x"], alien["y"], alien["color"], 16, 150)
                                aliens.remove(alien)
                            break
                    for asteroid in asteroids[:] if not hit else []:
                        if math.hypot(bullet["x"] - asteroid["x"],
                                      bullet["y"] - asteroid["y"]) < asteroid["radius"] + 5:
                            asteroid["hp"] -= 1
                            add_burst(bullet["x"], bullet["y"], CYAN, 4, 65)
                            hit = True
                            if asteroid["hp"] <= 0:
                                add_burst(asteroid["x"], asteroid["y"], ORANGE, 18, 180)
                                score += 15
                                asteroids_destroyed += 1
                                if asteroids_destroyed % 10 == 0:
                                    drop_kind = ["health", "rapid", "triple", "shield"][powerups_awarded % 4]
                                    spawn_powerup(asteroid["x"], asteroid["y"], drop_kind)
                                    powerups_awarded += 1
                                if asteroid.get("kind") == "splitter" and asteroid["radius"] >= 22:
                                    for side in (-1, 1):
                                        asteroids.append(make_asteroid("fast", asteroid["x"] + side*12,
                                                                        asteroid["y"], max(11, asteroid["radius"]//2), True))
                                asteroids.remove(asteroid)
                            if bullet.get("pierce", 0) > 0:
                                bullet["pierce"] -= 1
                                hit = False
                            break
                    if not hit and boss is not None:
                        if abs(bullet["x"] - boss["x"]) < 155 and abs(bullet["y"] - boss["y"]) < 65:
                            boss["hp"] -= bullet.get("damage", 12)
                            add_burst(bullet["x"], bullet["y"], GOLD, 3, 55)
                            hit = True
                    if hit and bullet in player_bullets:
                        player_bullets.remove(bullet)

                # ALIEN SCOUTS: sweep across the screen and fire boss-themed patterns.
                for alien in aliens[:]:
                    alien["phase"] += dt * 2.5
                    alien["x"] += alien["vx"] * dt
                    alien["y"] += (72 + difficulty_level * 5) * dt
                    if alien["x"] < 30 or alien["x"] > WIDTH - 30:
                        alien["vx"] *= -1
                    alien["fire"] -= dt
                    if alien["fire"] <= 0:
                        alien_fire(alien)
                        alien["fire"] = max(0.85, 2.0 - difficulty_level * 0.08)
                    if alien["y"] > HEIGHT + 30:
                        aliens.remove(alien)
                        continue
                    if math.hypot(player_x-alien["x"], player_y-alien["y"]) < 34:
                        aliens.remove(alien)
                        damage_player(18)

                # ASTEROIDS UPDATE / PLAYER COLLISIONS
                for asteroid in asteroids[:]:
                    asteroid["y"] += asteroid["speed"] * dt
                    if asteroid.get("target_x") is not None:
                        asteroid["vx"] += clamp((asteroid["target_x"] - asteroid["x"]) * asteroid.get("tracking", 0.10), -42, 42) * dt
                        asteroid["vx"] = clamp(asteroid["vx"], -150, 150)
                        asteroid["x"] += asteroid["vx"] * dt
                    asteroid["angle"] += asteroid["spin"] * dt
                    if asteroid["y"] > HEIGHT + asteroid["radius"]:
                        asteroids.remove(asteroid)
                        score += 5
                        continue
                    if math.hypot(player_x - asteroid["x"], player_y - asteroid["y"]) < 27 + asteroid["radius"] * 0.72:
                        asteroids.remove(asteroid)
                        damage_player(25)

                # POWERUPS
                for p in powerups[:]:
                    p["y"] += p["speed"] * dt
                    p["phase"] += dt * 4
                    if math.hypot(player_x - p["x"], player_y - p["y"]) < 42:
                        apply_powerup(p["kind"])
                        add_burst(p["x"], p["y"], CYAN, 18, 130)
                        powerups.remove(p)
                    elif p["y"] > HEIGHT + 25:
                        powerups.remove(p)

                # ENEMY PROJECTILES
                for bullet in enemy_bullets[:]:
                    bullet["x"] += bullet["vx"] * dt
                    bullet["y"] += bullet["vy"] * dt
                    if (bullet["y"] < -30 or bullet["y"] > HEIGHT + 30 or
                            bullet["x"] < -30 or bullet["x"] > WIDTH + 30):
                        enemy_bullets.remove(bullet)
                        continue
                    if math.hypot(player_x - bullet["x"], player_y - bullet["y"]) < 23 + bullet["r"] * 0.65:
                        enemy_bullets.remove(bullet)
                        damage_player(12)

                # BOSS AI / ABILITIES
                update_boss(dt)

            # DRAW ASTEROIDS / PROJECTILES / POWERUPS
            for asteroid in asteroids:
                draw_asteroid(asteroid)
            for alien in aliens:
                draw_alien(alien)
            for bullet in player_bullets:
                draw_bullet(bullet)
            for bullet in enemy_bullets:
                draw_enemy_bullet(bullet)
            for p in powerups:
                draw_powerup(p)
            if boss is not None:
                draw_boss(boss)

            update_particles(dt)
            if not game_over:
                if player_invulnerable <= 0 or int(elapsed * 12) % 2 == 0:
                    draw_player(player_x, player_y)
                    if drone_count > 0:
                        draw_companion_drones(player_x, player_y)

            update_hud()

            if game_over:
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 155))
                screen.blit(overlay, (0, 0))
                draw_centered("SHIP DESTROYED", 225, RED, big_font)
                draw_centered(f"FINAL SCORE: {score}", 305, WHITE, font)
                draw_centered("Press R to restart  |  ESC to exit", 365, GREEN, small_font)

            pygame.display.flip()

    finally:
        if ser is not None:
            ser.close()
        pygame.quit()


if __name__ == "__main__":
    main()
