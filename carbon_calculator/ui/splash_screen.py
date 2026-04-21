"""
ui/splash_screen.py
Cinematic opening: glowing bubble with plant, floating particles,
then bubble expands into Earth.
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk
import math, random, time
from PIL import Image, ImageTk, ImageDraw, ImageFilter

from ui.theme import *
from ui.animations import AnimLoop, ease_in_out, ease_out, lerp_color


class Particle:
    def __init__(self, w, h):
        self.reset(w, h)

    def reset(self, w, h):
        self.x  = random.uniform(0, w)
        self.y  = random.uniform(0, h)
        self.vx = random.uniform(-0.4, 0.4)
        self.vy = random.uniform(-0.8, -0.2)
        self.r  = random.uniform(1.0, 3.5)
        self.alpha = random.uniform(0.3, 1.0)
        self.fade  = random.uniform(0.003, 0.008)
        self.life  = random.uniform(0.4, 1.0)
        self.w = w; self.h = h

    def step(self):
        self.x    += self.vx
        self.y    += self.vy
        self.life -= self.fade
        self.alpha = max(0, self.life)
        if self.life <= 0 or self.y < -10:
            self.reset(self.w, self.h)
            self.y = self.h + 5


class SplashScreen(tk.Canvas):
    N_PARTICLES = 90

    def __init__(self, master, on_complete, **kw):
        super().__init__(master, bg=BG_VOID, highlightthickness=0, **kw)
        self.on_complete  = on_complete
        self._loop        = AnimLoop(self)
        self._phase       = "intro"   # intro → idle → expand → done
        self._frame_t     = 0.0
        self._expand_t    = 0.0
        self._idle_start  = None
        self._bubble_scale = 1.0
        self._opacity      = 0.0
        self._particles    = []
        self._photo_refs   = []
        self.bind("<Configure>", self._on_configure)

    def _on_configure(self, e):
        self.W = e.width; self.H = e.height
        self._particles = [Particle(self.W, self.H) for _ in range(self.N_PARTICLES)]
        if not self._loop._running:
            from ui.assets_loader import get
            self._bubble_img  = get("bubble")
            self._plant_img   = get("plant")
            self._loop.add_callback(self._tick)
            self._loop.start()

    # ── Tick ────────────────────────────────────────────────────────────────────

    def _tick(self):
        self._frame_t += 0.016
        if not hasattr(self, "W"): return
        for p in self._particles: p.step()

        if self._phase == "intro":
            self._opacity = min(1.0, self._opacity + 0.02)
            if self._opacity >= 1.0:
                self._phase      = "idle"
                self._idle_start = time.time()

        elif self._phase == "idle":
            elapsed = time.time() - self._idle_start
            if elapsed >= 3.5:
                self._phase = "expand"

        elif self._phase == "expand":
            self._expand_t = min(1.0, self._expand_t + 0.018)
            self._bubble_scale = 1.0 + ease_in_out(self._expand_t) * 3.5
            self._opacity      = max(0.0, 1.0 - max(0, self._expand_t - 0.6) * 2.5)
            if self._expand_t >= 1.0:
                self._phase = "done"
                self._loop.stop()
                self.after(120, self.on_complete)

        self._draw()

    # ── Draw ────────────────────────────────────────────────────────────────────

    def _draw(self):
        self.delete("all")
        W, H = self.W, self.H

        # ── Background gradient (done with rectangles) ──────────────────────────
        for y in range(0, H, 4):
            t = y / H
            r = int(0   + t * 6)
            g = int(4   + t * 13)
            b = int(8   + t * 32)
            self.create_rectangle(0, y, W, y+4, fill=f"#{r:02x}{g:02x}{b:02x}",
                                  outline="")

        # ── Particles ────────────────────────────────────────────────────────────
        for p in self._particles:
            a  = int(p.alpha * self._opacity * 255)
            if a < 10: continue
            col = f"#{0:02x}{max(0,int(80+p.r*30)):02x}{max(0,int(100+p.r*40)):02x}"
            gr  = int(200 + p.r * 15); gc = int(255 * p.alpha)
            col = f"#{max(0,min(255,gc//4)):02x}{max(0,min(255,gc)):02x}{max(0,min(255,gc//2+80)):02x}"
            self.create_oval(p.x-p.r, p.y-p.r, p.x+p.r, p.y+p.r,
                             fill=col, outline="")

        # ── Horizon glow ─────────────────────────────────────────────────────────
        for i, radius in enumerate([200, 160, 120, 80]):
            a = int(self._opacity * (20 - i*4))
            if a < 2: continue
            self.create_oval(W//2-radius, H-radius*0.6,
                             W//2+radius, H+radius*0.6,
                             fill="", outline=GREEN_PLASMA,
                             width=1)

        # ── Bubble + Plant ───────────────────────────────────────────────────────
        cx, cy = W // 2, H // 2

        pulse   = 1.0 + math.sin(self._frame_t * 1.8) * 0.03
        scale   = self._bubble_scale * pulse * self._opacity
        if scale > 0.05 and hasattr(self, "_bubble_img") and self._bubble_img:
            bs = int(260 * scale)
            if 20 < bs < 1800:
                resized = self._bubble_img.resize((bs, bs), Image.LANCZOS)
                photo   = ImageTk.PhotoImage(resized)
                self._photo_refs = [photo]
                self.create_image(cx, cy, image=photo, anchor="center")

            # Plant inside bubble (only during non-expand)
            if self._expand_t < 0.3 and hasattr(self, "_plant_img"):
                p_scale = min(1.0, self._opacity) * max(0, 1 - self._expand_t/0.3)
                ps = int(80 * self._bubble_scale * pulse * p_scale)
                if ps > 10:
                    pr = self._plant_img.resize((ps, ps), Image.LANCZOS)
                    pp = ImageTk.PhotoImage(pr)
                    self._photo_refs.append(pp)
                    self.create_image(cx, cy + int(ps * 0.1), image=pp, anchor="center")

        # ── Title text ────────────────────────────────────────────────────────────
        if self._phase in ("intro", "idle") and self._opacity > 0.3:
            a_factor = self._opacity
            self.create_text(W//2, H//2 + 165, text="INDIA CARBON TRACKER",
                             fill=GREEN_PLASMA,
                             font=("Courier New", 18, "bold"))
            self.create_text(W//2, H//2 + 192, text="Measure · Understand · Act",
                             fill=TEXT_SILVER,
                             font=("Helvetica", 11, "italic"))

        # ── Expand flash ─────────────────────────────────────────────────────────
        if self._phase == "expand" and self._expand_t > 0.7:
            flash_a = int((self._expand_t - 0.7) / 0.3 * 120)
            self.create_rectangle(0, 0, W, H,
                                  fill=f"#{min(255,flash_a):02x}{min(255,flash_a+20):02x}{min(255,flash_a+10):02x}",
                                  outline="")

    def destroy_clean(self):
        self._loop.stop()
        self.destroy()
