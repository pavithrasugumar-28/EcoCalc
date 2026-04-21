"""
engine/emission_calculator.py
Core CO2 emission calculation engine for India Carbon Calculator.

Usage:
    from engine.emission_calculator import calculate_emission, get_categories, get_activities

    result = calculate_emission("Petrol Car (Medium)", quantity=10)
    print(result)
    # → EmissionResult(emission_kg=1.92, unit='km', activity_name='Petrol Car (Medium)', ...)
"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import sqlite3
from dataclasses import dataclass
from typing import Optional

from db.setup import get_connection, ensure_schema as ensure_user_logs_table


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class EmissionResult:
    activity_id:   int
    activity_name: str
    category:      str
    quantity:      float
    unit:          str
    emission_kg:   float
    factor_used:   float
    region_name:   Optional[str]
    source:        Optional[str]

    def __str__(self) -> str:
        region_str = f" [{self.region_name}]" if self.region_name else ""
        return (
            f"{self.emission_kg:.4f} kg CO₂  |  "
            f"{self.activity_name}{region_str}  |  "
            f"{self.quantity} {self.unit}  |  "
            f"factor={self.factor_used} kg CO₂/{self.unit}"
        )


@dataclass
class ActivityInfo:
    activity_id: int
    name:        str
    category:    str
    unit:        str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_categories() -> list[str]:
    """Return all distinct activity categories (excludes 'Carbon Offset')."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT category FROM activities "
        "WHERE category != 'Carbon Offset' ORDER BY category"
    ).fetchall()
    conn.close()
    return [r["category"] for r in rows]


def get_activities(category: Optional[str] = None) -> list[ActivityInfo]:
    """Return activities, optionally filtered by category."""
    conn = get_connection()
    if category:
        rows = conn.execute(
            "SELECT id, name, category, unit FROM activities "
            "WHERE category = ? AND category != 'Carbon Offset' ORDER BY name",
            (category,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, name, category, unit FROM activities "
            "WHERE category != 'Carbon Offset' ORDER BY category, name"
        ).fetchall()
    conn.close()
    return [ActivityInfo(r["id"], r["name"], r["category"], r["unit"]) for r in rows]


def get_activity_by_name(activity_name: str) -> Optional[ActivityInfo]:
    """Look up a single activity by name (case-insensitive)."""
    conn = get_connection()
    row = conn.execute(
        "SELECT id, name, category, unit FROM activities WHERE LOWER(name) = LOWER(?)",
        (activity_name.strip(),)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return ActivityInfo(row["id"], row["name"], row["category"], row["unit"])


def calculate_emission(
    activity_name: str,
    quantity: float,
    region_name: Optional[str] = None,
) -> EmissionResult:
    """
    Calculate CO2 emission for a given activity and quantity.

    Parameters
    ----------
    activity_name : str
        Exact name of the activity (e.g. "Petrol Car (Medium)").
    quantity : float
        Amount consumed (must be > 0).
    region_name : str, optional
        Grid region for electricity activities (e.g. "Southern Grid").
        If provided and a region-specific factor exists it will be used.

    Returns
    -------
    EmissionResult

    Raises
    ------
    ValueError  – unknown activity, negative quantity, no emission factor found.
    """
    # --- Validate quantity ---
    try:
        quantity = float(quantity)
    except (TypeError, ValueError):
        raise ValueError(f"Quantity must be a number, got: {quantity!r}")
    if quantity < 0:
        raise ValueError(f"Quantity must be ≥ 0, got {quantity}")

    # --- Fetch activity ---
    activity = get_activity_by_name(activity_name)
    if activity is None:
        raise ValueError(f"Activity not found: {activity_name!r}")

    # --- Fetch emission factor ---
    conn = get_connection()

    # Prefer region-specific factor when region is given
    factor_row = None
    region_id  = None
    resolved_region_name = None

    if region_name:
        region_row = conn.execute(
            "SELECT id, name FROM regions WHERE LOWER(name) = LOWER(?)",
            (region_name.strip(),)
        ).fetchone()
        if region_row:
            region_id = region_row["id"]
            factor_row = conn.execute(
                "SELECT factor, source, region_id FROM emission_factors "
                "WHERE activity_id = ? AND region_id = ? LIMIT 1",
                (activity.activity_id, region_id)
            ).fetchone()
            if factor_row:
                resolved_region_name = region_row["name"]

    # Fall back to generic (region_id IS NULL) factor
    if factor_row is None:
        factor_row = conn.execute(
            "SELECT factor, source, region_id FROM emission_factors "
            "WHERE activity_id = ? AND region_id IS NULL LIMIT 1",
            (activity.activity_id,)
        ).fetchone()

    # Last resort — any factor for this activity
    if factor_row is None:
        factor_row = conn.execute(
            "SELECT factor, source, region_id FROM emission_factors "
            "WHERE activity_id = ? LIMIT 1",
            (activity.activity_id,)
        ).fetchone()

    conn.close()

    if factor_row is None:
        raise ValueError(f"No emission factor found for activity: {activity_name!r}")

    factor = factor_row["factor"]
    source = factor_row["source"]

    # --- Compute emission ---
    emission_kg = round(quantity * factor, 6)

    return EmissionResult(
        activity_id   = activity.activity_id,
        activity_name = activity.name,
        category      = activity.category,
        quantity      = quantity,
        unit          = activity.unit,
        emission_kg   = emission_kg,
        factor_used   = factor,
        region_name   = resolved_region_name,
        source        = source,
    )


def log_emission(result: EmissionResult, region_name: Optional[str] = None) -> int:
    """
    Persist an EmissionResult to user_logs.
    Returns the new row id.
    """
    ensure_user_logs_table()
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO user_logs
           (activity_id, activity_name, category, quantity, unit, emission_kg, region_name)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            result.activity_id,
            result.activity_name,
            result.category,
            result.quantity,
            result.unit,
            result.emission_kg,
            result.region_name or region_name,
        )
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def get_regions() -> list[str]:
    """Return all grid region names."""
    conn = get_connection()
    rows = conn.execute("SELECT name FROM regions ORDER BY name").fetchall()
    conn.close()
    return [r["name"] for r in rows]


# ---------------------------------------------------------------------------
# CLI quick-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        ("Petrol Car (Medium)", 10, None),
        ("Metro Rail", 20, None),
        ("Air Conditioner (1.5 Ton, 3-star)", 5, "Southern Grid"),
        ("Rice (White)", 100, None),
    ]
    print("=" * 70)
    for name, qty, region in tests:
        try:
            r = calculate_emission(name, qty, region)
            print(r)
        except ValueError as e:
            print(f"ERROR: {e}")
    print("=" * 70)
    print("Categories:", get_categories())
