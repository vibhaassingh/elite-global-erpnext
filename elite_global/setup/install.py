"""
After-install hook for the Elite Global ERPNext app.

Creates the Elite Global Enterprises Company if it's not already present
and sets a few company-scoped defaults that can't be set via JSON fixtures
(because they reference Account / Cost Center rows the fixtures don't
control).

This runs exactly once when `bench install-app elite_global` is executed
on a site.
"""

from __future__ import annotations

import frappe


COMPANY_NAME = "Elite Global Enterprises"
COMPANY_ABBR = "EGE"
COMPANY_DEFAULT_CURRENCY = "INR"
COMPANY_COUNTRY = "India"


def after_install() -> None:
    """Entry point invoked by Frappe after `install-app elite_global`."""
    _ensure_company()
    _ensure_credit_limits()
    frappe.db.commit()


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
    frappe.msgprint(f"Created Company: {COMPANY_NAME}")


def _ensure_credit_limits() -> None:
    """
    Seed the demo credit positions. Sharma Trading stays released;
    Bansal Wholesale gets a tight limit so the credit-check screen
    can show a real block.

    Customer credit limits live on the `customer_credit_limit` child
    table; we use frappe.set_value via the document to keep ERPNext's
    validation hooks active.
    """
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
        # Wipe + set so this is idempotent across re-runs.
        cust.credit_limits = []
        cust.append(
            "credit_limits",
            {"company": COMPANY_NAME, "credit_limit": limit},
        )
        cust.save(ignore_permissions=True)
