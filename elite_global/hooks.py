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
# Only schema-level fixtures here — Custom Fields, Workspace, Number
# Cards, Dashboard Charts. All master/seed data (UOMs, Item / Customer /
# Supplier Groups, Items, Suppliers, Customers, Warehouses) is created
# imperatively in `setup/install.py` so that ordering & company / type
# dependencies can be enforced explicitly.
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [["name", "like", "%-custom_variance_%"]],
    },
    {
        "dt": "Custom Field",
        "filters": [["name", "like", "%-custom_bid_%"]],
    },
    "Workspace",
    "Number Card",
]

# ── After-install hook ────────────────────────────────────────────────
# Runs once per site when the app is installed. We use it to bootstrap
# the Elite Global Company and any company-scoped defaults that can't be
# captured cleanly via JSON fixtures.
after_install = "elite_global.setup.install.after_install"

# ── After-migrate hook ────────────────────────────────────────────────
# Runs on `bench migrate` (and therefore on every Frappe Cloud site
# update). Keeps idempotent helpers like the Stock-by-Warehouse chart
# self-healing — they detect a stale/broken row and recreate.
after_migrate = "elite_global.setup.install.after_migrate"

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
