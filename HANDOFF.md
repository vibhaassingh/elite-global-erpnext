# Elite Global Enterprises — Engagement Handoff

**Client:** Mr. Saurabh Arora, Proprietor — Elite Global Enterprises (Refined Oil Distribution & C&F)
**Engagement:** K-PRO-2026-SA-002 · Phase 0 (clickable ERPNext demo + plain-English client guide)
**Delivered by:** Kerning AI · Hemco Group
**Last updated:** 2026-05-21

This is the cold-start document. If you've never touched this engagement, read this top to bottom and you'll be able to operate, repair, and extend both deliverables.

---

## 1. What was delivered

| # | Deliverable | What it is | Lives at |
|---|---|---|---|
| 1 | **ERPNext system** | A Frappe v15 / ERPNext v15 site with a custom app (`elite_global`) that seeds master + transactional demo data, a trimmed sidebar, a custom workspace, and a 5-step refined-oil C&F walkthrough. | https://eliteglobal.kerningai.eu |
| 2 | **Client guide** | A standalone Next.js webpage that explains the ERP in plain English — every module, where AI helps, the daily flow, glossary. Built for a layman to self-serve. | https://guideeliteglobal.kerningai.eu |

Both are **client-ready and live**. The WhatsApp cover message handing these to Mr. Arora has been drafted (ask Aditya for the copy).

---

## 2. Access & URLs — the reference table

| Thing | Value |
|---|---|
| **Live ERP (custom domain)** | https://eliteglobal.kerningai.eu |
| ERP underlying host | `elite-global.m.frappe.cloud` (Frappe Cloud) |
| **Live guide** | https://guideeliteglobal.kerningai.eu |
| ERP source repo | `github.com/vibhaassingh/elite-global-erpnext` (private) · branch `main` |
| Guide source | `~/elite-global-guide` (local) · deployed via Vercel CLI |
| Frappe Cloud bench | `bench-40431` — "Elite Global" — Mumbai region |
| Frappe Cloud dashboard | cloud.frappe.io → Benches → Elite Global |
| Vercel team | `kerning-ooo` ("Kerning's Projects") |
| Vercel project | `elite-global-guide` |

### Apps on the bench
| App | Repo | Branch | Notes |
|---|---|---|---|
| frappe | frappe/frappe | version-15 | framework (v15.108.0) |
| erpnext | frappe/erpnext | version-15 | core ERP |
| **elite_global** | vibhaassingh/elite-global-erpnext | main | **our custom app** |
| erpnext_germany | alyf-de/erpnext_germany | version-15 | (came with the bench template; harmless) |

---

## 3. Login & credentials

| Field | Value |
|---|---|
| Client login email | **pathcare94@gmail.com** |
| Client name on account | Saurabh Arora |
| Roles | System Manager + Sales / Purchase / Stock / Accounts Manager (full demo access) |
| Password | **Not set by us.** Client sets their own via *Forgot Password?* at the login screen. |

**First-time login flow (this is what the guide tells the client):**
1. Open https://eliteglobal.kerningai.eu
2. Click **Forgot Password?**
3. Enter `pathcare94@gmail.com`
4. Click the reset link emailed to that inbox (check spam)
5. Set a password → you're in

**Admin fallback:** the Frappe Cloud dashboard → site → ⋯ → **Login As Administrator** generates a one-shot SSO link that bypasses passwords entirely. Use this if the client's reset email fails or you need superuser access fast.

> Security note: we never set or share passwords. The client owns their own credential via the reset flow. Do not paste passwords into chat.

---

## 4. ERP architecture — how the custom app works

The custom app is **`elite_global`**. Everything it does is **idempotent and self-healing** — a fresh `bench install-app` and any future `bench migrate` both converge to the same correct state. This was a hard design constraint because Frappe Cloud re-runs migrate on every deploy.

### Entry points (`hooks.py`)
- `after_install` → one-time full bootstrap on first install
- `after_migrate` → runs the self-healing helper chain on **every** deploy
- `doc_events: Purchase Receipt.validate` → `variance.auto_flag_variance`
- `fixtures` → Custom Fields (variance + bid), Workspace, Number Card

