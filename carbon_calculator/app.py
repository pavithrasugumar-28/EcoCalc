"""
app.py — Main application controller.
Manages the cinematic screen flow:
  LoadingScreen → SplashScreen → EarthScreen → IndiaScreen → LoginScreen → DashboardScreen

Run:  python3 app.py
"""

from __future__ import annotations
import tkinter as tk
import sys, os, threading
sys.path.insert(0, os.path.dirname(__file__))

from ui.theme import WIN_W, WIN_H, BG_VOID, GREEN_PLASMA, TEXT_SILVER, BORDER_MID
from db.setup import ensure_schema


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("India Carbon Tracker")
        self.configure(bg=BG_VOID)
        self.geometry(f"{WIN_W}x{WIN_H}")
        self.minsize(900, 620)
        self._center()
        ensure_schema()

        self._current_screen = None
        self._user           = None

        self._show_loading_screen()
        threading.Thread(target=self._preload_assets, daemon=True).start()

    def _center(self):
        self.update_idletasks()
        sw = self.winfo_screenwidth(); sh = self.winfo_screenheight()
        self.geometry(f"{WIN_W}x{WIN_H}+{(sw-WIN_W)//2}+{(sh-WIN_H)//2}")

    def _show_loading_screen(self):
        self._loading_canvas = tk.Canvas(self, bg=BG_VOID, highlightthickness=0)
        self._loading_canvas.pack(fill="both", expand=True)
        self._draw_loading(0)

    def _draw_loading(self, pct):
        c = self._loading_canvas
        c.delete("all")
        W = self.winfo_width() or WIN_W
        H = self.winfo_height() or WIN_H
        for y in range(0, H, 4):
            t = y/H; r=int(t*8); g=int(t*14+4); b=int(t*38+8)
            c.create_rectangle(0,y,W,y+4, fill=f"#{r:02x}{g:02x}{b:02x}", outline="")
        c.create_text(W//2, H//2-55, text="🌿", font=("",46), fill=GREEN_PLASMA)
        c.create_text(W//2, H//2-8,  text="INDIA CARBON TRACKER",
                       fill=GREEN_PLASMA, font=("Courier New",18,"bold"))
        c.create_text(W//2, H//2+18, text="Preparing cinematic experience...",
                       fill=TEXT_SILVER, font=("Helvetica",10,"italic"))
        bw=320; bh=6; bx=W//2-bw//2; by=H//2+50
        c.create_rectangle(bx,by,bx+bw,by+bh, fill="#0A2030", outline=BORDER_MID)
        fw = int(bw*pct)
        if fw>0:
            c.create_rectangle(bx,by,bx+fw,by+bh, fill=GREEN_PLASMA, outline="")
        c.create_text(W//2, by+20, text=f"{pct*100:.0f}%",
                       fill=TEXT_SILVER, font=("Courier New",9))

    def _preload_assets(self):
        from ui import assets_loader
        def progress(p):
            self.after(0, lambda: self._draw_loading(p))
        assets_loader.preload(progress)
        self.after(400, self._on_assets_ready)

    def _on_assets_ready(self):
        self._loading_canvas.destroy()
        self._show_splash()

    def _clear(self):
        if self._current_screen:
            try:
                if hasattr(self._current_screen, "destroy_clean"):
                    self._current_screen.destroy_clean()
                else:
                    self._current_screen.destroy()
            except: pass
        self._current_screen = None

    def _show_splash(self):
        self._clear()
        from ui.splash_screen import SplashScreen
        s = SplashScreen(self, on_complete=self._show_earth)
        s.pack(fill="both", expand=True)
        self._current_screen = s

    def _show_earth(self):
        self._clear()
        aura = 0.3
        if self._user:
            from db.setup import get_connection
            from ui.theme import INDIA_AVG_DAILY_KG
            conn = get_connection()
            row  = conn.execute(
                "SELECT SUM(emission_kg) as t FROM user_logs WHERE user_id=? "
                "AND DATE(logged_at)=DATE('now','localtime')", (self._user["id"],)
            ).fetchone()
            conn.close()
            today = row["t"] or 0
            tgt   = self._user.get("daily_target_kg", INDIA_AVG_DAILY_KG)
            aura  = min(1.0, today / (tgt*2)) if tgt>0 else 0.3
        from ui.earth_screen import EarthScreen
        s = EarthScreen(self, on_click=self._show_india, aura_level=aura)
        s.pack(fill="both", expand=True)
        self._current_screen = s

    def _show_india(self):
        self._clear()
        from ui.india_screen import IndiaScreen
        s = IndiaScreen(self, on_click=self._show_login)
        s.pack(fill="both", expand=True)
        self._current_screen = s

    def _show_login(self):
        self._clear()
        from ui.login_screen import LoginScreen
        s = LoginScreen(self, on_login=self._on_login_success)
        s.pack(fill="both", expand=True)
        self._current_screen = s

    def _on_login_success(self, user: dict):
        self._user = user
        self._show_dashboard()

    def _show_dashboard(self):
        self._clear()
        from ui.dashboard_screen import DashboardScreen
        s = DashboardScreen(self, user=self._user, on_logout=self._on_logout)
        s.pack(fill="both", expand=True)
        self._current_screen = s

    def _on_logout(self):
        self._user = None
        self._show_earth()


if __name__ == "__main__":
    app = App()
    app.mainloop()
