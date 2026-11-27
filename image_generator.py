# image_generator.py
import asyncio
import io
import math
import random
from functools import lru_cache

import discord
from PIL import Image, ImageDraw, ImageFont

from config import FONT_BOLD, FONT_DISPLAY, FONT_SERIF, FONT_TYPEWRITER

W, H = 1100, 694

BLUE   = (0, 35, 135)
GOLD   = (226, 178, 40)
BLACK  = (12, 12, 16)
WHITE  = (255, 255, 255)

TITLE = "FELLAS BEING IDIOTS"


# ── Fonts (cached) ──
@lru_cache(maxsize=128)
def _font(path: str, size: int):
    for p in (path, FONT_BOLD,
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _display(size): return _font(FONT_DISPLAY, size)
def _type(size):    return _font(FONT_TYPEWRITER, size)
def _serif(size):   return _font(FONT_SERIF, size)


def _fit(text, font_fn, max_w, max_size, min_size=14):
    """Largest font (<= max_size) whose text width fits max_w."""
    tmp = ImageDraw.Draw(Image.new("L", (1, 1)))
    for size in range(max_size, min_size - 1, -2):
        f = font_fn(size)
        b = tmp.textbbox((0, 0), text, font=f)
        if b[2] - b[0] <= max_w:
            return f
    return font_fn(min_size)


def _text(draw, text, font, x, top, fill, align="l"):
    """Draw text so the glyph box's top edge sits at `top` (x = left/centre/right)."""
    b = draw.textbbox((0, 0), text, font=font)
    w = b[2] - b[0]
    if align == "c":
        x = x - w // 2
    elif align == "r":
        x = x - w
    draw.text((x - b[0], top - b[1]), text, font=font, fill=fill)
    return b[3] - b[1]


def _tracked(draw, text, font, cx, top, fill, total_w):
    """Centre text, stretching letter-spacing so it spans total_w."""
    adv = [draw.textlength(c, font=font) for c in text]
    track = (total_w - sum(adv)) / max(len(text) - 1, 1)
    x = cx - total_w / 2
    off = font.getbbox("H")[1]
    for ch, a in zip(text, adv):
        draw.text((x, top - off), ch, font=font, fill=fill)
        x += a + track


def _spaced(draw, text, font, x, y, fill, track=3):
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + track


# ── Guilloche security background (cached) ──
_bg_cache: dict[tuple[int, int], Image.Image] = {}


def _guilloche(w, h):
    """Near-white security paper: grey lattice ribbon (top), soft wave ribbons
    (middle) and a dense blue-teal weave (bottom). Drawn at 2x, then downsampled."""
    k = 2
    W2, H2 = w * k, h * k
    base = Image.new("RGB", (W2, H2), (246, 247, 249))
    ov = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    def line(pts, col, width=2):
        d.line([(x * k, y * k) for x, y in pts], fill=col, width=width)

    xs = list(range(-10, w + 12, 3))

    # 1) lattice ribbon between two wavy envelopes (zigzag mesh)
    def lattice(top_fn, bot_fn, step, col, reach=14):
        for x0 in range(-40, w + 40, step):
            for dx in (-reach, reach):
                d.line([(x0 * k, top_fn(x0) * k), ((x0 + dx) * k, bot_fn(x0 + dx) * k)],
                       fill=col, width=1)
                d.line([(x0 * k, bot_fn(x0) * k), ((x0 + dx) * k, top_fn(x0 + dx) * k)],
                       fill=col, width=1)

    lattice(lambda x: 10 + 7 * math.sin(x / 75),
            lambda x: 100 + 18 * math.sin(x / 95 + 1.0), 9, (140, 140, 160, 235), reach=16)
    # faint hatch behind the seal / centre
    lattice(lambda x: 120 + 10 * math.sin(x / 120 + 2),
            lambda x: 340 + 14 * math.sin(x / 110), 12, (175, 178, 195, 70), reach=9)

    # bottom diamond mesh across the full width
    lattice(lambda x: 440 + 16 * math.sin(x / 85),
            lambda x: 700 + 8 * math.sin(x / 100 + 1), 10, (135, 180, 205, 120), reach=13)

    # 2) smooth pale wave ribbons (outlines)
    for base_y, amp, ph, col in ((395, 22, 0.0, (170, 176, 192, 170)),
                                 (432, 26, 0.5, (170, 176, 192, 150)),
                                 (470, 24, 1.1, (125, 168, 196, 140))):
        for off in (0, 7):
            line([(x, base_y + off + amp * math.sin(x / 120 + ph)) for x in xs],
                 col, 1)

    # 3) dense blue-teal weave: fans of fast sines riding slow waves
    def fan(cy, amp, slow_amp, slow_f, fast_f, n, step, col, ph0=0.0):
        for i in range(n):
            ph = ph0 + i * step
            pts = []
            for x in xs:
                env = 0.55 + 0.45 * math.sin(x / 170 + ph0 + 1.2)
                y = (cy + slow_amp * math.sin(x * slow_f + ph0)
                     + amp * env * math.sin(x * fast_f + ph))
                pts.append((x, y))
            line(pts, col, 1)

    BL = (85, 145, 185, 235)
    fan(575, 40, 48, 1 / 48, 1 / 6, 18, 0.33, BL, 0.0)
    fan(540, 34, 44, 1 / 48, 1 / 7, 14, 0.4, (100, 155, 190, 200), 1.4)
    fan(650, 26, 26, 1 / 42, 1 / 5.5, 14, 0.4, BL, 2.2)
    fan(470, 22, 34, 1 / 55, 1 / 6.5, 10, 0.5, (110, 160, 192, 170), 0.8)

    out = Image.alpha_composite(base.convert("RGBA"), ov)
    return out.resize((w, h), Image.LANCZOS)


def _get_background(w, h):
    key = (w, h)
    if key not in _bg_cache:
        _bg_cache[key] = _guilloche(w, h)
    return _bg_cache[key].copy()


# ── Helpers ──
def _star(draw, cx, cy, r, fill):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.42
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    draw.polygon(pts, fill=fill)


def _arc_text(img, text, cx, cy, radius, font, fill, top=True, gap=2):
    tmp_d = ImageDraw.Draw(Image.new("L", (1, 1)))
    adv = [tmp_d.textlength(c, font=font) + gap for c in text]
    span = sum(adv) / radius
    ang = -math.pi / 2 - span / 2 if top else math.pi / 2 + span / 2
    T = int(font.size * 2)
    for ch, a in zip(text, adv):
        th = ang + a / radius / 2 if top else ang - a / radius / 2
        x, y = cx + radius * math.cos(th), cy + radius * math.sin(th)
        tile = Image.new("RGBA", (T, T), (0, 0, 0, 0))
        ImageDraw.Draw(tile).text((T // 2, T // 2), ch, font=font, fill=fill, anchor="mm")
        deg = math.degrees(th)
        tile = tile.rotate(-(deg + 90) if top else -(deg - 90), resample=Image.BICUBIC)
        img.paste(tile, (int(x - T / 2), int(y - T / 2)), tile)
        ang = ang + a / radius if top else ang - a / radius


def _leaf(d, x, y, ang, length, width, fill, outline):
    pts = []
    for i in range(0, 21):
        t = i / 20
        pts.append((t * length, width / 2 * math.sin(math.pi * t) ** 0.8))
    for i in range(20, -1, -1):
        t = i / 20
        pts.append((t * length, -width / 2 * math.sin(math.pi * t) ** 0.8))
    ca, sa = math.cos(ang), math.sin(ang)
    d.polygon([(x + px * ca - py * sa, y + px * sa + py * ca) for px, py in pts],
              fill=fill, outline=outline)


def _laurel(d, mirror):
    def bez(t):
        p0, p1, p2 = (268, 420), (205, 350), (262, 258)
        return ((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1])
    m = (lambda x: 700 - x) if mirror else (lambda x: x)
    stem = [(m(bez(i / 30)[0]), bez(i / 30)[1]) for i in range(31)]
    d.line(stem, fill=(30, 100, 50), width=4)
    greens = [((52, 150, 78), (20, 80, 40)), ((34, 112, 58), (16, 70, 36))]
    for n, t in enumerate([0.08, 0.2, 0.32, 0.45, 0.58, 0.71, 0.84]):
        x, y = bez(t)
        x2, y2 = bez(t + 0.02)
        tang = math.atan2(y2 - y, x2 - x)
        for side in (-1, 1):
            a = tang + side * 0.72
            if mirror:
                a = math.pi - a
            f, o = greens[(n + (side > 0)) % 2]
            _leaf(d, m(x), y, a, 58, 26, f, o)
    x, y = bez(1.0)
    tang = math.atan2(bez(1.0)[1] - bez(0.97)[1], bez(1.0)[0] - bez(0.97)[0])
    a = math.pi - tang if mirror else tang
    _leaf(d, m(x), y, a, 54, 24, greens[0][0], greens[0][1])


@lru_cache(maxsize=1)
def _build_seal(size: int = 270) -> Image.Image:
    """Original emblem: gold spiked rim, navy disc, ring text, 13 stars,
    striped shield with scales, laurels and a motto banner."""
    k = 2
    S = 700 * k
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = 350 * k

    def P(r, a):
        return (c + r * k * math.cos(a), c + r * k * math.sin(a))

    # spiked rim: back row (darker) then front row, each spike two-toned
    for n, rows in ((22, (318, 282, (196, 142, 12), (232, 178, 24), 0.5)),
                    (22, (350, 300, (222, 168, 14), (255, 218, 52), 0.0))):
        tip, base, dark, light, off = rows
        for i in range(n):
            a = (i + off) * 2 * math.pi / n
            half = math.pi / n
            tp, bl, br, mid = P(tip, a), P(base, a - half), P(base, a + half), P(base - 2, a)
            d.polygon([tp, bl, mid], fill=light)
            d.polygon([tp, mid, br], fill=dark)

    d.ellipse([c - 312 * k, c - 312 * k, c + 312 * k, c + 312 * k], fill=(244, 200, 40))
    d.ellipse([c - 302 * k, c - 302 * k, c + 302 * k, c + 302 * k], fill=(18, 56, 145))
    for r, w in ((290, 5), (226, 5)):
        d.ellipse([c - r * k, c - r * k, c + r * k, c + r * k],
                  outline=(244, 204, 50), width=w * k)

    # ring text
    f = ImageFont.truetype(FONT_SERIF, 54 * k)
    _arc_text(img, "DEPARTMENT OF IDIOCY", c, c, 258 * k, f, WHITE, top=True, gap=5 * k)
    _arc_text(img, "FELLAS BEING IDIOTS", c, c, 258 * k, f, WHITE, top=False, gap=5 * k)

    # 13 stars
    for i in range(13):
        a = -math.pi / 2 + i * 2 * math.pi / 13
        x, y = P(198, a)
        _star(d, x, y, 24 * k, (252, 212, 46))

    # laurels
    big = Image.new("RGBA", (700, 700), (0, 0, 0, 0))
    bd = ImageDraw.Draw(big)
    _laurel(bd, False)
    _laurel(bd, True)

    # shield (body with stripes, gold chief, scales)
    body = [(282, 272), (418, 272), (418, 372), (350, 416), (282, 372)]
    mask = Image.new("L", (700, 700), 0)
    ImageDraw.Draw(mask).polygon(body, fill=255)
    stripes = Image.new("RGBA", (700, 700), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stripes)
    sw = 136 / 5
    for i in range(5):
        col = (206, 22, 62) if i % 2 == 0 else (250, 250, 250)
        sd.rectangle([282 + i * sw, 260, 282 + (i + 1) * sw, 420], fill=col)
    big.paste(stripes, (0, 0), mask)
    bd.polygon(body, outline=(235, 235, 235))
    bd.line(body + [body[0]], fill=(235, 235, 235), width=3)
    bd.polygon([(292, 230), (408, 230), (418, 244), (418, 274), (282, 274), (282, 244)],
               fill=(248, 200, 40), outline=(235, 235, 235))
    navy = (20, 50, 120)
    bd.line([(350, 238), (350, 262)], fill=navy, width=4)
    bd.ellipse([345, 233, 355, 243], outline=navy, width=3)
    bd.line([(306, 250), (394, 250)], fill=navy, width=4)
    for sx in (312, 388):
        bd.line([(sx, 250), (sx - 11, 266)], fill=navy, width=2)
        bd.line([(sx, 250), (sx + 11, 266)], fill=navy, width=2)
        bd.pieslice([sx - 12, 254, sx + 12, 278], 0, 180, fill=navy)

    # motto banner
    paper, edge = (251, 249, 241), (140, 140, 140)
    def quad(pts, text, ang, fx, fy, fs):
        bd.polygon(pts, fill=paper, outline=edge)
        t = Image.new("RGBA", (260, 70), (0, 0, 0, 0))
        ImageDraw.Draw(t).text((130, 35), text, font=ImageFont.truetype(FONT_SERIF, fs),
                               fill=(30, 30, 50), anchor="mm")
        t = t.rotate(ang, resample=Image.BICUBIC, expand=True)
        big.paste(t, (int(fx - t.width / 2), int(fy - t.height / 2)), t)
    quad([(206, 412), (318, 434), (322, 482), (214, 458)], "FIDELITY", -10.5, 258, 448, 18)
    quad([(494, 412), (382, 434), (378, 482), (486, 458)], "INTEGRITY", 10.5, 442, 448, 18)
    quad([(306, 448), (394, 448), (396, 492), (304, 492)], "BRAVERY", 0, 350, 470, 18)

    base = img.resize((size, size), Image.LANCZOS)
    top = big.resize((size, size), Image.LANCZOS)
    return Image.alpha_composite(base, top)


def _paste_seal(card, cx, cy, size=270):
    seal = _build_seal(size)
    card.paste(seal, (cx - size // 2, cy - size // 2), seal)


def _draw_barcode(draw, x, y, w, h, code):
    rng = random.Random(code)
    cur = x
    while cur < x + w:
        bw = rng.choice([2, 2, 3, 3, 4, 5])
        bw = min(bw, x + w - cur)
        draw.rectangle([cur, y, cur + bw - 1, y + h], fill=BLACK)
        cur += bw + rng.choice([2, 3, 3, 4])


# ── Synchronous renderer (runs in thread) ──
def _render_card(avatar_bytes, logo_bytes, guild_name, display_name, code, member_id):
    avatar = (Image.open(io.BytesIO(avatar_bytes)).convert("RGB")
              if avatar_bytes else Image.new("RGB", (512, 512), (120, 130, 150)))

    card = _get_background(W, H)
    d = ImageDraw.Draw(card)

    # Title (full width, heavy condensed)
    _tracked(d, TITLE, _display(100), W // 2, 20, BLUE, 940)

    # Big acronym
    _text(d, "FBI", _display(288), 455, 132, BLUE, "c")

    # Seal
    _paste_seal(card, 160, 268)

    # Photo: blue frame, white mat
    fx0, fy0, fx1, fy1 = 648, 118, 958, 494
    d.rectangle([fx0, fy0, fx1, fy1], fill=BLUE)
    d.rectangle([fx0 + 10, fy0 + 10, fx1 - 10, fy1 - 10], fill=WHITE)
    pw, ph = fx1 - fx0 - 36, fy1 - fy0 - 36
    ar = avatar.width / avatar.height
    if ar > pw / ph:
        nh, nw = ph, int(ph * ar)
    else:
        nw, nh = pw, int(pw / ar)
    photo = avatar.resize((nw, nh), Image.LANCZOS).crop(
        ((nw - pw) // 2, (nh - ph) // 2, (nw - pw) // 2 + pw, (nh - ph) // 2 + ph))
    card.paste(photo, (fx0 + 18, fy0 + 18))

    # Vertical member code (reads top-to-bottom)
    f_v = _fit(code, _display, 210, 40)
    tb = d.textbbox((0, 0), code, font=f_v)
    tile = Image.new("RGBA", (tb[2] - tb[0] + 4, tb[3] - tb[1] + 4), (0, 0, 0, 0))
    ImageDraw.Draw(tile).text((2 - tb[0], 2 - tb[1]), code, font=f_v, fill=BLACK)
    tile = tile.rotate(-90, expand=True)
    card.paste(tile, (1000 - tile.width // 2, 300 - tile.height // 2), tile)

    # Rank + name
    col_w = fx1 - fx0 + 10
    cx = (fx0 + fx1) // 2
    _text(d, "SPECIAL AGENT", _fit("SPECIAL AGENT", _display, col_w, 70), cx, 508, BLACK, "c")
    name = display_name.upper()
    _text(d, name, _fit(name, _display, col_w, 70, 22), cx, 578, BLACK, "c")

    # Certify text (typewriter, wide tracking)
    f_c = _type(19)
    for i, line in enumerate(("THIS IS TO CERTIFY THAT THE HOLDER",
                              "IS AN OFFICIAL MEMBER OF THE",
                              "FELLAS BEING IDIOTS")):
        _spaced(d, line, f_c, 40, 408 + i * 47, BLACK, track=4)

    # Barcode + code
    _draw_barcode(d, 40, 548, 480, 68, code)
    _spaced(d, code, _type(22), 40, 624, BLACK, track=3)

    # Rounded corners
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1], radius=34, fill=255)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.paste(card, (0, 0), mask)

    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ── Async entry point ──
async def generate_id_card(member: discord.Member, code: str) -> discord.File:
    guild = member.guild

    try:
        avatar_bytes = await member.display_avatar.with_size(512).read()
    except Exception:
        avatar_bytes = None

    logo_bytes = None
    if guild.icon is not None:
        try:
            logo_bytes = await guild.icon.with_size(512).read()
        except Exception:
            logo_bytes = None

    png = await asyncio.to_thread(
        _render_card, avatar_bytes, logo_bytes,
        guild.name, member.display_name, code, member.id,
    )
    return discord.File(fp=io.BytesIO(png), filename=f"id_card_{member.id}.png")
