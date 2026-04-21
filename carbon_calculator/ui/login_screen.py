"""
ui/login_screen.py
Glassmorphism login & register screen with animated background.
"""

from __future__ import annotations
import tkinter as tk
from tkinter import messagebox
import math, random, time
from PIL import Image, ImageTk, ImageDraw, ImageFilter

from ui.theme import *
from ui.animations import AnimLoop, ease_out_elastic, ease_in_out
from db.setup import verify_user, create_user, ensure_schema


class LoginScreen(tk.Canvas):
    """Full-window canvas with floating particles + glass login panel."""

    def __init__(self, master, on_login, **kw):
        super().__init__(master, bg=BG_VOID, highlightthickness=0, **kw)
        self.on_login  = on_login
        self._t        = 0.0
        self._opacity  = 0.0
        self._mode     = "login"   # "login" | "register"
        self._photos   = []
        self._particles= []
        self._slide_x  = 0.0       # panel slide-in animation
        self._error_msg= ""
        self._error_t  = 0.0
        self._loop     = AnimLoop(self)

        ensure_schema()
        self.bind("<Configure>", self._on_configure)

    def _on_configure(self, e):
        self.W = e.width; self.H = e.height
        self._build_widgets()
        if not hasattr(self, "_stars"):
            self._stars    = [(random.randint(0,e.width), random.randint(0,e.height),
                               random.uniform(0.3,1.0)) for _ in range(140)]
            self._particles= [_FP(e.width, e.height) for _ in range(60)]
        if not self._loop._running:
            self._loop.add_callback(self._tick)
            self._loop.start()

    def _build_widgets(self):
        """Build the glass panel overlay with tkinter widgets."""
        # Destroy any existing widgets
        for w in self.winfo_children():
            w.destroy()

        W, H = self.W, self.H
        PW, PH = 400, 520 if self._mode=="login" else 580
        px = W//2 - PW//2
        py = H//2 - PH//2

        # Glass frame (actual tk.Frame placed on canvas)
        self._panel_frame = tk.Frame(self, bg=BG_CARD,
                                     highlightthickness=1,
                                     highlightbackground=BORDER_GLOW)
        self._panel_frame.place(x=px, y=py, width=PW, height=PH)

        # Build interior
        f = self._panel_frame
        pad = {"padx":30}

        # Logo + title
        tk.Label(f, text="🌿", bg=BG_CARD, font=("",32)).pack(pady=(24,0))
        tk.Label(f, text="EcoCalc",
                 bg=BG_CARD, fg=GREEN_PLASMA,
                 font=("Courier New", 14, "bold")).pack(**pad)
        tk.Label(f, text="Login to your account" if self._mode=="login" else "Create new account",
                 bg=BG_CARD, fg=TEXT_SILVER,
                 font=("Helvetica", 10)).pack(pady=(2,16), **pad)

        # Separator
        tk.Frame(f, bg=BORDER_MID, height=1).pack(fill="x", padx=20)

        inner = tk.Frame(f, bg=BG_CARD)
        inner.pack(fill="both", expand=True, padx=30, pady=14)

        # Fields
        self._field_user = _GlassEntry(inner, "👤  Username", wide=True)
        self._field_user.pack(fill="x", pady=6)

        if self._mode == "register":
            self._field_disp = _GlassEntry(inner, "✏️  Display Name", wide=True)
            self._field_disp.pack(fill="x", pady=6)
            self._field_city = _GlassEntry(inner, "📍  City", wide=True)
            self._field_city.pack(fill="x", pady=6)

        self._field_pass = _GlassEntry(inner, "🔒  Password", wide=True, password=True)
        self._field_pass.pack(fill="x", pady=6)

        if self._mode == "register":
            self._field_confirm = _GlassEntry(inner, "🔒  Confirm Password", wide=True, password=True)
            self._field_confirm.pack(fill="x", pady=6)

        # Error label
        self._error_lbl = tk.Label(inner, text="", bg=BG_CARD, fg=RED_AURA,
                                   font=("Helvetica", 9), wraplength=320)
        self._error_lbl.pack(pady=(2,0))

        # Action button
        _GlowButton(inner,
                    text="SIGN IN" if self._mode=="login" else "CREATE ACCOUNT",
                    command=self._submit,
                    color=GREEN_PLASMA).pack(fill="x", pady=(10,4))

        # Toggle mode
        toggle_text = "New here? Create an account →" if self._mode=="login" else "← Back to Login"
        tk.Button(inner, text=toggle_text,
                  bg=BG_CARD, fg=CYAN_GLOW,
                  font=("Helvetica", 9),
                  relief="flat", cursor="hand2", bd=0,
                  activebackground=BG_CARD, activeforeground=GREEN_PLASMA,
                  command=self._toggle_mode).pack()

        # Bind Enter key
        self.bind_all("<Return>", lambda e: self._submit())
        self._field_user.focus()

    def _toggle_mode(self):
        self._mode = "register" if self._mode == "login" else "login"
        self._build_widgets()

    def _submit(self):
        username = self._field_user.get().strip()
        password = self._field_pass.get()

        if not username or not password:
            self._show_error("Please fill in all fields.")
            return

        if self._mode == "login":
            user = verify_user(username, password)
            if user:
                self._loop.stop()
                self.after(100, lambda: self.on_login(user))
            else:
                self._show_error("Invalid username or password.")
        else:
            confirm = self._field_confirm.get()
            if password != confirm:
                self._show_error("Passwords do not match.")
                return
            if len(password) < 4:
                self._show_error("Password must be at least 4 characters.")
                return
            disp = getattr(self._field_disp, "get", lambda: username)()
            city = getattr(self._field_city, "get", lambda: "Chennai")()
            uid  = create_user(username, password, disp, city)
            if uid == -1:
                self._show_error("Username already taken. Try another.")
            else:
                from db.setup import verify_user as vu
                user = vu(username, password)
                self._loop.stop()
                self.after(100, lambda: self.on_login(user))

    def _show_error(self, msg):
        self._error_lbl.config(text=f"⚠  {msg}")
        self._error_lbl.after(3000, lambda: self._error_lbl.config(text=""))

    def _tick(self):
        self._t += 0.016
        self._opacity = min(1.0, self._opacity + 0.02)
        for p in self._particles: p.step()
        self._draw_bg()

    def _draw_bg(self):
        """Draw only background (canvas layer behind the panel)."""
        self.delete("bg_layer")
        if not hasattr(self, "W"): return
        W, H = self.W, self.H

        # Background gradient
        for y in range(0, H, 4):
            t = y/H
            r=int(0+t*8); g=int(4+t*16); b=int(8+t*40)
            self.create_rectangle(0,y,W,y+4,
                                  fill=f"#{r:02x}{g:02x}{b:02x}", outline="",
                                  tags="bg_layer")
        # Stars
        for sx, sy, sa in self._stars:
            sc = int(sa * 80)
            col = f"#{sc//2:02x}{sc:02x}{sc//2+30:02x}"
            self.create_oval(sx-1,sy-1,sx+1,sy+1, fill=col, outline="",
                             tags="bg_layer")
        # Particles
        for p in self._particles:
            a = int(p.alpha * 255)
            if a < 5: continue
            gv = int(100 + p.r*30)
            col = f"#{gv//8:02x}{min(255,gv):02x}{gv//4+60:02x}"
            self.create_oval(p.x-p.r, p.y-p.r, p.x+p.r, p.y+p.r,
                             fill=col, outline="", tags="bg_layer")

        # Corner logo text
        self.create_text(30, H-20, text="India Carbon Tracker v2.0",
                         fill=TEXT_DIM,
                         font=("Courier New", 8), anchor="w",
                         tags="bg_layer")

        # Lift panel above canvas drawings
        if hasattr(self, "_panel_frame"):
            self._panel_frame.lift()

    def destroy_clean(self):
        self._loop.stop()
        try: self.unbind_all("<Return>")
        except: pass
        self.destroy()


