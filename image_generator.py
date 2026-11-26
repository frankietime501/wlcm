# image_generator.py
import asyncio
import hashlib
import io
import math
import random
from functools import lru_cache

import discord
from PIL import Image, ImageDraw, ImageFont

from config import FONT_BOLD, FONT_REGULAR

W, H = 1100, 680

NAVY      = (22, 42, 78)
NAVY_MID  = (40, 65, 115)
BG_CREAM  = (248, 246, 240)
TEXT_DARK = (30, 30, 40)
WHITE     = (255, 255, 255)


# ── Fonts (cached) ──
@lru_cache(maxsize=128)
def _load_font(path: str, size: int):
    for p in (path,
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


@lru_cache(maxsize=32)
def _load_serif(size: int):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return _load_font(FONT_BOLD, size)


# ── Guilloche background (cached) ──
_bg_cache: dict[tuple[int, int], Image.Image] = {}


def _guilloche_background(w: int, h: int) -> Image.Image:
    base = Image.new("RGB", (w, h), BG_CREAM)
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    for spacing in range(-20, h + 20, 16):
        pts = []
        for x in range(0, w, 2):
            y = spacing + 9 * math.sin(x / 45 + spacing / 22)
            if -5 <= y <= h + 5:
                pts.append((x, int(y)))
        if len(pts) > 1:
            d.line(pts, fill=(160, 170, 190, 45), width=1)

    for spacing in range(-w, w + h, 22):
        pts = []
        for x in range(0, w, 2):
            y = (spacing - x * 0.5) + 7 * math.sin(x / 55 + spacing / 30)
            if -5 <= y <= h + 5:
                pts.append((x, int(y)))
        if len(pts) > 1:
            d.line(pts, fill=(150, 160, 185, 30), width=1)

    return Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")


def _get_background(w: int, h: int) -> Image.Image:
    key = (w, h)
    if key not in _bg_cache:
        _bg_cache[key] = _guilloche_background(w, h)
    return _bg_cache[key].copy()


# ── Helpers ──
def _circle_mask(size: int):
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).ellipse((0, 0, size - 1, size - 1), fill=255)
    return m


def _to_circle(img: Image.Image, size: int) -> Image.Image:
    img = img.convert("RGBA").resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), _circle_mask(size))
    return out


def _code_seed(code: str) -> int:
    return int(hashlib.md5(code.encode()).hexdigest()[:8], 16)


def _draw_barcode(canvas: Image.Image, x: int, y: int, w: int, h: int, seed: int):
    rng = random.Random(seed)
    d = ImageDraw.Draw(canvas)
    cur = x
    while cur < x + w:
        bw = rng.choice([1, 2, 2, 3, 3, 4])
        if cur + bw > x + w:
            bw = x + w - cur
        if rng.random() > 0.35:
            d.rectangle([cur, y, cur + bw - 1, y + h], fill=(10, 10, 15))
        cur += bw + rng.choice([1, 2])
    d.rectangle([x, y, x + w, y + h], outline=(80, 80, 90), width=1)


