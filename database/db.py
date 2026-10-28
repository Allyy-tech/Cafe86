"""
Database connection handling.

Every query anywhere in this app is written with '?' placeholders and a
separate parameters tuple (see blueprints/*.py). We never use Python string
formatting (f-strings, %, .format(), string concatenation) to build a query
with user-supplied values — that is exactly the pattern that causes SQL
injection. Table/column names that appear inline in a few dashboard queries
are fixed strings written by us, never user input.
"""
import sqlite3
from datetime import datetime

from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE_PATH"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)


def now_str():
    """Local timestamp string used consistently for every created_at/updated
    column in the app, so 'today' means the same thing everywhere."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run_migrations(db):
    """Brings an existing database file up to date with schema.sql.

    CREATE TABLE IF NOT EXISTS only matters for a table that doesn't exist
    yet — it does nothing to a users table that was already created before
    the email column existed. Without this, an app that's been running
    since before this feature would crash the first time any query touched
    users.email.     This is intentionally small and manual rather than a migration
    framework (Alembic, etc.). New columns and indexes are checked before
    being added, so these upgrades are safe to run on every startup.
    """
    columns = [row["name"] for row in db.execute("PRAGMA table_info(users)").fetchall()]
    if "email" not in columns:
        db.execute("ALTER TABLE users ADD COLUMN email TEXT")
    if "approval_status" not in columns:
        db.execute(
            "ALTER TABLE users ADD COLUMN approval_status TEXT NOT NULL DEFAULT 'approved'"
        )
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)")

    transaction_columns = [
        row["name"] for row in db.execute("PRAGMA table_info(transactions)").fetchall()
    ]
    if "service_type" not in transaction_columns:
        db.execute(
            "ALTER TABLE transactions ADD COLUMN service_type TEXT NOT NULL "
            "DEFAULT 'takeout' CHECK (service_type IN ('dine_in', 'takeout'))"
        )
    if "is_demo" not in transaction_columns:
        db.execute(
            "ALTER TABLE transactions ADD COLUMN is_demo INTEGER NOT NULL "
            "DEFAULT 0 CHECK (is_demo IN (0, 1))"
        )
    db.execute("UPDATE menu_items SET category = 'Coffee Drinks' WHERE category = 'Coffee'")
    db.execute("UPDATE menu_items SET category = 'Freshie Drinks' WHERE category = 'Drinks'")
    db.commit()
