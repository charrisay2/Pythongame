# -*- coding: utf-8 -*-
"""
SOUL SURVIVORS
Game sinh tồn góc nhìn từ trên xuống (top-down pixel survival shooter)
Phong cách Vampire Survivors: tự động bắn, né quái, nhặt EXP, lên cấp chọn nâng cấp.

Chạy từ source:   python main.py
Build ra file exe: python build_exe.py   (hoặc nhấp đúp build_exe.bat)

Điều khiển:
    WASD / phím mũi tên : di chuyển
    Súng tự động bắn kẻ địch gần nhất
    ESC / P             : tạm dừng
    1 2 3               : chọn nâng cấp khi lên cấp
    M                   : bật/tắt âm thanh
    F11                 : toàn màn hình
"""

import io
import json
import math
import os
import random
import struct
import sys
import wave

import pygame

# ---------------------------------------------------------------------------
# CẤU HÌNH CHUNG
# ---------------------------------------------------------------------------
LOGICAL_W, LOGICAL_H = 360, 202          # độ phân giải "ảo" -> scale nguyên lần cho pixel art
WORLD_W, WORLD_H = 2400, 2400            # kích thước bản đồ
FPS = 60
BASE_W, BASE_H = 1440, 808               # cửa sổ mặc định (4x)
TITLE = "Soul Survivors"
SAVE_PATH = os.path.join(os.path.expanduser("~"), ".soul_survivors.json")

C_BG = (11, 10, 16)
C_WHITE = (244, 244, 250)
C_DIM = (152, 150, 172)
C_HP = (222, 74, 84)
C_XP = (120, 214, 255)
C_GOLD = (255, 206, 92)


# ---------------------------------------------------------------------------
# HÀM TIỆN ÍCH
# ---------------------------------------------------------------------------
def clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def dist2(ax, ay, bx, by):
    dx = ax - bx
    dy = ay - by
    return dx * dx + dy * dy


def xp_for(level):
    return int(6 + 5 * level + 0.9 * level * level)


def load_font(size, bold=False):
    """Ưu tiên font hệ thống Windows (hiển thị đủ dấu tiếng Việt)."""
    size = max(8, int(size))
    names = ["segoeuib.ttf", "arialbd.ttf", "tahomabd.ttf"] if bold else \
            ["segoeui.ttf", "arial.ttf", "tahoma.ttf"]
    win_dir = os.environ.get("WINDIR", r"C:\Windows")
    for n in names:
        p = os.path.join(win_dir, "Fonts", n)
        if os.path.exists(p):
            try:
                return pygame.font.Font(p, size)
            except Exception:
                pass
    try:
        return pygame.font.Font(None, size)
    except Exception:
        return pygame.font.Font(None, 16)


def synth_wav(freq=440.0, dur=0.12, vol=0.3, kind="square", sweep=0.0, noise=0.0, rate=22050):
    """Sinh 1 file WAV ngắn trong bộ nhớ (không cần file âm thanh bên ngoài)."""
    n = max(1, int(rate * dur))
    data = bytearray()
    phase = 0.0
    for i in range(n):
        p = i / n
        f = freq * (1.0 + sweep * p)
        phase += 2.0 * math.pi * f / rate
        if kind == "square":
            v = 1.0 if math.sin(phase) > 0 else -1.0
        elif kind == "saw":
            v = ((phase / (2.0 * math.pi)) % 1.0) * 2.0 - 1.0
        elif kind == "noise":
            v = random.uniform(-1.0, 1.0)
        else:
            v = math.sin(phase)
        if noise > 0:
            v = v * (1.0 - noise) + random.uniform(-1.0, 1.0) * noise
        env = (1.0 - p) ** 1.6
        s = int(max(-1.0, min(1.0, v * vol * env)) * 32767)
        data += struct.pack("<h", s)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(data))
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# PIXEL ART: sprite dựng từ "nửa ảnh" rồi lật gương -> luôn đối xứng
# ---------------------------------------------------------------------------
def sprite_from_half(half_rows, palette):
    rows = [h + h[::-1] for h in half_rows]
    return sprite_from_rows(rows, palette)


def sprite_from_rows(rows, palette):
    w = max(len(r) for r in rows)
    h = len(rows)
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            col = palette.get(ch)
            if col is not None:
                surf.fill(col, (x, y, 1, 1))
    return surf


def white_version(surf):
    try:
        m = pygame.mask.from_surface(surf)
        return m.to_surface(setcolor=(255, 255, 255, 230), unsetcolor=(0, 0, 0, 0))
    except Exception:
        return surf


# --- nhân vật chính: 16x20 ---
PLAYER_PAL = {
    "o": (26, 22, 34),
    "h": (44, 116, 62),
    "g": (92, 190, 98),
    "G": (150, 224, 132),
    "s": (250, 206, 160),
    "S": (212, 156, 118),
    "e": (34, 30, 44),
    "c": (26, 80, 74),
    "C": (46, 132, 116),
    "w": (88, 180, 152),
    "b": (48, 32, 24),
    "B": (88, 60, 40),
}
PLAYER_HALF = [
    ".....ooo",
    "...ooggg",
    "..oghGGg",
    ".oghGGGg",
    ".oghssss",
    ".oghssss",
    ".oghsees",
    ".oghssss",
    "..ogSsss",
    ".ocCCCCC",
    "ocCCCCCC",
    "ocCwwCCC",
    "ocCwwCCC",
    "ocCCCCCC",
    ".ocCCCCC",
    ".obb.bb.",
    ".obb.bb.",
    ".obb.bb.",
    ".oBB.BB.",
    "..oo.oo.",
]

# --- hồn ma: 16x16 ---
GHOST_PAL = {
    "o": (28, 26, 42),
    "w": (250, 252, 255),
    "W": (204, 212, 240),
    "k": (38, 36, 58),
}
GHOST_HALF = [
    ".....ooo",
    "...oowww",
    "..owwwww",
    ".owwwwww",
    ".owwwwww",
    ".owkkwww",
    ".owkkwww",
    ".owwwwww",
    ".owwwwww",
    ".owWWwww",
    ".owWWwww",
    ".oWWwwww",
    ".owwwwww",
    ".owwwwww",
    ".oWwwwwW",
    ".oo.oo.o",
]

# --- dơi: 16x12 ---
BAT_PAL = {
    "o": (28, 20, 42),
    "P": (70, 44, 110),
    "p": (120, 80, 170),
    "r": (255, 80, 80),
    "w": (36, 26, 54),
}
BAT_HALF = [
    "o.......",
    "oPo.....",
    "oPPo..oo",
    "oPPPoppp",
    "oPPpPppp",
    ".oppprrw",
    "..oppppp",
    "...opppp",
    "....oppp",
    ".....opp",
    "......op",
    ".......o",
]

# --- bộ xương: 14x18 ---
SKEL_PAL = {
    "o": (36, 32, 48),
    "w": (236, 236, 224),
    "W": (196, 196, 184),
    "k": (44, 40, 58),
}
SKEL_HALF = [
    "...oooo",
    "..owwww",
    ".owwwww",
    ".owkwww",
    ".owkwww",
    ".owwwww",
    ".owooow",
    ".oWWWWW",
    "..oWWWW",
    ".owwwww",
    ".owwwww",
    ".ow.www",
    ".owwwww",
    ".ow.www",
    "..owwww",
    "..oww..",
    "..oww..",
    "..oww..",
]

