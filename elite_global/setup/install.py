"""
After-install hook for the Elite Global ERPNext app.

This runs once when `bench install-app elite_global` succeeds on a
site. It bootstraps everything that needs an explicit ordering — first
the Company, then UOMs / groups, then Items / Suppliers / Customers /
Warehouses, finally the per-customer credit limits.

All of this used to be JSON fixtures, but fixtures load in arbitrary
order and ahead of the `after_install` hook — which means Warehouse
records that reference a Company or Warehouse Type that doesn't exist
yet will fail with `LinkValidationError`. Doing it in Python keeps the
dependency chain deterministic.
"""

from __future__ import annotations

import frappe


COMPANY_NAME = "Elite Global Enterprises"
COMPANY_ABBR = "EGE"
COMPANY_DEFAULT_CURRENCY = "INR"
COMPANY_COUNTRY = "India"


def after_install() -> None:
    """
    Entry point invoked by Frappe after `install-app elite_global`.

    The master data (Company, UOMs, groups, items, suppliers, customers,
    warehouses, credit limits) is set up imperatively here so the
    ordering is explicit.

    The transactional demo data — RFQ + Supplier Quotations + PO + PR
    with variance + Sales Orders — is also loaded as part of install
    via `elite_global.setup.demo.install_demo()`. That helper is
    idempotent: re-running it deletes any prior demo rows before
    re-inserting, so it remains safe to call from
    `bench --site <site> execute elite_global.setup.demo.install_demo`
    after each code change.

    Demo data load failures don't break the install — we log and
    continue so the site stays usable even if a sample doc trips a
    validation we haven't caught yet.
    """
    _ensure_company()
    _ensure_uoms()
    _ensure_supplier_groups()
    _ensure_customer_groups()
    _ensure_item_groups()
    _ensure_items()
    _ensure_suppliers()
    _ensure_customers()
    _ensure_warehouses()
    _ensure_credit_limits()
    frappe.db.commit()

    # Seed transactional demo. Wrapped so install still succeeds if a
    # sample doc fails — the demo helper is rerunnable from the bench.
    try:
        from elite_global.setup.demo import install_demo
        install_demo()
        frappe.db.commit()
    except Exception:  # noqa: BLE001 — log and continue
        frappe.log_error(
            title="elite_global · demo seed failed during install",
            message=frappe.get_traceback(),
        )


# ── Company ─────────────────────────────────────────────────────────────

def _ensure_company() -> None:
    if frappe.db.exists("Company", COMPANY_NAME):
        return
    company = frappe.new_doc("Company")
    company.update(
        {
            "company_name": COMPANY_NAME,
            "abbr": COMPANY_ABBR,
            "default_currency": COMPANY_DEFAULT_CURRENCY,
            "country": COMPANY_COUNTRY,
            "domain": "Distribution",
            "chart_of_accounts": "Standard with Numbers",
            "create_chart_of_accounts_based_on": "Standard Template",
        }
    )
    company.insert(ignore_permissions=True)


# ── UOMs ────────────────────────────────────────────────────────────────

def _ensure_uoms() -> None:
    for u in ("Tin", "Jar", "Pouch"):
        if frappe.db.exists("UOM", u):
            continue
        doc = frappe.new_doc("UOM")
        doc.uom_name = u
        doc.must_be_whole_number = 1
        doc.enabled = 1
        doc.insert(ignore_permissions=True)


# ── Groups (Supplier / Customer / Item) ────────────────────────────────

def _ensure_supplier_groups() -> None:
    _ensure_simple_group(
        "Supplier Group",
        name="Refined Oil Principal",
        parent="All Supplier Groups",
    )


def _ensure_customer_groups() -> None:
    for name in ("Refined Oil Distributor", "Refined Oil Retailer", "Refined Oil Institutional"):
        _ensure_simple_group(
            "Customer Group", name=name, parent="All Customer Groups"
        )


def _ensure_item_groups() -> None:
    _ensure_simple_group(
        "Item Group", name="Refined Edible Oils", parent="All Item Groups"
    )


def _ensure_simple_group(doctype: str, *, name: str, parent: str) -> None:
    if frappe.db.exists(doctype, name):
        return
    parent_field = {
        "Supplier Group": "parent_supplier_group",
        "Customer Group": "parent_customer_group",
        "Item Group": "parent_item_group",
    }[doctype]
    name_field = {
        "Supplier Group": "supplier_group_name",
        "Customer Group": "customer_group_name",
        "Item Group": "item_group_name",
    }[doctype]
    doc = frappe.new_doc(doctype)
    doc.update({name_field: name, parent_field: parent, "is_group": 0})
    doc.insert(ignore_permissions=True)


# ── Items ───────────────────────────────────────────────────────────────

ITEMS = [
    ("EG-RSFO-15KG-TIN", "Refined Sunflower Oil · 15 kg tin", "Tin", 1485),
    ("EG-RSFO-15L-JAR", "Refined Sunflower Oil · 15 L jar", "Jar", 1480),
    ("EG-RSFO-1L-POUCH", "Refined Sunflower Oil · 1 L pouch (case of 10)", "Pouch", 145),
    ("EG-RSBO-15KG-TIN", "Refined Soybean Oil · 15 kg tin", "Tin", 1410),
    ("EG-RMO-15KG-TIN", "Refined Mustard Oil · 15 kg tin", "Tin", 1680),
    ("EG-RPO-15KG-TIN", "Refined Palm Oil · 15 kg tin", "Tin", 1335),
    ("EG-RRBO-15KG-TIN", "Refined Rice Bran Oil · 15 kg tin", "Tin", 1520),
]


