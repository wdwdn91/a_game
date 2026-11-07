import sys
import math
import random
import pygame

# ---------------- 配置 ----------------
W, H = 960, 640
FPS = 60

PLAYER_SPEED = 4.2
AI_SPEED = 3.2
BULLET_SPEED = 11
PLAYER_FIRE_CD = 220
AI_FIRE_CD = 700
PLAYER_HP = 100
AI_HP = 100
BULLET_DMG = 12
PLAYER_R = 14
AI_R = 14
AUTO_AIM_ERR = 0.05        # 自动瞄准误差（弧度），0 = 百发百中

BG = (22, 24, 32)
WALL_COLOR = (52, 56, 72)
WALL_EDGE = (78, 84, 108)
PLAYER_COLOR = (90, 170, 255)
AI_COLOR = (255, 96, 110)
BULLET_PLAYER = (150, 210, 255)
BULLET_AI = (255, 150, 160)
TEXT = (230, 234, 242)
DIM = (150, 158, 178)


class Wall:
    def __init__(self, x, y, w, h):
        self.rect = pygame.Rect(x, y, w, h)

    def draw(self, surf):
        pygame.draw.rect(surf, WALL_COLOR, self.rect, border_radius=4)
        pygame.draw.rect(surf, WALL_EDGE, self.rect, width=2, border_radius=4)


class Bullet:
    def __init__(self, x, y, vx, vy, owner, color):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.owner = owner
        self.color = color
        self.alive = True
        self.r = 3

    def update(self, walls):
        steps = max(1, int(math.hypot(self.vx, self.vy) // 3))
        for _ in range(steps):
            self.x += self.vx / steps
            self.y += self.vy / steps
            if not (0 <= self.x <= W and 0 <= self.y <= H):
                self.alive = False
                return
            for w in walls:
                if w.rect.collidepoint(self.x, self.y):
                    self.alive = False
                    return

    def draw(self, surf):
        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), self.r)
        pygame.draw.circle(surf, (255, 255, 255), (int(self.x), int(self.y)), 1)


class Actor:
    def __init__(self, x, y, r, color, hp):
        self.x, self.y = x, y
        self.r = r
        self.color = color
        self.hp = hp
        self.max_hp = hp
        self.angle = -math.pi / 2
        self.last_shot = 0

    @property
    def pos(self):
        return pygame.Vector2(self.x, self.y)

    def try_move(self, dx, dy, walls):
        nx = self.x + dx
        if not self._collides(nx, self.y, walls):
            self.x = nx
        ny = self.y + dy
        if not self._collides(self.x, ny, walls):
            self.y = ny
        self.x = max(self.r, min(W - self.r, self.x))
        self.y = max(self.r, min(H - self.r, self.y))

    def _collides(self, x, y, walls):
        for w in walls:
            cx = max(w.rect.left, min(x, w.rect.right))
            cy = max(w.rect.top, min(y, w.rect.bottom))
            if (x - cx) ** 2 + (y - cy) ** 2 < self.r ** 2:
                return True
        return False

    def draw(self, surf):
        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), self.r)
        pygame.draw.circle(surf, (255, 255, 255), (int(self.x), int(self.y)), self.r, 2)
        gx = self.x + math.cos(self.angle) * (self.r + 10)
        gy = self.y + math.sin(self.angle) * (self.r + 10)
        pygame.draw.line(surf, (240, 240, 250), (self.x, self.y), (gx, gy), 5)
        bw, bh = 40, 5
        bx, by = self.x - bw / 2, self.y - self.r - 14
        pygame.draw.rect(surf, (60, 60, 70), (bx, by, bw, bh), border_radius=2)
        ratio = max(0, self.hp / self.max_hp)
        pygame.draw.rect(surf, self.color, (bx, by, bw * ratio, bh), border_radius=2)