### The self-healing helper chain (`setup/install.py`, runs on every migrate)
| Helper | Why it exists |
|---|---|
| `_ensure_warehouse_types` | ERPNext defaults a "Transit" warehouse type that doesn't exist on a fresh site → LinkValidationError without this |
| `_ensure_root_groups` | Creates "All Supplier/Customer/Item Groups" + "All Territories" tree roots |
| `_ensure_price_lists` | Standard Selling / Standard Buying (Sales Orders require a selling price list) |
| `_ensure_stock_chart` | Builds the "Stock by warehouse" Group-By chart over Stock Ledger Entry |
| `_ensure_workspace_chart_attached` | Re-attaches the chart to the workspace — Frappe's fixture loader strips chart refs that aren't a separate fixture record |
| `_normalize_workspace_content` | Rewrites content blocks so `number_card_name` / `chart_name` match the link-table **label** (Frappe looks widgets up by label, not record name — mismatch = silently dropped block) |
| `_hide_unused_workspaces` | Hides ~23 irrelevant ERPNext verticals/modules from the sidebar |
| `_relabel_workspace` | Keeps the workspace title = "Elite Global Enterprises" |
| `_mark_setup_complete` | Dismisses the ERPNext setup-wizard nag bar |

### Master data created (`setup/install.py`)
- **Company:** Elite Global Enterprises (abbr EGE, INR, India), FY 2026-04-01 → 2027-03-31
- **5 customers** with credit limits: Sharma ₹10L · Verma ₹2.5L · **Bansal ₹2L (tight, trips the credit demo)** · Reliance ₹20L · Saffron ₹7.5L
- **3 suppliers:** Adani Wilmar, Marico, Bunge (all "(EG)")
- **7 items** (refined oils — sunflower, soybean, mustard, palm, rice bran in tin/jar/pouch)
- **3 warehouses:** Panipat Godown, Karnal Depot, Stock in Transit
- Custom UOMs: Tin, Jar, Pouch

### Transactional demo (`setup/demo.py`)
Wiped & reseeded idempotently. Produces:
- 1 RFQ → 3 Supplier Quotations (Marico cheapest) → 1 Purchase Order
- **2 Purchase Receipts:** one submitted-clean (sunflower → feeds the stock chart), one draft-with-variance (soybean qty + mustard rate → feeds the walkthrough)
- **2 Sales Orders:** Sharma (submitted, clean) + Bansal (draft, trips the ₹2L credit block on submit)

### Variance engine (`setup/variance.py`)
On every Purchase Receipt save, compares each line to the linked PO. Sets `custom_variance_flagged`, `custom_variance_kind` (Quantity / Rate / Unit / Multiple) and per-line variance. 0.5% tolerance.

---

## 5. The 5-step walkthrough (what the client demos)

| Step | Sidebar shortcut | DocType | The "wow" |
|---|---|---|---|
| 01 | Bid Manager | Supplier Quotation | 3 bids side-by-side, auto-scored best-on-price / best-on-terms |
| 02 | Sales Deal Booking | Sales Order | Books a customer order; credit check fires on submit |
| 03 | Goods Arrival | Purchase Receipt | Draft receipt auto-flagged: soybean = Quantity variance, mustard = Rate variance |
| 04 | Credit Check | Customer | Submitting Bansal's ₹2.97L order is **blocked** (limit ₹2L), names Saurabh as approver |
| 05 | Dashboard | Workspace | 4 number cards + live stock-by-warehouse chart roll everything up |

Home base: the **Elite Global Enterprises** workspace (left sidebar).

---

## 6. Operations — redeploy, reseed, repair

### Redeploy the ERP app (after a code change)
1. `git push origin main`
2. Frappe Cloud dashboard → Benches → Elite Global → **Apps** → ⋯ on "Elite Global" → **Fetch Latest Updates**
3. Top-right **Update Available** → tick the app → **Next** → tick the site → **Deploy and update site**
4. ~5–7 min (bench rebuild + site migrate). The migrate auto-runs the self-healing chain.

### Reset the demo data (System Manager only)
`GET/POST https://eliteglobal.kerningai.eu/api/method/elite_global.api.run_demo_seed`
Wipes prior demo rows and reseeds the full transaction set.

### Repair the workspace (if cards/chart vanish)
`GET https://eliteglobal.kerningai.eu/api/method/elite_global.api.repair_workspace`
Re-runs stock chart + chart-attach + content-normalize + relabel; returns post-state diagnostics.

