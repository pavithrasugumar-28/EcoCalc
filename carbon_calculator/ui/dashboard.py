"""
ui/dashboard.py
Emission dashboard — today's total, weekly total, category breakdown.
Uses matplotlib for bar chart and pie chart. All data from local SQLite.

Run:
    python3 ui/dashboard.py   (from carbon_calculator/ root)
"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
from typing import Optional

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from db.setup import get_connection, ensure_user_logs_table


# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

BG        = "#F0F4F0"
CARD_BG   = "#FFFFFF"
ACCENT    = "#2E7D32"
ACCENT_LT = "#4CAF50"
TEXT_DARK = "#1B2B1B"
TEXT_MID  = "#4A5E4A"

CATEGORY_COLOURS = {
    "Transportation":    "#1565C0",
    "Household Energy":  "#F57F17",
    "Food":              "#2E7D32",
    "Water Usage":       "#00838F",
    "Waste Management":  "#6A1B9A",
    "Purchases":         "#AD1457",
}
DEFAULT_COLOUR = "#78909C"

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _get_today_logs() -> list[dict]:
    ensure_user_logs_table()
    conn = get_connection()
    rows = conn.execute(
        """SELECT activity_name, category, quantity, unit, emission_kg, logged_at
           FROM user_logs
           WHERE DATE(logged_at) = DATE('now','localtime')
           ORDER BY logged_at DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _get_week_logs() -> list[dict]:
    ensure_user_logs_table()
    conn = get_connection()
    rows = conn.execute(
        """SELECT activity_name, category, quantity, unit, emission_kg,
                  DATE(logged_at) AS day
           FROM user_logs
           WHERE logged_at >= DATE('now','localtime','-6 days')
           ORDER BY logged_at"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _daily_totals(logs: list[dict]) -> dict[str, float]:
    """Aggregate emission_kg by day string (last 7 days, filled with 0)."""
    today = datetime.now().date()
    days = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    totals = {d: 0.0 for d in days}
    for row in logs:
        d = row["day"]
        if d in totals:
            totals[d] += row["emission_kg"]
    return totals


def _category_totals(logs: list[dict]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for row in logs:
        cat = row["category"]
        totals[cat] = totals.get(cat, 0.0) + row["emission_kg"]
    return totals


# ---------------------------------------------------------------------------
# Dashboard window
# ---------------------------------------------------------------------------

class DashboardApp(tk.Tk):
    def __init__(self):
        super().__init__()
        ensure_user_logs_table()

        self.title("📊 Carbon Emission Dashboard")
        self.configure(bg=BG)
        self.resizable(True, True)
        self._center_window(1050, 720)

        self._build_header()
        self._build_stats_bar()
        self._build_charts()
        self._build_log_table()
        self._build_footer()

        self._refresh()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_header(self):
        hdr = tk.Frame(self, bg=ACCENT, padx=20, pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="📊  Emission Dashboard",
                 bg=ACCENT, fg="white",
                 font=("Segoe UI", 16, "bold")).pack(side="left")
        tk.Button(hdr, text="🔄 Refresh", command=self._refresh,
                  bg=ACCENT_LT, fg="white",
                  font=("Segoe UI", 10, "bold"),
                  relief="flat", cursor="hand2", padx=10,
                  activebackground="#81C784").pack(side="right")

    def _build_stats_bar(self):
        bar = tk.Frame(self, bg="#E8F5E9", padx=16, pady=10)
        bar.pack(fill="x")

        self.stat_today = self._stat_card(bar, "Today", "—")
        self.stat_week  = self._stat_card(bar, "This Week", "—")
        self.stat_top   = self._stat_card(bar, "Top Category", "—")
        self.stat_logs  = self._stat_card(bar, "Log Entries", "—")

    def _stat_card(self, parent, label, value):
        card = tk.Frame(parent, bg=CARD_BG,
                        highlightthickness=1, highlightbackground="#A5D6A7",
                        padx=18, pady=10)
        card.pack(side="left", padx=8)
        tk.Label(card, text=label, bg=CARD_BG, fg=TEXT_MID,
                 font=("Segoe UI", 9)).pack()
        val_lbl = tk.Label(card, text=value, bg=CARD_BG, fg=ACCENT,
                           font=("Segoe UI", 15, "bold"))
        val_lbl.pack()
        return val_lbl

    def _build_charts(self):
        chart_row = tk.Frame(self, bg=BG)
        chart_row.pack(fill="both", expand=True, padx=12, pady=6)

        # Left: bar chart (weekly by day)
        left = tk.Frame(chart_row, bg=CARD_BG,
                        highlightthickness=1, highlightbackground="#D0E8D0")
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        tk.Label(left, text="Daily Emissions — Last 7 Days",
                 bg=CARD_BG, fg=TEXT_DARK,
                 font=("Segoe UI", 11, "bold")).pack(pady=(10, 0))
        self.bar_fig = Figure(figsize=(5.2, 3.2), dpi=96, facecolor=CARD_BG)
        self.bar_ax  = self.bar_fig.add_subplot(111)
        self.bar_canvas = FigureCanvasTkAgg(self.bar_fig, master=left)
        self.bar_canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)

        # Right: pie chart (category breakdown this week)
        right = tk.Frame(chart_row, bg=CARD_BG,
                         highlightthickness=1, highlightbackground="#D0E8D0")
        right.pack(side="right", fill="both", expand=True, padx=(6, 0))
        tk.Label(right, text="Category Breakdown — This Week",
                 bg=CARD_BG, fg=TEXT_DARK,
                 font=("Segoe UI", 11, "bold")).pack(pady=(10, 0))
        self.pie_fig = Figure(figsize=(5.2, 3.2), dpi=96, facecolor=CARD_BG)
        self.pie_ax  = self.pie_fig.add_subplot(111)
        self.pie_canvas = FigureCanvasTkAgg(self.pie_fig, master=right)
        self.pie_canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)

    def _build_log_table(self):
        tbl_frame = tk.Frame(self, bg=CARD_BG,
                             highlightthickness=1, highlightbackground="#D0E8D0")
        tbl_frame.pack(fill="x", padx=12, pady=(0, 6))
        tk.Label(tbl_frame, text="Today's Activity Log",
                 bg=CARD_BG, fg=TEXT_DARK,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(8, 4))

        cols = ("Time", "Activity", "Category", "Quantity", "Emission (kg CO₂)")
        self.tree = ttk.Treeview(tbl_frame, columns=cols,
                                 show="headings", height=6)
        widths = (90, 240, 140, 90, 120)
        for col, w in zip(cols, widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="center")
        sb = ttk.Scrollbar(tbl_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, 8), pady=(0, 8))
        self.tree.pack(fill="x", padx=8, pady=(0, 8))

    def _build_footer(self):
        ft = tk.Frame(self, bg="#C8E6C9", padx=12, pady=6)
        ft.pack(fill="x", side="bottom")
        tk.Label(ft, text="All data stored locally — no internet required.",
                 bg="#C8E6C9", fg=TEXT_MID,
                 font=("Segoe UI", 9)).pack(side="left")

    # ------------------------------------------------------------------
    # Data & rendering
    # ------------------------------------------------------------------

    def _refresh(self):
        today_logs = _get_today_logs()
        week_logs  = _get_week_logs()

        today_total = sum(r["emission_kg"] for r in today_logs)
        week_total  = sum(r["emission_kg"] for r in week_logs)
        cat_totals  = _category_totals(week_logs)
        top_cat     = max(cat_totals, key=cat_totals.get) if cat_totals else "—"

        self.stat_today.config(text=f"{today_total:.2f} kg")
        self.stat_week.config( text=f"{week_total:.2f} kg")
        self.stat_top.config(  text=top_cat)
        self.stat_logs.config( text=str(len(today_logs)))

        self._draw_bar(week_logs)
        self._draw_pie(cat_totals)
        self._fill_table(today_logs)

    def _draw_bar(self, week_logs):
        daily = _daily_totals(week_logs)
        labels = [d[5:] for d in daily.keys()]   # MM-DD
        values = list(daily.values())
        colours = [ACCENT_LT if v > 0 else "#CFE8CF" for v in values]

        ax = self.bar_ax
        ax.clear()
        bars = ax.bar(labels, values, color=colours, edgecolor="white", linewidth=0.8)

        # Value labels on top of bars
        for bar, val in zip(bars, values):
            if val > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.01 * (max(values) or 1),
                    f"{val:.2f}",
                    ha="center", va="bottom",
                    fontsize=8, color=TEXT_MID
                )

        ax.set_facecolor("#FAFFF7")
        ax.set_ylabel("kg CO₂", fontsize=9, color=TEXT_MID)
        ax.set_xlabel("Date", fontsize=9, color=TEXT_MID)
        ax.tick_params(colors=TEXT_MID, labelsize=8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["left", "bottom"]].set_color("#C8E6C9")
        ax.set_axisbelow(True)
        ax.yaxis.grid(True, color="#E8F5E9", linewidth=0.7)
        self.bar_fig.tight_layout(pad=1.5)
        self.bar_canvas.draw()

    def _draw_pie(self, cat_totals):
        ax = self.pie_ax
        ax.clear()

        if not cat_totals:
            ax.text(0.5, 0.5, "No data yet\nLog activities to see breakdown",
                    ha="center", va="center", fontsize=10, color=TEXT_MID,
                    transform=ax.transAxes)
            self.pie_canvas.draw()
            return

        labels  = list(cat_totals.keys())
        sizes   = list(cat_totals.values())
        colours = [CATEGORY_COLOURS.get(l, DEFAULT_COLOUR) for l in labels]

        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=None,
            colors=colours,
            autopct=lambda p: f"{p:.1f}%" if p > 4 else "",
            startangle=140,
            pctdistance=0.78,
            wedgeprops={"linewidth": 1.5, "edgecolor": "white"},
        )
        for at in autotexts:
            at.set_fontsize(8)
            at.set_color("white")

        ax.legend(
            wedges, [f"{l} ({v:.1f})" for l, v in zip(labels, sizes)],
            loc="lower center",
            bbox_to_anchor=(0.5, -0.22),
            fontsize=7.5,
            frameon=False,
            ncol=2,
        )
        ax.set_facecolor(CARD_BG)
        self.pie_fig.tight_layout(pad=1.5)
        self.pie_canvas.draw()

    def _fill_table(self, today_logs):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for row in today_logs:
            t = row["logged_at"].split(" ")[-1][:8] if " " in row["logged_at"] else row["logged_at"]
            self.tree.insert("", "end", values=(
                t,
                row["activity_name"],
                row["category"],
                f"{row['quantity']} {row['unit']}",
                f"{row['emission_kg']:.4f}",
            ))
        if not today_logs:
            self.tree.insert("", "end", values=("—", "No logs yet today", "—", "—", "—"))

    # ------------------------------------------------------------------

    def _center_window(self, w, h):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = DashboardApp()
    app.mainloop()
