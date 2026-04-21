from __future__ import annotations
import tkinter as tk
import math
from PIL import Image, ImageTk, ImageDraw, ImageFilter

from ui.theme import *
from ui.animations import AnimLoop, ease_in_out_cubic

class EarthScreen(tk.Canvas):
    EARTH_SIZE = 240

    def __init__(self, master, on_click, aura_level: float = 0.3, **kw):
        super().__init__(master, bg=BG_VOID, highlightthickness=0, **kw)
        self.on_click   = on_click
        self.aura_level = aura_level
        self._frame_idx = 0
        self._frame_t   = 0.0
        self._opacity   = 0.0
        self._zoom_t    = 0.0
        self._zooming   = False
        self._photos    = []
        self._loop      = AnimLoop(self)
        self.bind("<Configure>", self._on_configure)
        self.bind("<Button-1>",  self._on_click)
        self.bind("<Motion>",    self._on_motion)
        self._hover = False

    def _on_configure(self, e):
        self.W = e.width; self.H = e.height
        from ui.assets_loader import get
        key = "earth_frames_red" if self.aura_level > 0.6 else "earth_frames"
        frames_raw = get(key)
        self._frames = [f.resize((self.EARTH_SIZE, self.EARTH_SIZE), Image.LANCZOS) for f in frames_raw] if frames_raw else []
        if not self._loop._running:
            self._loop.add_callback(self._tick)
            self._loop.start()

    def _on_motion(self, e):
        if not hasattr(self, "W"): return
        cx, cy = self.W//2, self.H//2
        d = math.hypot(e.x - cx, e.y - cy)
        self._hover = d < self.EARTH_SIZE//2 + 20
        self.config(cursor="hand2" if self._hover else "")

    def _on_click(self, e):
        if not hasattr(self, "W"): return
        cx, cy = self.W//2, self.H//2
        d = math.hypot(e.x - cx, e.y - cy)
        if d < self.EARTH_SIZE//2 + 30 and not self._zooming:
            self._zooming = True

    def _tick(self):
        self._frame_t += 0.016
        self._opacity  = min(1.0, self._opacity + 0.015)
        if self._zooming:
            self._zoom_t = min(1.0, self._zoom_t + 0.022)
            if self._zoom_t >= 1.0:
                self._loop.stop()
                self.after(80, self.on_click)
        if getattr(self, "_frames", []):
            self._frame_idx = (self._frame_idx + 0.28) % len(self._frames)
        self._draw()

    def _draw(self):
        self.delete("all")
        if not hasattr(self, "W"): return
        W, H = self.W, self.H
        cx, cy = W // 2, H // 2

        # Space Background
        self.create_rectangle(0, 0, W, H, fill=BG_VOID, outline="")
        if not hasattr(self, "_stars"):
            import random
            self._stars = [(random.randint(0,W), random.randint(0,H)) for _ in range(120)]
        for sx, sy in self._stars:
            self.create_oval(sx-1, sy-1, sx+1, sy+1, fill="#223344", outline="")

        if not getattr(self, "_frames", []): return

        scale = 1.0 + (ease_in_out_cubic(self._zoom_t) * 8.0 if self._zooming else 0)
        es = int(self.EARTH_SIZE * scale)
        if es < 1: return

        # Atmosphere Glow
        aura_col = lerp_aura(self.aura_level)
        for i in range(10, 0, -1):
            self.create_oval(cx-es//2-i*2, cy-es//2-i*2, cx+es//2+i*2, cy+es//2+i*2,
                             fill="", outline=aura_col, width=1)

        # Earth Frame
        fidx = int(self._frame_idx) % len(self._frames)
        frame_img = self._frames[fidx]
        if es != self.EARTH_SIZE:
            frame_img = frame_img.resize((es, es), Image.LANCZOS)
            
        photo = ImageTk.PhotoImage(frame_img)
        self._photos = [photo]
        self.create_image(cx, cy, image=photo, anchor="center")

        # Atmosphere Rim
        self.create_oval(cx-es//2, cy-es//2, cx+es//2, cy+es//2,
                         fill="", outline=CYAN_GLOW, width=1)

def lerp_aura(level: float) -> str:
    level = max(0, min(1, level))
    def p(c): c=c.lstrip("#"); return int(c[0:2],16),int(c[2:4],16),int(c[4:6],16)
    c1, c2 = ("#2AFFA6", "#FFB347") if level < 0.5 else ("#FFB347", "#FF4444")
    t = level * 2 if level < 0.5 else (level - 0.5) * 2
    r1,g1,b1=p(c1); r2,g2,b2=p(c2)
    return f"#{int(r1+(r2-r1)*t):02x}{int(g1+(g2-g1)*t):02x}{int(b1+(b2-b1)*t):02x}"