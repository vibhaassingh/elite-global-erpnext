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
    """Wipe prior demo rows and seed fresh ones. Safe to re-run.

    Each step is wrapped so a single failing record (e.g., a field
    shape that diverges from vanilla ERPNext) doesn't break the
    remaining demo data — the demo stays partially populated and we
    can fix the offending step in a follow-up commit.
    """
    _wipe_prior()

    rfq = None
    quotes = []
    po = None

    def _step(label: str, fn):
        try:
            return fn()
        except Exception as e:
            frappe.log_error(
                title=f"elite_global demo · {label} failed",
                message=frappe.get_traceback(),
            )
            return None

    rfq = _step("rfq", _create_rfq)
    if rfq:
        quotes = _step("supplier_quotations", lambda: _create_supplier_quotations(rfq)) or []
    if quotes:
        po = _step("purchase_order", lambda: _create_purchase_order_from(quotes[0]))
    if po:
        # Two receipts against the same PO:
        #   A) submitted clean — sunflower, full qty + PO rate. Creates
        #      Stock Ledger Entry rows so the workspace's
        #      "Stock by warehouse" chart has data the moment the demo
        #      loads — no walkthrough action required.
        #   B) draft, with variance — soybean (qty variance) + mustard
        #      (rate variance). Stays as Draft so "03 · Goods Arrival"
        #      has something the user can review & submit during the
        #      walkthrough.
        _step("purchase_receipt_clean", lambda: _create_purchase_receipt_clean(po))
        _step("purchase_receipt", lambda: _create_purchase_receipt_with_variance(po))

    _step("sales_order_clean", _create_sales_order_clean)
    _step("sales_order_blocked", _create_sales_order_blocked)

    frappe.db.commit()
    frappe.msgprint("Elite Global demo seeded.", title="Done", indicator="green")


# ── Step 01 · Bid Manager ───────────────────────────────────────────────

