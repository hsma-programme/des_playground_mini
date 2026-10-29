"""Draw the hospital-style background for the full model animation.

All coordinates are pixels in the original 3600x1425 image. The waiting areas,
bays/cubicles, entrance and exit keep the exact bounds measured from the
original drawio export, because the animation's event positions are tuned to them.

Usage (needs Pillow; the fonts are the Windows Century Gothic ones):
    python "resources/make_hospital_background.py" "resources/Full Model Background Image - Hospital Layout.png"
"""
import sys
from PIL import Image, ImageDraw, ImageFont

W, H = 3600, 1425
SS = 2  # supersample for anti-aliasing

FONT_B = "C:/Windows/Fonts/GOTHICB.TTF"
FONT_R = "C:/Windows/Fonts/GOTHIC.TTF"

# ---- measured bounds (do not change) -------------------------------------
WAIT = {
    "triage": (278, 293, 853, 668),
    "stab": (970, 99, 1553, 317),
    "t_treat": (2620, 99, 3253, 312),
    "reg": (980, 959, 1563, 1162),
    "exam": (1850, 959, 2403, 1162),
    "nt_treat": (2680, 959, 3263, 1162),
}
BAYS = {
    "triage": (338, 746, 827, 825),
    "stab": (967, 386, 1556, 455),
    "t_treat": (2637, 386, 3276, 455),
    "reg": (977, 1241, 1566, 1310),
    "exam": (1847, 1241, 2406, 1310),
    "nt_treat": (2677, 1241, 3266, 1310),
}
ENTRANCE = (168, 108, 203, 298)
EXIT = (3281, 606, 3316, 796)
TRAUMA_ROOM = (870, 19, 3313, 512)
NONTRAUMA_ROOM = (870, 889, 3323, 1382)
TRIAGE_ROOM = (185, 19, 870, 905)

# vidigi event anchors (x, y in plot units; plot is 700 x 675)
# queues fill leftwards 10 units apart, wrapping every 10, rows 22 units up
QUEUE_ANCHORS = {
    "triage": (150, 400),
    "stab": (295, 540),
    "t_treat": (630, 540),
    "reg": (290, 140),
    "exam": (460, 140),
    "nt_treat": (625, 140),
}
RESOURCE_ANCHORS = {
    "triage": 150,
    "stab": 295,
    "t_treat": 630,
    "reg": 290,
    "exam": 460,
    "nt_treat": 625,
}


def ux(x):
    return x / 700 * W


def uy(y):
    return (1 - y / 675) * H


# ---- palette (image is shown at 50% opacity over #1b1a1a) -----------------
WALL = (226, 232, 240, 255)
CORRIDOR = (78, 84, 96, 150)
FLOOR_TRAUMA = (92, 62, 68, 215)
FLOOR_NT = (58, 72, 104, 215)
FLOOR_TRIAGE = (56, 86, 82, 215)
WAIT_FILL = (214, 218, 226, 255)
CHAIR = (166, 175, 192, 255)
CHAIR_BACK = (136, 146, 166, 255)
BAY_FILL = (196, 230, 232, 255)
BAY_EDGE = (70, 150, 165, 255)
CURTAIN = (120, 185, 195, 255)
RED = (240, 92, 92, 255)
BLUE = (64, 152, 244, 255)
GREEN = (92, 206, 168, 255)
WHITE = (255, 255, 255, 255)
TEXT = (250, 250, 252, 255)
EXIT_GREEN = (40, 190, 100, 255)


