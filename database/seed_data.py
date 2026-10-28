"""
Creates tables (if missing) and seeds demo data (if the database is empty).

Runs automatically every time the app starts. Safe to run repeatedly:
CREATE TABLE IF NOT EXISTS makes the schema step idempotent, and the seed
step only inserts the very first time (it checks whether the users table is
empty), so restarting never wipes real data you've since entered.
"""
from datetime import datetime, timedelta

from flask import current_app
from werkzeug.security import generate_password_hash

from database.db import get_db, now_str, run_migrations

# Menu: (name, category, selling price, cost to make)
MENU_ITEMS = [
    ("Espresso",              "Coffee Drinks",   90,  26.10),
    ("Americano",             "Coffee Drinks",  100,  26.10),
    ("Cappuccino",            "Coffee Drinks",  120,  41.10),
    ("Caffe Latte",           "Coffee Drinks",  130,  46.10),
    ("Caffe Mocha",           "Coffee Drinks",  140,  51.60),
    ("Iced Coffee",           "Coffee Drinks",  110,  36.10),
    ("Hot Chocolate",         "Coffee Drinks",  110,  38.00),
    ("Croissant",             "Pastry",   70,  35.00),
    ("Blueberry Muffin",      "Pastry",   75,  30.00),
    ("Chocolate Chip Cookie", "Pastry",   50,  15.00),
    ("Cheesecake Slice",      "Pastry",   95,  42.00),
    ("Ham & Cheese Sandwich", "Food",     95,  38.00),
    ("Tuna Sandwich",         "Food",     90,  36.00),
    ("Caesar Salad",          "Food",    120,  52.00),
    ("Bottled Water",         "Freshie Drinks",   30,  12.00),
    ("Iced Tea",              "Freshie Drinks",   55,  18.00),
]

# Demo cashier accounts. CHANGE THESE before using this for anything real —
# see the README for how. There's no seeded admin: the first run of the app
# has zero admin accounts on purpose, so it lands on /admin-setup instead of
# shipping a known default admin password in the code.
USERS = [
    # (username, full_name, role, password_or_None, pin)
    ("cashier1", "Cashier One", "cashier", None, "1428"),
    ("cashier2", "Cashier Two", "cashier", None, "2637"),
]


def init_schema(app):
    db = get_db()
    with open(app.config["SCHEMA_PATH"], "r", encoding="utf-8") as f:
        db.executescript(f.read())
    db.commit()
    run_migrations(db)


def ensure_seed_data():
    db = get_db()

    menu_count = db.execute("SELECT COUNT(*) AS c FROM menu_items").fetchone()["c"]
    if menu_count == 0:
        for name, category, price, cost in MENU_ITEMS:
            db.execute(
                "INSERT INTO menu_items (name, category, price, cost_price, is_active) "
                "VALUES (?, ?, ?, ?, 1)",
                (name, category, price, cost),
            )

    user_count = db.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    if user_count == 0 and current_app.config.get("SEED_DEMO_USERS", True):
        for username, full_name, role, password, pin in USERS:
            password_hash = generate_password_hash(password) if password else None
            db.execute(
                "INSERT INTO users (username, password_hash, pin_hash, full_name, role, is_active, created_at) "
                "VALUES (?, ?, ?, ?, ?, 1, ?)",
                (username, password_hash, generate_password_hash(pin), full_name, role, now_str()),
            )

    db.commit()


def ensure_demo_sales():
    """Add five labeled sample sales only to the untouched demo cashier setup."""
    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    demo_cashiers = db.execute(
        "SELECT id FROM users WHERE username IN ('cashier1', 'cashier2') "
        "AND role = 'cashier' AND is_active = 1 ORDER BY username"
    ).fetchall()
    transaction_count = db.execute(
        "SELECT COUNT(*) AS c FROM transactions"
    ).fetchone()["c"]
    if len(demo_cashiers) != 2 or transaction_count:
        db.commit()
        return

    cashier_id = demo_cashiers[0]["id"]
    samples = (
        ("Espresso", 1, "cash", "dine_in"),
        ("Caffe Latte", 2, "ewallet", "takeout"),
        ("Blueberry Muffin", 1, "cash", "takeout"),
        ("Iced Tea", 2, "ewallet", "dine_in"),
        ("Ham & Cheese Sandwich", 1, "cash", "dine_in"),
    )
    now = datetime.now()
    for index, (item_name, quantity, payment_method, service_type) in enumerate(samples):
        item = db.execute(
            "SELECT id, price, cost_price FROM menu_items WHERE name = ?",
            (item_name,),
        ).fetchone()
        if not item:
            raise RuntimeError(f"Missing demo menu item: {item_name}")

        total = round(item["price"] * quantity, 2)
        vat_amount = round(total - total / 1.12, 2)
        sale_time = max(
            now - timedelta(minutes=index * 4),
            now.replace(hour=0, minute=0, second=0, microsecond=0),
        )
        created_at = sale_time.strftime("%Y-%m-%d %H:%M:%S")
        cursor = db.execute(
            "INSERT INTO transactions "
            "(cashier_id, created_at, subtotal, vat_amount, total, payment_method, "
            "service_type, amount_tendered, change_due, status, sync_status, is_demo) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 'completed', 'synced', 1)",
            (cashier_id, created_at, total, vat_amount, total, payment_method,
             service_type, total),
        )
        db.execute(
            "INSERT INTO transaction_items "
            "(transaction_id, menu_item_id, item_name, unit_price, unit_cost, quantity, line_total) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (cursor.lastrowid, item["id"], item_name, item["price"],
             item["cost_price"], quantity, total),
        )
    db.commit()
