# 🌿 India Carbon Tracker — Cinematic Edition

A fully offline carbon emission calculator with cinematic UI.

## Quick Start

```bash
cd carbon_calculator
pip install pillow matplotlib numpy --break-system-packages
python3 app.py
```

**Demo login:** `demo` / `demo123`

## Cinematic Screen Flow

```
Loading Screen → Splash (Bubble+Plant) → Earth (click) → India Map (click) → Login → Dashboard
```

## Features

### Splash Screen
- Glowing bubble with plant inside, floating particles
- Auto-transitions after 3.5 seconds with flash expansion

### Earth Screen
- 36-frame procedurally rendered rotating Earth
- Carbon Aura ring: green (low) → amber → red (high)
- Click anywhere on Earth to zoom into India

### India Map Screen
- Pulsing glow outline of India with lat/lon grid
- Click to proceed to login

### Login / Register
- Glassmorphism panel with animated particle background
- Username / Password with animated focus states
- Register with display name, city, grid region

### Dashboard (Mission Control)
- **Animated circular gauge** — today's CO₂ with smooth fill animation
- **4 stat cards** — Today / Week / vs India avg / Year projection
- **7-day bar chart** — colour coded vs target (green/amber/red)
- **Category pie chart** — breakdown by activity type
- **Activity log table** — colour coded by emission severity
- **Biggest Win card** — top recommendation with year savings + tree count
- **Eco Tips + Offset** — dynamic tips and tree offset calculator
- **Carbon Aura** — affects Earth glow on next visit
- Auto-refreshes every 8 seconds
- Export to CSV

### Activity Logger
- **Searchable activity dropdown** — type to filter 210 activities
- **Live CO₂ counter** — animated number that counts up
- **Year projection** — shows daily → annual impact vs India average
- **Recommendations** — greener alternatives with year savings
- **Recurring flag** — mark activities as daily habits
- **Daily total bar** — shows progress toward target

### Profile Settings
- Display name, city, grid region
- Custom daily CO₂ target

## Architecture

```
app.py                      ← Main controller / screen router
db/setup.py                 ← SQLite schema, auth (SHA-256)
engine/emission_calculator.py ← CO₂ = quantity × factor, region-aware
recommendation/rule_engine.py ← Sustainable alternatives + tips
ui/
  theme.py                  ← Design system (colours, fonts)
  animations.py             ← Tween engine, AnimLoop (60fps)
  assets_loader.py          ← Procedural Earth/India/Bubble generation
  splash_screen.py          ← Animated bubble intro
  earth_screen.py           ← Rotating Earth with aura
  india_screen.py           ← India map
  login_screen.py           ← Glassmorphism login/register
  dashboard_screen.py       ← Mission control dashboard
  activity_form.py          ← Searchable activity logger
```

## Database

SQLite — `india_carbon_emissions.db`
- 210 activities across 6 categories
- 302 emission factors (region-aware for electricity)
- 14 sustainable alternatives
- 205 sustainability tips
- Users, logs, goals tables