class Canvas:
    def __init__(self):
        self.im = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    @staticmethod
    def p(v):
        return [round(c * SS) for c in v]

    def layer(self):
        """Draw onto a separate layer (so alpha fills don't stack)."""
        return Canvas._Layer(self)

    class _Layer:
        def __init__(self, parent):
            self.parent = parent

        def __enter__(self):
            self.im = Image.new("RGBA", self.parent.im.size, (0, 0, 0, 0))
            self.d = ImageDraw.Draw(self.im)
            return self

        def __exit__(self, *a):
            self.parent.im.alpha_composite(self.im)
            self.parent.d = ImageDraw.Draw(self.parent.im)

    def rect(self, box, fill=None, outline=None, width=0, radius=0, d=None):
        d = d or self.d
        d.rounded_rectangle(self.p(box), radius=radius * SS, fill=fill,
                            outline=outline, width=round(width * SS))

    def line(self, pts, fill, width, d=None, joint="curve"):
        d = d or self.d
        flat = [tuple(self.p(pt)) for pt in pts]
        d.line(flat, fill=fill, width=round(width * SS), joint=joint)
        r = width * SS / 2
        for x, y in (flat[0], flat[-1]):  # round caps
            d.ellipse([x - r, y - r, x + r, y + r], fill=fill)

    def poly(self, pts, fill, d=None):
        d = d or self.d
        d.polygon([tuple(self.p(pt)) for pt in pts], fill=fill)

    def ellipse(self, box, fill=None, outline=None, width=0, d=None):
        d = d or self.d
        d.ellipse(self.p(box), fill=fill, outline=outline, width=round(width * SS))

    def text(self, xy, s, size, fill=TEXT, font=FONT_B, anchor="mm", d=None):
        d = d or self.d
        f = ImageFont.truetype(font, round(size * SS))
        d.text(tuple(self.p(xy)), s, font=f, fill=fill, anchor=anchor)

    def save(self, path):
        self.im.resize((W, H), Image.LANCZOS).save(path, optimize=True)


def arrow_path(c, pts, colour, width=13, head=30, dotted=False):
    """A wayfinding line painted on the floor, ending in an arrowhead."""
    (x1, y1), (x2, y2) = pts[-2], pts[-1]
    # stop the line short so the head has a clean point
    if x1 == x2:
        sgn = 1 if y2 > y1 else -1
        tip = (x2, y2)
        base = (x2, y2 - sgn * head)
        wing = [(x2 - head * 0.62, base[1]), (x2 + head * 0.62, base[1])]
    else:
        sgn = 1 if x2 > x1 else -1
        tip = (x2, y2)
        base = (x2 - sgn * head, y2)
        wing = [(base[0], y2 - head * 0.62), (base[0], y2 + head * 0.62)]
    body = pts[:-1] + [base]
    if dotted:
        dotted_line(c, body, colour, width)
    else:
        c.line(body, colour, width)
    c.poly([tip, wing[0], wing[1]], colour)


