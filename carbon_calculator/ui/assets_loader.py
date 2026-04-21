"""
ui/assets_loader.py
Procedurally generate all visual assets (Earth frames, India map,
background gradients, icons) using PIL + numpy. No internet required.
"""

from __future__ import annotations
import math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from typing import List

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)

# ── Earth texture (360×180) ─────────────────────────────────────────────────────

def _make_earth_texture() -> np.ndarray:
    """Procedurally generate a simple Earth colour texture (360×180, RGB)."""
    H, W = 180, 360
    tex = np.zeros((H, W, 3), np.uint8)

    # Ocean base
    for y in range(H):
        lat = (y / H - 0.5) * 180
        # Depth gradient: deeper at equator
        depth = max(0, 1 - abs(lat) / 90)
        r = int(12  + depth * 15)
        g = int(55  + depth * 30)
        b = int(130 + depth * 25)
        tex[y, :] = [r, g, b]

    # Simplified land masses (lat, lon bounding boxes → approximate)
    land_patches = [
        # (lat_min, lat_max, lon_min, lon_max, r, g, b)
        # Eurasia
        (25, 72, -10, 70,   45, 120, 50),
        (15, 55, 70, 140,   50, 130, 55),
        (50, 75, 0,  80,    45, 105, 40),
        # Africa
        (-35, 38, -18, 52,  60, 130, 55),
        # Americas
        (25, 70, -170, -55, 55, 115, 45),
        (-55, 15, -82, -35, 50, 120, 50),
        # Australia
        (-40, -10, 113, 154, 65, 120, 40),
        # Greenland
        (60, 84, -55, -16, 220, 240, 240),
        # Antarctica
        (-90, -67, -180, 180, 230, 240, 250),
    ]

    def lon_to_x(lon):  return int((lon + 180) / 360 * W) % W
    def lat_to_y(lat):  return int((90 - lat) / 180 * H)

    for (lat1, lat2, lon1, lon2, lr, lg, lb) in land_patches:
        y1, y2 = lat_to_y(lat2), lat_to_y(lat1)
        x1, x2 = lon_to_x(lon1), lon_to_x(lon2)
        y1,y2 = max(0,y1), min(H-1,y2)
        if x1 < x2:
            tex[y1:y2, x1:x2] = [lr, lg, lb]
        else:  # wraps around date line
            tex[y1:y2, x1:] = [lr, lg, lb]
            tex[y1:y2, :x2] = [lr, lg, lb]

    # India highlight (brighter green)
    for y in range(H):
        for x in range(W):
            lat = 90 - y/H*180
            lon = x/W*360 - 180
            if 8 <= lat <= 36 and 68 <= lon <= 98:
                if tex[y, x, 1] > tex[y, x, 2]:  # already land
                    # slight warm tint
                    tex[y, x] = [80, 140, 60]

    # Add slight noise for texture
    rng = np.random.default_rng(42)
    noise = rng.integers(-8, 8, (H, W, 3))
    tex = np.clip(tex.astype(int) + noise, 0, 255).astype(np.uint8)
    return tex