# --- xương khổng lồ (giáp đen, mắt đỏ): 18x22 ---
BRUTE_PAL = {
    "o": (22, 22, 32),
    "w": (198, 204, 220),
    "W": (160, 166, 184),
    "C": (58, 64, 86),
    "b": (44, 48, 64),
    "B": (70, 76, 96),
    "k": (240, 70, 70),
}
BRUTE_HALF = [
    "....ooooo",
    "...owwwww",
    "..owwwwww",
    "..owwwwww",
    "..owkwwww",
    "..owkwwww",
    "..owwwwww",
    "..owooooo",
    "...oWWWWW",
    "....oWWWW",
    "oo.oCCCCC",
    "oCCoCCCCC",
    "oCCwwwwww",
    "oCCCCCCCC",
    "oCCwwwwww",
    ".oCCCCCCC",
    ".oCwwwwww",
    "..oCCCCCC",
    "..oWwwwwW",
    "...owwwwW",
    "...oww.ww",
    "...oww.ww",
    "...oWW.WW",
    "....oo.oo",
]


def make_gun():
    s = pygame.Surface((13, 5), pygame.SRCALPHA)
    pygame.draw.rect(s, (58, 58, 70), (0, 1, 13, 3))
    pygame.draw.rect(s, (108, 108, 124), (3, 1, 8, 1))
    pygame.draw.rect(s, (28, 28, 36), (0, 0, 13, 1))
    pygame.draw.rect(s, (28, 28, 36), (0, 4, 10, 1))
    pygame.draw.rect(s, (92, 68, 46), (2, 3, 4, 2))
    pygame.draw.rect(s, (54, 40, 28), (2, 3, 4, 1))
    return s


def make_tree(rng):
    w, h = 32, 42
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (110, 160, 68), (4, h - 12, w - 8, 11))
    tw = 8
    tx = w // 2 - tw // 2
    pygame.draw.rect(s, (92, 58, 36), (tx, h - 18, tw, 16))
    pygame.draw.rect(s, (130, 88, 54), (tx + 1, h - 18, 3, 15))
    pygame.draw.rect(s, (60, 36, 22), (tx + tw - 2, h - 18, 2, 16))
    clusters = [
        (0.50, 0.46, 0.42),
        (0.26, 0.55, 0.30),
        (0.74, 0.55, 0.30),
        (0.50, 0.26, 0.32),
        (0.33, 0.34, 0.25),
        (0.67, 0.34, 0.25),
    ]
    dark = (38, 98, 50)
    mid = (72, 156, 64)
    light = (112, 192, 86)
    hi = (156, 216, 112)
    for cx, cy, r in clusters:
        rx = r * w * 0.55 + rng.uniform(-1.0, 1.0)
        ry = r * h * 0.60 + rng.uniform(-1.0, 1.0)
        px = cx * w + rng.uniform(-1.5, 1.5)
        py = cy * h + rng.uniform(-1.5, 1.5)
        pygame.draw.ellipse(s, dark, (int(px - rx), int(py - ry), int(rx * 2), int(ry * 2)))
    for cx, cy, r in clusters:
        rx = r * w * 0.40
        ry = r * h * 0.44
        px = cx * w - 1
        py = cy * h - 2
        pygame.draw.ellipse(s, mid, (int(px - rx), int(py - ry), int(rx * 2), int(ry * 2)))
    for cx, cy, r in clusters[:4]:
        rx = r * w * 0.24
        ry = r * h * 0.26
        pygame.draw.ellipse(s, light, (int(cx * w - rx - 2), int(cy * h - ry - 4),
                                       int(rx * 2), int(ry * 2)))
    for cx, cy, r in clusters[:2]:
        rx = r * w * 0.11
        ry = r * h * 0.12
        pygame.draw.ellipse(s, hi, (int(cx * w - rx - 3), int(cy * h - ry - 6),
                                    int(rx * 2), int(ry * 2)))
    return s


