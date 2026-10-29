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
from pymongo import MongoClient


class MongoBackedConnection:
    """Compatibility bridge: MongoDB persists rows; SQLite evaluates legacy SQL.

    This keeps the existing SQL-heavy POS routes operational while the Mongo
    collections remain the durable source. Transaction items are embedded in
    each transaction document when written to MongoDB.
    """
    TABLES = ("users", "menu_items", "transactions", "transaction_items",
              "audit_log", "password_resets")
    MONGO_TABLES = ("users", "menu_items", "transactions", "audit_log", "password_resets")

    def __init__(self, uri, database_name, schema_path):
        self.client = MongoClient(uri, serverSelectionTimeoutMS=10000)
        self.client.admin.command("ping")
        self.mongo = self.client[database_name]
        self.sqlite = sqlite3.connect(":memory:", detect_types=sqlite3.PARSE_DECLTYPES)
        self.sqlite.row_factory = sqlite3.Row
        self.sqlite.execute("PRAGMA foreign_keys = ON")
        with open(schema_path, "r", encoding="utf-8") as schema:
            self.sqlite.executescript(schema.read())
        self._load()
        self.baseline = self._current_documents()

    def _documents(self, table):
        return list(self.mongo[table].find({}))

    def _load(self):
        for table in ("users", "menu_items", "transactions", "audit_log", "password_resets"):
            docs = self._documents(table)
            for doc in docs:
                mongo_id = doc.pop("_id")
                doc.setdefault("id", doc.get("legacy_id"))
                self.mongo[table].update_one(
                    {"_id": mongo_id},
                    {"$set": {"id": doc["id"], "legacy_id": doc["id"]}},
                )
                doc.pop("legacy_id", None)
                embedded_items = []
                if table == "transactions":
                    embedded_items = doc.pop("items", [])
                self._insert(table, doc)
                if table == "transactions":
                    for item in embedded_items:
                        item.setdefault("id", item.get("legacy_id"))
                        item.pop("legacy_id", None)
                        self._insert("transaction_items", item)
        for table in self.MONGO_TABLES:
            self.mongo[table].create_index("id", unique=True)
        # Loading rows uses INSERT statements, which leave an implicit SQLite
        # transaction open. Routes such as ensure_demo_sales() start their own
        # explicit BEGIN IMMEDIATE transaction, so close the load transaction.
        self.sqlite.commit()

    def _insert(self, table, doc):
        columns = [row["name"] for row in self.sqlite.execute(f"PRAGMA table_info({table})")]
        values = {key: value for key, value in doc.items() if key in columns}
        if not values:
            return
        names = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        self.sqlite.execute(
            f"INSERT OR REPLACE INTO {table} ({names}) VALUES ({marks})", tuple(values.values())
        )

    def _current_documents(self):
        snapshot = {}
        for table in self.MONGO_TABLES:
            by_id = {}
            for row in self.sqlite.execute(f"SELECT * FROM {table}").fetchall():
                doc = dict(row)
                record_id = doc["id"]
                doc["legacy_id"] = record_id
                if table == "transactions":
                    doc["items"] = []
                    items = self.sqlite.execute(
                        "SELECT * FROM transaction_items WHERE transaction_id = ? ORDER BY id",
                        (record_id,),
                    ).fetchall()
                    for item_row in items:
                        item = dict(item_row)
                        item["legacy_id"] = item["id"]
                        doc["items"].append(item)
                by_id[record_id] = doc
            snapshot[table] = by_id
        return snapshot

    def execute(self, *args, **kwargs):
        return self.sqlite.execute(*args, **kwargs)

    def executescript(self, *args, **kwargs):
        return self.sqlite.executescript(*args, **kwargs)

    def commit(self):
        self.sqlite.commit()
        current = self._current_documents()
        for table in self.MONGO_TABLES:
            collection = self.mongo[table]
            previous = self.baseline[table]
            changed = current[table]
            for record_id in previous.keys() - changed.keys():
                collection.delete_one({"id": record_id})
            for record_id, doc in changed.items():
                if previous.get(record_id) != doc:
                    collection.replace_one({"id": record_id}, doc, upsert=True)
        self.baseline = current

    def rollback(self):
        self.sqlite.rollback()

    def close(self):
        self.sqlite.close()
        self.client.close()

    def __getattr__(self, name):
        return getattr(self.sqlite, name)


def get_db():
    if "db" not in g:
        if current_app.config.get("MONGODB_URI"):
            g.db = MongoBackedConnection(
                current_app.config["MONGODB_URI"],
                current_app.config["MONGODB_DATABASE"],
                current_app.config["SCHEMA_PATH"],
            )
        else:
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
    menu_columns = [row["name"] for row in db.execute("PRAGMA table_info(menu_items)").fetchall()]
    if "image_filename" not in menu_columns:
        db.execute("ALTER TABLE menu_items ADD COLUMN image_filename TEXT")
    if "is_archived" not in menu_columns:
        db.execute("ALTER TABLE menu_items ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0")
    if "archived_at" not in menu_columns:
        db.execute("ALTER TABLE menu_items ADD COLUMN archived_at TEXT")
    db.execute("UPDATE menu_items SET category = 'Coffee Drinks' WHERE category = 'Coffee'")
    db.execute("UPDATE menu_items SET category = 'Freshie Drinks' WHERE category = 'Drinks'")
    db.execute("UPDATE menu_items SET category = 'Meals' WHERE category IN ('Food', 'Cuisine')")
    if "description" not in menu_columns:
        db.execute("ALTER TABLE menu_items ADD COLUMN description TEXT NOT NULL DEFAULT ''")
    from database.product_descriptions import default_product_description
    existing_products = db.execute(
        "SELECT id, name, category FROM menu_items WHERE description IS NULL OR description = ''"
    ).fetchall()
    for product in existing_products:
        db.execute(
            "UPDATE menu_items SET description = ? WHERE id = ?",
            (default_product_description(product["name"], product["category"]), product["id"]),
        )
    db.commit()
