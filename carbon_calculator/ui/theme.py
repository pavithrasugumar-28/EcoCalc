"""ui/theme.py — Cinematic dark-green design system."""

# ── Backgrounds ────────────────────────────────────────────────────────────────
BG_VOID      = "#000408"      # absolute void
BG_DEEP      = "#060D18"      # deep space
BG_SPACE     = "#0A1628"      # space blue
BG_OCEAN     = "#0D2137"      # deep ocean
BG_CARD      = "#0F1F30"      # card surface

# ── Greens ─────────────────────────────────────────────────────────────────────
GREEN_PLASMA  = "#2AFFA6"     # primary glow / accent
GREEN_ECO     = "#1DB954"     # eco mid
GREEN_FOREST  = "#0B3D2E"     # deep forest
GREEN_LEAF    = "#27AE60"     # leaf
GREEN_PALE    = "#A8F0C6"     # pale text accent

# ── Blues & Cyans ───────────────────────────────────────────────────────────────
CYAN_GLOW     = "#66FCF1"     # atmosphere
CYAN_MID      = "#45B7D1"     # mid
BLUE_DEEP     = "#0A2540"     # panel bg
BLUE_NIGHT    = "#132238"     # slightly lighter

# ── Danger / Warm ───────────────────────────────────────────────────────────────
RED_AURA      = "#FF4444"     # high emission
AMBER_WARN    = "#FFB347"     # mid emission
GOLD          = "#FFD700"     # achievements

# ── Text ────────────────────────────────────────────────────────────────────────
TEXT_WHITE    = "#F0FFF8"     # primary text
TEXT_SILVER   = "#B0C4C0"     # secondary text
TEXT_DIM      = "#607070"     # disabled/hint
TEXT_GLOW     = "#2AFFA6"     # highlighted

# ── Borders & Dividers ──────────────────────────────────────────────────────────
BORDER_GLOW   = "#2AFFA6"
BORDER_DIM    = "#1A3040"
BORDER_MID    = "#1E4060"

# ── Typography ──────────────────────────────────────────────────────────────────
FONT_DISPLAY  = ("Courier New", 28, "bold")       # hero numbers
FONT_TITLE    = ("Courier New", 18, "bold")
FONT_HEADING  = ("Helvetica", 14, "bold")
FONT_BODY     = ("Helvetica", 11)
FONT_SMALL    = ("Helvetica", 9)
FONT_TINY     = ("Helvetica", 8)
FONT_MONO     = ("Courier New", 11)
FONT_MONO_SM  = ("Courier New", 9)
FONT_LABEL    = ("Helvetica", 10)

# ── Sizes ───────────────────────────────────────────────────────────────────────
WIN_W = 1200
WIN_H = 780
PADDING = 20
RADIUS = 12

# ── Category colours ────────────────────────────────────────────────────────────
CATEGORY_PALETTE = {
    "Transportation":   "#1E88E5",
    "Household Energy": "#FFB300",
    "Food":             "#43A047",
    "Water Usage":      "#00ACC1",
    "Waste Management": "#8E24AA",
    "Purchases":        "#E53935",
    "Carbon Offset":    "#2AFFA6",
}

def cat_color(cat: str) -> str:
    return CATEGORY_PALETTE.get(cat, "#607D8B")

# ── India average baseline ───────────────────────────────────────────────────────
INDIA_AVG_ANNUAL_KG = 1900.0       # ~1.9 tonnes CO₂/year/person
INDIA_AVG_DAILY_KG  = INDIA_AVG_ANNUAL_KG / 365   # ~5.2 kg/day
