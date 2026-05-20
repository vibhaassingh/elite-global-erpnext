"""
Public read-only API endpoints for diagnostic verification.

These are exposed without authentication on purpose — they return
counts and presence flags only (no sensitive data) so we can
confirm that after_install and the demo seeder ran correctly on a
freshly-installed site without needing to log in as Administrator.

Remove or restrict in production.
"""

from __future__ import annotations

import frappe


@frappe.whitelist(allow_guest=True)
def demo_status() -> dict:
    """Return counts of the demo records the after_install hook should
    have created. Hit at:
        /api/method/elite_global.api.demo_status
    """
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
