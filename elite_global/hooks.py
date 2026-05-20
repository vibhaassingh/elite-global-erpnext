"""
Frappe hooks for the Elite Global Enterprises ERPNext custom app.

Reference: https://frappeframework.com/docs/user/en/python-api/hooks
"""

app_name = "elite_global"
app_title = "Elite Global"
app_publisher = "Kerning AI"
app_description = (
    "Elite Global Enterprises — Refined Oil Distribution & C&F — ERPNext "
    "customisations and demo seed."
)
app_email = "hello@kerning.ooo"
app_license = "MIT"
required_apps = ["frappe", "erpnext"]

# ── Fixtures ───────────────────────────────────────────────────────────
# Records exported into JSON files under `elite_global/fixtures/` and
# re-imported on `bench migrate` / `bench install-app`. Used here for
# Custom Fields and master data the demo depends on.
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [["name", "like", "%-custom_variance_%"]],
    },
    {
        "dt": "Custom Field",
        "filters": [["name", "like", "%-custom_bid_%"]],
    },
    {"dt": "UOM", "filters": [["name", "in", ["Tin", "Jar", "Pouch"]]]},
    {"dt": "Warehouse", "filters": [["warehouse_name", "like", "Elite%"]]},
    {"dt": "Supplier Group", "filters": [["name", "like", "Refined Oil%"]]},
    {"dt": "Customer Group", "filters": [["name", "like", "Refined Oil%"]]},
    {"dt": "Item Group", "filters": [["name", "like", "Refined%"]]},
    {"dt": "Item", "filters": [["item_code", "like", "EG-%"]]},
    {"dt": "Supplier", "filters": [["supplier_name", "like", "%(EG)"]]},
    {"dt": "Customer", "filters": [["customer_name", "like", "%(EG)"]]},
    "Workspace",
    "Number Card",
    "Dashboard Chart",
]

# ── After-install hook ────────────────────────────────────────────────
# Runs once per site when the app is installed. We use it to bootstrap
# the Elite Global Company and any company-scoped defaults that can't be
# captured cleanly via JSON fixtures.
after_install = "elite_global.setup.install.after_install"

# ── DocType events ────────────────────────────────────────────────────
# Auto-flag variance on Purchase Receipt save if any line shows a
# quantity, rate or unit mismatch against the linked Purchase Order.
doc_events = {
    "Purchase Receipt": {
        "validate": "elite_global.setup.variance.auto_flag_variance",
    },
}

# ── Branding ──────────────────────────────────────────────────────────
# Show "Elite Global" in the navbar of the demo site.
website_context = {
    "favicon": "/assets/elite_global/favicon.ico",
    "splash_image": "/assets/elite_global/splash.png",
}
