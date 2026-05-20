"""
Transactional demo loader.

Invoke from the bench console:

    bench --site <site> execute elite_global.setup.demo.install_demo

This bootstraps the five-step walkthrough Mr. Arora will click through:

  01 · Bid Manager       — 1 RFQ + 3 Supplier Quotations (Adani / Marico / Bunge)
  02 · Sales Deal Book.  — 2 Sales Orders (one releases, one trips credit)
  03 · Goods Arrival +UM — 1 Purchase Order + 1 Purchase Receipt with 3
                            variance rows (qty / rate / unit)
  04 · Credit Check      — implicit in (02); Bansal Wholesale gets blocked
  05 · Dashboard         — populated by the rows above + workspace JSON

Idempotent: re-running deletes any prior demo rows (tagged with
`remarks LIKE '[demo]%'`) before re-inserting, so you can run it after
every code change without polluting.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import frappe

DEMO_TAG = "[demo · elite_global]"
COMPANY = "Elite Global Enterprises"
WAREHOUSE = "Elite - Panipat Godown - EGE"
TRANSIT = "Elite - Stock in Transit - EGE"

today = datetime.today().date()
yday = today - timedelta(days=1)


# ── Entry point ─────────────────────────────────────────────────────────

def install_demo() -> None:
    """Wipe prior demo rows and seed fresh ones. Safe to re-run."""
    _wipe_prior()

    rfq = _create_rfq()
    quotes = _create_supplier_quotations(rfq)
    po = _create_purchase_order_from(quotes[0])
    _create_purchase_receipt_with_variance(po)

    _create_sales_order_clean()
    _create_sales_order_blocked()

    frappe.db.commit()
    frappe.msgprint("Elite Global demo seeded.", title="Done", indicator="green")


# ── Step 01 · Bid Manager ───────────────────────────────────────────────

def _create_rfq() -> Any:
    rfq = frappe.new_doc("Request for Quotation")
    rfq.transaction_date = today
    rfq.status = "Submitted"
    rfq.message_for_supplier = (
        f"{DEMO_TAG} Refined Sunflower Oil · 15 kg tin · 1,200 tins · "
        "deliver to Panipat godown. Best price + terms wins."
    )
    rfq.append("items", {
        "item_code": "EG-RSFO-15KG-TIN",
        "qty": 1200,
        "uom": "Tin",
        "warehouse": WAREHOUSE,
        "schedule_date": today + timedelta(days=2),
    })
    for s in [
        "Adani Wilmar Ltd. (EG)",
        "Marico Ltd. (EG)",
        "Bunge India Pvt. Ltd. (EG)",
    ]:
        rfq.append("suppliers", {"supplier": s})
    rfq.insert(ignore_permissions=True)
    rfq.submit()
    return rfq


def _create_supplier_quotations(rfq: Any) -> list[Any]:
    """Three vendors bid against the same RFQ — different rate / terms."""
    bids_spec = [
        {
            "supplier": "Adani Wilmar Ltd. (EG)",
            "rate": 1448,
            "freight_terms": "FOR destination",
            "scheme": "Scheme: ₹6 / tin on full-load lifting.",
            "best_on_price": 0,
            "best_on_terms": 1,
        },
        {
            "supplier": "Marico Ltd. (EG)",
            "rate": 1442,
            "freight_terms": "Ex-plant · ₹38/tin freight",
            "scheme": "Plant discount ₹4/tin if dispatched within 48h.",
            "best_on_price": 1,
            "best_on_terms": 0,
        },
        {
            "supplier": "Bunge India Pvt. Ltd. (EG)",
            "rate": 1455,
            "freight_terms": "FOR destination · rake dispatch",
            "scheme": "Rake dispatch — ETA Panipat 60 h.",
            "best_on_price": 0,
            "best_on_terms": 0,
        },
    ]
    out: list[Any] = []
    for spec in bids_spec:
        sq = frappe.new_doc("Supplier Quotation")
        sq.supplier = spec["supplier"]
        sq.transaction_date = today
        sq.valid_till = today + timedelta(days=2)
        sq.remarks = f"{DEMO_TAG} bid against {rfq.name}"
        sq.custom_bid_best_on_price = spec["best_on_price"]
        sq.custom_bid_best_on_terms = spec["best_on_terms"]
        sq.custom_bid_freight_terms = spec["freight_terms"]
        sq.custom_bid_scheme = spec["scheme"]
        sq.append("items", {
            "item_code": "EG-RSFO-15KG-TIN",
            "qty": 1200,
            "uom": "Tin",
            "rate": spec["rate"],
            "warehouse": WAREHOUSE,
            "schedule_date": today + timedelta(days=2),
            "request_for_quotation": rfq.name,
        })
        sq.insert(ignore_permissions=True)
        sq.submit()
        out.append(sq)
    return out


# ── Step 03 · Goods Arrival + Unit Mgmt ─────────────────────────────────

def _create_purchase_order_from(winning_quote: Any) -> Any:
    """PO follows the cheapest bid (Marico in the demo)."""
    # Pick the actual cheapest one by walking the just-inserted quotes.
    quotes = frappe.get_all(
        "Supplier Quotation",
        filters={"remarks": ["like", f"{DEMO_TAG}%"], "docstatus": 1},
        fields=["name", "supplier", "grand_total"],
    )
    winner = sorted(quotes, key=lambda q: q.grand_total)[0]

    po = frappe.new_doc("Purchase Order")
    po.supplier = winner.supplier
    po.transaction_date = today
    po.schedule_date = today + timedelta(days=2)
    po.remarks = f"{DEMO_TAG} from winning bid {winner.name}"
    po.append("items", {
        "item_code": "EG-RSFO-15KG-TIN",
        "qty": 1200,
        "uom": "Tin",
        "rate": frappe.db.get_value("Supplier Quotation Item",
                                    {"parent": winner.name,
                                     "item_code": "EG-RSFO-15KG-TIN"},
                                    "rate"),
        "warehouse": WAREHOUSE,
        "schedule_date": today + timedelta(days=2),
    })
    # Add two more items so the receipt can show different variance kinds.
    po.append("items", {
        "item_code": "EG-RSBO-15KG-TIN",
        "qty": 300,
        "uom": "Tin",
        "rate": 1382,
        "warehouse": WAREHOUSE,
        "schedule_date": today + timedelta(days=2),
    })
    po.append("items", {
        "item_code": "EG-RMO-15KG-TIN",
        "qty": 100,
        "uom": "Tin",
        "rate": 1640,
        "warehouse": WAREHOUSE,
        "schedule_date": today + timedelta(days=2),
    })
    po.insert(ignore_permissions=True)
    po.submit()
    return po


def _create_purchase_receipt_with_variance(po: Any) -> Any:
    """Receipt that intentionally introduces qty / rate / unit variance."""
    pr = frappe.new_doc("Purchase Receipt")
    pr.supplier = po.supplier
    pr.posting_date = today
    pr.remarks = f"{DEMO_TAG} variance demo against {po.name}"

    # 01: clean — sunflower oil, exactly as PO.
    sunflower = po.items[0]
    pr.append("items", {
        "item_code": sunflower.item_code,
        "qty": sunflower.qty,
        "uom": sunflower.uom,
        "rate": sunflower.rate,
        "warehouse": WAREHOUSE,
        "purchase_order": po.name,
        "purchase_order_item": sunflower.name,
    })

    # 02: short delivery — soybean 300 -> 288 tins (-4%).
    soybean = po.items[1]
    pr.append("items", {
        "item_code": soybean.item_code,
        "qty": 288,
        "uom": soybean.uom,
        "rate": soybean.rate,
        "warehouse": WAREHOUSE,
        "purchase_order": po.name,
        "purchase_order_item": soybean.name,
    })

    # 03: rate variance — mustard 1640 -> 1672 (+1.95%).
    mustard = po.items[2]
    pr.append("items", {
        "item_code": mustard.item_code,
        "qty": mustard.qty,
        "uom": mustard.uom,
        "rate": 1672,
        "warehouse": WAREHOUSE,
        "purchase_order": po.name,
        "purchase_order_item": mustard.name,
    })

    pr.insert(ignore_permissions=True)
    # Don't submit — leave as Draft so the variance review screen has
    # something the user can act on during the demo.
    return pr


# ── Step 02 + 04 · Sales Deal Booking + Credit Check ────────────────────

def _create_sales_order_clean() -> Any:
    """Sharma Trading — within credit limit, releases for dispatch."""
    so = frappe.new_doc("Sales Order")
    so.customer = "Sharma Trading Co. (EG)"
    so.transaction_date = today
    so.delivery_date = today + timedelta(days=2)
    so.remarks = f"{DEMO_TAG} clean booking — credit OK"
    so.append("items", {
        "item_code": "EG-RSFO-15KG-TIN",
        "qty": 200,
        "uom": "Tin",
        "rate": 1485,
        "warehouse": WAREHOUSE,
        "delivery_date": today + timedelta(days=2),
    })
    so.insert(ignore_permissions=True)
    so.submit()
    return so


def _create_sales_order_blocked() -> Any:
    """Bansal Wholesale — overdue + near limit; ERPNext blocks on submit."""
    so = frappe.new_doc("Sales Order")
    so.customer = "Bansal Wholesale (EG)"
    so.transaction_date = today
    so.delivery_date = today + timedelta(days=2)
    so.remarks = f"{DEMO_TAG} should trip credit block on submit"
    so.append("items", {
        "item_code": "EG-RSFO-15KG-TIN",
        "qty": 200,
        "uom": "Tin",
        "rate": 1485,
        "warehouse": WAREHOUSE,
        "delivery_date": today + timedelta(days=2),
    })
    so.insert(ignore_permissions=True)
    # Intentionally don't submit — leave in Draft. The demo walkthrough
    # asks the user to click Submit, which triggers ERPNext's credit
    # limit hold and shows the block UX live.
    return so


# ── Cleanup ─────────────────────────────────────────────────────────────

def _wipe_prior() -> None:
    """Remove demo rows from any previous run so we stay idempotent."""
    doctypes = [
        "Purchase Receipt",
        "Purchase Order",
        "Supplier Quotation",
        "Request for Quotation",
        "Sales Order",
    ]
    for dt in doctypes:
        rows = frappe.get_all(
            dt,
            filters=[["remarks", "like", f"{DEMO_TAG}%"]],
            fields=["name", "docstatus"],
        )
        for row in rows:
            try:
                doc = frappe.get_doc(dt, row.name)
                if doc.docstatus == 1:
                    doc.cancel()
                doc.delete(ignore_permissions=True)
            except Exception as e:
                frappe.log_error(f"Demo wipe failed: {dt} {row.name}", str(e))
