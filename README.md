# Secure Cafe Point of Sale System

A Flask and SQLite point-of-sale system developed as an academic final
project. It demonstrates staff/admin accounts, order taking, payment
recording, sales reporting, and an Excel export.

This is a project/demo system, not a payment processor. It does not verify
e-wallet payments, and it should not be used for real customer or business
records without a separate security and operational review.

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

- Menu grouped into Coffee Drinks, Freshie Drinks, Food, and Pastry.
- Dine In and Take Out order types.
- Cash and e-wallet options in local development. The supplied InstaPay QR
  is served only to authenticated users from
  `private/instapay-merchant-qr.jpg`, outside the public static directory.
  Scanning or displaying it does not confirm payment.
- Receipts, today's sales, manager-approved voids, and an append-only audit
  log.
- Dashboard summary and most-ordered products.
- Admin-only Excel export with a visual Dashboard, a seven-day sales chart,
  an all-transactions bar chart, a top-five products chart, and full
  Transactions, Transaction Items, and Menu Products sheets. Every
  transaction row includes its sold product names and quantities, and the
  line-item sheet gives the unit price, cost, quantity, and line total. The
  Menu Products sheet lists all catalog products. The all-transactions chart
  includes voided and demo records with their status shown in the category
  label; dashboard summary totals exclude those records.

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

The hosting provider supplies a public URL, so you do not need to own a
custom domain. Be aware that persistent disks/volumes may require a paid
hosting plan; check the provider's current plan details before deploying.

If you need admin password reset emails, configure `GMAIL_ADDRESS` and
`GMAIL_APP_PASSWORD` as private environment variables. Do not put account
passwords or app passwords in the project files.

## Tests

```powershell
.\.venv\Scripts\python.exe tests\test_security.py
```

The tests use temporary databases and do not change the local cafe database.
