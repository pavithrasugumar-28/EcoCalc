"""
recommendation/rule_engine.py
Sustainability recommendation engine for India Carbon Calculator.

For a given logged activity, fetches all sustainable alternatives from the
database and computes the potential emission saving.

Usage:
    from recommendation.rule_engine import get_recommendations, Recommendation

    recs = get_recommendations("Petrol Car (Medium)", quantity=10)
    for r in recs:
        print(r)
"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dataclasses import dataclass
from typing import Optional

from db.setup import get_connection
from engine.emission_calculator import calculate_emission, get_activity_by_name


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class Recommendation:
    original_activity:     str
    original_emission_kg:  float
    alternative_activity:  str
    alternative_category:  str
    alternative_unit:      str
    alternative_emission_kg: float
    saving_kg:             float
    reduction_percentage:  float
    saving_label:          str       # human-readable one-liner

    def __str__(self) -> str:
        sign = "+" if self.saving_kg < 0 else "-"
        abs_saving = abs(self.saving_kg)
        return (
            f"  ↪  Switch to '{self.alternative_activity}'  →  "
            f"{sign}{abs_saving:.4f} kg CO₂  "
            f"({abs(self.reduction_percentage):.0f}% {'reduction' if self.reduction_percentage >= 0 else 'increase'})"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_recommendations(
    activity_name: str,
    quantity: float,
    region_name: Optional[str] = None,
    include_increases: bool = False,
) -> list[Recommendation]:
    """
    Return all sustainable alternatives for the given activity.

    Parameters
    ----------
    activity_name : str
        The activity the user logged.
    quantity : float
        Amount used (same unit as the activity).
    region_name : str, optional
        Grid region (forwarded to emission_calculator for electricity activities).
    include_increases : bool
        If False (default), filters out alternatives that *increase* emissions.

    Returns
    -------
    List[Recommendation], sorted by saving_kg descending (best saving first).
    """
    activity = get_activity_by_name(activity_name)
    if activity is None:
        return []

    conn = get_connection()
    rows = conn.execute(
        """
        SELECT
            sa.reduction_percentage,
            a.id   AS alt_id,
            a.name AS alt_name,
            a.category AS alt_category,
            a.unit AS alt_unit
        FROM sustainable_alternatives sa
        JOIN activities a ON sa.alternative_activity_id = a.id
        WHERE sa.activity_id = ?
        ORDER BY sa.reduction_percentage DESC
        """,
        (activity.activity_id,)
    ).fetchall()
    conn.close()

    # Original emission
    try:
        original = calculate_emission(activity_name, quantity, region_name)
    except ValueError:
        return []

    recommendations: list[Recommendation] = []

    for row in rows:
        reduction_pct = row["reduction_percentage"]

        if not include_increases and reduction_pct < 0:
            continue

        alt_name = row["alt_name"]
        alt_unit = row["alt_unit"]

        # Calculate alternative emission using the same quantity
        # (same distance/amount — user chose the same trip/task, different mode)
        try:
            alt_result = calculate_emission(alt_name, quantity, region_name)
            alt_emission = alt_result.emission_kg
        except ValueError:
            # Fallback: compute from reduction_percentage if no direct factor
            alt_emission = round(
                original.emission_kg * (1 - reduction_pct / 100), 6
            )

        saving_kg = round(original.emission_kg - alt_emission, 6)

        # Human-readable label
        if reduction_pct >= 90:
            quality = "🌿 Excellent"
        elif reduction_pct >= 60:
            quality = "✅ Great"
        elif reduction_pct >= 30:
            quality = "👍 Good"
        elif reduction_pct > 0:
            quality = "💡 Some saving"
        else:
            quality = "⚠️  Slightly worse"

        saving_label = (
            f"{quality} — save {abs(saving_kg):.3f} kg CO₂ "
            f"by choosing {alt_name!r} instead of {activity_name!r}"
        )

        recommendations.append(Recommendation(
            original_activity      = activity_name,
            original_emission_kg   = original.emission_kg,
            alternative_activity   = alt_name,
            alternative_category   = row["alt_category"],
            alternative_unit       = alt_unit,
            alternative_emission_kg= alt_emission,
            saving_kg              = saving_kg,
            reduction_percentage   = reduction_pct,
            saving_label           = saving_label,
        ))

    # Best saving first
    recommendations.sort(key=lambda r: r.saving_kg, reverse=True)
    return recommendations


def get_tips_for_category(category: str, limit: int = 3) -> list[str]:
    """
    Fetch random sustainability tips for the given activity category.
    """
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT tip FROM sustainability_tips
        WHERE LOWER(category) = LOWER(?)
        ORDER BY RANDOM()
        LIMIT ?
        """,
        (category, limit)
    ).fetchall()
    conn.close()
    return [r["tip"] for r in rows]


def get_offset_methods() -> list[dict]:
    """Return all carbon offset methods with offset amounts."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT name, offset_per_year, unit FROM carbon_offset_methods ORDER BY offset_per_year DESC"
    ).fetchall()
    conn.close()
    return [{"name": r["name"], "offset_per_year": r["offset_per_year"], "unit": r["unit"]} for r in rows]


def trees_needed_to_offset(emission_kg: float) -> dict:
    """
    Calculate how many Neem/Peepal/Banyan trees are needed to offset
    'emission_kg' kg CO₂ over one year.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT offset_per_year FROM carbon_offset_methods "
        "WHERE name LIKE '%Neem%' LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return {}
    trees = emission_kg / row["offset_per_year"]
    return {
        "emission_kg": emission_kg,
        "trees_needed": round(trees, 2),
        "kg_per_tree_per_year": row["offset_per_year"],
    }


# ---------------------------------------------------------------------------
# CLI quick-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_cases = [
        ("Petrol Car (Medium)",              10,  None),
        ("Air Conditioner (1.5 Ton, 3-star)", 5,  "Southern Grid"),
        ("Mutton (Goat/Lamb)",               0.5, None),
    ]

    for activity, qty, region in test_cases:
        print(f"\n{'='*65}")
        print(f"Activity : {activity}  |  Qty: {qty}  |  Region: {region or 'N/A'}")
        recs = get_recommendations(activity, qty, region)
        if recs:
            for r in recs:
                print(r)
        else:
            print("  (no alternatives found)")

        tips = get_tips_for_category(
            get_activity_by_name(activity).category if get_activity_by_name(activity) else ""
        )
        if tips:
            print("\n  💬 Tips:")
            for t in tips:
                print(f"    • {t}")

    print(f"\n{'='*65}")
    print("Offset methods:", [m["name"] for m in get_offset_methods()])
    print("Trees to offset 100 kg CO₂:", trees_needed_to_offset(100))
