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


def after_migrate() -> None:
    """
    Idempotent self-heal helpers — run on every `bench migrate` (which
    Frappe Cloud invokes whenever a site is updated). Lets us push
    fixes for the Dashboard Chart / Custom Fields / etc. without
    requiring a fresh app install.

    Wrapped per-step so a single failing helper doesn't break the
    migration of unrelated changes.
    """
    for label, fn in [
        ("warehouse_types", _ensure_warehouse_types),
        ("root_groups", _ensure_root_groups),
        ("price_lists", _ensure_price_lists),
        ("stock_chart", _ensure_stock_chart),
        ("workspace_chart_attached", _ensure_workspace_chart_attached),
        ("hide_unused_workspaces", _hide_unused_workspaces),
        ("relabel_workspace", _relabel_workspace),
        ("setup_complete", _mark_setup_complete),
    ]:
        try:
            fn()
        except Exception:
            frappe.log_error(
                title=f"elite_global · after_migrate {label} failed",
                message=frappe.get_traceback(),
            )
    frappe.db.commit()


def after_install() -> None:
    """
    Entry point invoked by Frappe after `install-app elite_global`.

    Ordering matters here. On a freshly-provisioned Frappe Cloud site
    several ERPNext setup-wizard records don't exist yet:

      * Warehouse Type 'Transit' — needed because Company.on_update
        cascades into creating "<Company> - Stores in Transit"
        whose `warehouse_type` defaults to 'Transit'.
      * Root tree nodes 'All Supplier Groups', 'All Customer Groups',
        'All Item Groups', 'All Territories' — required as parents
        for our child group records.

    We create those first, then the Company, then everything else.
    """
    _ensure_warehouse_types()
    _ensure_root_groups()
    _ensure_price_lists()
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
    _ensure_stock_chart()
    _ensure_workspace_chart_attached()
    _hide_unused_workspaces()
    _relabel_workspace()
    _mark_setup_complete()
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


# ── Root tree nodes (must exist before any child group / territory) ───

def _ensure_root_groups() -> None:
    """
    ERPNext's setup wizard normally creates the root nodes for Supplier
    Group, Customer Group, Item Group and Territory ("All <X>"). On a
    freshly-provisioned site these are missing — so referencing them as
    parents in our child group inserts fails with LinkValidationError.

    We create them as root tree nodes (is_group=1, no parent) so our
    child records can hang off them.
    """
    roots = [
        ("Supplier Group", "All Supplier Groups", "supplier_group_name"),
        ("Customer Group", "All Customer Groups", "customer_group_name"),
        ("Item Group", "All Item Groups", "item_group_name"),
        ("Territory", "All Territories", "territory_name"),
    ]
    for doctype, root_name, name_field in roots:
        if frappe.db.exists(doctype, root_name):
            continue
        doc = frappe.new_doc(doctype)
        doc.update({name_field: root_name, "is_group": 1})
        doc.insert(ignore_permissions=True)


# ── Price Lists (Sales Order requires Standard Selling) ───────────────

def _ensure_price_lists() -> None:
    """Sales Order requires `selling_price_list`. The standard 'Standard
    Selling' / 'Standard Buying' price lists ship with ERPNext's setup
    wizard — but on a freshly-provisioned site they're absent."""
    for name, buying, selling in [
        ("Standard Selling", 0, 1),
        ("Standard Buying", 1, 0),
    ]:
        if frappe.db.exists("Price List", name):
            continue
        doc = frappe.new_doc("Price List")
        doc.price_list_name = name
        doc.currency = "INR"
        doc.buying = buying
        doc.selling = selling
        doc.enabled = 1
        doc.insert(ignore_permissions=True)


# ── Warehouse Types (must exist before Company is created) ────────────

def _ensure_warehouse_types() -> None:
    """
    Create the standard 'Transit' Warehouse Type. ERPNext normally
    creates it via Setup Wizard, but on a freshly-provisioned Frappe
    Cloud site the wizard hasn't run, so any code path that creates a
    Warehouse (including Company.on_update's default warehouses) fails
    with `LinkValidationError: Could not find Warehouse Type: Transit`.
    """
    if not frappe.db.exists("Warehouse Type", "Transit"):
        wt = frappe.new_doc("Warehouse Type")
        wt.name = "Transit"
        wt.insert(ignore_permissions=True)


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
    # Note: the 'Transit' Warehouse Type is created up-front in
    # `_ensure_warehouse_types()` so Company.on_update's default
    # warehouse cascade has it available. Nothing to do here.
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


