"""ui/animations.py — Easing functions and animation scheduler."""

import math


# ── Easing functions ────────────────────────────────────────────────────────────

def linear(t): return t

def ease_in_out(t):
    return t * t * (3 - 2 * t)

def ease_in(t):
    return t * t

def ease_out(t):
    return 1 - (1 - t) ** 2

def ease_in_out_cubic(t):
    if t < 0.5:
        return 4 * t * t * t
    return 1 - (-2 * t + 2) ** 3 / 2

def ease_out_elastic(t):
    if t == 0: return 0
    if t == 1: return 1
    c4 = (2 * math.pi) / 3
    return 2 ** (-10 * t) * math.sin((t * 10 - 0.75) * c4) + 1

def ease_out_bounce(t):
    n1, d1 = 7.5625, 2.75
    if t < 1/d1:   return n1 * t * t
    elif t < 2/d1: t -= 1.5/d1;  return n1*t*t + 0.75
    elif t < 2.5/d1: t -= 2.25/d1; return n1*t*t + 0.9375
    else:           t -= 2.625/d1; return n1*t*t + 0.984375

def ease_in_out_sine(t):
    return -(math.cos(math.pi * t) - 1) / 2

def pulse(t, freq=1.0):
    """Oscillating 0→1→0 pulse."""
    return (math.sin(t * math.pi * 2 * freq) + 1) / 2


# ── Lerp helpers ────────────────────────────────────────────────────────────────

def lerp(a, b, t):
    return a + (b - a) * t

def lerp_color(c1: str, c2: str, t: float) -> str:
    """Linearly interpolate between two hex colours."""
    def parse(c):
        c = c.lstrip("#")
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    r1,g1,b1 = parse(c1); r2,g2,b2 = parse(c2)
    r = int(r1 + (r2-r1)*t); g = int(g1 + (g2-g1)*t); b = int(b1 + (b2-b1)*t)
    return f"#{r:02x}{g:02x}{b:02x}"

def hex_to_rgb(h: str):
    h = h.lstrip("#")
    return int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)

def rgb_to_hex(r,g,b) -> str:
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"


# ── Animation scheduler ─────────────────────────────────────────────────────────

class Tween:
    """Single-property tween with easing."""
    def __init__(self, start, end, duration_ms, ease=ease_in_out, on_update=None, on_done=None):
        self.start    = start
        self.end      = end
        self.duration = duration_ms
        self.ease     = ease
        self.on_update = on_update
        self.on_done   = on_done
        self.elapsed   = 0
        self.done      = False

    def step(self, dt_ms):
        if self.done: return
        self.elapsed = min(self.elapsed + dt_ms, self.duration)
        t = self.ease(self.elapsed / self.duration)
        val = self.start + (self.end - self.start) * t
        if self.on_update: self.on_update(val)
        if self.elapsed >= self.duration:
            self.done = True
            if self.on_done: self.on_done()


class AnimLoop:
    """Simple animation loop driven by tkinter's after()."""
    FPS = 60
    DT  = 1000 // FPS   # ms per frame

    def __init__(self, widget):
        self.widget  = widget
        self.tweens  = []
        self.callbacks = []   # (fn,) called every frame
        self._running = False
        self._job    = None

    def add_tween(self, tween: Tween):
        self.tweens.append(tween)

    def add_callback(self, fn):
        self.callbacks.append(fn)

    def remove_callback(self, fn):
        self.callbacks = [c for c in self.callbacks if c is not fn]

    def start(self):
        if self._running: return
        self._running = True
        self._tick()

    def stop(self):
        self._running = False
        if self._job:
            try: self.widget.after_cancel(self._job)
            except: pass

    def _tick(self):
        if not self._running: return
        for t in list(self.tweens):
            t.step(self.DT)
            if t.done: self.tweens.remove(t)
        for cb in list(self.callbacks):
            try: cb()
            except: pass
        self._job = self.widget.after(self.DT, self._tick)
