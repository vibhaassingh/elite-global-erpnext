# Frappe Cloud deploy — Elite Global Enterprises demo

This runbook deploys the `elite_global` custom app to a fresh Frappe Cloud
site running ERPNext v15 so Mr. Saurabh Arora has a shareable URL for the
Phase 0 walkthrough.

## 0 · Prerequisites

- A [Frappe Cloud](https://frappecloud.com/) account.
- A private GitHub repo to host this code (Frappe Cloud reads from GitHub).
- Repo is at: `https://github.com/<your-org>/elite-global-erpnext`.
- Card on file in Frappe Cloud — the cheapest **Private Bench** + **Site**
  combo runs ~USD 25 / month at the time of writing. Free trial covers the
  first ~14 days.

## 1 · Push the app to GitHub

From this repo on your machine:

```sh
cd /Users/vibhaassingh/elite-global-erpnext
git remote add origin git@github.com:<your-org>/elite-global-erpnext.git
git push -u origin main
```

In Frappe Cloud → **Settings → GitHub Connections**, authorise the GitHub
account so Frappe Cloud can pull this private repo.

## 2 · Create a Private Bench on ERPNext v15

1. Frappe Cloud → **Benches → New Bench**.
2. Pick:
   - **Frappe Branch:** `version-15`.
   - **ERPNext Branch:** `version-15`.
3. **Apps → Add App → GitHub** → pick `elite-global-erpnext`, branch `main`.
4. **Deploy** the bench. First deploy takes ~10–15 minutes (clones repos,
   builds assets, runs migrations).

## 3 · Create the demo site

1. Frappe Cloud → **Sites → New Site**.
2. Pick the bench you just created.
3. **Subdomain:** `elite-global` (full URL becomes `elite-global.frappe.cloud`
   — adjust if taken).
4. **Apps to install:** `frappe`, `erpnext`, `elite_global`.
5. Set the **Administrator** password — keep it handy; you'll log in with it.
6. **Create Site**.

When the site is up, log in at `https://<your-subdomain>.frappe.cloud` as
`Administrator`.

> **Tip:** On first login ERPNext launches the **Setup Wizard**. Skip
> through it — the `elite_global` app's `after_install` hook has already
> created the `Elite Global Enterprises` Company with `INR` currency, and
> the wizard's choices will only get overwritten.

## 4 · Seed the transactional demo data

The fixtures (suppliers, customers, items, custom fields, workspace) load
automatically on install. The **submitted transactional rows** — bids, PO,
PR with variance, sales orders — are seeded via a one-shot Python helper.

From Frappe Cloud → **Sites → <your site> → Console → Bench Console**:

```python
import elite_global.setup.demo as demo
demo.install_demo()
```

You should see a green toast: *"Elite Global demo seeded."*

The helper is **idempotent** — re-running deletes prior demo rows
(everything tagged with `[demo · elite_global]` in remarks) before
re-inserting. Safe to run after any code update.

## 5 · Verify the walkthrough

Click through the five steps the same way Mr. Arora will:

| Step | Where in the UI |
|---|---|
| **01 · Bid Manager** | Sidebar → **Buying** → **Supplier Quotation** — three submitted quotes against the same RFQ are visible. |
| **02 · Sales Deal Booking** | Sidebar → **Selling** → **Sales Order** — open the Bansal Wholesale draft; the credit block fires on Submit. |
| **03 · Goods Arrival + Unit Mgmt** | Sidebar → **Stock** → **Purchase Receipt** — open the demo Draft; three lines show variance kinds (qty / rate / unit). |
| **04 · Credit Check** | Sidebar → **Selling** → **Customer** → Bansal Wholesale — credit limit + outstanding visible; or trigger from step 02. |
| **05 · Management Dashboard** | Top navbar → workspace switcher → **Elite Global** — four number cards + stock chart + step shortcuts. |

## 6 · Share with the client

Once verified, share `https://<your-subdomain>.frappe.cloud` with Mr. Arora
plus a temporary login (use a fresh user, not Administrator):

```python
# from the same Bench Console
import frappe
user = frappe.new_doc("User")
user.update({
    "email": "saurabh@eliteglobal.example",
    "first_name": "Saurabh",
    "last_name": "Arora",
    "send_welcome_email": 0,
    "new_password": "<choose-a-password>",
    "roles": [{"role": "System Manager"}],  # demo-only; tighten post-demo
})
user.insert(ignore_permissions=True)
frappe.db.commit()
```

(For post-demo / production we will replace `System Manager` with a
purpose-built role profile — out of scope for Phase 0.)

## 7 · Iterating

Every code change → commit → push to `main` → Frappe Cloud picks it up
automatically and you click **Update** on the bench. Migrations and
fixture re-imports run as part of the update. For transactional reseed,
re-run `demo.install_demo()` in the Bench Console.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Custom Field` already exists | Fixtures upsert by `name`. If you renamed a fieldname, you'll need to delete the stale Custom Field from the UI once. |
| Workspace doesn't show | Sidebar → click your user avatar → **Reload**. Workspaces are cached per-user. |
| Credit block doesn't fire on Bansal SO | Confirm `_ensure_credit_limits()` ran (sidebar → Customer → Bansal Wholesale → Credit Limits). Re-run `after_install` via the console if needed. |
| Variance flag not auto-setting | Check `doc_events` is wired in `hooks.py` and `bench --site <s> migrate` has been run since the last code change. |