class AI(Actor):
    def __init__(self, x, y, walls):
        super().__init__(x, y, AI_R, AI_COLOR, AI_HP)
        self.walls = walls
        self.strafe_dir = random.choice([-1, 1])
        self.strafe_timer = 0

    def update(self, player, bullets, now):
        if self.hp <= 0:
            return
        to_player = player.pos - self.pos
        dist = to_player.length()
        if dist > 0:
            self.angle = math.atan2(to_player.y, to_player.x)

        has_los = self._line_of_sight(player)
        if has_los and now - self.last_shot > AI_FIRE_CD:
            self._shoot(bullets, now)

        desired = pygame.Vector2(0, 0)
        if dist > 320:
            desired = to_player.normalize() * AI_SPEED
        elif dist < 180:
            desired = -to_player.normalize() * AI_SPEED
        else:
            self.strafe_timer += 1
            if self.strafe_timer > 90:
                self.strafe_dir *= -1
                self.strafe_timer = 0
            perp = pygame.Vector2(-to_player.y, to_player.x).normalize()
            desired = perp * self.strafe_dir * AI_SPEED * 0.8
            desired += to_player.normalize() * 0.6

        if desired.length() > 0:
            test = self.pos + desired.normalize() * (self.r + 6)
            if self._collides(test.x, test.y, self.walls):
                perp = pygame.Vector2(-desired.y, desired.x).normalize()
                desired = perp * AI_SPEED

        self.try_move(desired.x, desired.y, self.walls)

    def _line_of_sight(self, player):
        steps = int(self.pos.distance_to(player.pos) // 8) + 1
        for i in range(1, steps):
            t = i / steps
            px = self.x + (player.x - self.x) * t
            py = self.y + (player.y - self.y) * t
            for w in self.walls:
                if w.rect.collidepoint(px, py):
                    return False
        return True

    def _shoot(self, bullets, now):
        self.last_shot = now
        err = random.uniform(-0.06, 0.06)
        a = self.angle + err
        vx = math.cos(a) * BULLET_SPEED
        vy = math.sin(a) * BULLET_SPEED
        sx = self.x + math.cos(a) * (self.r + 10)
        sy = self.y + math.sin(a) * (self.r + 10)
        bullets.append(Bullet(sx, sy, vx, vy, "ai", BULLET_AI))


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("人机枪战 — 自动瞄准")
        self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
        self.big_font = pygame.font.Font(None, 52)
        self.small = pygame.font.Font(None, 20)
        self.reset()

    def reset(self):
        self.walls = [
            Wall(160, 120, 180, 30), Wall(160, 120, 30, 140),
            Wall(620, 120, 180, 30), Wall(770, 120, 30, 140),
            Wall(160, 470, 180, 30), Wall(160, 360, 30, 140),
            Wall(620, 470, 180, 30), Wall(770, 360, 30, 140),
            Wall(430, 250, 100, 30), Wall(430, 360, 100, 30),
            Wall(300, 300, 30, 100), Wall(630, 300, 30, 100),
        ]
        self.player = Actor(120, H - 120, PLAYER_R, PLAYER_COLOR, PLAYER_HP)
        self.ai = AI(W - 120, 120, self.walls)
        self.bullets = []
        self.keys = {}
        self.space_down = False
        self.state = "playing"
        self.score = 0
        self.ai_score = 0

    def handle_events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                if e.key == pygame.K_r:
                    self.reset()
                if e.key == pygame.K_SPACE:
                    self.space_down = True
                self.keys[e.key] = True
            if e.type == pygame.KEYUP:
                if e.key == pygame.K_SPACE:
                    self.space_down = False
                self.keys[e.key] = False

    def update(self, now):
        if self.state != "playing":
            return

        # ---- 移动 ----
        dx = dy = 0
        if self.keys.get(pygame.K_UP): dy -= 1
        if self.keys.get(pygame.K_DOWN): dy += 1
        if self.keys.get(pygame.K_LEFT): dx -= 1
        if self.keys.get(pygame.K_RIGHT): dx += 1
        if dx or dy:
            v = pygame.Vector2(dx, dy).normalize() * PLAYER_SPEED
            self.player.try_move(v.x, v.y, self.walls)

        # ---- 自动瞄准：枪口始终指向 AI ----
        if self.ai.hp > 0:
            to_ai = self.ai.pos - self.player.pos
            if to_ai.length() > 0:
                self.player.angle = math.atan2(to_ai.y, to_ai.x)

        # ---- 空格开火，自动朝 AI 方向 ----
        if self.space_down and now - self.player.last_shot > PLAYER_FIRE_CD and self.ai.hp > 0:
            self.player.last_shot = now
            a = self.player.angle + random.uniform(-AUTO_AIM_ERR, AUTO_AIM_ERR)
            sx = self.player.x + math.cos(a) * (self.player.r + 10)
            sy = self.player.y + math.sin(a) * (self.player.r + 10)
            self.bullets.append(Bullet(sx, sy,
                                       math.cos(a) * BULLET_SPEED,
                                       math.sin(a) * BULLET_SPEED,
                                       "player", BULLET_PLAYER))

        self.ai.update(self.player, self.bullets, now)

        for b in self.bullets:
            b.update(self.walls)

        for b in self.bullets:
            if not b.alive:
                continue
            if b.owner == "player":
                if (b.x - self.ai.x) ** 2 + (b.y - self.ai.y) ** 2 < (self.ai.r + b.r) ** 2:
                    self.ai.hp -= BULLET_DMG
                    b.alive = False
            else:
                if (b.x - self.player.x) ** 2 + (b.y - self.player.y) ** 2 < (self.player.r + b.r) ** 2:
                    self.player.hp -= BULLET_DMG
                    b.alive = False

        self.bullets = [b for b in self.bullets if b.alive]

        if self.ai.hp <= 0:
            self.state = "win"; self.score += 1
        elif self.player.hp <= 0:
            self.state = "lose"; self.ai_score += 1

    def draw(self):
        self.screen.fill(BG)
        for w in self.walls:
            w.draw(self.screen)
        for b in self.bullets:
            b.draw(self.screen)
        if self.ai.hp > 0:
            self.ai.draw(self.screen)
        if self.player.hp > 0:
            self.player.draw(self.screen)

        # 自动瞄准锁定提示
        if self.state == "playing" and self.ai.hp > 0:
            tx, ty = int(self.ai.x), int(self.ai.y)
            pygame.draw.circle(self.screen, (255, 255, 255), (tx, ty), self.ai.r + 8, 1)

        self.screen.blit(self.font.render(f"你 {self.score} : {self.ai_score} AI", True, TEXT), (20, 16))
        self.screen.blit(self.small.render(
            "方向键移动 · 空格开火（自动瞄准）· R 重开 · Esc 退出", True, DIM), (20, H - 28))

        if self.state == "win":
            self.center_text("你赢了！", "按 R 再来一局")
        elif self.state == "lose":
            self.center_text("你被击倒了", "按 R 再来一局")

        pygame.display.flip()

    def center_text(self, title, sub):
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((18, 20, 28, 200))
        self.screen.blit(ov, (0, 0))
        t = self.big_font.render(title, True, TEXT)
        s = self.font.render(sub, True, DIM)
        self.screen.blit(t, (W // 2 - t.get_width() // 2, H // 2 - 50))
        self.screen.blit(s, (W // 2 - s.get_width() // 2, H // 2 + 10))

    def run(self):
        while True:
            now = pygame.time.get_ticks()
            self.handle_events()
            self.update(now)
            self.draw()
            self.clock.tick(FPS)


if __name__ == "__main__":
    Game().run()