def _draw_vertical_text(canvas, text, center_x, center_y, font, fill, gap=1):
    tiles = []
    for ch in text:
        tmp = Image.new("RGBA", (1, 1))
        bbox = ImageDraw.Draw(tmp).textbbox((0, 0), ch, font=font)
        cw, ch_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tile = Image.new("RGBA", (max(cw, 4), ch_h + 4), (0, 0, 0, 0))
        ImageDraw.Draw(tile).text((0 - bbox[0], 2 - bbox[1]), ch, font=font, fill=fill)
        tiles.append(tile)
    total_h = sum(t.height for t in tiles) + gap * (len(tiles) - 1)
    y = center_y - total_h // 2
    for t in tiles:
        canvas.paste(t, (center_x - t.width // 2, y), t)
        y += t.height + gap


def _wrap_text(text, font, max_width, draw):
    lines, current = [], ""
    for word in text.split():
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit_name(name, max_width, draw, base_size=32, min_size=13):
    size = base_size
    while size > min_size:
        font = _load_font(FONT_BOLD, size)
        bbox = draw.textbbox((0, 0), name, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return font, bbox
        size -= 1
    font = _load_font(FONT_BOLD, min_size)
    return font, draw.textbbox((0, 0), name, font=font)


def _fallback_logo(guild_name: str) -> Image.Image:
    img = Image.new("RGB", (512, 512), (40, 55, 90))
    d = ImageDraw.Draw(img)
    initial = (guild_name[:1] or "S").upper()
    font = _load_serif(280)
    bbox = d.textbbox((0, 0), initial, font=font)
    d.text((256 - (bbox[2] - bbox[0]) // 2,
            256 - (bbox[3] - bbox[1]) // 2 - bbox[1]), initial, font=font, fill=WHITE)
    return img


def _draw_seal(card, server_logo, cx, cy, radius, guild_name):
    draw = ImageDraw.Draw(card)
    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], outline=NAVY, width=3)
    draw.ellipse([cx - radius + 3, cy - radius + 3, cx + radius - 3, cy + radius - 3], outline=NAVY, width=1)
    inner = radius - 24
    draw.ellipse([cx - inner, cy - inner, cx + inner, cy + inner], outline=NAVY, width=2)
    inner2 = inner - 4
    draw.ellipse([cx - inner2, cy - inner2, cx + inner2, cy + inner2], outline=NAVY, width=1)

    ring_text = (guild_name.upper()[:26] + "   •   ")[:34]
    font_ring = _load_font(FONT_BOLD, 12)
    n = len(ring_text)
    tr = radius - 13
    for i, ch in enumerate(ring_text):
        angle = -math.pi / 2 + (i / n) * 2 * math.pi
        chx = cx + tr * math.cos(angle)
        chy = cy + tr * math.sin(angle)
        tmp = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
        ImageDraw.Draw(tmp).text((20, 20), ch, font=font_ring, fill=NAVY, anchor="mm")
        rot = math.degrees(angle) + 90
        rotated = tmp.rotate(-rot, resample=Image.BICUBIC)
        card.paste(rotated, (int(chx - 20), int(chy - 20)), rotated)

    logo_size = inner2 * 2 - 8
    logo_c = _to_circle(server_logo, logo_size)
    card.paste(logo_c, (cx - logo_size // 2, cy - logo_size // 2), logo_c)


# ── Synchronous renderer (runs in thread) ──
def _render_card(avatar_bytes: bytes | None, logo_bytes: bytes | None,
                 guild_name: str, display_name: str, code: str,
                 member_id: int) -> bytes:
    avatar_img = (Image.open(io.BytesIO(avatar_bytes)).convert("RGB")
                  if avatar_bytes else Image.new("RGB", (512, 512), (120, 120, 130)))
    server_logo = (Image.open(io.BytesIO(logo_bytes)).convert("RGB")
                   if logo_bytes else _fallback_logo(guild_name))

    card = _get_background(W, H).convert("RGBA")
    draw = ImageDraw.Draw(card)

    draw.rectangle([12, 12, W - 12, H - 12], outline=NAVY, width=3)
    draw.rectangle([20, 20, W - 20, H - 20], outline=NAVY, width=1)
    for (x, y, dx, dy) in [(12, 12, 1, 1), (W - 12, 12, -1, 1),
                            (12, H - 12, 1, -1), (W - 12, H - 12, -1, -1)]:
        draw.line([(x, y), (x + 40 * dx, y)], fill=NAVY, width=4)
        draw.line([(x, y), (x, y + 40 * dy)], fill=NAVY, width=4)

    f_header = _load_font(FONT_BOLD, 28)
    f_sub    = _load_font(FONT_BOLD, 14)
    f_sa     = _load_font(FONT_BOLD, 22)
    f_cert   = _load_font(FONT_REGULAR, 12)
    f_code   = _load_font(FONT_BOLD, 20)
    f_vert   = _load_font(FONT_BOLD, 15)
    f_tiny   = _load_font(FONT_REGULAR, 10)

    # Header
    header = "FELLAS BEING IDIOTS"
    bbox = draw.textbbox((0, 0), header, font=f_header)
    draw.text(((W - (bbox[2] - bbox[0])) // 2, 32), header, font=f_header, fill=NAVY)
    sub = "FELLAS BEING IDIOTS DISCORD COMMUNITY"
    bbox = draw.textbbox((0, 0), sub, font=f_sub)
    draw.text(((W - (bbox[2] - bbox[0])) // 2, 68), sub, font=f_sub, fill=NAVY_MID)
    draw.line([(40, 96), (W - 40, 96)], fill=NAVY, width=2)
    draw.line([(40, 100), (W - 40, 100)], fill=NAVY, width=1)

    # Large FBI
    f_letters = _load_serif(200)
    bbox = draw.textbbox((0, 0), "FBI", font=f_letters)
    lw, lh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    layer = Image.new("RGBA", (lw + 20, lh + 20), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((10 - bbox[0], 10 - bbox[1]), "FBI",
                               font=f_letters, fill=(*NAVY, 230))
    card.paste(layer, (400 - lw // 2, 285 - lh // 2), layer)

    # Seal
    _draw_seal(card, server_logo, cx=155, cy=310, radius=95, guild_name=guild_name)
    cap = "FIELD OFFICE"
    bbox = draw.textbbox((0, 0), cap, font=f_tiny)
    draw.text((155 - (bbox[2] - bbox[0]) // 2, 415), cap, font=f_tiny, fill=NAVY_MID)

    # Photo
    px, py, pw, ph = 780, 128, 210, 250
    draw.rectangle([px - 6, py - 6, px + pw + 6, py + ph + 6], outline=NAVY, width=4)
    draw.rectangle([px - 2, py - 2, px + pw + 2, py + ph + 2], outline=NAVY_MID, width=1)
    ar = avatar_img.width / avatar_img.height
    if ar > pw / ph:
        new_h = ph
        new_w = int(ph * ar)
        photo = avatar_img.resize((new_w, new_h), Image.LANCZOS).crop(
            ((new_w - pw) // 2, 0, (new_w - pw) // 2 + pw, ph))
    else:
        new_w = pw
        new_h = int(pw / ar)
        photo = avatar_img.resize((new_w, new_h), Image.LANCZOS).crop(
            (0, (new_h - ph) // 2, pw, (new_h - ph) // 2 + ph))
    card.paste(photo, (px, py))

    # Name
    pcx = px + pw // 2
    draw.text((pcx, py + ph + 22), "SPECIAL AGENT", font=f_sa, fill=NAVY, anchor="mm")
    name = display_name.upper()
    name_font, nb = _fit_name(name, pw + 40, draw)
    nw = nb[2] - nb[0]
    draw.text((pcx - nw // 2, py + ph + 44), name, font=name_font, fill=NAVY)
    draw.line([(pcx - nw // 2, py + ph + 52 + nb[3]), (pcx + nw // 2, py + ph + 52 + nb[3])],
              fill=NAVY, width=1)

    # Certification
    cert = ("THIS IS TO CERTIFY THAT THE HOLDER IS AN OFFICIAL MEMBER "
            "OF THE FELLAS BEING IDIOTS DISCORD COMMUNITY.")
    wrapped = _wrap_text(cert, f_cert, 640, draw)
    draw.text((60, 442), "CERTIFICATION", font=_load_font(FONT_BOLD, 10), fill=NAVY)
    for i, line in enumerate(wrapped):
        draw.text((60, 460 + i * 17), line, font=f_cert, fill=TEXT_DARK)
    sy = 460 + len(wrapped) * 17 + 30
    draw.line([(60, sy), (280, sy)], fill=NAVY, width=1)
    draw.text((60, sy + 4), "DIRECTOR, FELLAS BEING IDIOTS", font=f_tiny, fill=NAVY_MID)

    # Vertical code + barcode
    _draw_vertical_text(card, code, W - 42, 310, f_vert, NAVY, gap=1)
    bc_x, bc_y, bc_w, bc_h = 775, 535, 220, 55
    draw.text((bc_x, bc_y - 16), "MEMBER ID", font=_load_font(FONT_BOLD, 10), fill=NAVY)
    _draw_barcode(card, bc_x, bc_y, bc_w, bc_h, _code_seed(code))
    bbox = draw.textbbox((0, 0), code, font=f_code)
    draw.text((bc_x + bc_w // 2 - (bbox[2] - bbox[0]) // 2, bc_y + bc_h + 8),
              code, font=f_code, fill=NAVY)

    # Footer
    draw.line([(40, H - 55), (W - 40, H - 55)], fill=NAVY, width=1)
    disc = "FICTIONAL DISCORD COMMUNITY PARODY CARD  •  NOT A GOVERNMENT CREDENTIAL"
    bbox = draw.textbbox((0, 0), disc, font=f_tiny)
    draw.text(((W - (bbox[2] - bbox[0])) // 2, H - 40), disc, font=f_tiny, fill=NAVY_MID)

    buf = io.BytesIO()
    card.convert("RGB").save(buf, format="PNG", optimize=True)
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