def make_bush(rng):
    w, h = 18, 15
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (46, 104, 52), (1, 5, w - 2, h - 6))
    pygame.draw.ellipse(s, (72, 152, 62), (2, 4, w - 4, h - 8))
    pygame.draw.ellipse(s, (104, 186, 82), (4, 4, w // 2, h // 3))
    for _ in range(4):
        bx = rng.randint(3, w - 4)
        by = rng.randint(5, h - 5)
        pygame.draw.circle(s, (150, 212, 110), (bx, by), 1)
    return s


def make_rock(rng, big=False):
    w, h = (22, 18) if big else (15, 13)
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (68, 72, 82), (1, h - 5, w - 2, 4))
    pygame.draw.ellipse(s, (96, 102, 112), (1, 4, w - 2, h - 5))
    pygame.draw.ellipse(s, (150, 156, 166), (2, 3, w - 4, h - 7))
    pygame.draw.ellipse(s, (196, 202, 210), (3, 4, w // 2, max(2, h // 3)))
    pygame.draw.ellipse(s, (120, 126, 136), (w // 2, h - 6, w // 2 - 2, 3))
    return s


def make_gem():
    s = pygame.Surface((7, 9), pygame.SRCALPHA)
    pygame.draw.polygon(s, (26, 92, 140), [(3, 0), (6, 3), (3, 8), (0, 3)])
    pygame.draw.polygon(s, (94, 216, 244), [(3, 1), (5, 3), (3, 6), (1, 3)])
    pygame.draw.line(s, (232, 255, 255), (2, 3), (2, 4))
    return s


def make_heart():
    s = pygame.Surface((7, 7), pygame.SRCALPHA)
    rows = [
        ".oo.oo.",
        "orrorro",
        "orrrrro",
        ".orrro.",
        "..oro..",
        "...o...",
    ]
    pal = {"o": (120, 26, 44), "r": (240, 86, 108)}
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            c = pal.get(ch)
            if c:
                s.fill(c, (x, y, 1, 1))
    return s


def build_sprites():
    sp = {}
    sp["player"] = sprite_from_half(PLAYER_HALF, PLAYER_PAL).convert_alpha()
    sp["ghost"] = sprite_from_half(GHOST_HALF, GHOST_PAL).convert_alpha()
    sp["bat"] = sprite_from_half(BAT_HALF, BAT_PAL).convert_alpha()
    sp["skeleton"] = sprite_from_half(SKEL_HALF, SKEL_PAL).convert_alpha()
    sp["brute"] = sprite_from_half(BRUTE_HALF, BRUTE_PAL).convert_alpha()

    for k in ("player", "ghost", "bat", "skeleton", "brute"):
        sp[k + "_flash"] = white_version(sp[k])

    sp["gun"] = make_gun().convert_alpha()
    sp["gem"] = make_gem().convert_alpha()
    sp["heart"] = make_heart().convert_alpha()
    return sp


# ---------------------------------------------------------------------------
# THẾ GIỚI (nền cỏ + đường mòn + cây/đá/bụi)
# ---------------------------------------------------------------------------
class World:
    def __init__(self, seed=20261029):
        self.w, self.h = WORLD_W, WORLD_H
        rng = random.Random(seed)
        self.ground = pygame.Surface((self.w, self.h)).convert()
        self.ground.fill((146, 196, 78))

        # mảng màu lớn (alpha thấp) cho nền đỡ phẳng
        patches = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        for _ in range(60):
            cx = rng.uniform(0, self.w)
            cy = rng.uniform(0, self.h)
            rw = rng.uniform(200, 620)
            rh = rng.uniform(150, 480)
            col = rng.choice(((255, 255, 200, 18), (52, 104, 38, 16), (255, 236, 150, 14)))
            pygame.draw.ellipse(patches, col,
                                (int(cx - rw / 2), int(cy - rh / 2), int(rw), int(rh)))
        self.ground.blit(patches, (0, 0))

        # bãi cát
        for _ in range(6):
            cx = rng.uniform(0, self.w)
            cy = rng.uniform(0, self.h)
            rw = rng.uniform(150, 300)
            rh = rng.uniform(110, 220)
            pygame.draw.ellipse(self.ground, (226, 204, 138),
                                (int(cx - rw / 2), int(cy - rh / 2), int(rw), int(rh)))
            for _ in range(90):
                a = rng.uniform(0, math.tau)
                px = cx + math.cos(a) * rw / 2 * rng.uniform(0.82, 1.02)
                py = cy + math.sin(a) * rh / 2 * rng.uniform(0.82, 1.02)
                pygame.draw.circle(self.ground, (226, 204, 138),
                                   (int(px), int(py)), int(rng.uniform(6, 15)))
            for _ in range(260):
                px = cx + rng.uniform(-rw / 2, rw / 2)
                py = cy + rng.uniform(-rh / 2, rh / 2)
                if (px - cx) ** 2 / (rw / 2) ** 2 + (py - cy) ** 2 / (rh / 2) ** 2 < 1:
                    self.ground.fill(rng.choice(((206, 184, 122), (238, 218, 158))),
                                     (int(px), int(py), 2, 1))

        # hạt cỏ li ti (dày, tông gần nền)
        for _ in range(88000):
            x = rng.randrange(0, self.w)
            y = rng.randrange(0, self.h)
            c = rng.choice(((126, 178, 62), (132, 184, 68), (160, 208, 88),
                            (168, 214, 94), (120, 172, 58)))
            self.ground.fill(c, (x, y, 1 if rng.random() < 0.72 else 2, 1))

        # cụm cỏ nhọn
        for _ in range(9000):
            x = rng.randrange(2, self.w - 2)
            y = rng.randrange(3, self.h - 2)
            c = rng.choice(((112, 164, 54), (150, 200, 82), (172, 212, 96)))
            pygame.draw.line(self.ground, c, (x, y), (x, y - 2))
            if rng.random() < 0.5:
                pygame.draw.line(self.ground, c, (x + 2, y), (x + 2, y - 1))

        # hoa nhỏ
        for _ in range(700):
            x = rng.randrange(2, self.w - 2)
            y = rng.randrange(2, self.h - 2)
            col = rng.choice(((244, 244, 210), (250, 232, 160), (250, 214, 226)))
            self.ground.fill(col, (x, y, 1, 1))

        # đường mòn quanh co
        for _ in range(3):
            x = rng.uniform(0, self.w)
            y = rng.uniform(0, self.h)
            ang = rng.uniform(0, math.tau)
            for _ in range(320):
                r = rng.uniform(5.0, 7.0)
                pygame.draw.circle(self.ground, (146, 104, 64), (int(x), int(y)), int(r + 1))
                pygame.draw.circle(self.ground, (178, 134, 88), (int(x), int(y)), int(r))
                if rng.random() < 0.65:
                    pygame.draw.circle(
                        self.ground, (202, 160, 108),
                        (int(x + rng.uniform(-r, r)), int(y + rng.uniform(-r, r))), 1)
                ang += rng.uniform(-0.17, 0.17)
                x += math.cos(ang) * 8.0
                y += math.sin(ang) * 8.0
                if not (0 <= x < self.w and 0 <= y < self.h):
                    break

        # cây & đá: (x, y, surface, bán kính va chạm)
        self.props = []
        self.trees = [make_tree(rng).convert_alpha() for _ in range(5)]
        self.bushes = [make_bush(rng).convert_alpha() for _ in range(3)]
        self.rocks = [make_rock(rng).convert_alpha(), make_rock(rng, True).convert_alpha()]

        def add_prop(x, y, surf, r):
            self.props.append((x, y, surf, r))

        # rừng rìa bản đồ
        step = 30
        for x in range(0, self.w + step, step):
            add_prop(x + rng.uniform(-7, 7), 16 + rng.uniform(-6, 10), rng.choice(self.trees), 7)
            add_prop(x + rng.uniform(-7, 7), self.h - 8 + rng.uniform(-6, 6),
                     rng.choice(self.trees), 7)
        for y in range(0, self.h + step, step):
            add_prop(14 + rng.uniform(-7, 7), y + rng.uniform(-7, 7), rng.choice(self.trees), 7)
            add_prop(self.w - 12 + rng.uniform(-7, 7), y + rng.uniform(-7, 7),
                     rng.choice(self.trees), 7)

        # cây rải rác
        for _ in range(780):
            x = rng.uniform(40, self.w - 40)
            y = rng.uniform(40, self.h - 40)
            if dist2(x, y, self.w / 2, self.h / 2) < 95 * 95:
                continue
            add_prop(x, y, rng.choice(self.trees), 7)
        # bụi cây
        for _ in range(320):
            x = rng.uniform(40, self.w - 40)
            y = rng.uniform(40, self.h - 40)
            if dist2(x, y, self.w / 2, self.h / 2) < 80 * 80:
                continue
            add_prop(x, y, rng.choice(self.bushes), 0)
        # đá
        for _ in range(180):
            x = rng.uniform(40, self.w - 40)
            y = rng.uniform(40, self.h - 40)
            if dist2(x, y, self.w / 2, self.h / 2) < 130 * 130:
                continue
            add_prop(x, y, rng.choice(self.rocks), 5)


# ---------------------------------------------------------------------------
# ÂM THANH
# ---------------------------------------------------------------------------
class Sfx:
    def __init__(self):
        self.enabled = True
        self.sounds = {}
        if not pygame.mixer.get_init():
            return
        specs = {
            "shoot": (900, 0.055, 0.13, "square", -0.55, 0.12),
            "hit": (330, 0.05, 0.11, "noise", 0.0, 0.9),
            "kill": (190, 0.12, 0.14, "saw", -0.5, 0.15),
            "gem": (1180, 0.07, 0.11, "square", 0.6, 0.0),
            "hurt": (150, 0.20, 0.20, "square", -0.35, 0.2),
            "level": (640, 0.30, 0.16, "square", 1.1, 0.0),
            "dead": (240, 0.55, 0.20, "saw", -0.8, 0.1),
            "eshot": (430, 0.08, 0.07, "square", -0.2, 0.1),
        }
        try:
            for k, (f, d, v, kind, sw, nz) in specs.items():
                snd = pygame.mixer.Sound(file=synth_wav(f, d, v, kind, sw, nz))
                snd.set_volume(0.45)
                self.sounds[k] = snd
        except Exception:
            self.sounds = {}

    def play(self, name):
        if not self.enabled:
            return
        snd = self.sounds.get(name)
        if snd is not None:
            try:
                snd.play()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# THỰC THỂ
# ---------------------------------------------------------------------------
class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color", "size")

    def __init__(self, x, y, vx, vy, life, color, size):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.max_life = life
        self.color = color
        self.size = size


class Gem:
    __slots__ = ("x", "y", "value", "kind", "t", "pulled")

    def __init__(self, x, y, value, kind=1):
        self.x = x
        self.y = y
        self.value = value
        self.kind = kind      # 1 = exp, 0 = hồi máu
        self.t = random.uniform(0, 6.28)
        self.pulled = False


class Bullet:
    __slots__ = ("x", "y", "vx", "vy", "dmg", "pierce", "r", "life", "crit", "hits")

    def __init__(self, x, y, ang, speed, dmg, pierce, r, crit=False):
        self.x = x
        self.y = y
        self.vx = math.cos(ang) * speed
        self.vy = math.sin(ang) * speed
        self.dmg = dmg
        self.pierce = pierce
        self.r = r
        self.life = 1.4
        self.crit = crit
        self.hits = set()


class EnemyBullet:
    __slots__ = ("x", "y", "vx", "vy", "dmg", "life")

    def __init__(self, x, y, ang, speed, dmg):
        self.x = x
        self.y = y
        self.vx = math.cos(ang) * speed
        self.vy = math.sin(ang) * speed
        self.dmg = dmg
        self.life = 3.2


ENEMY_TYPES = {
    "ghost":    dict(hp=18,  speed=42, dmg=8,  xp=1, r=7,  sprite="ghost"),
    "bat":      dict(hp=12,  speed=82, dmg=6,  xp=1, r=6,  sprite="bat"),
    "skeleton": dict(hp=48,  speed=35, dmg=12, xp=3, r=7,  sprite="skeleton"),
    "brute":    dict(hp=175, speed=29, dmg=20, xp=9, r=10, sprite="brute"),
}


class Enemy:
    _uid = 0

    def __init__(self, kind, x, y, hp_scale, sprites):
        Enemy._uid += 1
        self.uid = Enemy._uid
        cfg = ENEMY_TYPES[kind]
        self.kind = kind
        self.x = x
        self.y = y
        self.r = cfg["r"]
        self.max_hp = cfg["hp"] * hp_scale
        self.hp = self.max_hp
        self.speed = cfg["speed"] * random.uniform(0.9, 1.12)
        self.dmg = cfg["dmg"]
        self.xp = cfg["xp"]
        self.surf = sprites[cfg["sprite"]]
        self.flash_surf = sprites[cfg["sprite"] + "_flash"]
        self.flash_t = 0.0
        self.t = random.uniform(0, 6.28)
        self.phase = random.uniform(0, 6.28)
        self.shoot_cd = random.uniform(1.0, 2.6)
        self.bob = 0.0

    def draw(self, surf, cx, cy):
        img = self.flash_surf if self.flash_t > 0 else self.surf
        w, h = img.get_size()
        surf.blit(img, (int(self.x - cx - w / 2), int(self.y - cy - h + 2 + self.bob)))
        if self.hp < self.max_hp:
            bw = max(12, int(w * 0.9))
            frac = clamp(self.hp / self.max_hp, 0, 1)
            bx = int(self.x - cx - bw / 2)
            by = int(self.y - cy - h - 3)
            pygame.draw.rect(surf, (26, 20, 26), (bx, by, bw, 3))
            pygame.draw.rect(surf, (226, 78, 84), (bx, by, int(bw * frac), 3))


class Player:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.max_hp = 100.0
        self.hp = 100.0
        self.speed = 92.0
        self.damage = 13.0
        self.fire_rate = 0.42
        self.bullet_speed = 400.0
        self.pierce = 0
        self.shots = 1
        self.spread = 0.15
        self.bullet_size = 2.6
        self.magnet = 58.0
        self.crit = 0.0
        self.regen = 0.0
        self.level = 1
        self.xp = 0
        self.xp_need = xp_for(1)
        self.invuln = 0.0
        self.aim = 0.0
        self.fire_timer = 0.0
        self.walk_t = 0.0
        self.moving = False
        self.kills = 0


# ---------------------------------------------------------------------------
# NÂNG CẤP
# ---------------------------------------------------------------------------
UPGRADES = [
    dict(id="dmg", name="Đạn mạnh", desc="+6 sát thương mỗi viên", max=8,
         apply=lambda p: setattr(p, "damage", p.damage + 6)),
    dict(id="rate", name="Bắn nhanh", desc="Tốc độ bắn +14%", max=8,
         apply=lambda p: setattr(p, "fire_rate", max(0.10, p.fire_rate * 0.86))),
    dict(id="multi", name="Đa đạn", desc="Bắn thêm 1 viên mỗi lần", max=4,
         apply=lambda p: setattr(p, "shots", p.shots + 1)),
    dict(id="pierce", name="Xuyên thấu", desc="Đạn xuyên thêm 1 mục tiêu", max=4,
         apply=lambda p: setattr(p, "pierce", p.pierce + 1)),
    dict(id="speed", name="Nhanh chân", desc="Tốc độ chạy +9", max=6,
         apply=lambda p: setattr(p, "speed", p.speed + 9)),
    dict(id="hp", name="Sinh lực", desc="+25 máu tối đa và hồi 25 máu", max=6,
         apply=lambda p: (setattr(p, "max_hp", p.max_hp + 25),
                          setattr(p, "hp", min(p.max_hp + 25, p.hp + 25)))),
    dict(id="regen", name="Hồi phục", desc="Hồi 0.6 máu mỗi giây", max=5,
         apply=lambda p: setattr(p, "regen", p.regen + 0.6)),
    dict(id="magnet", name="Nam châm", desc="Bán kính hút EXP +40", max=4,
         apply=lambda p: setattr(p, "magnet", p.magnet + 40)),
    dict(id="crit", name="Chí mạng", desc="+8% tỉ lệ chí mạng (x2 sát thương)", max=5,
         apply=lambda p: setattr(p, "crit", min(0.8, p.crit + 0.08))),
    dict(id="size", name="Đạn lớn", desc="Đạn to hơn, dễ trúng hơn", max=3,
         apply=lambda p: setattr(p, "bullet_size", p.bullet_size + 1.1)),
]


# ---------------------------------------------------------------------------
# GAME
# ---------------------------------------------------------------------------
class Game:
    def __init__(self, app):
        self.app = app
        self.world = app.world
        self.sprites = app.sprites
        self.reset()

    def reset(self):
        self.state = "menu"
        self.player = Player(WORLD_W / 2, WORLD_H / 2)
        self.bullets = []
        self.ebullets = []
        self.enemies = []
        self.gems = []
        self.particles = []
        self.time = 0.0
        self.spawn_timer = 0.8
        self.shake = 0.0
        self.muzzle = 0.0
        self.muzzle_ang = 0.0
        self.levelup_choices = []
        self.up_levels = {}
        self.pending_levels = 0
        self.cam_x = self.player.x - LOGICAL_W / 2
        self.cam_y = self.player.y - LOGICAL_H / 2

    def start(self):
        self.reset()
        self.state = "play"

    # ---------------- vòng lặp ----------------
    def update(self, dt):
        if self.state == "play":
            self.update_play(dt)
        elif self.state == "menu":
            self.time += dt
            self.cam_x = self.player.x - LOGICAL_W / 2 + math.sin(self.time * 0.35) * 40
            self.cam_y = self.player.y - LOGICAL_H / 2 + math.cos(self.time * 0.27) * 26

    def update_play(self, dt):
        p = self.player
        self.time += dt
        if self.shake > 0:
            self.shake = max(0.0, self.shake - dt * 45)
        if self.muzzle > 0:
            self.muzzle = max(0.0, self.muzzle - dt)
        if p.invuln > 0:
            p.invuln = max(0.0, p.invuln - dt)
        if p.regen > 0 and p.hp < p.max_hp:
            p.hp = min(p.max_hp, p.hp + p.regen * dt)

        # di chuyển
        keys = pygame.key.get_pressed()
        dx = dy = 0.0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            dx -= 1.0
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            dx += 1.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dy -= 1.0
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dy += 1.0
        if dx or dy:
            ln = math.hypot(dx, dy)
            dx /= ln
            dy /= ln
            p.moving = True
            p.walk_t += dt
        else:
            p.moving = False
        p.x = clamp(p.x + dx * p.speed * dt, 14, WORLD_W - 14)
        p.y = clamp(p.y + dy * p.speed * dt, 18, WORLD_H - 8)
        self.collide_props(p)

        self.player_shoot(dt)
        self.update_bullets(dt)
        self.update_enemies(dt)
        self.update_enemy_bullets(dt)
        self.update_gems(dt)
        self.update_particles(dt)
        self.spawn_wave(dt)

        # camera mượt
        tx = p.x - LOGICAL_W / 2
        ty = p.y - LOGICAL_H / 2
        k = min(1.0, dt * 9.0)
        self.cam_x += (tx - self.cam_x) * k
        self.cam_y += (ty - self.cam_y) * k

    def collide_props(self, p):
        for (px, py, surf, r) in self.world.props:
            if r <= 0:
                continue
            ddx = p.x - px
            ddy = (p.y - 4) - py
            if abs(ddx) > 34 or abs(ddy) > 34:
                continue
            d = math.hypot(ddx, ddy)
            need = r + 4
            if 0.001 < d < need:
                push = need - d
                p.x += ddx / d * push
                p.y += ddy / d * push

    # ---------------- bắn ----------------
    def player_shoot(self, dt):
        p = self.player
        p.fire_timer -= dt
        target = self.nearest_enemy(p.x, p.y, 280)
        if target is None:
            return
        ang = math.atan2(target.y - 6 - (p.y - 8), target.x - p.x)
        p.aim = ang
        if p.fire_timer > 0:
            return
        p.fire_timer = p.fire_rate
        n = p.shots
        for i in range(n):
            off = (i - (n - 1) / 2.0) * p.spread
            a = ang + off + random.uniform(-0.035, 0.035)
            crit = random.random() < p.crit
            dmg = p.damage * (2.0 if crit else 1.0)
            self.bullets.append(Bullet(p.x + math.cos(a) * 10, p.y - 8 + math.sin(a) * 10,
                                       a, p.bullet_speed, dmg, p.pierce, p.bullet_size, crit))
        self.muzzle = 0.06
        self.muzzle_ang = ang
        self.app.sfx.play("shoot")

    def nearest_enemy(self, x, y, rng):
        best = None
        bd = rng * rng
        for e in self.enemies:
            d = dist2(x, y - 6, e.x, e.y - 6)
            if d < bd:
                bd = d
                best = e
        return best

    def update_bullets(self, dt):
        for b in list(self.bullets):
            b.x += b.vx * dt
            b.y += b.vy * dt
            b.life -= dt
            if b.life <= 0 or not (0 <= b.x <= WORLD_W and 0 <= b.y <= WORLD_H):
                if b in self.bullets:
                    self.bullets.remove(b)
                continue
            for e in list(self.enemies):
                rr = e.r + b.r
                if dist2(b.x, b.y, e.x, e.y - 6) < rr * rr:
                    if e.uid in b.hits:
                        continue
                    b.hits.add(e.uid)
                    e.hp -= b.dmg
                    e.flash_t = 0.09
                    self.spawn_particles(b.x, b.y, 4, (255, 232, 140), 70)
                    self.app.sfx.play("hit")
                    if e.hp <= 0:
                        self.kill_enemy(e)
                    if b.pierce > 0:
                        b.pierce -= 1
                    else:
                        if b in self.bullets:
                            self.bullets.remove(b)
                        break

    def update_enemy_bullets(self, dt):
        p = self.player
        for eb in list(self.ebullets):
            eb.x += eb.vx * dt
            eb.y += eb.vy * dt
            eb.life -= dt
            if eb.life <= 0:
                self.ebullets.remove(eb)
                continue
            if dist2(eb.x, eb.y, p.x, p.y - 7) < 8 * 8 and p.invuln <= 0:
                self.damage_player(eb.dmg)
                self.ebullets.remove(eb)

    # ---------------- kẻ địch ----------------
    def update_enemies(self, dt):
        p = self.player
        for e in list(self.enemies):
            e.t += dt
            if e.flash_t > 0:
                e.flash_t = max(0.0, e.flash_t - dt)
            ang = math.atan2((p.y - 6) - (e.y - 6), p.x - e.x)
            if e.kind == "bat":
                ang += math.sin(e.t * 5.0 + e.phase) * 0.6
                e.bob = math.sin(e.t * 10.0) * 2.0 - 2.0
            elif e.kind == "ghost":
                e.bob = math.sin(e.t * 3.0 + e.phase) * 1.6 - 1.0
            else:
                e.bob = 0.0
            e.x += math.cos(ang) * e.speed * dt
            e.y += math.sin(ang) * e.speed * dt
            e.x = clamp(e.x, 8, WORLD_W - 8)
            e.y = clamp(e.y, 12, WORLD_H - 4)

            if e.kind in ("skeleton", "brute"):
                e.shoot_cd -= dt
                if e.shoot_cd <= 0 and dist2(e.x, e.y, p.x, p.y) < 230 * 230:
                    e.shoot_cd = random.uniform(1.8, 3.0) if e.kind == "skeleton" \
                        else random.uniform(1.4, 2.2)
                    self.ebullets.append(EnemyBullet(e.x, e.y - 10, ang, 115, e.dmg * 0.65))
                    self.app.sfx.play("eshot")

            rr = e.r + 7
            if p.invuln <= 0 and dist2(e.x, e.y - 6, p.x, p.y - 6) < rr * rr:
                self.damage_player(e.dmg)

    def damage_player(self, dmg):
        p = self.player
        p.hp -= dmg
        p.invuln = 0.62
        self.shake = 3.2
        self.app.sfx.play("hurt")
        self.spawn_particles(p.x, p.y - 8, 10, (232, 74, 84), 95)
        if p.hp <= 0:
            p.hp = 0.0
            self.state = "over"
            self.app.sfx.play("dead")
            if p.kills > self.app.best_score:
                self.app.best_score = p.kills
                self.app.save()

    def kill_enemy(self, e):
        if e in self.enemies:
            self.enemies.remove(e)
        self.player.kills += 1
        self.app.sfx.play("kill")
        self.spawn_particles(e.x, e.y - 6, 12, (208, 198, 228), 115)
        pieces = 1 if e.xp < 3 else 2
        for _ in range(pieces):
            self.gems.append(Gem(e.x + random.uniform(-5, 5), e.y + random.uniform(-4, 4),
                                 max(1, e.xp // pieces)))
        if random.random() < 0.055:
            self.gems.append(Gem(e.x, e.y, 0, kind=0))

    def spawn_wave(self, dt):
        self.spawn_timer -= dt
        if self.spawn_timer > 0:
            return
        t = self.time
        interval = max(0.17, 1.05 - t * 0.0075)
        self.spawn_timer = interval * random.uniform(0.7, 1.3)
        if len(self.enemies) > 220:
            return

        count = 1 + int(t // 45)
        pool = ["ghost"]
        if t > 18:
            pool += ["bat", "bat"]
        if t > 45:
            pool += ["skeleton"]
        if t > 80:
            pool += ["skeleton", "brute"]
        if t > 140:
            pool += ["bat", "brute", "skeleton"]

        hp_scale = 1.0 + t / 95.0
        for _ in range(count):
            kind = random.choice(pool)
            ang = random.uniform(0, math.tau)
            rad = random.uniform(215, 290)
            x = clamp(self.player.x + math.cos(ang) * rad, 24, WORLD_W - 24)
            y = clamp(self.player.y + math.sin(ang) * rad, 28, WORLD_H - 20)
            self.enemies.append(Enemy(kind, x, y, hp_scale, self.sprites))

    # ---------------- EXP ----------------
    def update_gems(self, dt):
        p = self.player
        for g in list(self.gems):
            g.t += dt
            d = math.hypot(p.x - g.x, (p.y - 6) - g.y)
            if g.pulled or d < p.magnet:
                g.pulled = True
                ang = math.atan2((p.y - 6) - g.y, p.x - g.x)
                spd = 150.0 + max(0.0, (p.magnet - d)) * 2.2
                g.x += math.cos(ang) * spd * dt
                g.y += math.sin(ang) * spd * dt
            if d < 9:
                self.gems.remove(g)
                if g.kind == 0:
                    p.hp = min(p.max_hp, p.hp + 12)
                    self.spawn_particles(g.x, g.y, 6, (255, 130, 150), 60)
                else:
                    p.xp += g.value
                    self.spawn_particles(g.x, g.y, 3, (140, 226, 255), 40)
                    if p.xp >= p.xp_need:
                        self.level_up()
                self.app.sfx.play("gem")

    def level_up(self):
        p = self.player
        while p.xp >= p.xp_need:
            p.xp -= p.xp_need
            p.level += 1
            p.xp_need = xp_for(p.level)
            self.pending_levels += 1
        if self.pending_levels > 0 and self.state == "play":
            self.roll_upgrades()
            if self.levelup_choices:
                self.state = "levelup"
                self.app.sfx.play("level")
            else:
                p.hp = min(p.max_hp, p.hp + 30)
                self.pending_levels = 0

    def roll_upgrades(self):
        pool = [u for u in UPGRADES if self.up_levels.get(u["id"], 0) < u["max"]]
        random.shuffle(pool)
        self.levelup_choices = pool[:3]

    def choose_upgrade(self, i):
        if not (0 <= i < len(self.levelup_choices)):
            return
        up = self.levelup_choices[i]
        self.up_levels[up["id"]] = self.up_levels.get(up["id"], 0) + 1
        try:
            up["apply"](self.player)
        except Exception:
            pass
        self.pending_levels -= 1
        if self.pending_levels > 0:
            self.roll_upgrades()
            if not self.levelup_choices:
                self.player.hp = min(self.player.max_hp, self.player.hp + 30)
                self.pending_levels = 0
                self.state = "play"
        else:
            self.levelup_choices = []
            self.state = "play"

    # ---------------- hiệu ứng ----------------
    def spawn_particles(self, x, y, n, color, speed):
        if len(self.particles) > 420:
            return
        for _ in range(n):
            a = random.uniform(0, math.tau)
            v = random.uniform(0.25, 1.0) * speed
            self.particles.append(Particle(x, y, math.cos(a) * v, math.sin(a) * v,
                                           random.uniform(0.18, 0.5), color,
                                           random.choice((1, 1, 2))))

    def update_particles(self, dt):
        for pa in list(self.particles):
            pa.life -= dt
            if pa.life <= 0:
                self.particles.remove(pa)
                continue
            pa.x += pa.vx * dt
            pa.y += pa.vy * dt
            pa.vx *= 0.92
            pa.vy *= 0.92


# ---------------------------------------------------------------------------
# APP: cửa sổ, vẽ, HUD, menu
# ---------------------------------------------------------------------------
class App:
    def __init__(self):
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        try:
            pygame.mixer.init(22050, -16, 1, 512)
        except Exception:
            pass
        pygame.display.set_caption(TITLE)

        self.window = pygame.display.set_mode((BASE_W, BASE_H), pygame.RESIZABLE)
        self.fullscreen = False
        self.clock = pygame.time.Clock()
        self.running = True
        self.frame = pygame.Surface((LOGICAL_W, LOGICAL_H)).convert()
        self._fonts = {}
        self._scaled = None
        self.best_score = 0
        self.load()

        self.loading("Đang tạo thế giới...")
        self.sprites = build_sprites()
        self.world = World(20261029)
        try:
            pygame.display.set_icon(pygame.transform.scale(self.sprites["player"], (64, 80)))
        except Exception:
            pass

        self.sfx = Sfx()
        self.game = Game(self)
        self.compute_view()

    # ---------------- lưu điểm ----------------
    def load(self):
        try:
            with open(SAVE_PATH, "r", encoding="utf-8") as f:
                self.best_score = int(json.load(f).get("best", 0))
        except Exception:
            self.best_score = 0

    def save(self):
        try:
            with open(SAVE_PATH, "w", encoding="utf-8") as f:
                json.dump({"best": self.best_score}, f)
        except Exception:
            pass

    # ---------------- khung hình ----------------
    def compute_view(self):
        w, h = self.window.get_size()
        s = max(1, min(w // LOGICAL_W, h // LOGICAL_H))
        self.scale = s
        self.vw = LOGICAL_W * s
        self.vh = LOGICAL_H * s
        self.ox = (w - self.vw) // 2
        self.oy = (h - self.vh) // 2
        if self._scaled is None or self._scaled.get_size() != (self.vw, self.vh):
            self._scaled = pygame.Surface((self.vw, self.vh)).convert()

    def ui(self):
        """hệ số phóng cho HUD (1.0 khi cửa sổ cao 808px)"""
        return self.vh / 808.0

    def font(self, size, bold=False):
        key = (int(size), bold)
        f = self._fonts.get(key)
        if f is None:
            f = load_font(size, bold)
            self._fonts[key] = f
        return f

    def text(self, surf, s, size, color, pos, anchor="topleft", bold=False, shadow=True):
        f = self.font(size, bold)
        img = f.render(s, True, color)
        rect = img.get_rect(**{anchor: pos})
        if shadow:
            off = max(1, int(size) // 14)
            sh = f.render(s, True, (0, 0, 0))
            sh.set_alpha(160)
            surf.blit(sh, (rect.x + off, rect.y + off))
        surf.blit(img, rect)
        return rect

    def text_wrapped(self, surf, s, size, color, center_x, top_y, max_w, gap=2):
        f = self.font(size)
        words = s.split()
        lines = []
        cur = ""
        for wd in words:
            test = (cur + " " + wd).strip()
            if not cur or f.size(test)[0] <= max_w:
                cur = test
            else:
                lines.append(cur)
                cur = wd
        if cur:
            lines.append(cur)
        y = top_y
        for ln in lines:
            img = f.render(ln, True, color)
            surf.blit(img, (center_x - img.get_width() // 2, y))
            y += img.get_height() + gap

    def loading(self, msg):
        self.window.fill(C_BG)
        w, h = self.window.get_size()
        self.text(self.window, msg, 28, C_WHITE, (w // 2, h // 2), "center")
        pygame.display.flip()
        pygame.event.pump()

    # ---------------- sự kiện ----------------
    def handle_events(self):
        g = self.game
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.running = False
            elif ev.type == pygame.VIDEORESIZE:
                if not self.fullscreen:
                    self.window = pygame.display.set_mode((max(640, ev.w), max(360, ev.h)),
                                                          pygame.RESIZABLE)
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_F11:
                    self.toggle_fullscreen()
                elif ev.key == pygame.K_m:
                    self.sfx.enabled = not self.sfx.enabled
                elif g.state == "menu":
                    if ev.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
                        g.start()
                elif g.state == "play":
                    if ev.key in (pygame.K_ESCAPE, pygame.K_p):
                        g.state = "pause"
                elif g.state == "pause":
                    if ev.key in (pygame.K_ESCAPE, pygame.K_p):
                        g.state = "play"
                elif g.state == "levelup":
                    if ev.key in (pygame.K_1, pygame.K_KP1):
                        g.choose_upgrade(0)
                    elif ev.key in (pygame.K_2, pygame.K_KP2):
                        g.choose_upgrade(1)
                    elif ev.key in (pygame.K_3, pygame.K_KP3):
                        g.choose_upgrade(2)
                elif g.state == "over":
                    if ev.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
                        g.start()
                    elif ev.key == pygame.K_ESCAPE:
                        g.reset()
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                if g.state == "levelup":
                    for i, r in enumerate(self.card_rects()):
                        if r.collidepoint(ev.pos):
                            g.choose_upgrade(i)
                            break
                elif g.state == "menu":
                    g.start()
                elif g.state == "over":
                    g.start()

    def toggle_fullscreen(self):
        if self.fullscreen:
            self.window = pygame.display.set_mode((BASE_W, BASE_H), pygame.RESIZABLE)
            self.fullscreen = False
        else:
            try:
                self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                self.fullscreen = True
            except Exception:
                self.fullscreen = False
        self.compute_view()

    # ---------------- vẽ thế giới ----------------
    def draw_world(self, frame):
        g = self.game
        cx = g.cam_x
        cy = g.cam_y
        if g.shake > 0:
            cx += random.uniform(-g.shake, g.shake)
            cy += random.uniform(-g.shake, g.shake)
        cx = clamp(cx, 0, WORLD_W - LOGICAL_W)
        cy = clamp(cy, 0, WORLD_H - LOGICAL_H)
        ix, iy = int(cx), int(cy)
        frame.blit(self.world.ground, (0, 0), (ix, iy, LOGICAL_W, LOGICAL_H))

        # EXP gem / tim nằm dưới chân
        for gm in g.gems:
            if not (ix - 12 < gm.x < ix + LOGICAL_W + 12 and iy - 12 < gm.y < iy + LOGICAL_H + 12):
                continue
            img = self.sprites["heart"] if gm.kind == 0 else self.sprites["gem"]
            w, h = img.get_size()
            bob = math.sin(gm.t * 6.0) * 1.2
            frame.blit(img, (int(gm.x - ix - w / 2), int(gm.y - iy - h - 2 + bob)))

        # sắp xếp theo trục y để tạo chiều sâu
        items = []
        for (px, py, surf, r) in self.world.props:
            if ix - 44 < px < ix + LOGICAL_W + 44 and iy - 64 < py < iy + LOGICAL_H + 64:
                items.append((py, 2, (px, py, surf)))
        for e in g.enemies:
            if ix - 30 < e.x < ix + LOGICAL_W + 30 and iy - 44 < e.y < iy + LOGICAL_H + 40:
                items.append((e.y, 1, e))
        p = g.player
        if g.state != "menu":
            items.append((p.y, 0, p))
        items.sort(key=lambda it: it[0])

        for _, kind, obj in items:
            if kind == 2:
                px, py, surf = obj
                frame.blit(surf, (int(px - ix - surf.get_width() / 2),
                                  int(py - iy - surf.get_height())))
            elif kind == 1:
                obj.draw(frame, ix, iy)
            else:
                self.draw_player(frame, ix, iy)

        # đạn
        for b in g.bullets:
            if not (ix - 12 < b.x < ix + LOGICAL_W + 12 and iy - 12 < b.y < iy + LOGICAL_H + 12):
                continue
            bx, by = int(b.x - ix), int(b.y - iy)
            ln = max(1.0, math.hypot(b.vx, b.vy))
            dx = b.vx / ln
            dy = b.vy / ln
            col = (255, 210, 90) if not b.crit else (255, 140, 90)
            pygame.draw.line(frame, col, (bx, by), (int(bx - dx * 7), int(by - dy * 7)), 2)
            frame.fill((255, 250, 220), (bx, by, 1, 1))

        for eb in g.ebullets:
            ex, ey = int(eb.x - ix), int(eb.y - iy)
            pygame.draw.rect(frame, (188, 176, 210), (ex - 2, ey - 2, 4, 4))
            frame.fill((246, 240, 255), (ex - 1, ey - 1, 2, 2))

        # hạt hiệu ứng
        for pa in g.particles:
            a = clamp(pa.life / pa.max_life, 0, 1)
            col = (int(pa.color[0] * a), int(pa.color[1] * a), int(pa.color[2] * a))
            frame.fill(col, (int(pa.x - ix), int(pa.y - iy), pa.size, pa.size))

    def draw_player(self, frame, cx, cy):
        g = self.game
        p = g.player
        img = self.sprites["player_flash"] if (p.invuln > 0 and int(p.invuln * 22) % 2 == 0) \
            else self.sprites["player"]
        w, h = img.get_size()
        bob = -1 if (p.moving and int(p.walk_t * 8) % 2 == 0) else 0
        pygame.draw.ellipse(frame, (108, 156, 64), (int(p.x - cx - 6), int(p.y - cy - 3), 12, 4))
        frame.blit(img, (int(p.x - cx - w / 2), int(p.y - cy - h + bob)))

        gun = pygame.transform.rotate(self.sprites["gun"], -math.degrees(p.aim))
        gx = p.x - cx + math.cos(p.aim) * 7
        gy = p.y - cy - 9 + math.sin(p.aim) * 7
        rect = gun.get_rect(center=(int(gx), int(gy)))
        frame.blit(gun, rect)

        if g.muzzle > 0:
            mx = p.x - cx + math.cos(p.aim) * 14
            my = p.y - cy - 9 + math.sin(p.aim) * 14
            pygame.draw.circle(frame, (255, 226, 120), (int(mx), int(my)), 3)
            pygame.draw.circle(frame, (255, 255, 230), (int(mx), int(my)), 1)

    # ---------------- HUD ----------------
    def draw_hud(self):
        win = self.window
        k = self.ui()
        ox, oy, w = self.ox, self.oy, self.vw
        p = self.game.player

        # thanh EXP trên cùng
        bh = max(7, int(9 * k))
        pygame.draw.rect(win, (16, 14, 24), (ox, oy, w, bh))
        frac = clamp(p.xp / max(1, p.xp_need), 0, 1)
        if frac > 0:
            pygame.draw.rect(win, C_XP, (ox, oy, int(w * frac), bh))
            pygame.draw.rect(win, (190, 244, 255), (ox, oy, int(w * frac), max(1, int(2 * k))))
        pygame.draw.rect(win, (60, 56, 84), (ox, oy, w, bh), 1)

        # bảng máu
        px, py = ox + int(16 * k), oy + int(20 * k)
        pw, ph = int(220 * k), int(17 * k)
        pygame.draw.rect(win, (14, 12, 20), (px - int(3 * k), py - int(3 * k),
                                            pw + int(6 * k), ph + int(6 * k)),
                         border_radius=int(4 * k))
        pygame.draw.rect(win, (44, 40, 58), (px, py, pw, ph))
        hf = clamp(p.hp / p.max_hp, 0, 1)
        if hf > 0:
            pygame.draw.rect(win, C_HP, (px, py, int(pw * hf), ph))
            pygame.draw.rect(win, (250, 130, 138), (px, py, int(pw * hf), max(2, int(5 * k))))
        pygame.draw.rect(win, (86, 80, 112), (px, py, pw, ph), 1)
        self.text(win, "%d / %d" % (int(p.hp), int(p.max_hp)), int(13 * k), C_WHITE,
                  (px + pw // 2, py + ph // 2), "center")

        # level
        self.text(win, "Lv %d" % p.level, int(19 * k), C_XP,
                  (ox + w - int(14 * k), oy + int(14 * k)), "topright", bold=True)

        # đồng hồ
        mm = int(self.game.time // 60)
        ss = int(self.game.time % 60)
        tw, th = int(110 * k), int(42 * k)
        tpanel = pygame.Surface((tw, th), pygame.SRCALPHA)
        pygame.draw.rect(tpanel, (10, 10, 18, 120), tpanel.get_rect(),
                         border_radius=int(7 * k))
        win.blit(tpanel, (ox + w // 2 - tw // 2, oy + int(10 * k)))
        self.text(win, "%02d:%02d" % (mm, ss), int(30 * k), C_WHITE,
                  (ox + w // 2, oy + int(13 * k)), "midtop", bold=True)

        # bảng thống kê nhỏ
        sx, sy = ox + int(14 * k), oy + int(48 * k)
        sw, sh = int(148 * k), int(46 * k)
        panel = pygame.Surface((sw, sh), pygame.SRCALPHA)
        pygame.draw.rect(panel, (10, 10, 18, 125), panel.get_rect(),
                         border_radius=int(7 * k))
        win.blit(panel, (sx, sy))
        self.text(win, "Hạ gục: %d" % p.kills, int(16 * k), C_WHITE,
                  (sx + int(11 * k), sy + int(5 * k)), "topleft")
        self.text(win, "Kỷ lục: %d" % self.best_score, int(13 * k), C_DIM,
                  (sx + int(11 * k), sy + int(27 * k)), "topleft")

        # gợi ý đầu game
        if self.game.time < 12:
            self.text(win, "WASD di chuyển  •  Súng tự động bắn  •  ESC tạm dừng",
                      int(14 * k), (232, 232, 240),
                      (ox + w // 2, oy + self.vh - int(26 * k)), "center")

        if not self.sfx.enabled:
            self.text(win, "TẮT ÂM THANH (M)", int(12 * k), C_DIM,
                      (ox + w - int(14 * k), oy + self.vh - int(22 * k)), "topright")

    # ---------------- overlay ----------------
    def dim(self, alpha=180):
        d = pygame.Surface((self.vw, self.vh), pygame.SRCALPHA)
        d.fill((8, 7, 14, alpha))
        self.window.blit(d, (self.ox, self.oy))

    def card_rects(self):
        k = self.ui()
        cw, ch, gap = int(250 * k), int(186 * k), int(24 * k)
        n = max(1, len(self.game.levelup_choices))
        total = n * cw + (n - 1) * gap
        x0 = self.ox + (self.vw - total) // 2
        y0 = self.oy + int(self.vh * 0.53) - ch // 2
        return [pygame.Rect(x0 + i * (cw + gap), y0, cw, ch) for i in range(n)]

    def draw_levelup(self):
        win = self.window
        k = self.ui()
        self.dim(205)
        cx = self.ox + self.vw // 2
        self.text(win, "LÊN CẤP!", int(38 * k), C_GOLD, (cx, self.oy + int(56 * k)),
                  "midtop", bold=True)
        self.text(win, "Chọn 1 nâng cấp  (bấm 1 / 2 / 3 hoặc click)", int(15 * k), C_DIM,
                  (cx, self.oy + int(106 * k)), "midtop")

        mouse = pygame.mouse.get_pos()
        for i, r in enumerate(self.card_rects()):
            if i >= len(self.game.levelup_choices):
                break
            up = self.game.levelup_choices[i]
            hover = r.collidepoint(mouse)
            bg = (46, 42, 64) if hover else (28, 25, 42)
            pygame.draw.rect(win, bg, r, border_radius=int(9 * k))
            pygame.draw.rect(win, C_GOLD if hover else (92, 86, 124), r,
                             max(1, int(2 * k)), border_radius=int(9 * k))
            self.text(win, "[%d]" % (i + 1), int(13 * k), C_DIM,
                      (r.centerx, r.top + int(9 * k)), "midtop")
            self.text(win, up["name"], int(22 * k), C_WHITE,
                      (r.centerx, r.top + int(32 * k)), "midtop", bold=True)
            self.text_wrapped(win, up["desc"], int(14 * k), (206, 204, 220),
                              r.centerx, r.top + int(70 * k), r.width - int(26 * k))
            lvl = self.game.up_levels.get(up["id"], 0)
            self.text(win, "cấp %d / %d" % (lvl, up["max"]), int(12 * k), C_DIM,
                      (r.centerx, r.bottom - int(24 * k)), "midtop")

    def draw_pause(self):
        win = self.window
        k = self.ui()
        self.dim(170)
        cx = self.ox + self.vw // 2
        self.text(win, "TẠM DỪNG", int(36 * k), C_WHITE,
                  (cx, self.oy + self.vh // 2 - int(26 * k)), "center", bold=True)
        self.text(win, "ESC / P để tiếp tục", int(16 * k), C_DIM,
                  (cx, self.oy + self.vh // 2 + int(26 * k)), "center")

    def draw_over(self):
        win = self.window
        k = self.ui()
        self.dim(210)
        g = self.game
        cx = self.ox + self.vw // 2
        cy = self.oy + self.vh // 2
        self.text(win, "BẠN ĐÃ GỤC NGÃ", int(42 * k), (240, 92, 100),
                  (cx, cy - int(100 * k)), "center", bold=True)
        mm = int(g.time // 60)
        ss = int(g.time % 60)
        lines = [
            "Thời gian sống sót: %02d:%02d" % (mm, ss),
            "Hạ gục: %d" % g.player.kills,
            "Cấp đạt được: %d" % g.player.level,
            "Kỷ lục: %d" % self.best_score,
        ]
        y = cy - int(34 * k)
        for ln in lines:
            self.text(win, ln, int(18 * k), C_WHITE, (cx, y), "center")
            y += int(32 * k)
        self.text(win, "SPACE để chơi lại  •  ESC về menu", int(16 * k), C_GOLD,
                  (cx, cy + int(108 * k)), "center")

    def draw_menu(self):
        win = self.window
        k = self.ui()
        self.dim(155)
        cx = self.ox + self.vw // 2
        cy = self.oy + self.vh // 2

        self.text(win, "SOUL SURVIVORS", int(56 * k), C_GOLD,
                  (cx, cy - int(126 * k)), "center", bold=True)
        self.text(win, "Sinh tồn giữa rừng quái vật", int(19 * k), (216, 214, 230),
                  (cx, cy - int(70 * k)), "center")

        self.text(win, "NHẤN SPACE ĐỂ BẮT ĐẦU", int(23 * k), C_WHITE,
                  (cx, cy + int(4 * k)), "center", bold=True)

        tips = [
            "WASD / mũi tên: di chuyển    •    Súng tự động bắn kẻ địch gần nhất",
            "Nhặt đá EXP xanh để lên cấp, chọn nâng cấp bằng 1 / 2 / 3",
            "ESC: tạm dừng    •    M: bật tắt âm thanh    •    F11: toàn màn hình",
        ]
        y = cy + int(58 * k)
        for t in tips:
            self.text(win, t, int(14 * k), C_DIM, (cx, y), "center")
            y += int(26 * k)

        self.text(win, "Kỷ lục hạ gục: %d" % self.best_score, int(15 * k), C_XP,
                  (cx, cy + int(142 * k)), "center")

    # ---------------- render ----------------
    def draw(self):
        win = self.window
        win.fill(C_BG)
        g = self.game
        self.draw_world(self.frame)
        pygame.transform.scale(self.frame, (self.vw, self.vh), self._scaled)
        win.blit(self._scaled, (self.ox, self.oy))

        if g.state in ("play", "pause"):
            self.draw_hud()
        if g.state == "menu":
            self.draw_menu()
        elif g.state == "pause":
            self.draw_pause()
        elif g.state == "levelup":
            self.draw_levelup()
        elif g.state == "over":
            self.draw_over()
        pygame.display.flip()

    # ---------------- chạy ----------------
    def run(self):
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            self.handle_events()
            if not self.running:
                break
            self.game.update(dt)
            self.compute_view()
            self.draw()
        pygame.quit()


def main():
    random.seed()
    app = App()
    app.run()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # pragma: no cover
        import traceback
        traceback.print_exc()
        try:
            pygame.quit()
        except Exception:
            pass
        try:
            import tkinter.messagebox as mb
            mb.showerror("Loi", str(exc))
        except Exception:
            pass
        sys.exit(1)