# ── Stock-by-Warehouse Dashboard Chart ─────────────────────────────────

STOCK_CHART_NAME = "Refined Oil — Stock by Warehouse"


def _ensure_stock_chart() -> None:
    """
    Create the Dashboard Chart imperatively (avoiding fixtures, which
    failed `filters_json` mandatory validation).

    Field reference for the 'Stock Balance' report in ERPNext v15:
      * `from_date` / `to_date` — required range; default to last 12
        months so the bar chart has data.
      * `valuation_field_type` — required in v15 (this is the field
        Frappe rejects empty filters_json on).
      * `warehouse: ""` — empty = all warehouses; the bar chart's
        `x_field: warehouse` is what groups the bars.
      * `y_axis[].y_field: "bal_qty"` — Stock Balance's closing
        quantity column.
    """
    # If an earlier broken version exists (missing x_field / y_axis),
    # delete it so we can recreate with the correct render config.
    if frappe.db.exists("Dashboard Chart", STOCK_CHART_NAME):
        existing = frappe.db.get_value(
            "Dashboard Chart", STOCK_CHART_NAME, "x_field"
        )
        if existing:  # already correct, nothing to do
            return
        frappe.delete_doc(
            "Dashboard Chart", STOCK_CHART_NAME, ignore_permissions=True, force=True
        )

    import json as _json
    from frappe.utils import nowdate, add_months

    filters = {
        "company": COMPANY_NAME,
        "from_date": add_months(nowdate(), -12),
        "to_date": nowdate(),
        "warehouse": "",
        "valuation_field_type": "Currency",
    }

    try:
        chart = frappe.get_doc({
            "doctype": "Dashboard Chart",
            "chart_name": STOCK_CHART_NAME,
            "chart_type": "Report",
            "report_name": "Stock Balance",
            "type": "Bar",
            "module": "Elite Global",
            "is_public": 1,
            "timespan": "Last Year",
            "time_interval": "Monthly",
            "timeseries": 0,
            "filters_json": _json.dumps(filters),
            "x_field": "warehouse",
            "y_axis": [{"y_field": "bal_qty", "color": "#449CF0"}],
        })
        chart.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(
            title="elite_global · stock chart insert failed",
            message=frappe.get_traceback(),
        )


# ── Mark Setup Wizard complete ────────────────────────────────────────

def _mark_setup_complete() -> None:
    """
    The desk shows a "Setup Site" warning bar until System Settings.
    setup_complete = 1. Our after_install has already created the
    Company / Currency / Country / Domain — there's nothing left for
    the user to fill in. Set the flag so the warning disappears.
    """
    try:
        frappe.db.set_single_value("System Settings", "setup_complete", 1)
    except Exception:
        frappe.log_error(
            title="elite_global · mark setup_complete failed",
            message=frappe.get_traceback(),
        )


# ── Workspace hygiene (sidebar cleanup + rename) ──────────────────────

# Sidebar entries we hide from Mr. Arora's view. ERPNext ships a
# workspace per industry vertical & per internal operations module —
# none of them apply to a refined-oil distribution & C&F business, and
# they make the demo harder to read. We don't delete them (admins can
# unhide later if a workspace is ever wanted back), just flip the
# `is_hidden` flag so they drop out of the rendered sidebar.
HIDDEN_WORKSPACES = [
    # Industry verticals not relevant to refined-oil distribution
    "Manufacturing",
    "Healthcare",
    "Education",
    "Non Profit",
    "Agriculture",
    "Hospitality",
    "Hotels",
    "Restaurant",
    "Pharmaceutical",
    # Internal ops modules we're not running in the demo
    "Quality",
    "Loan Management",
    "Loans",
    "Support",
    "Assets",
    "Projects",
    "HR",
    "Payroll",
    # Frappe utility / onboarding modules
    "Build",
    "Welcome Workspace",
    "Marketplace",
    "Website",
    "Tools",
    "ERPNext Integrations",
]

WORKSPACE_NAME = "Elite Global"
WORKSPACE_LABEL = "Elite Global Enterprises"


