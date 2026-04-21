"""
main.py — Entry point for India Carbon Emission Calculator.

Usage:
    python3 main.py              # opens Activity Form (default)
    python3 main.py --dashboard  # opens Dashboard directly
"""

import sys
import os

# Make project root importable
sys.path.insert(0, os.path.dirname(__file__))

from db.setup import ensure_user_logs_table, DB_PATH

def main():
    ensure_user_logs_table()
    print(f"[Carbon Calc] DB: {DB_PATH}")

    mode = "--dashboard" if "--dashboard" in sys.argv else "form"

    if mode == "--dashboard":
        from ui.dashboard import DashboardApp
        app = DashboardApp()
    else:
        from ui.activity_form import ActivityFormApp
        app = ActivityFormApp()

    app.mainloop()


if __name__ == "__main__":
    main()
