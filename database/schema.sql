-- Secure Cafe Point of Sale System — database schema
-- Re-runnable: every statement is idempotent, so this file is safely
-- executed on every app startup without wiping existing data.

PRAGMA foreign_keys = ON;

-- Employees and admins. Cashiers authenticate with their username (Staff ID)
-- and PIN at the terminal;
-- admins additionally have an email + password for the back office, and
-- that email is what a password-reset code gets sent to. email is NULL for
-- cashier-only accounts (they have no password to reset) and NOT NULL,
-- enforced at the application level, for admins.
-- password_hash is NULL for cashier-only accounts since they never use it
-- (least privilege: no unused credential sitting around).
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT UNIQUE NOT NULL,
    email           TEXT,
    password_hash   TEXT,
    pin_hash        TEXT NOT NULL,
    full_name       TEXT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('admin', 'cashier')),
    approval_status TEXT NOT NULL DEFAULT 'approved' CHECK (approval_status IN ('pending', 'approved')),
    is_active       INTEGER NOT NULL DEFAULT 1,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until    TEXT,
    created_at      TEXT NOT NULL
);

-- The unique index on email (rather than a column-level UNIQUE constraint)
-- lives in database/db.py's run_migrations(), not here. It has to run
-- AFTER the email column is guaranteed to exist, and on a database created
-- before this feature existed, that column doesn't exist until migration
-- adds it — so creating the index here, unconditionally, would fail with
-- "no such column: email" on exactly the databases that most need it.

-- What's sellable at the counter.
--   price      = VAT-inclusive selling price
--   cost_price = what it costs the cafe to make one (used for profit
--                reporting). Cost is recorded directly on the item.
CREATE TABLE IF NOT EXISTS menu_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT UNIQUE NOT NULL,
    category    TEXT NOT NULL,
    price       REAL NOT NULL,
    cost_price  REAL NOT NULL DEFAULT 0,
    is_active   INTEGER NOT NULL DEFAULT 1,
    image_filename TEXT,
    description TEXT NOT NULL DEFAULT '',
    is_archived INTEGER NOT NULL DEFAULT 0,
    archived_at TEXT
);

-- One row per sale.
--   payment_method / amount_tendered / change_due support real counter
--   workflow (cash handling), not just a total.
--   sync_status / synced_at back the offline-mode queue.
--   payment_method no longer offers 'card' as a selectable option (see
--   blueprints/pos.py's VALID_PAYMENT_METHODS) — no migration needed for
--   that: a database created before this change keeps its old, slightly
--   more permissive constraint, which is harmless, and any historical
--   'card' rows in it remain valid, readable records either way.
CREATE TABLE IF NOT EXISTS transactions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cashier_id      INTEGER NOT NULL REFERENCES users(id),
    created_at      TEXT NOT NULL,
    subtotal        REAL NOT NULL,
    vat_amount      REAL NOT NULL,
    total           REAL NOT NULL,
    payment_method  TEXT NOT NULL DEFAULT 'cash' CHECK (payment_method IN ('cash', 'ewallet')),
    service_type    TEXT NOT NULL DEFAULT 'takeout' CHECK (service_type IN ('dine_in', 'takeout')),
    amount_tendered REAL NOT NULL DEFAULT 0,
    change_due      REAL NOT NULL DEFAULT 0,
    is_demo         INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'completed' CHECK (status IN ('completed', 'voided')),
    voided_by       INTEGER REFERENCES users(id),
    voided_at       TEXT,
    void_reason     TEXT,
    sync_status     TEXT NOT NULL DEFAULT 'pending' CHECK (sync_status IN ('pending', 'synced')),
    synced_at       TEXT
);

-- Line items. item_name, unit_price AND unit_cost are all copied at sale
-- time rather than looked up live, so a receipt never silently changes if
-- the menu is edited later, and historical profit stays accurate. This is
-- the Integrity guarantee for past records.
CREATE TABLE IF NOT EXISTS transaction_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id  INTEGER NOT NULL REFERENCES transactions(id),
    menu_item_id    INTEGER NOT NULL REFERENCES menu_items(id),
    item_name       TEXT NOT NULL,
    unit_price      REAL NOT NULL,
    unit_cost       REAL NOT NULL DEFAULT 0,
    quantity        INTEGER NOT NULL,
    line_total      REAL NOT NULL
);

-- Non-repudiation log: every sensitive action, who did it, and when.
-- Nothing in this table is ever updated or deleted by the application —
-- only inserted — so it stays a trustworthy history.
CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER REFERENCES users(id),
    actor_name  TEXT,
    action      TEXT NOT NULL,
    details     TEXT,
    created_at  TEXT NOT NULL
);

-- Forgot-password OTP state. otp_hash is hashed the same way passwords are
-- — never stored as plain digits — even though it's only valid for a few
-- minutes. attempts caps brute-forcing a 6-digit code; used=1 makes a code
-- single-use; a fresh request invalidates any earlier unused code for that
-- same user, so only ever one code is live at a time.
CREATE TABLE IF NOT EXISTS password_resets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    otp_hash    TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    attempts    INTEGER NOT NULL DEFAULT 0,
    used        INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
