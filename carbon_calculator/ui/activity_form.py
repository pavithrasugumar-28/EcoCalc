"""
ui/activity_form.py
Enhanced activity logger — searchable dropdown, live CO2 counter,
recommendation panel, year-projection, recurring flag.
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
import math, time
from datetime import datetime

from ui.theme import *
from ui.animations import AnimLoop
from db.setup import get_connection, ensure_schema
from engine.emission_calculator import (
    get_categories, get_activities, get_regions,
    calculate_emission, log_emission, get_activity_by_name
)
from recommendation.rule_engine import get_recommendations, get_tips_for_category, trees_needed_to_offset


class ActivityFormWindow(tk.Toplevel):
    """Full activity logging window with searchable controls."""

    def __init__(self, parent, user: dict, on_save=None):
        super().__init__(parent)
        self.user     = user
        self.on_save  = on_save
        self.title("Log Activity")
        self.configure(bg=BG_DEEP)
        self.resizable(False, False)
        self.geometry("860x640")
        self._result  = None
        self._loop    = AnimLoop(self)
        self._co2_anim= 0.0
        self._co2_target = 0.0
        self._pulse   = 0.0

        ensure_schema()
        self._build()
        self._loop.add_callback(self._tick)
        self._loop.start()
        self._refresh_daily_total()

    def _build(self):
        hdr = tk.Frame(self, bg=BG_VOID)
        hdr.pack(fill="x")
        tk.Label(hdr, text="LOG ACTIVITY",
                 bg=BG_VOID, fg=GREEN_PLASMA,
                 font=("Courier New",13,"bold")).pack(side="left",padx=16,pady=10)
        tk.Button(hdr, text="Close", command=self.destroy,
                  bg=BG_VOID, fg=TEXT_DIM,
                  font=("Helvetica",9), relief="flat", cursor="hand2",
                  activebackground=BG_VOID).pack(side="right", padx=10)
        tk.Frame(self, bg=BORDER_MID, height=1).pack(fill="x")

        body = tk.Frame(self, bg=BG_DEEP)
        body.pack(fill="both", expand=True, padx=14, pady=10)

        # Left: form
        lf = tk.Frame(body, bg=BG_CARD,
                      highlightthickness=1, highlightbackground=BORDER_MID)
        lf.pack(side="left", fill="both", expand=False, padx=(0,8))
        lf.config(width=360)
        lf.pack_propagate(False)

        inner = tk.Frame(lf, bg=BG_CARD, padx=20, pady=16)
        inner.pack(fill="both", expand=True)

        # Daily total
        tf_outer = tk.Frame(inner, bg=BG_OCEAN,
                             highlightthickness=1, highlightbackground=BORDER_MID)
        tf_outer.pack(fill="x", pady=(0,14))
        tf = tk.Frame(tf_outer, bg=BG_OCEAN, padx=12, pady=8)
        tf.pack(fill="x")
        tk.Label(tf, text="TODAY'S TOTAL", bg=BG_OCEAN, fg=TEXT_DIM,
                 font=("Courier New",8,"bold")).pack(side="left")
        self._daily_lbl = tk.Label(tf, text="0.000 kg CO2",
                                    bg=BG_OCEAN, fg=GREEN_PLASMA,
                                    font=("Courier New",11,"bold"))
        self._daily_lbl.pack(side="right")

        # Category
        tk.Label(inner, text="Category", bg=BG_CARD, fg=TEXT_DIM,
                 font=("Helvetica",9)).pack(anchor="w")
        self._cat_var = tk.StringVar()
        cats = get_categories()
        self._cat_cb = ttk.Combobox(inner, textvariable=self._cat_var,
                                     values=cats, state="readonly",
                                     font=("Helvetica",11))
        self._cat_cb.pack(fill="x", pady=(2,10))
        self._cat_cb.bind("<<ComboboxSelected>>", self._on_cat_change)

        # Activity search
        tk.Label(inner, text="Activity (type to search)", bg=BG_CARD, fg=TEXT_DIM,
                 font=("Helvetica",9)).pack(anchor="w")
        self._act_var = tk.StringVar()
        self._act_var.trace("w", self._on_act_search)
        act_ef = tk.Frame(inner, bg=BG_OCEAN,
                          highlightthickness=1, highlightbackground=BORDER_MID)
        act_ef.pack(fill="x")
        self._act_entry = tk.Entry(act_ef, textvariable=self._act_var,
                                    bg=BG_OCEAN, fg=TEXT_WHITE,
                                    insertbackground=GREEN_PLASMA,
                                    font=("Helvetica",11), relief="flat", bd=0)
        self._act_entry.pack(fill="x", padx=8, pady=6)
        self._act_entry.bind("<FocusIn>",  lambda e: act_ef.config(highlightbackground=GREEN_PLASMA))
        self._act_entry.bind("<FocusOut>", lambda e: act_ef.config(highlightbackground=BORDER_MID))
        self._act_entry.bind("<Down>",     lambda e: self._lb_focus())
        self._act_entry.bind("<Return>",   lambda e: self._on_calculate())

        # Listbox
        self._lb_frame = tk.Frame(inner, bg=BG_OCEAN,
                                   highlightthickness=1, highlightbackground=BORDER_MID)
        self._listbox  = tk.Listbox(self._lb_frame,
                                     bg=BG_OCEAN, fg=TEXT_SILVER,
                                     selectbackground=GREEN_FOREST,
                                     selectforeground=GREEN_PLASMA,
                                     font=("Helvetica",10), relief="flat",
                                     bd=0, height=5, highlightthickness=0)
        lb_sb = ttk.Scrollbar(self._lb_frame, orient="vertical",
                               command=self._listbox.yview)
        self._listbox.config(yscrollcommand=lb_sb.set)
        lb_sb.pack(side="right", fill="y")
        self._listbox.pack(side="left", fill="both", expand=True)
        self._listbox.bind("<<ListboxSelect>>", self._on_lb_select)

        # Quantity
        tk.Label(inner, text="Quantity", bg=BG_CARD, fg=TEXT_DIM,
                 font=("Helvetica",9)).pack(anchor="w", pady=(10,0))
        qty_row = tk.Frame(inner, bg=BG_CARD)
        qty_row.pack(fill="x", pady=(2,10))
        self._qty_var = tk.StringVar()
        qty_ef = tk.Frame(qty_row, bg=BG_OCEAN,
                          highlightthickness=1, highlightbackground=BORDER_MID)
        qty_ef.pack(side="left", fill="x", expand=True)
        self._qty_entry = tk.Entry(qty_ef, textvariable=self._qty_var,
                                    bg=BG_OCEAN, fg=TEXT_WHITE,
                                    insertbackground=GREEN_PLASMA,
                                    font=("Helvetica",12), relief="flat", bd=0)
        self._qty_entry.pack(fill="x", padx=8, pady=6)
        self._unit_lbl = tk.Label(qty_row, text="", bg=BG_CARD, fg=GREEN_PLASMA,
                                   font=("Courier New",11,"bold"))
        self._unit_lbl.pack(side="left", padx=8)

        # Region
        tk.Label(inner, text="Grid Region (electricity only)", bg=BG_CARD, fg=TEXT_DIM,
                 font=("Helvetica",9)).pack(anchor="w")
        self._region_var = tk.StringVar(
            value=self.user.get("grid_region","Southern Grid") or "Southern Grid")
        regions = ["None"] + get_regions()
        self._region_cb = ttk.Combobox(inner, textvariable=self._region_var,
                                        values=regions, state="readonly",
                                        font=("Helvetica",10))
        self._region_cb.pack(fill="x", pady=(2,10))

        # Recurring
        self._recurring_var = tk.BooleanVar(value=False)
        tk.Checkbutton(inner, text="Mark as recurring daily activity",
                       variable=self._recurring_var,
                       bg=BG_CARD, fg=TEXT_SILVER,
                       selectcolor=BG_OCEAN,
                       font=("Helvetica",9),
                       activebackground=BG_CARD).pack(anchor="w", pady=(0,14))

        # Buttons
        calc_btn = tk.Button(inner, text="CALCULATE EMISSION",
                  command=self._on_calculate,
                  bg=GREEN_FOREST, fg=GREEN_PLASMA,
                  font=("Courier New",11,"bold"),
                  relief="flat", cursor="hand2",
                  pady=10, activebackground=BG_OCEAN)
        calc_btn.pack(fill="x", pady=(0,6))
        calc_btn.bind("<Enter>", lambda e: calc_btn.config(bg=BG_OCEAN))
        calc_btn.bind("<Leave>", lambda e: calc_btn.config(bg=GREEN_FOREST))

        self._save_btn = tk.Button(inner, text="SAVE TO LOG",
                                    command=self._on_save,
                                    bg=BG_CARD, fg=TEXT_DIM,
                                    font=("Courier New",11,"bold"),
                                    relief="flat", cursor="hand2",
                                    pady=8, state="disabled")
        self._save_btn.pack(fill="x")

        # Right: results
        rf = tk.Frame(body, bg=BG_CARD,
                      highlightthickness=1, highlightbackground=BORDER_MID)
        rf.pack(side="right", fill="both", expand=True)

        self._em_canvas = tk.Canvas(rf, bg=BG_CARD, width=300, height=120,
                                     highlightthickness=0)
        self._em_canvas.pack(fill="x", padx=20, pady=(16,0))

        self._year_lbl = tk.Label(rf, text="",
                                   bg=BG_CARD, fg=TEXT_DIM,
                                   font=("Helvetica",9), justify="center")
        self._year_lbl.pack(pady=(0,10))

        tk.Frame(rf, bg=BORDER_MID, height=1).pack(fill="x", padx=20)

        tk.Label(rf, text="GREENER ALTERNATIVES",
                 bg=BG_CARD, fg=TEXT_SILVER,
                 font=("Courier New",9,"bold")).pack(anchor="w", padx=20, pady=(10,4))

        self._rec_text = tk.Text(rf, bg=BG_CARD, fg=TEXT_SILVER,
                                  font=("Helvetica",9), relief="flat", bd=0,
                                  padx=14, pady=4, wrap="word",
                                  state="disabled", height=18,
                                  insertbackground=GREEN_PLASMA)
        rec_sb = ttk.Scrollbar(rf, orient="vertical", command=self._rec_text.yview)
        self._rec_text.config(yscrollcommand=rec_sb.set)
        rec_sb.pack(side="right", fill="y", padx=(0,8), pady=(0,8))
        self._rec_text.pack(side="left", fill="both", expand=True, padx=(8,0))

        self._load_activities(None)

    def _on_cat_change(self, _=None):
        self._load_activities(self._cat_var.get())
        self._act_var.set("")
        self._unit_lbl.config(text="")

    def _load_activities(self, cat):
        acts = get_activities(cat)
        self._all_acts = acts
        self._show_lb([a.name for a in acts[:30]])

    def _on_act_search(self, *_):
        q   = self._act_var.get().lower()
        cat = self._cat_var.get()
        acts = get_activities(cat if cat else None)
        filtered = [a for a in acts if q in a.name.lower()] if q else acts[:30]
        self._show_lb([a.name for a in filtered[:25]])
        exact = get_activity_by_name(self._act_var.get())
        self._unit_lbl.config(text=exact.unit if exact else "")

    def _show_lb(self, items):
        if items:
            self._lb_frame.pack(fill="x", pady=(0,4))
            self._listbox.delete(0,"end")
            for item in items:
                self._listbox.insert("end", item)
        else:
            self._lb_frame.pack_forget()

    def _on_lb_select(self, _=None):
        sel = self._listbox.curselection()
        if sel:
            name = self._listbox.get(sel[0])
            self._act_var.set(name)
            act  = get_activity_by_name(name)
            if act: self._unit_lbl.config(text=act.unit)
            self._lb_frame.pack_forget()
            self._qty_entry.focus_set()

    def _lb_focus(self):
        if self._lb_frame.winfo_ismapped():
            self._listbox.focus_set()
            self._listbox.selection_set(0)

    def _on_calculate(self):
        act_name = self._act_var.get().strip()
        qty_str  = self._qty_var.get().strip()
        region   = self._region_var.get()
        if region == "None": region = None

        if not act_name:
            messagebox.showwarning("Missing","Please select an activity.", parent=self); return
        if not qty_str:
            messagebox.showwarning("Missing","Please enter a quantity.", parent=self); return
        try: qty = float(qty_str)
        except:
            messagebox.showerror("Invalid","Quantity must be a number.", parent=self); return

        try:
            result = calculate_emission(act_name, qty, region)
        except ValueError as e:
            messagebox.showerror("Error", str(e), parent=self); return

        self._result     = result
        self._co2_target = result.emission_kg
        self._save_btn.config(state="normal", bg=AMBER_WARN, fg="white")
        self._update_result_panel(result, region)

    def _update_result_panel(self, result, region=None):
        recs   = get_recommendations(result.activity_name, result.quantity, region)
        tips   = get_tips_for_category(result.category, limit=2)
        offset = trees_needed_to_offset(result.emission_kg)
        yr     = result.emission_kg * 365

        self._year_lbl.config(
            text=f"Every day for a year: {yr:.1f} kg  =  {yr/1000:.3f} tonnes\n"
                 f"India avg: {INDIA_AVG_ANNUAL_KG:.0f} kg/yr  |  "
                 f"{'ABOVE' if yr>INDIA_AVG_ANNUAL_KG else 'BELOW'} national average",
            fg=RED_AURA if yr > INDIA_AVG_ANNUAL_KG else GREEN_PLASMA)

        t = self._rec_text
        t.config(state="normal"); t.delete("1.0","end")
        t.tag_configure("head", font=("Courier New",9,"bold"), foreground=GREEN_PLASMA)
        t.tag_configure("item", font=("Helvetica",10),          foreground=TEXT_WHITE)
        t.tag_configure("save", font=("Helvetica",8),           foreground=GREEN_PALE)
        t.tag_configure("tip",  font=("Helvetica",8,"italic"),  foreground=TEXT_DIM)
        t.tag_configure("warn", font=("Helvetica",9),           foreground=AMBER_WARN)

        if recs:
            t.insert("end","GREENER ALTERNATIVES\n\n","head")
            for r in recs:
                em = "🌿" if r.reduction_percentage>=80 else "✅" if r.reduction_percentage>=40 else "💡"
                t.insert("end",f"{em}  {r.alternative_activity}\n","item")
                t.insert("end",
                    f"    Save {abs(r.saving_kg):.3f} kg CO2  "
                    f"({r.reduction_percentage:.0f}% less)\n"
                    f"    = {abs(r.saving_kg)*365:.0f} kg/year saved\n\n","save")
        else:
            t.insert("end","No direct alternatives found.\n","warn")

        if offset:
            t.insert("end","OFFSET THIS EMISSION\n","head")
            t.insert("end",
                f"  Plant {offset['trees_needed']:.2f} Neem/Peepal trees\n"
                f"  to offset this over 1 year\n\n","tip")

        if tips:
            t.insert("end","ECO TIPS\n","head")
            for tip in tips:
                t.insert("end",f"  - {tip}\n","tip")

        t.config(state="disabled")

    def _draw_co2_display(self):
        c = self._em_canvas
        c.delete("all")
        W = c.winfo_width() or 300
        H = c.winfo_height() or 120
        self._pulse += 0.06
        c.create_rectangle(0,0,W,H, fill=BG_CARD, outline="")
        val = self._co2_anim
        if val > 0:
            col = GREEN_PLASMA if val<2 else AMBER_WARN if val<5 else RED_AURA
            cr,cg,cb = _hex3(col)
            # Glow
            gr = int(30 + math.sin(self._pulse)*8)
            for dr in range(gr,0,-4):
                c.create_oval(W//2-dr-10,H//2-dr-16,
                               W//2+dr+70,H//2+dr+16,
                               fill=f"#{cr:02x}{cg:02x}{cb:02x}", outline="")
            c.create_text(W//2, H//2-10, text=f"{val:.3f}",
                           fill=col, font=("Courier New",30,"bold"), anchor="center")
            c.create_text(W//2, H//2+22, text="kg CO2",
                           fill=TEXT_SILVER, font=("Helvetica",11), anchor="center")

    def _tick(self):
        if self._co2_anim < self._co2_target:
            self._co2_anim = min(self._co2_target,
                                  self._co2_anim + (self._co2_target-self._co2_anim)*0.08+0.002)
        self._draw_co2_display()

    def _refresh_daily_total(self):
        conn = get_connection()
        row  = conn.execute(
            "SELECT SUM(emission_kg) as t FROM user_logs WHERE user_id=? "
            "AND DATE(logged_at)=DATE('now','localtime')",
            (self.user["id"],)
        ).fetchone()
        conn.close()
        total  = row["t"] or 0
        target = self.user.get("daily_target_kg", INDIA_AVG_DAILY_KG)
        pct    = min(100, total/target*100) if target > 0 else 0
        col    = GREEN_PLASMA if pct < 75 else AMBER_WARN if pct < 120 else RED_AURA
        self._daily_lbl.config(
            text=f"{total:.3f} kg CO2  ({pct:.0f}% of target)", fg=col)

    def _on_save(self):
        if not self._result: return
        region = self._region_var.get()
        if region == "None": region = None
        ensure_schema()
        conn = get_connection()
        from db.setup import now_str
        conn.execute(
            "INSERT INTO user_logs "
            "(user_id,activity_id,activity_name,category,quantity,unit,emission_kg,region_name,is_recurring,logged_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (self.user["id"],
             self._result.activity_id, self._result.activity_name,
             self._result.category, self._result.quantity,
             self._result.unit, self._result.emission_kg,
             self._result.region_name or region,
             1 if self._recurring_var.get() else 0,
             now_str())
        )
        conn.commit(); conn.close()
        self._save_btn.config(state="disabled", bg=BG_CARD, fg=TEXT_DIM)
        self._refresh_daily_total()
        if self.on_save: self.on_save()
        messagebox.showinfo("Saved",
            f"Logged: {self._result.emission_kg:.3f} kg CO2\n"
            f"Activity: {self._result.activity_name}", parent=self)
        self._result = None; self._co2_target = 0.0
        self._qty_var.set(""); self._act_var.set("")

    def destroy(self):
        self._loop.stop()
        super().destroy()


def _hex3(h):
    h=h.lstrip("#"); return int(h[0:2],16),int(h[2:4],16),int(h[4:6],16)
