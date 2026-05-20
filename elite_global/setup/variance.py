"""
Auto-flag variance on Purchase Receipt save.

Wired via `doc_events` in hooks.py:

    doc_events = {
        "Purchase Receipt": {
            "validate": "elite_global.setup.variance.auto_flag_variance",
        },
    }

For each receipt line, compare received qty / rate / uom against the
linked Purchase Order line. Set per-line `custom_variance_kind` and
`custom_variance_pct`, and roll up to the parent document with
`custom_variance_flagged`, `custom_variance_kind` (None / Quantity /
Rate / Unit / Multiple).

Tolerance is intentionally tight (0.5%) so the demo lights up; real
clients will want this exposed as a setting.
"""

from __future__ import annotations

from typing import Any

import frappe


# Anything outside ±0.5% on price or quantity counts as variance.
TOLERANCE_PCT = 0.5


def auto_flag_variance(doc: Any, method: str | None = None) -> None:
    """Validate hook on Purchase Receipt."""
    if not getattr(doc, "items", None):
        return

    kinds: set[str] = set()

    for line in doc.items:
        po_line = _po_line_for(line)
        if not po_line:
            line.custom_variance_kind = "None"
            line.custom_variance_pct = 0
            continue

        line_kind = _classify_line(line, po_line)
        line.custom_variance_kind = line_kind
        line.custom_variance_pct = _variance_pct(line, po_line, line_kind)

        if line_kind != "None":
            kinds.add(line_kind)

    if not kinds:
        doc.custom_variance_flagged = 0
        doc.custom_variance_kind = "None"
        return

    doc.custom_variance_flagged = 1
    doc.custom_variance_kind = next(iter(kinds)) if len(kinds) == 1 else "Multiple"


# ── Internals ───────────────────────────────────────────────────────────

def _po_line_for(line: Any) -> Any | None:
    """Fetch the originating Purchase Order Item, if any."""
    po_detail = getattr(line, "purchase_order_item", None) or getattr(
        line, "po_detail", None
    )
    if not po_detail:
        return None
    try:
        return frappe.get_doc("Purchase Order Item", po_detail)
    except frappe.DoesNotExistError:
        return None


def _classify_line(line: Any, po_line: Any) -> str:
    """Return 'None' / 'Quantity' / 'Rate' / 'Unit' for one PR line."""
    pr_uom = (getattr(line, "uom", "") or "").strip()
    po_uom = (getattr(po_line, "uom", "") or "").strip()
    if pr_uom and po_uom and pr_uom != po_uom:
        return "Unit"

    po_qty = float(getattr(po_line, "qty", 0) or 0)
    pr_qty = float(getattr(line, "qty", 0) or 0)
    if po_qty and abs(pr_qty - po_qty) / po_qty * 100 > TOLERANCE_PCT:
        return "Quantity"

    po_rate = float(getattr(po_line, "rate", 0) or 0)
    pr_rate = float(getattr(line, "rate", 0) or 0)
    if po_rate and abs(pr_rate - po_rate) / po_rate * 100 > TOLERANCE_PCT:
        return "Rate"

    return "None"


def _variance_pct(line: Any, po_line: Any, kind: str) -> float:
    if kind == "Quantity":
        po_qty = float(getattr(po_line, "qty", 0) or 0)
        pr_qty = float(getattr(line, "qty", 0) or 0)
        return round((pr_qty - po_qty) / po_qty * 100, 2) if po_qty else 0
    if kind == "Rate":
        po_rate = float(getattr(po_line, "rate", 0) or 0)
        pr_rate = float(getattr(line, "rate", 0) or 0)
        return round((pr_rate - po_rate) / po_rate * 100, 2) if po_rate else 0
    return 0
