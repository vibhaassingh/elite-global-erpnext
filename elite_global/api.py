"""
Diagnostic API endpoints for the Elite Global demo.

These now require a System Manager session — the early-build version
allowed Guest access for unauthenticated verification, but that is
not safe to leave on a shareable demo URL. Hit these from the
ERPNext Desk after logging in as Administrator.
"""

from __future__ import annotations

import frappe


@frappe.whitelist()
def run_demo_seed() -> dict:
    """
    Run the transactional demo seeder explicitly. Hit at:
        /api/method/elite_global.api.run_demo_seed

    Requires System Manager — the decorator drops Guest, the body
    enforces the role server-side so any authenticated non-admin
    user gets 403.

    Returns either {"ok": true, "ran": "install_demo"} on success, or
    {"ok": false, "error": "<exception>", "traceback": "..."} on
    failure. Useful when after_install swallowed the demo seed call.
    """
    frappe.only_for("System Manager")
    try:
        from elite_global.setup.demo import install_demo
        install_demo()
        frappe.db.commit()
        return {"ok": True, "ran": "install_demo"}
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": frappe.get_traceback(),
        }


@frappe.whitelist()
def repair_workspace() -> dict:
    """
    Manually re-run the workspace self-heal helpers. Useful when
    after_migrate didn't pick the chart back up — calling this hits
    `_ensure_stock_chart`, `_ensure_workspace_chart_attached`,
    `_hide_unused_workspaces`, `_relabel_workspace` in order and returns
    the visible state of the workspace's `charts` link table + the
    chart-block presence in `content`.

    Returns either {"ok": true, ...state diagnostics...} or
    {"ok": false, "error": ..., "traceback": ...} on failure — so we
    can see exactly what the after_migrate try/except swallowed.

    Hit at: /api/method/elite_global.api.repair_workspace
    """
    frappe.only_for("System Manager")
    try:
        from elite_global.setup.install import (
            _ensure_stock_chart,
            _ensure_workspace_chart_attached,
            _hide_unused_workspaces,
            _relabel_workspace,
            WORKSPACE_NAME,
            STOCK_CHART_NAME,
        )
        _ensure_stock_chart()
        _ensure_workspace_chart_attached()
        _hide_unused_workspaces()
        _relabel_workspace()
        frappe.db.commit()

        # Read back the post-state so we can verify the fix landed
        import json as _json
        ws = frappe.get_doc("Workspace", WORKSPACE_NAME)
        chart_link_present = any(
            c.chart_name == STOCK_CHART_NAME for c in (ws.charts or [])
        )
        content_blocks = _json.loads(ws.content or "[]")
        chart_block_present = any(
            b.get("type") == "chart"
            and b.get("data", {}).get("chart_name") == STOCK_CHART_NAME
            for b in content_blocks
        )
        return {
            "ok": True,
            "ran": "repair_workspace",
            "label": ws.label,
            "title": ws.title,
            "chart_link_present": chart_link_present,
            "chart_block_present": chart_block_present,
            "content_block_ids": [b.get("id") for b in content_blocks],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": frappe.get_traceback(),
        }


@frappe.whitelist()
def demo_status() -> dict:
    """Return counts of the demo records the after_install hook should
    have created. Hit at:
        /api/method/elite_global.api.demo_status

    Requires System Manager (belt + suspenders: the decorator drops
    Guest, the body enforces the role).
    """
    frappe.only_for("System Manager")

    def count(doctype: str, filters: dict | list | None = None) -> int:
        try:
            return frappe.db.count(doctype, filters or {})
        except Exception as e:  # pragma: no cover
            return -1

    company_exists = frappe.db.exists("Company", "Elite Global Enterprises") is not None

    return {
        "company_present": company_exists,
        "uoms_eg": count("UOM", {"name": ["in", ["Tin", "Jar", "Pouch"]]}),
        "item_groups": count("Item Group", {"item_group_name": ["like", "Refined%"]}),
        "supplier_groups": count("Supplier Group", {"supplier_group_name": ["like", "Refined Oil%"]}),
        "customer_groups": count("Customer Group", {"customer_group_name": ["like", "Refined Oil%"]}),
        "items": count("Item", {"item_code": ["like", "EG-%"]}),
        "suppliers": count("Supplier", {"supplier_name": ["like", "%(EG)"]}),
        "customers": count("Customer", {"customer_name": ["like", "%(EG)"]}),
        "warehouses": count("Warehouse", {"warehouse_name": ["like", "Elite%"]}),
        "rfqs": count("Request for Quotation", {"message_for_supplier": ["like", "%demo · elite_global%"]}),
        "supplier_quotations": count("Supplier Quotation", {"remarks": ["like", "%demo · elite_global%"]}),
        "purchase_orders": count("Purchase Order", {"remarks": ["like", "%demo · elite_global%"]}),
        "purchase_receipts": count("Purchase Receipt", {"remarks": ["like", "%demo · elite_global%"]}),
        "sales_orders": count("Sales Order", {"remarks": ["like", "%demo · elite_global%"]}),
    }
