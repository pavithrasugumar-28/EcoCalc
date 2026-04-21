from __future__ import annotations
import tkinter as tk
import math
from PIL import Image, ImageTk, ImageFilter
from ui.theme import *
from ui.animations import AnimLoop

class IndiaScreen(tk.Canvas):
    def __init__(self, master, on_click, **kw):
        super().__init__(master, bg=BG_VOID, highlightthickness=0, **kw)
        self.on_click  = on_click
        self._opacity  = 0.0
        self._pulse_t  = 0.0
        self._clicked  = False
        self._fade_out = 0.0
        self._photos   = []
        self._loop     = AnimLoop(self)
        self.bind("<Configure>",  self._on_configure)
        self.bind("<Button-1>",   self._on_click)
        self.bind("<Motion>",     self._on_motion)
        self._hover = False

    def _on_configure(self, e):
        self.W = e.width; self.H = e.height
        from ui.assets_loader import get
        raw = get("india_img")
        target_h = int(self.H * 0.72)
        ratio = target_h / raw.height
        self._iw, self._ih = int(raw.width * ratio), target_h
        self._india_img = raw.resize((self._iw, self._ih), Image.LANCZOS)
        if not self._loop._running:
            self._loop.add_callback(self._tick)
            self._loop.start()

    def _on_motion(self, e):
        if not hasattr(self, "W"): return
        cx, cy = self.W//2, self.H//2 - 20
        d  = math.hypot(e.x - cx, e.y - cy)
        self._hover = d < min(self._iw, self._ih)//2
        self.config(cursor="hand2" if self._hover else "")

    def _on_click(self, e):
        if not self._clicked and self._opacity > 0.7:
            self._clicked = True

    def _tick(self):
        self._pulse_t += 0.016
        self._opacity  = min(1.0, self._opacity + 0.018)
        if self._clicked:
            self._fade_out = min(1.0, self._fade_out + 0.04)
            if self._fade_out >= 1.0:
                self._loop.stop()
                self.after(50, self.on_click)
        self._draw()

    def _draw(self):
        self.delete("all")
        if not hasattr(self,"W") or not hasattr(self,"_india_img"): return
        W, H, cx, cy = self.W, self.H, self.W // 2, self.H // 2 - 20

        # Background
        self.create_rectangle(0, 0, W, H, fill=BG_VOID, outline="")

        # Atmosphere Glow
        pulse = math.sin(self._pulse_t * 2) * 5
        for i in range(15, 0, -3):
            r_w, r_h = self._iw // 2 + i + pulse, self._ih // 2 + i + pulse
            self.create_oval(cx-r_w, cy-r_h, cx+r_w, cy+r_h, fill="", outline=GREEN_FOREST, width=1)

        # India Shadow & Main Image
        shadow_img = self._get_shadow_img()
        photo_main = ImageTk.PhotoImage(self._india_img)
        self._photos = [shadow_img, photo_main] # KEEPING REFERENCES ALIVE

        self.create_image(cx + 12, cy + 12, image=shadow_img, anchor="center")
        self.create_image(cx, cy, image=photo_main, anchor="center")

        if self._opacity > 0.5 and not self._clicked:
            self.create_text(W//2, H - 40, text="▼  Click to enter your tracker  ▼",
                             fill=GREEN_PLASMA, font=("Helvetica", 12, "italic"))

    def _get_shadow_img(self):
        if not hasattr(self, "_shadow_photo") or self._shadow_photo_size != self._india_img.size:
            shadow = Image.new("RGBA", self._india_img.size, (0, 0, 0, 0))
            mask = self._india_img.split()[-1] 
            shadow.paste((0, 0, 0, 100), mask=mask)
            shadow = shadow.filter(ImageFilter.GaussianBlur(radius=4))
            self._shadow_photo = ImageTk.PhotoImage(shadow)
            self._shadow_photo_size = self._india_img.size
        return self._shadow_photo