def _create_rfq() -> Any:
    rfq = frappe.new_doc("Request for Quotation")
    rfq.company = COMPANY
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
        "stock_uom": "Tin",
        "conversion_factor": 1,
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
        sq.company = COMPANY
        sq.supplier = spec["supplier"]
        sq.transaction_date = today
        sq.valid_till = today + timedelta(days=2)
        # Supplier Quotation has no 'remarks' top-level field; demo
        # identification happens via supplier name.
        sq.custom_bid_best_on_price = spec["best_on_price"]
        sq.custom_bid_best_on_terms = spec["best_on_terms"]
        sq.custom_bid_freight_terms = spec["freight_terms"]
        sq.custom_bid_scheme = spec["scheme"]
        sq.append("items", {
            "item_code": "EG-RSFO-15KG-TIN",
            "qty": 1200,
            "uom": "Tin",
        "stock_uom": "Tin",
        "conversion_factor": 1,
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
    # Supplier Quotation has no 'remarks' column in this ERPNext build,
    # so we identify our demo quotes by our three demo suppliers.
    demo_suppliers = [
        "Adani Wilmar Ltd. (EG)",
        "Marico Ltd. (EG)",
        "Bunge India Pvt. Ltd. (EG)",
    ]
    quotes = frappe.get_all(
        "Supplier Quotation",
        filters={"supplier": ["in", demo_suppliers], "docstatus": 1},
        fields=["name", "supplier", "grand_total"],
        order_by="creation desc",
        limit_page_length=3,
    )
    winner = sorted(quotes, key=lambda q: q.grand_total)[0]

    po = frappe.new_doc("Purchase Order")
    po.company = COMPANY
    po.supplier = winner.supplier
    po.transaction_date = today
    po.schedule_date = today + timedelta(days=2)
    # Purchase Order doctype has no `remarks` field in vanilla ERPNext;
    # demo tagging happens via the linked supplier quotation.
    po.append("items", {
        "item_code": "EG-RSFO-15KG-TIN",
        "qty": 1200,
        "uom": "Tin",
        "stock_uom": "Tin",
        "conversion_factor": 1,
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
        "stock_uom": "Tin",
        "conversion_factor": 1,
        "rate": 1382,
        "warehouse": WAREHOUSE,
        "schedule_date": today + timedelta(days=2),
    })
    po.append("items", {
        "item_code": "EG-RMO-15KG-TIN",
        "qty": 100,
        "uom": "Tin",
        "stock_uom": "Tin",
        "conversion_factor": 1,
        "rate": 1640,
        "warehouse": WAREHOUSE,
        "schedule_date": today + timedelta(days=2),
    })
    po.insert(ignore_permissions=True)
    po.submit()
    return po


def _create_purchase_receipt_clean(po: Any) -> Any:
    """Submitted PR for the sunflower line — receives 1200 tins at the
    PO rate, no variance. Submitting creates Stock Ledger Entry rows
    that populate the workspace's "Stock by warehouse" chart on demo
    load, so Mr. Arora sees actual data before he even starts the
    walkthrough."""
    pr = frappe.new_doc("Purchase Receipt")
    pr.company = COMPANY
    pr.supplier = po.supplier
    pr.posting_date = today
    pr.remarks = f"{DEMO_TAG} clean receipt — sunflower delivery"

    sunflower = po.items[0]
    pr.append("items", {
        "item_code": sunflower.item_code,
        "qty": sunflower.qty,
        "uom": sunflower.uom,
        "stock_uom": sunflower.uom,
        "conversion_factor": 1,
        "rate": sunflower.rate,
        "warehouse": WAREHOUSE,
        "purchase_order": po.name,
        "purchase_order_item": sunflower.name,
    })

    pr.insert(ignore_permissions=True)
    pr.submit()  # Submit → creates SLE rows for the chart
    return pr


def _create_purchase_receipt_with_variance(po: Any) -> Any:
    """Draft PR for the soybean + mustard lines — short-delivery on
    soybean and a rate variance on mustard. Stays as Draft so the
    "03 · Goods Arrival" walkthrough step has a flagged receipt for
    the user to review and submit."""
    pr = frappe.new_doc("Purchase Receipt")
    pr.company = COMPANY
    pr.supplier = po.supplier
    pr.posting_date = today
    pr.remarks = f"{DEMO_TAG} variance demo against {po.name}"

    # 01: short delivery — soybean 300 -> 288 tins (-4%).
    soybean = po.items[1]
    pr.append("items", {
        "item_code": soybean.item_code,
        "qty": 288,
        "uom": soybean.uom,
        "stock_uom": soybean.uom,
        "conversion_factor": 1,
        "rate": soybean.rate,
        "warehouse": WAREHOUSE,
        "purchase_order": po.name,
        "purchase_order_item": soybean.name,
    })

    # 02: rate variance — mustard 1640 -> 1672 (+1.95%).
    mustard = po.items[2]
    pr.append("items", {
        "item_code": mustard.item_code,
        "qty": mustard.qty,
        "uom": mustard.uom,
        "stock_uom": mustard.uom,
        "conversion_factor": 1,
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
    so.company = COMPANY
    so.selling_price_list = "Standard Selling"
    so.price_list_currency = "INR"
    so.plc_conversion_rate = 1
    so.currency = "INR"
    so.conversion_rate = 1
    so.customer = "Sharma Trading Co. (EG)"
    so.transaction_date = today
    so.delivery_date = today + timedelta(days=2)
    so.remarks = f"{DEMO_TAG} clean booking — credit OK"
    so.append("items", {
        "item_code": "EG-RSFO-15KG-TIN",
        "qty": 200,
        "uom": "Tin",
        "stock_uom": "Tin",
        "conversion_factor": 1,
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
    so.company = COMPANY
    so.selling_price_list = "Standard Selling"
    so.price_list_currency = "INR"
    so.plc_conversion_rate = 1
    so.currency = "INR"
    so.conversion_rate = 1
    so.customer = "Bansal Wholesale (EG)"
    so.transaction_date = today
    so.delivery_date = today + timedelta(days=2)
    so.remarks = f"{DEMO_TAG} should trip credit block on submit"
    so.append("items", {
        "item_code": "EG-RSFO-15KG-TIN",
        "qty": 200,
        "uom": "Tin",
        "stock_uom": "Tin",
        "conversion_factor": 1,
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
    """Remove demo rows from any previous run so we stay idempotent.

    Different DocTypes use different free-text fields:
      Sales Order / Purchase Receipt / Supplier Quotation: `remarks`
      Purchase Order: `customer_address` is the wrong field; `terms`
        and `tc_name` are used. Purchase Order in vanilla ERPNext
        DOES NOT have a `remarks` top-level field. We tag PO rows
        via the Comment system instead.
      Request for Quotation: uses `message_for_supplier`.
    """
    # (doctype, field, value-prefix) — skip silently if the column is
    # missing for that DocType (older ERPNext versions vary).
    targets = [
        ("Sales Order", "remarks", DEMO_TAG),
        ("Purchase Receipt", "remarks", DEMO_TAG),
        ("Request for Quotation", "message_for_supplier", DEMO_TAG),
    ]
    for dt, field, prefix in targets:
        try:
            rows = frappe.get_all(
                dt,
                filters=[[field, "like", f"{prefix}%"]],
                fields=["name", "docstatus"],
            )
        except Exception:
            # Column doesn't exist in this ERPNext build — skip cleanly.
            continue
        for row in rows:
            try:
                doc = frappe.get_doc(dt, row.name)
                if doc.docstatus == 1:
                    doc.cancel()
                doc.delete(ignore_permissions=True)
            except Exception as e:
                frappe.log_error(f"Demo wipe failed: {dt} {row.name}", str(e))

    # Purchase Order + Supplier Quotation have no `remarks` field —
    # wipe by demo supplier set.
    demo_suppliers = [
        "Adani Wilmar Ltd. (EG)",
        "Marico Ltd. (EG)",
        "Bunge India Pvt. Ltd. (EG)",
    ]
    for dt in ("Purchase Order", "Supplier Quotation"):
        try:
            rows = frappe.get_all(
                dt,
                filters={"supplier": ["in", demo_suppliers]},
                fields=["name", "docstatus"],
            )
        except Exception:
            continue
        for row in rows:
            try:
                doc = frappe.get_doc(dt, row.name)
                if doc.docstatus == 1:
                    doc.cancel()
                doc.delete(ignore_permissions=True)
            except Exception:
                pass