def generate_earth_frames(n_frames: int = 36, size: int = 220,
                           aura_color: str = "#2AFFA6") -> List[Image.Image]:
    """
    Render n_frames of a rotating Earth sphere with atmosphere glow.
    aura_color: emission aura tint (green=low, red=high).
    """
    texture = _make_earth_texture()
    th, tw = texture.shape[:2]
    cx = cy = size // 2
    r  = size // 2 - 18          # sphere radius (leave room for atmosphere)

    # Parse aura colour
    ac = aura_color.lstrip("#")
    ar, ag, ab = int(ac[0:2], 16), int(ac[2:4], 16), int(ac[4:6], 16)

    frames: List[Image.Image] = []

    # Pre-compute pixel grid
    y_idx, x_idx = np.mgrid[0:size, 0:size]
    dx_all = (x_idx - cx).astype(float)
    dy_all = (y_idx - cy).astype(float)
    d_sq   = dx_all**2 + dy_all**2
    sphere_mask = d_sq <= r * r
    atm_mask    = (d_sq <= (r+14)**2) & ~sphere_mask

    dx_m  = dx_all[sphere_mask] / r
    dy_m  = dy_all[sphere_mask] / r
    dz_sq = np.maximum(0, 1 - dx_m**2 - dy_m**2)
    dz_m  = np.sqrt(dz_sq)

    # Lighting direction (upper-left)
    ld = np.array([-0.35, -0.40, 0.85], float)
    ld /= np.linalg.norm(ld)
    nrm = np.column_stack([dx_m, dy_m, dz_m])
    lighting = np.clip(nrm @ ld * 0.75 + 0.30, 0, 1)

    for i in range(n_frames):
        rot = 2 * math.pi * i / n_frames
        img = np.zeros((size, size, 4), np.uint8)

        lon = (np.arctan2(dx_m, dz_m) + rot) % (2 * math.pi)
        lat = np.arcsin(np.clip(dy_m, -1, 1))
        tx  = (lon / (2 * math.pi) * tw).astype(int) % tw
        ty  = np.clip(((lat + math.pi/2) / math.pi * th).astype(int), 0, th-1)

        colors = texture[ty, tx]
        lit    = (colors[:, :3] * lighting[:, np.newaxis]).astype(np.uint8)
        img[sphere_mask] = np.column_stack([lit, np.full(sphere_mask.sum(), 255)])

        # Atmosphere rim glow
        atm_d   = np.sqrt(d_sq[atm_mask])
        t_rim   = np.clip(1 - (atm_d - r) / 14, 0, 1) ** 2
        atm_r   = (ar * t_rim).astype(np.uint8)
        atm_g   = (ag * t_rim).astype(np.uint8)
        atm_b   = (ab * t_rim).astype(np.uint8)
        atm_a   = (180 * t_rim).astype(np.uint8)
        img[atm_mask] = np.column_stack([atm_r, atm_g, atm_b, atm_a])

        pil = Image.fromarray(img, "RGBA")
        # Soft outer glow using blur overlay
        glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse([cx-r-20, cy-r-20, cx+r+20, cy+r+20],
                   fill=(ar, ag, ab, 30))
        glow = glow.filter(ImageFilter.GaussianBlur(10))
        pil = Image.alpha_composite(glow, pil)
        frames.append(pil)

    return frames


# ── India map ───────────────────────────────────────────────────────────────────

# Approximate India outline (lon, lat) — clockwise
INDIA_OUTLINE = [
    (77.8,35.5),(78.4,34.5),(79.2,33.1),(78.8,32.2),(78.4,31.9),
    (79.0,31.4),(81.0,30.8),(81.9,30.3),(84.6,28.6),(85.2,27.9),
    (87.1,27.8),(88.4,27.1),(88.8,26.9),(89.9,26.8),(90.3,26.9),
    (92.9,26.5),(93.8,26.5),(94.6,26.8),(95.1,27.1),(96.0,27.5),
    (96.4,27.4),(96.6,28.0),(95.3,28.2),(94.6,27.0),(93.0,27.5),
    (93.4,26.7),(92.0,25.5),(91.0,25.1),(89.8,25.0),(89.5,23.9),
    (88.9,23.2),(89.0,22.1),(88.6,22.7),(87.5,22.2),(86.9,21.9),
    (85.8,21.1),(84.8,20.4),(83.9,19.4),(82.3,18.6),(80.7,16.9),
    (80.1,16.2),(80.7,13.6),(80.3,13.1),(80.3,11.5),(79.8,10.0),
    (79.2, 9.2),(78.2, 8.7),(77.6, 8.1),(76.9, 8.2),(76.2, 9.5),
    (75.8,11.8),(74.8,14.8),(74.1,13.1),(74.2,17.3),(72.8,19.0),
    (72.6,20.6),(70.2,22.9),(68.7,22.2),(68.1,23.1),(68.7,23.6),
    (71.0,24.0),(72.0,24.3),(73.0,23.5),(72.8,26.0),(70.5,23.6),
    (69.5,22.8),(68.1,23.1),(67.8,26.5),(66.8,28.6),(68.1,28.5),
    (68.9,28.0),(70.6,28.0),(72.4,28.5),(73.5,29.5),(74.3,31.5),
    (74.9,32.5),(75.4,32.8),(76.8,34.1),(77.3,35.1),(77.8,35.5),
]