def _hide_unused_workspaces() -> None:
    """
    Hide ERPNext workspaces irrelevant to a refined-oil distribution
    business. Keeps the Desk sidebar focused on Selling / Buying /
    Stock / Accounting / CRM and the custom Elite Global Enterprises
    workspace.

    Idempotent — safe to re-run on every `after_migrate`. We don't
    raise on missing workspaces (some only exist when their parent
    module is installed) and we don't raise on protected workspaces
    either — we just log and continue so one stubborn row doesn't
    break the rest of the chain.
    """
    for name in HIDDEN_WORKSPACES:
        if not frappe.db.exists("Workspace", name):
            continue
        try:
            frappe.db.set_value(
                "Workspace", name, "is_hidden", 1, update_modified=False
            )
        except Exception:
            frappe.log_error(
                title=f"elite_global · hide workspace {name} failed",
                message=frappe.get_traceback(),
            )


def _ensure_workspace_chart_attached() -> None:
    """
    Re-attach the Stock-by-Warehouse chart to the Elite Global workspace
    after fixture sync.

    Frappe's workspace fixture loader strips chart references that
    aren't backed by a separate fixture record. Our chart is created
    imperatively in `_ensure_stock_chart` (not a JSON fixture), so the
    workspace's `charts` child table row and the `ch1` content block
    get dropped on every migrate — leaving the chart record itself in
    place but invisible on the workspace page.

    This helper re-attaches both the link-table row and the content
    block, idempotently. Runs after `_ensure_stock_chart` so the chart
    record is guaranteed to exist before we reference it. Number cards
    survive fixture sync because they're declared as a fixture
    (`Number Card` in hooks.py), but the chart isn't — adding the chart
    as a fixture would require checking in its JSON, which we deliberately
    avoid since the chart is constructed imperatively to match the
    company name & date range.
    """
    if not frappe.db.exists("Workspace", WORKSPACE_NAME):
        return
    if not frappe.db.exists("Dashboard Chart", STOCK_CHART_NAME):
        return

    import json as _json

    ws = frappe.get_doc("Workspace", WORKSPACE_NAME)

    # Re-attach the chart row in the `charts` child table
    has_chart_link = any(
        c.chart_name == STOCK_CHART_NAME for c in (ws.charts or [])
    )
    if not has_chart_link:
        ws.append(
            "charts",
            {"chart_name": STOCK_CHART_NAME, "label": "Stock by warehouse"},
        )

    # Re-attach the `ch1` content block. We insert it (plus a leading
    # spacer) just before the `ql` Walkthrough header so the rendered
    # layout matches the original JSON: number cards → spacer → chart
    # → spacer → walkthrough.
    content = _json.loads(ws.content or "[]")
    # Match on either the short label ("Stock by warehouse") or the
    # full record name (in case an older deploy left the previous block
    # shape on disk). Either form means we don't need to re-insert.
    has_ch1 = any(
        b.get("type") == "chart"
        and b.get("data", {}).get("chart_name")
        in (STOCK_CHART_NAME, "Stock by warehouse")
        for b in content
    )
    if not has_ch1:
        ql_idx = next(
            (i for i, b in enumerate(content) if b.get("id") == "ql"),
            len(content),
        )
        # The content's `chart_name` must match the link table's `label`
        # field, NOT the Dashboard Chart's actual record name. Frappe's
        # workspace JS `make()` looks up the linked widget by
        # `obj.label`, so a mismatch silently drops the block.
        content.insert(
            ql_idx,
            {
                "id": "ch1",
                "type": "chart",
                "data": {"chart_name": "Stock by warehouse", "col": 12},
            },
        )
        content.insert(
            ql_idx,
            {"id": "sp2", "type": "spacer", "data": {"col": 12}},
        )
        ws.content = _json.dumps(content)

    if not has_chart_link or not has_ch1:
        ws.save(ignore_permissions=True)


def _relabel_workspace() -> None:
    """
    Update the sidebar label of the custom workspace to the full
    client name ("Elite Global Enterprises"). The workspace primary
    key stays "Elite Global" so existing references in number cards,
    shortcuts and the dashboard chart don't break — we only touch the
    user-visible `label` and `title` fields.

    Idempotent — runs on every `after_migrate`. Reads cheaply via
    `frappe.db.exists` before writing.
    """
    if not frappe.db.exists("Workspace", WORKSPACE_NAME):
        return
    try:
        frappe.db.set_value(
            "Workspace",
            WORKSPACE_NAME,
            {"label": WORKSPACE_LABEL, "title": WORKSPACE_LABEL},
            update_modified=False,
        )
    except Exception:
        frappe.log_error(
            title="elite_global · relabel workspace failed",
            message=frappe.get_traceback(),
        )