def _ensure_items() -> None:
    for code, name, uom, rate in ITEMS:
        if frappe.db.exists("Item", code):
            continue
        doc = frappe.new_doc("Item")
        doc.update(
            {
                "item_code": code,
                "item_name": name,
                "description": name,
                "item_group": "Refined Edible Oils",
                "stock_uom": uom,
                "is_stock_item": 1,
                "include_item_in_manufacturing": 0,
                "standard_rate": rate,
            }
        )
        doc.insert(ignore_permissions=True)


# ── Suppliers ───────────────────────────────────────────────────────────

SUPPLIERS = [
    ("Adani Wilmar Ltd. (EG)", "Principal — Mundra plant. Brands: Fortune. Scheme-driven dispatches; competitive on terms."),
    ("Marico Ltd. (EG)", "Principal — Jaipur depot. Brands: Saffola. Best plant discount on quick lifting."),
    ("Bunge India Pvt. Ltd. (EG)", "Principal — Haldia plant. Brands: Dalda. Rake dispatches, longest credit window."),
]


def _ensure_suppliers() -> None:
    for sname, details in SUPPLIERS:
        if frappe.db.exists("Supplier", sname):
            continue
        doc = frappe.new_doc("Supplier")
        doc.update(
            {
                "supplier_name": sname,
                "supplier_group": "Refined Oil Principal",
                "supplier_type": "Company",
                "country": "India",
                "default_currency": "INR",
                "supplier_details": details,
            }
        )
        doc.insert(ignore_permissions=True)


# ── Customers ──────────────────────────────────────────────────────────

CUSTOMERS = [
    ("Sharma Trading Co. (EG)", "Refined Oil Distributor", "Distributor — Karnal. Reliable payer. Credit position healthy."),
    ("Verma Kirana Stores (EG)", "Refined Oil Retailer", "Retailer — Sonipat. Small ticket, frequent off-take."),
    ("Bansal Wholesale (EG)", "Refined Oil Distributor", "Distributor — Panipat. Currently overdue on multiple invoices. Credit on hold."),
    ("Reliance Smart - Karnal (EG)", "Refined Oil Distributor", "Modern trade — Karnal store. Long PDC cycle but reliable."),
    ("Hotel Saffron Kitchens (EG)", "Refined Oil Institutional", "Institutional buyer — Delhi. Bulk tins on monthly contract."),
]


def _ensure_customers() -> None:
    for cname, group, details in CUSTOMERS:
        if frappe.db.exists("Customer", cname):
            continue
        doc = frappe.new_doc("Customer")
        doc.update(
            {
                "customer_name": cname,
                "customer_type": "Company",
                "customer_group": group,
                "territory": "All Territories",
                "country": "India",
                "default_currency": "INR",
                "customer_details": details,
            }
        )
        doc.insert(ignore_permissions=True)


# ── Warehouses ─────────────────────────────────────────────────────────

# (warehouse_name, warehouse_type) — types must exist; "Transit" ships with
# ERPNext as a standard Warehouse Type. Leaving warehouse_type blank for the
# standard godowns avoids unnecessary link validation.
WAREHOUSES = [
    ("Elite - Panipat Godown", None),
    ("Elite - Karnal Depot", None),
    ("Elite - Stock in Transit", "Transit"),
]


def _ensure_warehouses() -> None:
    # ERPNext's `Warehouse` doctype has `warehouse_type` defaulting to
    # "Transit". On a freshly-provisioned site the "Transit" Warehouse
    # Type record doesn't exist yet (it's normally created when the
    # Setup Wizard runs), so every Warehouse insert trips a
    # `LinkValidationError: Could not find Warehouse Type: Transit`
    # — even when we don't set the field. We create it ourselves
    # before any warehouse insert.
    if not frappe.db.exists("Warehouse Type", "Transit"):
        wt = frappe.new_doc("Warehouse Type")
        wt.name = "Transit"
        wt.insert(ignore_permissions=True)

    for wname, wtype in WAREHOUSES:
        if frappe.db.exists("Warehouse", f"{wname} - {COMPANY_ABBR}"):
            continue
        if frappe.db.exists("Warehouse", wname):
            continue
        doc = frappe.new_doc("Warehouse")
        doc.update(
            {
                "warehouse_name": wname,
                "is_group": 0,
                "company": COMPANY_NAME,
            }
        )
        if wtype:
            doc.warehouse_type = wtype
        doc.insert(ignore_permissions=True)


# ── Credit limits ──────────────────────────────────────────────────────

def _ensure_credit_limits() -> None:
    if not frappe.db.exists("Company", COMPANY_NAME):
        return
    targets = [
        ("Sharma Trading Co. (EG)", 1_000_000),
        ("Verma Kirana Stores (EG)", 250_000),
        ("Bansal Wholesale (EG)", 500_000),
        ("Reliance Smart - Karnal (EG)", 2_000_000),
        ("Hotel Saffron Kitchens (EG)", 750_000),
    ]
    for customer_name, limit in targets:
        if not frappe.db.exists("Customer", customer_name):
            continue
        cust = frappe.get_doc("Customer", customer_name)
        cust.credit_limits = []
        cust.append(
            "credit_limits",
            {"company": COMPANY_NAME, "credit_limit": limit},
        )
        cust.save(ignore_permissions=True)