def generate_india_image(size: int = 400, glow: bool = True) -> Image.Image:
    """Render India map outline on transparent background."""
    # Compute bounding box of outline
    lons = [p[0] for p in INDIA_OUTLINE]
    lats = [p[1] for p in INDIA_OUTLINE]
    lon_min, lon_max = min(lons)-1, max(lons)+1
    lat_min, lat_max = min(lats)-1, max(lats)+1

    margin = 30
    def to_px(lon, lat):
        x = margin + (lon - lon_min) / (lon_max - lon_min) * (size - 2*margin)
        y = margin + (lat_max - lat) / (lat_max - lat_min) * (size - 2*margin)
        return int(x), int(y)

    img  = Image.new("RGBA", (size, size), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    pts  = [to_px(lo, la) for lo, la in INDIA_OUTLINE]

    if glow:
        # Multi-pass glow
        for radius in [18, 12, 6]:
            gimg = Image.new("RGBA", (size, size), (0,0,0,0))
            gd   = ImageDraw.Draw(gimg)
            gd.polygon(pts, fill=(42, 255, 166, 60))
            gd.line(pts + [pts[0]], fill=(42, 255, 166, 200), width=3)
            gimg = gimg.filter(ImageFilter.GaussianBlur(radius))
            img  = Image.alpha_composite(img, gimg)

    # Fill
    draw.polygon(pts, fill=(27, 100, 60, 180))
    # Outline
    draw.line(pts + [pts[0]], fill=(42, 255, 166, 255), width=2)

    # Southern grid highlight
    southern = [p for p in INDIA_OUTLINE if p[1] < 20]
    if southern:
        s_pts = [to_px(lo, la) for lo, la in southern]
        gimg2 = Image.new("RGBA", (size, size), (0,0,0,0))
        gd2   = ImageDraw.Draw(gimg2)
        gd2.polygon(s_pts, fill=(100, 252, 241, 50))
        gimg2 = gimg2.filter(ImageFilter.GaussianBlur(8))
        img   = Image.alpha_composite(img, gimg2)

    return img


# ── Gradient background ─────────────────────────────────────────────────────────

def generate_bg(w: int, h: int, top="#000408", bottom="#0A1628") -> Image.Image:
    img  = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    tr,tg,tb = int(top[1:3],16), int(top[3:5],16), int(top[5:7],16)
    br,bg,bb = int(bottom[1:3],16), int(bottom[3:5],16), int(bottom[5:7],16)
    for y in range(h):
        t = y / h
        r = int(tr + (br-tr)*t); g = int(tg + (bg-tg)*t); b = int(tb + (bb-tb)*t)
        draw.line([(0,y),(w,y)], fill=(r,g,b))
    return img


# ── Bubble / splash ─────────────────────────────────────────────────────────────

def generate_bubble(size: int = 260) -> Image.Image:
    """A glowing translucent sphere."""
    img  = Image.new("RGBA", (size, size), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    cx = cy = size // 2
    r  = size // 2 - 10

    # Outer atmosphere
    for dr in range(30, 0, -1):
        a = int(50 * (1 - dr/30)**2)
        draw.ellipse([cx-r-dr, cy-r-dr, cx+r+dr, cy+r+dr],
                     fill=(42, 255, 166, a))

    # Body
    for dr in range(r, 0, -1):
        t = dr / r
        r_ = int(15 + t * 30)
        g_ = int(40 + t * 80)
        b_ = int(50 + t * 100)
        a_ = int(120 * t)
        draw.ellipse([cx-dr, cy-dr, cx+dr, cy+dr], fill=(r_,g_,b_,a_))

    # Specular highlight
    draw.ellipse([cx-r//3, cy-r//2, cx+r//8, cy-r//8],
                 fill=(180, 255, 230, 60))
    draw.ellipse([cx-r//4, cy-r//2+5, cx+r//12, cy-r//8+5],
                 fill=(220, 255, 250, 40))

    # Rim glow
    img2 = img.filter(ImageFilter.GaussianBlur(6))
    return Image.alpha_composite(img2, img)


def generate_plant_icon(size: int = 80) -> Image.Image:
    """Simple leaf/plant icon."""
    img  = Image.new("RGBA", (size, size), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    cx, cy = size//2, size//2

    # Stem
    draw.line([(cx, cy+size//3), (cx, cy-size//4)],
              fill=(27, 180, 80, 240), width=3)

    # Left leaf
    draw.ellipse([cx-size//3, cy-size//4, cx+2, cy+size//8],
                 fill=(42, 200, 90, 220))
    draw.ellipse([cx-size//3+2, cy-size//4+2, cx, cy+size//8-2],
                 fill=(60, 220, 100, 180))

    # Right leaf
    draw.ellipse([cx-2, cy-size//3, cx+size//3, cy+size//16],
                 fill=(42, 200, 90, 220))
    draw.ellipse([cx, cy-size//3+2, cx+size//3-2, cy+size//16-2],
                 fill=(60, 220, 100, 180))

    # Glow
    g = img.filter(ImageFilter.GaussianBlur(4))
    return Image.alpha_composite(g, img)


# ── Glassmorphism panel ─────────────────────────────────────────────────────────

def generate_glass_panel(w: int, h: int, bg_img: Image.Image,
                          x0: int, y0: int,
                          color=(13, 30, 50), alpha=170,
                          border=(42, 255, 166)) -> Image.Image:
    """
    Crop and blur a region of bg_img, tint it, add border glow.
    Returns RGBA image of the panel.
    """
    # Crop background region
    region = bg_img.crop((x0, y0, x0+w, y0+h)).convert("RGBA")
    region = region.filter(ImageFilter.GaussianBlur(14))

    # Tint overlay
    tint = Image.new("RGBA", (w, h), (*color, alpha))
    panel = Image.alpha_composite(region, tint)

    # Rounded corner mask
    mask = Image.new("L", (w, h), 0)
    md   = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, w-1, h-1], radius=16, fill=255)
    panel.putalpha(mask)

    # Border glow (outer)
    for bw in [8, 5, 2]:
        glow = Image.new("RGBA", (w, h), (0,0,0,0))
        gd   = ImageDraw.Draw(glow)
        gd.rounded_rectangle([bw//2, bw//2, w-bw//2-1, h-bw//2-1],
                              radius=16, outline=(*border, 80//bw), width=1)
        glow = glow.filter(ImageFilter.GaussianBlur(bw))
        panel = Image.alpha_composite(panel, glow)

    # Hard border
    bd = ImageDraw.Draw(panel)
    bd.rounded_rectangle([0, 0, w-1, h-1], radius=16,
                          outline=(*border, 160), width=1)
    return panel


# ── Circular gauge ──────────────────────────────────────────────────────────────

def generate_gauge(size: int, value: float, max_val: float,
                   label: str, unit: str,
                   color: str = "#2AFFA6") -> Image.Image:
    """Render a circular gauge as PIL image."""
    img  = Image.new("RGBA", (size, size), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    cx = cy = size // 2
    outer_r = size // 2 - 6
    inner_r = outer_r - 18

    # Track
    draw.arc([cx-outer_r, cy-outer_r, cx+outer_r, cy+outer_r],
             start=135, end=405, fill=(30,60,50,180), width=18)

    # Filled arc
    pct    = min(1.0, value / max_val) if max_val > 0 else 0
    extent = pct * 270
    cr,cg,cb = int(color[1:3],16), int(color[3:5],16), int(color[5:7],16)
    if extent > 0:
        draw.arc([cx-outer_r, cy-outer_r, cx+outer_r, cy+outer_r],
                 start=135, end=135+extent,
                 fill=(cr, cg, cb, 255), width=18)

    # Glow on arc end
    if extent > 0:
        ang_r = math.radians(135 + extent)
        ex = cx + outer_r * math.cos(ang_r)
        ey = cy + outer_r * math.sin(ang_r)
        for dr in range(12, 0, -1):
            a = int(100 * (1-dr/12)**2)
            draw.ellipse([ex-dr, ey-dr, ex+dr, ey+dr],
                         fill=(cr,cg,cb,a))

    # Value text
    val_str = f"{value:.1f}"
    draw.text((cx, cy-8), val_str, fill=(cr,cg,cb,255),
              font=None, anchor="mm")
    draw.text((cx, cy+12), unit, fill=(180,220,200,200),
              font=None, anchor="mm")
    draw.text((cx, cy+size//2-10), label, fill=(140,190,160,200),
              font=None, anchor="mm")

    return img


# ── Preload all assets ──────────────────────────────────────────────────────────

_cache: dict = {}

def preload(progress_cb=None):
    """Generate and cache all heavy assets. Call once at startup."""
    steps = [
        ("earth_frames", lambda: generate_earth_frames(36, 220)),
        ("earth_frames_red", lambda: generate_earth_frames(36, 220, "#FF4444")),
        ("india_img",    lambda: generate_india_image(400)),
        ("bubble",       lambda: generate_bubble(260)),
        ("plant",        lambda: generate_plant_icon(80)),
    ]
    total = len(steps)
    for i, (key, fn) in enumerate(steps):
        _cache[key] = fn()
        if progress_cb:
            progress_cb((i+1) / total)

def get(key):
    return _cache.get(key)