### Check demo counts
`GET https://eliteglobal.kerningai.eu/api/method/elite_global.api.demo_status`

### Redeploy the guide
`cd ~/elite-global-guide && vercel --scope kerning-ooo --prod`
(package.json is pinned to a CVE-patched Next.js — don't downgrade.)

---

## 7. Known quirks & gotchas (read before you debug)

1. **Workspace `name` vs `title` vs URL.** Frappe v15 builds the workspace URL slug from `title`, but looks the record up by `name`. They must agree. The record is named **"Elite Global Enterprises"** (renamed via `frappe.rename_doc`, which cascaded all child-table parents). The fixture dir is `workspace/elite_global_enterprises/`. If you rename again, do all three: `rename_doc` on the live site, the JSON `name`, and the fixture dir.

2. **Module Def stays "Elite Global".** Every doctype in the app references `module = "Elite Global"`. We deliberately did **not** rename the Module Def (would cascade through every doctype JSON). Only the *workspace* is "Elite Global Enterprises".

3. **Workspace fixture sync is timestamp-gated.** Frappe skips re-importing a workspace if the JSON's `modified` is older than the DB's. **When you edit the workspace JSON, bump its `modified` timestamp** or the change won't sync on deploy. `_normalize_workspace_content` is the runtime safety net for this.

4. **Cancelled PR-2026-00001 can't be deleted.** It has a linked GL Entry (correct ERPNext audit behavior). It's harmless — the "Variance Flagged Receipts" number card filters `docstatus < 2` so cancelled docs don't inflate the count.

5. **Chart "No Data" is filter-dependent.** The stock chart reads Stock Ledger Entry. It only shows bars for warehouses with movement. The submitted clean PR (sunflower → Panipat) is what gives it data — if you wipe receipts without re-submitting one, the chart goes empty (expected).

6. **Diagnostic endpoints are System-Manager-gated** (`frappe.only_for`). Safe to leave on; a Guest or non-admin gets 403.

---

## 8. Commit history (this engagement, newest first)

| Commit | What |
|---|---|
| `723a1e6` | Rename workspace record → Elite Global Enterprises (fixes sidebar 404) |
| `b2dc76f` | Tighten Bansal credit limit to ₹2L so the credit-check demo fires |
| `c3aa2e1` | Variance card excludes cancelled docs |
| `cd470ec` | Split demo PR into submitted-clean + draft-variance |
| `09a3099` | Group-By chart over Stock Ledger Entry + Fiscal Year helper |
| `0d0f8a8` | Self-heal workspace content + bump fixture timestamp |
| `c2d2198` | Add `repair_workspace` diagnostic endpoint |
| `b6eb196` | Re-attach chart after fixture sync drops it |
| `5246092` | Sidebar cleanup (hide modules) + workspace rename |

---

## 9. What's next (per the proposal)

| Phase | Scope | Status |
|---|---|---|
| **Phase 0** | Clickable demo + client guide | ✅ **Delivered** (this doc) |
| Phase 1 | Production rollout — migrate real master data (customers, suppliers, items, opening stock) from Tally/Excel; real fiscal config; user accounts for the team | Pending client sign-off |
| Phase 2 | Mobile app wrap (Capacitor) so the team uses it on phones | Roadmap |
| Phase 3 | AI overlay — natural-language queries, demand forecasting, vendor-drift & margin alerts, anomaly detection (see the guide's "Coming next" section) | Roadmap |

---

## 10. First-week maintenance checklist

- [ ] Confirm Mr. Arora successfully logged in (ask him, or check User → last login)
- [ ] If his reset email never arrived, verify the site's outgoing email (Frappe Cloud → site → Mail) or send him a one-shot SSO link
- [ ] Leave the demo data as-is during his evaluation; only `run_demo_seed` if it gets messy
- [ ] Collect his feedback before starting Phase 1 (the guide invites him to WhatsApp screenshots)
- [ ] Custom domain `eliteglobal.kerningai.eu` is live; no DNS action needed unless it lapses

---

*Questions on any of this: the code is the source of truth — `setup/install.py` and `setup/demo.py` are heavily commented with the "why", not just the "what".*
