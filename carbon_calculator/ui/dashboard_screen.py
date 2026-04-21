"""
ui/dashboard_screen.py
Mission-control main dashboard. Shows:
  • Today's emission total with circular gauge
  • Weekly trend bar chart
  • Category breakdown pie
  • Activity log table
  • Biggest win recommendation card
  • Carbon aura indicator
  • User profile + daily target
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import math, time, csv, io
from datetime import datetime, timedelta
from typing import Optional

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.patches import FancyArrowPatch

from ui.theme import *
from ui.animations import AnimLoop, ease_in_out, ease_out
from db.setup import get_connection, ensure_schema

# ── Data helpers ─────────────────────────────────────────────────────────────────

def _today_logs(uid):
    ensure_schema()
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM user_logs WHERE user_id=? AND DATE(logged_at)=DATE('now','localtime') ORDER BY logged_at DESC",
        (uid,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _week_logs(uid):
    conn = get_connection()
    rows = conn.execute(
        "SELECT *, DATE(logged_at) AS day FROM user_logs WHERE user_id=? "
        "AND logged_at>=DATE('now','localtime','-6 days') ORDER BY logged_at",
        (uid,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _daily_totals(logs):
    today = datetime.now().date()
    days  = [(today - timedelta(days=i)).isoformat() for i in range(6,-1,-1)]
    tot   = {d: 0.0 for d in days}
    for r in logs:
        d = r.get("day","")[:10]
        if d in tot: tot[d] += r["emission_kg"]
    return tot

def _cat_totals(logs):
    tot = {}
    for r in logs:
        c = r["category"]; tot[c] = tot.get(c,0.0) + r["emission_kg"]
    return tot

def _get_weekly_summary(uid):
    conn = get_connection()
    this_week = conn.execute(
        "SELECT SUM(emission_kg) as total FROM user_logs WHERE user_id=? "
        "AND logged_at>=DATE('now','localtime','-6 days')", (uid,)
    ).fetchone()["total"] or 0
    last_week = conn.execute(
        "SELECT SUM(emission_kg) as total FROM user_logs WHERE user_id=? "
        "AND logged_at BETWEEN DATE('now','localtime','-13 days') AND DATE('now','localtime','-7 days')",
        (uid,)
    ).fetchone()["total"] or 0
    conn.close()
    return this_week, last_week


# ── Dashboard ────────────────────────────────────────────────────────────────────

class DashboardScreen(tk.Frame):
    REFRESH_MS = 8000

    def __init__(self, master, user: dict, on_logout, **kw):
        super().__init__(master, bg=BG_DEEP, **kw)
        self.user     = user
        self.on_logout= on_logout
        self._uid     = user["id"]
        self._loop    = AnimLoop(self)
        self._gauge_t = 0.0    # animated gauge fill
        self._target_gauge = 0.0
        self._chart_built  = False

        ensure_schema()
        self._build_layout()
        self._refresh_data()
        self._loop.add_callback(self._animate_tick)
        self._loop.start()
        self.after(self.REFRESH_MS, self._periodic_refresh)

    # ── Layout ──────────────────────────────────────────────────────────────────

    def _build_layout(self):
        # ── Top bar ──────────────────────────────────────────────────────────────
        topbar = tk.Frame(self, bg=BG_VOID, pady=0)
        topbar.pack(fill="x", side="top")
        tk.Label(topbar, text="🌿  EcoCalc",
                 bg=BG_VOID, fg=GREEN_PLASMA,
                 font=("Courier New", 14, "bold")).pack(side="left", padx=16, pady=8)
        # Nav buttons
        nav = tk.Frame(topbar, bg=BG_VOID)
        nav.pack(side="right", padx=10)
        for label, cmd in [("📊 Dashboard", None),
                           ("📝 Log Activity", self._open_activity_form),
                           ("📤 Export CSV",   self._export_csv),
                           ("👤 Profile",      self._open_profile),
                           ("🚪 Logout",       self.on_logout)]:
            active = label == "📊 Dashboard"
            btn = tk.Button(nav, text=label, command=cmd,
                            bg=GREEN_FOREST if active else BG_VOID,
                            fg=GREEN_PLASMA if active else TEXT_SILVER,
                            font=("Helvetica", 9, "bold" if active else "normal"),
                            relief="flat", cursor="hand2",
                            padx=10, pady=8, bd=0,
                            activebackground=GREEN_FOREST,
                            activeforeground=GREEN_PLASMA)
            btn.pack(side="left")
            btn.bind("<Enter>", lambda e,b=btn: b.config(bg=GREEN_FOREST))
            btn.bind("<Leave>", lambda e,b=btn,a=active: b.config(bg=GREEN_FOREST if a else BG_VOID))

        # Separator
        tk.Frame(self, bg=BORDER_MID, height=1).pack(fill="x")

        # ── Body ─────────────────────────────────────────────────────────────────
        body = tk.Frame(self, bg=BG_DEEP)
        body.pack(fill="both", expand=True, padx=12, pady=10)

        # ── Left column ──────────────────────────────────────────────────────────
        left = tk.Frame(body, bg=BG_DEEP)
        left.pack(side="left", fill="both", expand=False, padx=(0,8))
        left.config(width=300)

        # Gauge canvas
        self._gauge_canvas = tk.Canvas(left, bg=BG_CARD, width=280, height=280,
                                        highlightthickness=1,
                                        highlightbackground=BORDER_MID)
        self._gauge_canvas.pack(pady=(0,8))

        # Stat cards
        stats_frame = tk.Frame(left, bg=BG_DEEP)
        stats_frame.pack(fill="x")
        self._stat_today  = self._make_stat_card(stats_frame, "TODAY",   "—", GREEN_PLASMA)
        self._stat_today.grid(row=0,column=0,padx=4,pady=4)
        self._stat_week   = self._make_stat_card(stats_frame, "WEEK",    "—", CYAN_GLOW)
        self._stat_week.grid(row=0,column=1,padx=4,pady=4)
        self._stat_vs_avg = self._make_stat_card(stats_frame, "vs INDIA AVG","—", AMBER_WARN)
        self._stat_vs_avg.grid(row=1,column=0,padx=4,pady=4)
        self._stat_year   = self._make_stat_card(stats_frame, "YEAR PROJ","—", GREEN_ECO)
        self._stat_year.grid(row=1,column=1,padx=4,pady=4)

        # Biggest win card
        self._win_frame = tk.Frame(left, bg=BG_CARD,
                                    highlightthickness=1,
                                    highlightbackground=GREEN_FOREST)
        self._win_frame.pack(fill="x", pady=(8,0))
        tk.Label(self._win_frame, text="🏆  BIGGEST WIN THIS WEEK",
                 bg=BG_CARD, fg=GREEN_PLASMA,
                 font=("Courier New", 9, "bold")).pack(anchor="w", padx=10, pady=(8,2))
        self._win_lbl = tk.Label(self._win_frame, text="Log activities to see recommendations",
                                  bg=BG_CARD, fg=TEXT_SILVER,
                                  font=("Helvetica", 9), wraplength=250, justify="left")
        self._win_lbl.pack(anchor="w", padx=10, pady=(0,8))

        # ── Middle column ─────────────────────────────────────────────────────────
        mid = tk.Frame(body, bg=BG_DEEP)
        mid.pack(side="left", fill="both", expand=True, padx=(0,8))

        # Weekly bar chart
        chart_card = tk.Frame(mid, bg=BG_CARD,
                              highlightthickness=1, highlightbackground=BORDER_MID)
        chart_card.pack(fill="x", pady=(0,8))
        tk.Label(chart_card, text="DAILY EMISSIONS — LAST 7 DAYS",
                 bg=BG_CARD, fg=TEXT_SILVER,
                 font=("Courier New", 9, "bold")).pack(anchor="w", padx=12, pady=(8,2))
        self._bar_fig = Figure(figsize=(5.8, 2.5), dpi=96, facecolor=BG_CARD)
        self._bar_ax  = self._bar_fig.add_subplot(111)
        self._bar_canvas = FigureCanvasTkAgg(self._bar_fig, master=chart_card)
        self._bar_canvas.get_tk_widget().pack(fill="x", padx=8, pady=(0,8))

        # Activity log table
        log_card = tk.Frame(mid, bg=BG_CARD,
                            highlightthickness=1, highlightbackground=BORDER_MID)
        log_card.pack(fill="both", expand=True)
        hdr = tk.Frame(log_card, bg=BG_CARD)
        hdr.pack(fill="x", padx=12, pady=(8,4))
        tk.Label(hdr, text="TODAY'S ACTIVITY LOG",
                 bg=BG_CARD, fg=TEXT_SILVER,
                 font=("Courier New", 9, "bold")).pack(side="left")
        tk.Button(hdr, text="+ Add Activity",
                  command=self._open_activity_form,
                  bg=GREEN_FOREST, fg=GREEN_PLASMA,
                  font=("Helvetica", 8, "bold"), relief="flat",
                  cursor="hand2", padx=8, pady=2).pack(side="right")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.Treeview",
                         background=BG_CARD, foreground=TEXT_SILVER,
                         rowheight=28, fieldbackground=BG_CARD,
                         font=("Helvetica", 9))
        style.configure("Dark.Treeview.Heading",
                         background=BG_OCEAN, foreground=GREEN_PLASMA,
                         font=("Courier New", 8, "bold"))
        style.map("Dark.Treeview", background=[("selected", GREEN_FOREST)])

        cols = ("Time", "Activity", "Qty", "CO₂ kg", "Category")
        self._tree = ttk.Treeview(log_card, columns=cols,
                                   show="headings", height=7,
                                   style="Dark.Treeview")
        for col, w in zip(cols, [65, 210, 70, 75, 120]):
            self._tree.heading(col, text=col)
            self._tree.column(col, width=w, anchor="center" if col!="Activity" else "w")
        sb = ttk.Scrollbar(log_card, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0,8), pady=(0,8))
        self._tree.pack(fill="both", expand=True, padx=8, pady=(0,8))

        # ── Right column ──────────────────────────────────────────────────────────
        right = tk.Frame(body, bg=BG_DEEP)
        right.pack(side="right", fill="both", expand=False)
        right.config(width=260)

        # Pie chart
        pie_card = tk.Frame(right, bg=BG_CARD,
                             highlightthickness=1, highlightbackground=BORDER_MID)
        pie_card.pack(fill="x", pady=(0,8))
        tk.Label(pie_card, text="CATEGORY BREAKDOWN",
                 bg=BG_CARD, fg=TEXT_SILVER,
                 font=("Courier New", 9, "bold")).pack(anchor="w", padx=12, pady=(8,2))
        self._pie_fig = Figure(figsize=(2.7, 2.7), dpi=96, facecolor=BG_CARD)
        self._pie_ax  = self._pie_fig.add_subplot(111)
        self._pie_canvas = FigureCanvasTkAgg(self._pie_fig, master=pie_card)
        self._pie_canvas.get_tk_widget().pack(padx=8, pady=(0,8))

        # Tips / offset section
        tips_card = tk.Frame(right, bg=BG_CARD,
                              highlightthickness=1, highlightbackground=BORDER_MID)
        tips_card.pack(fill="both", expand=True)
        tk.Label(tips_card, text="🌳  OFFSET & TIPS",
                 bg=BG_CARD, fg=TEXT_SILVER,
                 font=("Courier New", 9, "bold")).pack(anchor="w", padx=12, pady=(8,2))
        self._tips_text = tk.Text(tips_card, bg=BG_CARD, fg=TEXT_SILVER,
                                   font=("Helvetica", 9), relief="flat",
                                   bd=0, padx=10, pady=4, wrap="word",
                                   state="disabled", height=14,
                                   insertbackground=GREEN_PLASMA)
        self._tips_text.pack(fill="both", expand=True, padx=4, pady=(0,8))

        # Status bar
        self._status_bar = tk.Frame(self, bg=BG_VOID, pady=4)
        self._status_bar.pack(fill="x", side="bottom")
        self._status_lbl = tk.Label(self._status_bar,
                                     text="Welcome back, " + self.user.get("display_name","User"),
                                     bg=BG_VOID, fg=TEXT_DIM,
                                     font=("Helvetica", 8))
        self._status_lbl.pack(side="left", padx=14)
        self._time_lbl = tk.Label(self._status_bar, text="",
                                   bg=BG_VOID, fg=TEXT_DIM,
                                   font=("Courier New", 8))
        self._time_lbl.pack(side="right", padx=14)

    def _make_stat_card(self, parent, label, value, color):
        card = tk.Frame(parent, bg=BG_CARD,
                        highlightthickness=1, highlightbackground=BORDER_MID,
                        padx=12, pady=8)
        tk.Label(card, text=label, bg=BG_CARD, fg=TEXT_DIM,
                 font=("Courier New", 7, "bold")).pack()
        val_lbl = tk.Label(card, text=value, bg=BG_CARD, fg=color,
                           font=("Courier New", 14, "bold"))
        val_lbl.pack()
        card._val_lbl = val_lbl
        return card

    # ── Animation tick ───────────────────────────────────────────────────────────

    def _animate_tick(self):
        # Smooth gauge animation
        if self._gauge_t < self._target_gauge:
            self._gauge_t = min(self._target_gauge,
                                self._gauge_t + (self._target_gauge - self._gauge_t) * 0.06 + 0.003)
        elif self._gauge_t > self._target_gauge:
            self._gauge_t = max(self._target_gauge,
                                self._gauge_t - abs(self._gauge_t - self._target_gauge) * 0.06)
        self._draw_gauge()
        # Update clock
        try:
            self._time_lbl.config(text=datetime.now().strftime("%a %d %b  %H:%M:%S"))
        except: pass

    # ── Gauge drawing ─────────────────────────────────────────────────────────────

    def _draw_gauge(self):
        c = self._gauge_canvas
        c.delete("all")
        W = c.winfo_width() or 280
        H = c.winfo_height() or 280
        cx, cy = W//2, H//2 - 10
        R  = min(cx, cy) - 20
        r2 = R - 26

        # Background ring
        c.create_arc(cx-R, cy-R, cx+R, cy+R,
                     start=135, extent=270,
                     style="arc", outline=BORDER_MID, width=26)

        # Value fill
        t   = self._gauge_t
        ext = t * 270
        if ext > 0:
            if t < 0.5:   col = lerp_col("#2AFFA6", "#FFB347", t*2)
            else:         col = lerp_col("#FFB347", "#FF4444", (t-0.5)*2)
            c.create_arc(cx-R, cy-R, cx+R, cy+R,
                         start=135, extent=ext,
                         style="arc", outline=col, width=26)
            # End cap glow
            ang_r = math.radians(135 + ext)
            ex = cx + R * math.cos(ang_r)
            ey = cy + R * math.sin(ang_r)
            for dr in range(18, 0, -2):
                a = max(0, int(120 * (1-dr/18)**2))
                cr,cg,cb = _hex3(col)
                c.create_oval(ex-dr, ey-dr, ex+dr, ey+dr,
                               fill=f"#{cr:02x}{cg:02x}{cb:02x}", outline="")

        # Tick marks
        for i in range(11):
            a_r = math.radians(135 + i*27)
            r3  = R + 6; r4 = R + 14
            c.create_line(cx + r3*math.cos(a_r), cy + r3*math.sin(a_r),
                          cx + r4*math.cos(a_r), cy + r4*math.sin(a_r),
                          fill=BORDER_MID, width=2)

        # Central value
        target  = self.user.get("daily_target_kg", INDIA_AVG_DAILY_KG)
        cur_kg  = t * target * 2
        c.create_text(cx, cy - 14, text=f"{cur_kg:.2f}",
                       fill=col if ext > 0 else GREEN_PLASMA,
                       font=("Courier New", 28, "bold"))
        c.create_text(cx, cy + 16, text="kg CO₂ today",
                       fill=TEXT_SILVER, font=("Helvetica", 9))

        # Target label
        c.create_text(cx, cy + 38, text=f"Target: {target:.1f} kg/day",
                       fill=TEXT_DIM, font=("Helvetica", 8))

        # User greeting
        c.create_text(cx, 20, text=self.user.get("display_name",""),
                       fill=GREEN_PALE, font=("Helvetica", 10, "bold"))
        c.create_text(cx, 36, text=self.user.get("city",""),
                       fill=TEXT_DIM, font=("Helvetica", 8))


    # ── Data refresh ─────────────────────────────────────────────────────────────

    def _refresh_data(self):
        today_logs = _today_logs(self._uid)
        week_logs  = _week_logs(self._uid)
        today_total= sum(r["emission_kg"] for r in today_logs)
        week_total, last_week = _get_weekly_summary(self._uid)

        target = self.user.get("daily_target_kg", INDIA_AVG_DAILY_KG)
        self._target_gauge = min(1.0, today_total / (target * 2)) if target > 0 else 0

        # Stat cards
        self._stat_today._val_lbl.config(text=f"{today_total:.2f} kg")
        self._stat_week._val_lbl.config( text=f"{week_total:.2f} kg")
        year_proj = today_total * 365
        self._stat_year._val_lbl.config( text=f"{year_proj/1000:.2f} t")
        vs_avg_pct = (today_total / INDIA_AVG_DAILY_KG - 1) * 100 if INDIA_AVG_DAILY_KG > 0 else 0
        sign = "▲" if vs_avg_pct > 0 else "▼"
        col  = RED_AURA if vs_avg_pct > 0 else GREEN_PLASMA
        self._stat_vs_avg._val_lbl.config(
            text=f"{sign}{abs(vs_avg_pct):.0f}%", fg=col)

        # Charts
        self._draw_bar_chart(week_logs)
        self._draw_pie_chart(_cat_totals(week_logs))

        # Log table
        self._fill_table(today_logs)

        # Biggest win
        self._compute_biggest_win(today_logs)

        # Tips
        self._update_tips(today_total, week_total)

    def _draw_bar_chart(self, week_logs):
        daily  = _daily_totals(week_logs)
        labels = [d[5:] for d in daily]
        values = list(daily.values())
        target = self.user.get("daily_target_kg", INDIA_AVG_DAILY_KG)

        ax = self._bar_ax; ax.clear()
        ax.set_facecolor(BG_CARD)
        self._bar_fig.patch.set_facecolor(BG_CARD)

        colors = []
        for v in values:
            if v == 0:         colors.append("#1A3040")
            elif v <= target:  colors.append("#1DB954")
            elif v <= target*1.5: colors.append("#FFB347")
            else:              colors.append("#FF4444")

        bars = ax.bar(labels, values, color=colors, edgecolor=BG_CARD,
                      linewidth=0.5, width=0.6)
        for bar, val in zip(bars, values):
            if val > 0:
                ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.03,
                        f"{val:.1f}", ha="center", va="bottom",
                        fontsize=7, color="#A0C0B0")

        # Target line
        ax.axhline(target, color=GREEN_PLASMA, linewidth=1,
                   linestyle="--", alpha=0.6, label=f"Target {target:.1f}")
        ax.legend(fontsize=7, facecolor=BG_CARD, edgecolor=BORDER_MID,
                  labelcolor=GREEN_PLASMA)

        ax.set_ylabel("kg CO₂", fontsize=7, color=TEXT_DIM)
        ax.tick_params(colors=TEXT_DIM, labelsize=7)
        for sp in ax.spines.values(): sp.set_color(BORDER_MID)
        ax.set_axisbelow(True)
        ax.yaxis.grid(True, color=BORDER_MID, linewidth=0.5, alpha=0.6)
        self._bar_fig.tight_layout(pad=1.2)
        self._bar_canvas.draw()

    def _draw_pie_chart(self, cat_tot):
        ax = self._pie_ax; ax.clear()
        ax.set_facecolor(BG_CARD)
        self._pie_fig.patch.set_facecolor(BG_CARD)

        if not cat_tot:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    color=TEXT_DIM, fontsize=9, transform=ax.transAxes)
            self._pie_canvas.draw()
            return

        labels = list(cat_tot.keys())
        sizes  = list(cat_tot.values())
        colors = [cat_color(l) for l in labels]
        wedges, texts, autos = ax.pie(
            sizes, colors=colors, autopct=lambda p: f"{p:.0f}%" if p>7 else "",
            startangle=140, pctdistance=0.72,
            wedgeprops={"linewidth":1.5,"edgecolor":BG_CARD})
        for at in autos: at.set_fontsize(7); at.set_color("white")
        ax.legend(wedges, [f"{l[:12]}" for l in labels],
                  loc="lower center", bbox_to_anchor=(0.5,-0.28),
                  fontsize=6.5, frameon=False,
                  labelcolor=TEXT_SILVER, ncol=2)
        self._pie_fig.tight_layout(pad=0.5)
        self._pie_canvas.draw()

    def _fill_table(self, logs):
        for row in self._tree.get_children(): self._tree.delete(row)
        for r in logs:
            t  = r["logged_at"].split(" ")[-1][:5] if " " in r["logged_at"] else r["logged_at"]
            ki = r["emission_kg"]
            tag = "high" if ki > 5 else ("mid" if ki > 2 else "low")
            self._tree.insert("", "end", values=(
                t, r["activity_name"],
                f"{r['quantity']:.1f} {r['unit']}",
                f"{ki:.3f}",
                r["category"]
            ), tags=(tag,))
        self._tree.tag_configure("high", foreground=RED_AURA)
        self._tree.tag_configure("mid",  foreground=AMBER_WARN)
        self._tree.tag_configure("low",  foreground=GREEN_PLASMA)
        if not logs:
            self._tree.insert("","end", values=("—","No activities logged yet","—","—","—"))

    def _compute_biggest_win(self, today_logs):
        from recommendation.rule_engine import get_recommendations
        best_saving = 0; best_msg = ""
        for r in today_logs[:5]:
            try:
                recs = get_recommendations(r["activity_name"], r["quantity"],
                                            r.get("region_name"))
                if recs:
                    top = recs[0]
                    if top.saving_kg > best_saving:
                        best_saving = top.saving_kg
                        best_msg = (f"Switch '{r['activity_name'][:22]}' → '{top.alternative_activity[:22]}'\n"
                                    f"Save {top.saving_kg:.2f} kg CO₂ "
                                    f"({top.reduction_percentage:.0f}% less)")
            except: pass

        if best_msg:
            yr = best_saving * 365
            best_msg += f"\n≈ {yr:.0f} kg/year · {yr/21:.1f} trees"
            self._win_lbl.config(text=best_msg, fg=GREEN_PLASMA)
        else:
            self._win_lbl.config(text="Log activities to see your biggest win!",
                                  fg=TEXT_DIM)

    def _update_tips(self, today_total, week_total):
        from recommendation.rule_engine import get_tips_for_category, trees_needed_to_offset
        self._tips_text.config(state="normal")
        self._tips_text.delete("1.0","end")
        t = self._tips_text
        t.tag_configure("head", font=("Courier New",9,"bold"), foreground=GREEN_PLASMA)
        t.tag_configure("tip",  font=("Helvetica",8),          foreground=TEXT_SILVER)
        t.tag_configure("num",  font=("Courier New",10,"bold"), foreground=CYAN_GLOW)
        t.tag_configure("dim",  font=("Helvetica",8),           foreground=TEXT_DIM)

        # Weekly comparison
        t.insert("end","◉ WEEKLY PROGRESS\n","head")
        pct = (week_total / (INDIA_AVG_DAILY_KG*7) - 1)*100 if INDIA_AVG_DAILY_KG>0 else 0
        sign = "▲" if pct>0 else "▼"
        t.insert("end",f"  {week_total:.2f} kg this week  {sign}{abs(pct):.0f}% vs India avg\n\n","tip")

        # Tree offset
        offset = trees_needed_to_offset(week_total)
        if offset:
            t.insert("end","◉ OFFSET NEEDED\n","head")
            t.insert("end",f"  {offset['trees_needed']:.1f} ","num")
            t.insert("end","Neem/Peepal trees to offset\n  this week's emission\n\n","tip")

        # Random tips
        t.insert("end","◉ ECO TIPS\n","head")
        tips = get_tips_for_category("Transportation", limit=2)
        tips+= get_tips_for_category("Household Energy", limit=1)
        for tip in tips:
            t.insert("end",f"  • {tip}\n","tip")

        t.config(state="disabled")

    def _periodic_refresh(self):
        try:
            self._refresh_data()
        except: pass
        self.after(self.REFRESH_MS, self._periodic_refresh)

    # ── Actions ───────────────────────────────────────────────────────────────────

    def _open_activity_form(self):
        from ui.activity_form import ActivityFormWindow
        ActivityFormWindow(self, self.user, on_save=self._refresh_data)

    def _export_csv(self):
        conn = get_connection()
        rows = conn.execute(
            "SELECT logged_at,activity_name,category,quantity,unit,emission_kg "
            "FROM user_logs WHERE user_id=? ORDER BY logged_at DESC", (self._uid,)
        ).fetchall()
        conn.close()
        if not rows:
            messagebox.showinfo("Export", "No data to export.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV","*.csv")],
            initialfile=f"emissions_{datetime.now():%Y%m%d}.csv")
        if path:
            with open(path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["Date","Activity","Category","Quantity","Unit","CO2_kg"])
                w.writerows(rows)
            messagebox.showinfo("Exported", f"Saved to:\n{path}")

    def _open_profile(self):
        ProfileWindow(self, self.user, on_save=self._on_profile_saved)

    def _on_profile_saved(self, updated_user):
        self.user = updated_user
        self._refresh_data()

    def destroy_clean(self):
        self._loop.stop()
        self.destroy()


# ── Profile Window ───────────────────────────────────────────────────────────────

class ProfileWindow(tk.Toplevel):
    def __init__(self, parent, user, on_save):
        super().__init__(parent)
        self.title("👤  Profile Settings")
        self.configure(bg=BG_DEEP)
        self.resizable(False, False)
        self.geometry("420x480")
        self._user    = user
        self.on_save  = on_save
        self._build()

    def _build(self):
        tk.Label(self, text="👤  PROFILE SETTINGS",
                 bg=BG_DEEP, fg=GREEN_PLASMA,
                 font=("Courier New", 13, "bold")).pack(pady=(20,4))
        tk.Frame(self, bg=BORDER_MID, height=1).pack(fill="x", padx=20)

        f = tk.Frame(self, bg=BG_DEEP, padx=30)
        f.pack(fill="both", expand=True, pady=10)

        fields_def = [
            ("Display Name", "display_name"),
            ("City",         "city"),
        ]
        self._vars = {}
        for label, key in fields_def:
            tk.Label(f, text=label, bg=BG_DEEP, fg=TEXT_DIM,
                     font=("Helvetica",9)).pack(anchor="w", pady=(8,0))
            var = tk.StringVar(value=self._user.get(key,""))
            ent = tk.Entry(f, textvariable=var,
                           bg=BG_OCEAN, fg=TEXT_WHITE,
                           insertbackground=GREEN_PLASMA,
                           relief="flat", bd=0, font=("Helvetica",11),
                           highlightthickness=1, highlightbackground=BORDER_MID)
            ent.pack(fill="x", ipady=6)
            self._vars[key] = var

        # Grid region
        tk.Label(f, text="Grid Region", bg=BG_DEEP, fg=TEXT_DIM,
                 font=("Helvetica",9)).pack(anchor="w", pady=(8,0))
        from engine.emission_calculator import get_regions
        self._region_var = tk.StringVar(value=self._user.get("grid_region","Southern Grid"))
        reg_cb = ttk.Combobox(f, textvariable=self._region_var,
                               values=get_regions(), state="readonly",
                               font=("Helvetica",11))
        reg_cb.pack(fill="x")

        # Daily target
        tk.Label(f, text=f"Daily CO₂ Target (kg)  — India avg: {INDIA_AVG_DAILY_KG:.1f}",
                 bg=BG_DEEP, fg=TEXT_DIM,
                 font=("Helvetica",9)).pack(anchor="w", pady=(8,0))
        self._target_var = tk.DoubleVar(value=self._user.get("daily_target_kg", INDIA_AVG_DAILY_KG))
        tk.Entry(f, textvariable=self._target_var,
                 bg=BG_OCEAN, fg=TEXT_WHITE,
                 insertbackground=GREEN_PLASMA,
                 relief="flat", bd=0, font=("Helvetica",11),
                 highlightthickness=1, highlightbackground=BORDER_MID).pack(fill="x", ipady=6)

        tk.Button(f, text="💾  SAVE PROFILE",
                  command=self._save,
                  bg=GREEN_FOREST, fg=GREEN_PLASMA,
                  font=("Courier New",11,"bold"),
                  relief="flat", cursor="hand2",
                  pady=10).pack(fill="x", pady=(20,0))

    def _save(self):
        from db.setup import update_user_profile, get_user
        update_user_profile(
            self._user["id"],
            display_name  = self._vars["display_name"].get(),
            city          = self._vars["city"].get(),
            grid_region   = self._region_var.get(),
            daily_target_kg = self._target_var.get(),
        )
        updated = get_user(self._user["id"])
        self.on_save(updated)
        self.destroy()


# ── Helpers ───────────────────────────────────────────────────────────────────────

def lerp_col(c1, c2, t):
    def p(c): c=c.lstrip("#"); return int(c[0:2],16),int(c[2:4],16),int(c[4:6],16)
    r1,g1,b1=p(c1); r2,g2,b2=p(c2)
    return f"#{int(r1+(r2-r1)*t):02x}{int(g1+(g2-g1)*t):02x}{int(b1+(b2-b1)*t):02x}"

def _hex3(h):
    h=h.lstrip("#"); return int(h[0:2],16),int(h[2:4],16),int(h[4:6],16)
