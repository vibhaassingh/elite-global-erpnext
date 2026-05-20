# Elite Global Enterprises — ERPNext Custom App

> **Client:** Elite Global Enterprises · Refined Oil Distribution & C&F · India
> **Proprietor:** Mr. Saurabh Arora
> **Status:** Phase 0 — clickable demo on dummy data
> **Reference:** Kerning AI proposal `K-PRO-2026-SA-002`

This is a Frappe custom app that turns a vanilla ERPNext v15 site into the
**Elite Global Enterprises** demo environment. It does not fork ERPNext —
it layers a thin set of fixtures, custom fields, a workspace and a small
setup script on top of the standard ERPNext bid → purchase → receive → sell
→ collect loop.

## What the demo covers

| Step | ERPNext primitive | Custom layer |
|---|---|---|
| **01 · Bid Manager** | Supplier Quotation against an RFQ | Demo data: 3 vendors bidding on the same RFQ for refined sunflower oil. |
| **02 · Sales Deal Booking** | Sales Order | Customer master with realistic distributor / retailer types. |
| **03 · Goods Arrival + Unit Mgmt** | Purchase Receipt vs Purchase Order | Custom fields on Purchase Receipt: `variance_kind`, `variance_note`, `variance_flagged`. |
| **04 · Automated Credit Check** | Built-in `Customer.credit_limit` + Sales Order check | Customers seeded with realistic credit limits and overdue positions. |
| **05 · Management Dashboard** | Workspace + Number Cards + Charts | Custom `Elite Global` workspace surfacing all of the above. |

## Why ERPNext rather than a custom build

The proposal commits ERP modules (purchase, sales, inventory, dispatch,
billing, freight, dashboard) plus an AI overlay. Every one of those is
already a first-class concept in ERPNext. Building on top of it means we
ship the demo in days, not months — and the production system inherits a
mature, open-source, well-supported backbone.

## Repo layout

```
elite-global-erpnext/
├── elite_global/                # the Frappe app
│   ├── __init__.py              # __version__
│   ├── hooks.py                 # entry point — fixtures, install hooks, etc.
│   ├── modules.txt              # list of modules in this app
│   ├── patches.txt              # migration patches (empty)
│   ├── elite_global/            # module dir (matches modules.txt)
│   │   ├── doctype/             # any custom DocTypes
│   │   └── workspace/           # custom Workspaces
│   ├── fixtures/                # JSON seed data (Custom Fields, masters)
│   ├── setup/                   # Python helpers run on install
│   ├── public/                  # static assets
│   └── templates/               # web view templates (if any)
├── docs/
│   └── frappe-cloud-deploy.md   # how to deploy this to Frappe Cloud
├── pyproject.toml               # app metadata
├── license.txt
└── README.md                    # you are here
```

## Quick start — Frappe Cloud (preferred for the client demo)

The fastest path to a shareable URL for Mr. Arora is Frappe Cloud:

1. Push this repo to a private GitHub repo (e.g. `kerning-ai/elite-global-erpnext`).
2. In Frappe Cloud → **Benches** → create a new Private Bench on ERPNext v15.
3. **Apps** → Add App → install from this GitHub repo (Frappe Cloud will ask
   for repo access).
4. Deploy the bench (one-click).
5. **Sites** → New Site, pick the bench above, install `erpnext` + `elite_global`.
6. After site is live, run `bench --site <site> execute elite_global.setup.demo.install_demo`
   from the Frappe Cloud SSH console — this seeds the transactional demo
   data (supplier quotations, sample SO, sample PR with variance).
7. Share the site URL with the client. Login: `Administrator` (initial
   password set during site creation).

Full step-by-step including screenshots / gotchas: see
[`docs/frappe-cloud-deploy.md`](docs/frappe-cloud-deploy.md).

## Quick start — Local bench (for development)

Requires [`bench`](https://github.com/frappe/bench) installed locally.

```sh
# in your benches/ directory
bench init --frappe-branch version-15 elite-bench
cd elite-bench

bench new-site elite.localhost --admin-password admin
bench get-app erpnext --branch version-15
bench get-app /Users/vibhaassingh/elite-global-erpnext   # or git URL
bench --site elite.localhost install-app erpnext elite_global

bench --site elite.localhost execute elite_global.setup.demo.install_demo
bench start
```

Open `http://elite.localhost:8000` and log in as `Administrator`.

## What's seeded

- **Company:** Elite Global Enterprises (INR)
- **Warehouses:** Panipat godown, Karnal depot, Stock in Transit
- **Suppliers:** Adani Wilmar (Fortune), Marico (Saffola), Bunge (Dalda) — all
  with addresses, GSTIN, payment terms.
- **Items:** Refined Sunflower Oil (15kg tin, 15L jar, 1L pouch), Refined
  Soybean Oil, Refined Mustard Oil, Refined Palm Oil, Refined Rice Bran Oil.
- **Customers:** Sharma Trading Co. (released), Bansal Wholesale (blocked
  by credit overdue), Reliance Smart — Karnal, Hotel Saffron Kitchens.
- **Transactions:**
  - 1 RFQ with 3 Supplier Quotations attached (Bid Manager screen).
  - 1 submitted Purchase Order against the winning quote.
  - 1 Purchase Receipt against the PO with 3 lines flagged as variances
    (quantity, rate, unit).
  - 2 Sales Orders — one releases, one trips the credit block.
- **Workspace:** "Elite Global" with five number cards mapped to the demo
  steps, plus quick links and a stock-by-warehouse chart.

## License

MIT — see `license.txt`. Demo data is illustrative and references public
brand names only as recognisable category placeholders.
