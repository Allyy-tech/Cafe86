# Secure Cafe Point of Sale System

A Flask cafe point-of-sale demo for staff sign-in, order checkout, sales
history, manager-approved voids, administration, and reporting. It uses
SQLite by default and can use MongoDB as its persistent store when
`MONGODB_URI` is set.

This is a project/demo system, not a payment processor. It does not verify
e-wallet payments, and it should not be used for real customer or business
records without a separate security and operational review.

## System overview

### People and workflows

- **Cashiers** sign in with a staff ID or optional email and PIN. They select
  menu items, quantities, Dine In or Take Out, and a payment method. Checkout
  recalculates prices on the server, records the sale, and provides a
  receipt. Cash change is calculated by the server.
- **Administrators** sign in with an email and password. They manage menu
  products and staff accounts, approve staff sign-up requests, view sales
  and audit history, approve voids using a manager PIN, and export reports
  to Excel.
- In **Catalog Management**, admins can add, replace, or remove a product
  image. PNG, JPG, and WEBP files up to 5 MB are accepted. Images appear in
  the catalog and on the cashier's menu; files are stored under
  `instance/product_images/` and are served only to signed-in users.
- Products can be archived from Catalog Management. Archived items leave the
  working catalog and cashier menu while their records, images, and past
  sales stay preserved. Admins can restore them from the **Archive** tab.
  Permanently deleting an archived product requires confirmation and is only
  allowed when no transaction line items refer to it, preserving sales history.
- **A first-run owner setup** creates the first admin. After an admin exists,
  that setup route closes; further accounts require an administrator.
- **Password recovery** sends an expiring one-time code to an admin's email
  when email settings are configured.

### Sales and records

For each sale, the app stores its cashier, date, totals, payment and service
type, status, and sync status. Each sold product's name, price, cost,
quantity, and line total are captured with the sale so later menu edits do
not change old receipts or profit calculations. Voids keep the original
sale and record who approved it, when, and why. Sensitive actions are
written to an append-only audit log.

The admin dashboard summarizes completed non-demo sales and shows product,
category, payment, and recent-sales information. Excel exports include
Transactions and Transaction Items sheets. Demo and voided records remain
identifiable in the export; dashboard totals exclude demo and voided sales.

### Database choices

- **SQLite mode** is the default. The app reads and writes `instance/cafe.db`.
- **MongoDB mode** is enabled by setting `MONGODB_URI`. MongoDB then stores
  the app's persistent records. Existing route queries currently run in an
  in-memory SQLite compatibility layer, which loads MongoDB records when a
  request starts and writes changed records back to MongoDB on commit.
  Transaction line items are embedded in their transaction documents.
  This mode is intended for one app process; it is not designed for multiple
  workers or multiple app servers.
- The SQLite-to-MongoDB import script copies the current local database and
  leaves the SQLite source intact. Import first, then launch the app with
  `MONGODB_URI` set to use the MongoDB copy.

### Internet status and the “Back up now” control

Checkout and receipt creation do not call the internet connectivity check.
The app has a pending/synced status field and an online indicator, but the
backup integration is currently a **simulation**: “Back up now” checks that
the internet is reachable, changes pending records to `synced`, and records
a `SYNC_COMPLETED` audit entry. It does not upload sales to MongoDB Atlas,
cloud storage, or any other off-site destination. It is a manual action;
automatic upload when the connection returns is not implemented. Do not
treat a `synced` status as proof of an external backup.

### Current scope and limits

- E-wallet checkout is only recorded; the app does not verify payment.
- Inventory tracking and stock deductions are not implemented.
- The backup/sync operation does not send data to an external service.
- Demo accounts and sample sales are for local demonstration only.

## Run locally

Requirements: Python 3.10 or newer and VS Code (optional).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5000>. On a fresh database, the sample menu and two
demo cashiers are created. Create the first administrator through **Set up
the owner account**. The demo staff credentials are for local testing only:

| Username | PIN |
|---|---|
| `cashier1` | `1428` |
| `cashier2` | `2637` |

Do not publish those demo accounts. Production WSGI startup disables demo
users by default.

## Sign-in and accounts

Admins and staff use the same sign-in page. Admins enter their username or
email and password; staff enter their username or optional email and PIN.
The login page includes an addition CAPTCHA, and admin password recovery is
available through a one-time email code. Public staff sign-up creates an
inactive account request; an administrator must approve it in **Account
Management** before the staff member can sign in.

The first admin is created through `/admin-setup`. After that, additional
accounts are created or approved by an existing admin. Staff PINs and admin
passwords are stored as hashes.

## POS features

- Menu grouped into Coffee Drinks, Freshie Drinks, Meals, and Pastry.
- Dine In and Take Out order types.
- Cash and e-wallet options in local development. The supplied InstaPay QR
  is served only to authenticated users from
  `private/instapay-merchant-qr.jpg`, outside the public static directory.
  Scanning or displaying it does not confirm payment.