# ── Helpers ──────────────────────────────────────────────────────────────────────

class _FP:  # Floating Particle
    def __init__(self, w, h):
        self.w=w; self.h=h; self.reset()
    def reset(self):
        self.x  = random.uniform(0,self.w)
        self.y  = random.uniform(0,self.h)
        self.vx = random.uniform(-0.3,0.3)
        self.vy = random.uniform(-0.6,-0.1)
        self.r  = random.uniform(1,3)
        self.alpha=random.uniform(0.2,0.8)
        self.fade=random.uniform(0.003,0.007)
        self.life=random.uniform(0.3,1.0)
    def step(self):
        self.x+=self.vx; self.y+=self.vy
        self.life-=self.fade; self.alpha=max(0,self.life)
        if self.life<=0 or self.y<-10:
            self.reset(); self.y=self.h+5


class _GlassEntry(tk.Frame):
    """Custom styled entry with placeholder."""
    def __init__(self, parent, placeholder, wide=False, password=False, **kw):
        super().__init__(parent, bg=BG_CARD, **kw)
        self._placeholder = placeholder
        self._is_pw       = password
        self._has_focus   = False

        self._label = tk.Label(self, text=placeholder,
                               bg=BG_CARD, fg=TEXT_DIM,
                               font=("Helvetica", 10))
        self._label.pack(anchor="w")

        entry_frame = tk.Frame(self, bg=BORDER_MID, pady=1)
        entry_frame.pack(fill="x")
        inner = tk.Frame(entry_frame, bg=BG_OCEAN, padx=10, pady=6)
        inner.pack(fill="x", padx=1, pady=1)

        self._var = tk.StringVar()
        self._entry = tk.Entry(inner, textvariable=self._var,
                               bg=BG_OCEAN, fg=TEXT_WHITE,
                               insertbackground=GREEN_PLASMA,
                               relief="flat", bd=0,
                               font=("Helvetica", 11),
                               show="●" if password else "")
        self._entry.pack(fill="x")
        self._entry.bind("<FocusIn>",  self._focus_in)
        self._entry.bind("<FocusOut>", self._focus_out)

        self._border_frame = entry_frame

    def _focus_in(self, e):
        self._border_frame.config(bg=GREEN_PLASMA)
        self._label.config(fg=GREEN_PLASMA)
    def _focus_out(self, e):
        self._border_frame.config(bg=BORDER_MID)
        self._label.config(fg=TEXT_DIM)

    def get(self):
        return self._var.get()

    def focus(self):
        self._entry.focus_set()


class _GlowButton(tk.Frame):
    """Neon glow button."""
    def __init__(self, parent, text, command, color=GREEN_PLASMA, **kw):
        super().__init__(parent, bg=BG_CARD, **kw)
        self._color   = color
        self._command = command
        self._hovered = False

        self._btn = tk.Button(
            self, text=text, command=command,
            bg=BG_CARD, fg=color,
            font=("Courier New", 12, "bold"),
            relief="flat", bd=0, cursor="hand2",
            activebackground=BG_OCEAN, activeforeground=color,
            pady=12,
            highlightthickness=1, highlightbackground=color
        )
        self._btn.pack(fill="x")
        self._btn.bind("<Enter>", self._hover_in)
        self._btn.bind("<Leave>", self._hover_out)

    def _hover_in(self, e):
        self._btn.config(bg=GREEN_FOREST, fg=GREEN_PLASMA)
    def _hover_out(self, e):
        self._btn.config(bg=BG_CARD, fg=self._color)