def dotted_line(c, pts, colour, width, gap=26):
    import math
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        length = math.hypot(x2 - x1, y2 - y1)
        n = max(1, int(length // gap))
        for i in range(n + 1):
            t = i / n
            x, y = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
            r = width * 0.55
            c.ellipse((x - r, y - r, x + r, y + r), fill=colour)


def walls(c, segments, width=16):
    for seg in segments:
        c.line(seg, WALL, width, joint=None)


def tiled_floor(c, box, fill, tile=64, line=(255, 255, 255, 22), radius=18):
    x0, y0, x1, y1 = box
    with c.layer() as L:
        c.rect(box, fill=fill, radius=radius, d=L.d)
        mask = Image.new("L", L.im.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(c.p(box), radius=radius * SS, fill=255)
        grid = Image.new("RGBA", L.im.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(grid)
        x = x0 + tile
        while x < x1:
            gd.line(c.p((x, y0, x, y1)), fill=line, width=2 * SS)
            x += tile
        y = y0 + tile
        while y < y1:
            gd.line(c.p((x0, y, x1, y)), fill=line, width=2 * SS)
            y += tile
        L.im.paste(grid, (0, 0), Image.composite(grid, Image.new("RGBA", grid.size), mask))


def waiting_area(c, key):
    x0, y0, x1, y1 = WAIT[key]
    c.rect((x0, y0, x1, y1), fill=WAIT_FILL, radius=26)
    # a chair under each spot where vidigi seats a queued patient
    ax, ay = QUEUE_ANCHORS[key]
    for row in range(3):
        cy = uy(ay + 22 * row)
        for k in range(10):
            cx = ux(ax - 10 * k)
            if x0 + 22 < cx < x1 - 22 and y0 + 26 < cy < y1 - 20:
                c.rect((cx - 19, cy - 14, cx + 19, cy + 17), fill=CHAIR, radius=8)
                c.rect((cx - 21, cy - 24, cx + 21, cy - 14), fill=CHAIR_BACK, radius=5)


def bay_area(c, key):
    x0, y0, x1, y1 = BAYS[key]
    c.rect((x0 - 4, y0 - 4, x1 + 4, y1 + 4), fill=BAY_FILL, outline=BAY_EDGE, width=5, radius=16)
    # curtain rail along the top, curtains between each bay slot
    c.line([(x0 + 14, y0 + 7), (x1 - 14, y0 + 7)], BAY_EDGE, 4)
    ax = ux(RESOURCE_ANCHORS[key])
    step = ux(10)
    x = ax - step / 2
    while x > x0 + 20:
        if x < x1 - 20:
            # a gently pleated curtain
            pts = []
            y = y0 + 7
            i = 0
            while y < y1 - 6:
                pts.append((x + (4 if i % 2 else -4), y))
                y += 10
                i += 1
            c.line(pts, CURTAIN, 4)
        x -= step


def door(c, box, label, label_xy, sign_fill=None, side="left"):
    x0, y0, x1, y1 = box
    # door frame and two sliding glass leaves
    c.rect((x0, y0, x1, y1), fill=(170, 205, 235, 150), outline=WALL, width=5, radius=6)
    mid = (y0 + y1) / 2
    c.line([(x0 + 6, mid), (x1 - 6, mid)], WALL, 4)
    for yy in (y0 + (mid - y0) * 0.5, mid + (y1 - mid) * 0.5):
        c.line([((x0 + x1) / 2, yy - 18), ((x0 + x1) / 2, yy + 18)], (255, 255, 255, 200), 3)
    tx, ty = label_xy
    if sign_fill:
        f = ImageFont.truetype(FONT_B, 34 * SS)
        w = c.d.textlength(label, font=f) / SS
        c.rect((tx - w / 2 - 16, ty - 28, tx + w / 2 + 16, ty + 28), fill=sign_fill, radius=10)
    c.text(label_xy, label, 34)


def pathway_sign(c, box, colour, label, icon):
    x0, y0, x1, y1 = box
    # hanging sign: two short chains and a plate with an icon
    c.rect((x0 + 6, y0 + 8, x1 + 6, y1 + 8), fill=(0, 0, 0, 90), radius=18)
    c.rect(box, fill=colour, outline=WALL, width=5, radius=18)
    cx, cy = x0 + 62, (y0 + y1) / 2
    c.ellipse((cx - 34, cy - 34, cx + 34, cy + 34), fill=WHITE)
    icon(c, cx, cy, colour)
    size = 56
    while ImageFont.truetype(FONT_B, size * SS).getlength(label) / SS > x1 - x0 - 150:
        size -= 1
    c.text(((x0 + 110 + x1) / 2 - 8, cy + 2), label, size)


def icon_cross(c, cx, cy, colour):
    c.rect((cx - 8, cy - 23, cx + 8, cy + 23), fill=colour, radius=3)
    c.rect((cx - 23, cy - 8, cx + 23, cy + 8), fill=colour, radius=3)


def icon_ecg(c, cx, cy, colour):
    c.line([(cx - 26, cy + 2), (cx - 12, cy + 2), (cx - 5, cy - 20), (cx + 4, cy + 20),
            (cx + 11, cy + 2), (cx + 26, cy + 2)], colour, 6)


def ae_sign(c):
    """Hospital A&E sign outside, below the entrance."""
    sx0, sy0, sx1, sy1 = 70, 935, 830, 1070
    c.rect((sx0 + 6, sy0 + 8, sx1 + 6, sy1 + 8), fill=(0, 0, 0, 90), radius=16)
    c.rect((sx0, sy0, sx1, sy1), fill=(0, 94, 184, 255), outline=WALL, width=5, radius=16)
    c.rect((sx0 + 24, sy0 + 22, sx0 + 116, sy1 - 22), fill=WHITE, radius=12)
    c.text((sx0 + 70, (sy0 + sy1) / 2 + 2), "H", 74, fill=(0, 94, 184, 255))
    c.text((sx0 + 145, sy0 + 44), "A&E", 50, anchor="lm")
    c.text((sx0 + 145, sy0 + 98), "Emergency Department", 36, font=FONT_R, anchor="lm")


def main(out):
    c = Canvas()

    # ---- floors -------------------------------------------------------
    with c.layer() as L:
        # corridor joining the rooms, running out to the exit
        c.rect((870, 500, 3316, 900), fill=CORRIDOR, d=L.d)
    tiled_floor(c, TRIAGE_ROOM, FLOOR_TRIAGE, radius=10)
    tiled_floor(c, TRAUMA_ROOM, FLOOR_TRAUMA, radius=10)
    tiled_floor(c, NONTRAUMA_ROOM, FLOOR_NT, radius=10)

    # ---- walls (with door gaps where the floor lines pass) -------------
    tx0, ty0, tx1, ty1 = TRIAGE_ROOM
    rx0, ry0, rx1, ry1 = TRAUMA_ROOM
    nx0, ny0, nx1, ny1 = NONTRAUMA_ROOM
    walls(c, [
        # triage: entrance in left wall, opening to the corridor on the right
        [(tx0, ENTRANCE[1]), (tx0, ty0), (tx1, ty0)],
        [(tx0, ENTRANCE[3]), (tx0, ty1), (tx1, ty1), (tx1, 822)],
        [(tx1, 755), (tx1, ry1)],
        # trauma room
        [(rx0, ry0), (rx1, ry0), (rx1, ry1), (3312, ry1)],
        [(3270, ry1), (948, ry1)],
        [(886, ry1), (rx0, ry1), (rx0, ry0)],
        # non-trauma room
        [(nx0, ny0), (908, ny0)],
        [(972, ny0), (2556, ny0)],
        [(2622, ny0), (3262, ny0)],
        [(nx0, ny0), (nx0, ny1), (nx1, ny1), (nx1, ny0), (3322, ny0)],
    ])

    # ---- floor wayfinding lines -----------------------------------------
    arrow_path(c, [(203, 205), (238, 205), (238, 480), (278, 480)], GREEN)
    arrow_path(c, [(582, 668), (582, 742)], GREEN)
    # trauma (red) and non-trauma (blue) lines leave triage side by side
    arrow_path(c, [(831, 775), (917, 775), (917, 208), (966, 208)], RED)
    arrow_path(c, [(831, 802), (940, 802), (940, 1060), (976, 1060)], BLUE)
    arrow_path(c, [(1261, 317), (1261, 382)], RED)
    arrow_path(c, [(1560, 420), (2290, 420), (2290, 205), (2616, 205)], RED)
    arrow_path(c, [(2936, 312), (2936, 382)], RED)
    arrow_path(c, [(3280, 420), (3291, 420), (3291, 604)], RED)
    arrow_path(c, [(1271, 1162), (1271, 1237)], BLUE)
    arrow_path(c, [(1570, 1275), (1700, 1275), (1700, 1060), (1846, 1060)], BLUE)
    arrow_path(c, [(2126, 1162), (2126, 1237)], BLUE)
    arrow_path(c, [(2410, 1275), (2590, 1275), (2590, 1060), (2676, 1060)], BLUE)
    arrow_path(c, [(2590, 1046), (2590, 700), (3279, 700)], BLUE, dotted=True)
    arrow_path(c, [(2971, 1162), (2971, 1237)], BLUE)
    arrow_path(c, [(3270, 1275), (3292, 1275), (3292, 798)], BLUE)

    # ---- patient areas -------------------------------------------------
    for k in WAIT:
        waiting_area(c, k)
    for k in BAYS:
        bay_area(c, k)

    # ---- doors and outside ----------------------------------------------
    door(c, ENTRANCE, "Entrance", (85, 203))
    door(c, EXIT, "EXIT", (3420, 648), sign_fill=EXIT_GREEN)
    ae_sign(c)

    # ---- signs and labels -----------------------------------------------
    pathway_sign(c, (1840, 517, 2380, 614), (214, 82, 88, 255), "Trauma Pathway", icon_ecg)
    pathway_sign(c, (1760, 786, 2460, 882), (36, 108, 196, 255), "Non-Trauma Pathway", icon_cross)

    labels = [
        ("Triage Waiting Room", WAIT["triage"], "above"),
        ("Triage Rooms", BAYS["triage"], "below"),
        ("Stabilisation Waiting Area", WAIT["stab"], "above"),
        ("Stabilisation Bays", BAYS["stab"], "below"),
        ("Treatment Waiting Area", WAIT["t_treat"], "above"),
        ("Treatment Cubicles", BAYS["t_treat"], "below"),
        ("Registration Waiting Area", WAIT["reg"], "above"),
        ("Registration Cubicles", BAYS["reg"], "below"),
        ("Examination Waiting Area", WAIT["exam"], "above"),
        ("Examination Bays", BAYS["exam"], "below"),
        ("Treatment Waiting Area", WAIT["nt_treat"], "above"),
        ("Treatment Cubicles", BAYS["nt_treat"], "below"),
    ]
    for s, (x0, y0, x1, y1), where in labels:
        y = y0 - 38 if where == "above" else y1 + 31
        c.text(((x0 + x1) / 2, y), s, 40 if where == "above" else 37)

    c.save(out)


if __name__ == "__main__":
    main(sys.argv[1])