- Receipts, today's sales, manager-approved voids, and an append-only audit
  log.
- Dashboard summary and most-ordered products.
- Admin-only Excel exports for the current week-to-date, month-to-date,
  year-to-date, or all time, with Transactions and Transaction Items sheets. Every
  transaction row includes its sold product names and quantities, and the
  line-item sheet gives the unit price, cost, quantity, and line total.
  Voided and demo records remain identified by status in the exported rows.

The system does not currently include inventory management. Demo sales are
added only for the untouched local demo accounts and are excluded from
business dashboard totals.

## Publish a public demo

The project includes a WSGI entry point, `wsgi.py`, a `Procfile`, and a
Linux-only Gunicorn dependency. For a Render or Railway deployment:

1. Put the source in a private or public GitHub repository and connect the
   repository to your hosting provider. Do not commit local data, virtual
   environments, or secrets. The repository `.gitignore` excludes the
   local database, private merchant QR, virtual environments, and `.env`.
2. Use the build command `pip install -r requirements.txt` and start command
   `gunicorn --workers 1 --bind 0.0.0.0:$PORT wsgi:application`.
3. Attach persistent storage to the web service. SQLite data stored on an
   ephemeral filesystem can disappear on restart or redeploy. Use a
   provider plan that supports persistent disks/volumes.
4. Set these environment variables in the provider dashboard (not in source
   control). Generate separate random values for `SECRET_KEY` and
   `ADMIN_SETUP_TOKEN`:

   | Variable | Example |
   |---|---|
   | `SECRET_KEY` | Generate a unique secret with `python -c "import secrets; print(secrets.token_hex(32))"` |
   | `ADMIN_SETUP_TOKEN` | Generate a different unique value with the same command |
   | `APP_ENV` | `production` |
   | `DATABASE_PATH` | Render disk mounted at `/var/data`: `/var/data/cafe.db`; Railway volume mounted at `/data`: `/data/cafe.db` |
   | `PUBLIC_DEMO` | `1` |
   | `SEED_DEMO_USERS` | `0` |
   | `SESSION_COOKIE_SECURE` | `1` |

   Production startup requires an explicit `SECRET_KEY`, `DATABASE_PATH`,
   and `ADMIN_SETUP_TOKEN`. The database path must be inside the persistent
   storage mount.
5. Deploy, open `/admin-setup`, and enter your private setup token to create
   your own admin account. This route closes after the first admin exists.
   Sign in as that admin and create staff accounts as needed.

`PUBLIC_DEMO=1` hides the merchant QR and disables e-wallet checkout in the
public demo. It also rejects e-wallet checkout requests server-side. The
real merchant QR is private and should not be uploaded with a public demo.
Use only fictional data when demonstrating the site to a client. A public
demo is not suitable for actual cafe sales or sensitive business records.

### Run the app with MongoDB

After importing the SQLite data, set `MONGODB_URI` in the same PowerShell
window used to start Flask, then launch the app with the project interpreter:

```powershell
$env:MONGODB_URI = "mongodb://localhost:27017/"
$env:MONGODB_DATABASE = "cafe_pos"
.\.venv\Scripts\python.exe app.py
```

When `MONGODB_URI` is set, MongoDB is the persistent store. The compatibility
layer loads MongoDB documents into an in-memory SQLite query database for the
existing SQL routes, then writes changed records back to MongoDB on commit.
Sale line items are saved embedded in their transaction. Use one app process
for this mode; it is not designed for concurrent workers or multi-server
deployment. If `MONGODB_URI` is unset, the app uses the local SQLite file.

The hosting provider supplies a public URL, so you do not need to own a
custom domain. Be aware that persistent disks/volumes may require a paid
hosting plan; check the provider's current plan details before deploying.

## Importing the local SQLite data into MongoDB

`database/migrate_sqlite_to_mongodb.py` copies local SQLite records to MongoDB.
It retains the numeric IDs and embeds each transaction's line items in that
transaction document. Re-running the import updates matching IDs instead of
inserting duplicates. It does not delete or modify the SQLite source.

Set `MONGODB_URI` to your MongoDB connection string, then run:

```powershell
.\.venv\Scripts\python.exe -m database.migrate_sqlite_to_mongodb
```

The default source is `instance/cafe.db` and the default target database is
`cafe_pos`. Set `SQLITE_PATH` or `MONGODB_DATABASE` to override either value.
After importing, start the app with the same `MONGODB_URI` and database name
to use MongoDB mode. Keep the SQLite file as a backup.

If you need admin password reset emails, configure `GMAIL_ADDRESS` and
`GMAIL_APP_PASSWORD` as private environment variables. Do not put account
passwords or app passwords in the project files.

## Tests

```powershell
.\.venv\Scripts\python.exe tests\test_security.py
```

The tests use temporary databases and do not change the local cafe database.
