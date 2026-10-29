"""Copy an existing Cafe POS SQLite database into MongoDB.

Usage (PowerShell):
  $env:MONGODB_URI = "mongodb+srv://..."
  python -m database.migrate_sqlite_to_mongodb

Documents retain the SQLite integer IDs in ``legacy_id``. Transaction line
items are embedded in their transaction, which keeps receipts self-contained.
The copy is repeatable: rerunning replaces only documents with matching
legacy_id values in the selected target database.
"""
import os
import sqlite3
from pathlib import Path

from pymongo import MongoClient


COLLECTIONS = ("users", "menu_items", "transactions", "audit_log", "password_resets")


def rows(connection, table):
    return [dict(row) for row in connection.execute(f"SELECT * FROM {table}").fetchall()]


def migrate(sqlite_path, mongo_uri, database_name):
    source = sqlite3.connect(sqlite_path)
    source.row_factory = sqlite3.Row
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10000)
    client.admin.command("ping")
    target = client[database_name]

    try:
        items_by_transaction = {}
        for item in rows(source, "transaction_items"):
            item["legacy_id"] = item.pop("id")
            item["id"] = item["legacy_id"]
            items_by_transaction.setdefault(item["transaction_id"], []).append(item)

        report = {}
        for collection_name in COLLECTIONS:
            collection = target[collection_name]
            records = rows(source, collection_name)
            for record in records:
                legacy_id = record.pop("id")
                record["legacy_id"] = legacy_id
                record["id"] = legacy_id
                if collection_name == "transactions":
                    record["items"] = items_by_transaction.pop(legacy_id, [])
                collection.replace_one({"legacy_id": legacy_id}, record, upsert=True)
            collection.create_index("legacy_id", unique=True)
            report[collection_name] = len(records)

        if items_by_transaction:
            raise RuntimeError(
                "Some transaction items reference a transaction absent from the source database."
            )
        target["menu_items"].create_index("name", unique=True)
        target["users"].create_index("username", unique=True)
        # SQLite permits multiple NULL emails under a UNIQUE index. MongoDB's
        # sparse unique index still indexes explicit null values, so restrict
        # this index to actual email strings instead.
        target["users"].create_index(
            "email", unique=True, partialFilterExpression={"email": {"$type": "string"}}
        )
        return report
    finally:
        source.close()
        client.close()


def main():
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        raise SystemExit("Set MONGODB_URI to the MongoDB connection string first.")
    sqlite_path = os.environ.get(
        "SQLITE_PATH", str(Path(__file__).resolve().parents[1] / "instance" / "cafe.db")
    )
    database_name = os.environ.get("MONGODB_DATABASE", "cafe_pos")
    if not Path(sqlite_path).is_file():
        raise SystemExit(f"SQLite database not found: {sqlite_path}")
    report = migrate(sqlite_path, uri, database_name)
    print(f"Imported SQLite records into MongoDB database '{database_name}':")
    for collection, count in report.items():
        print(f"  {collection}: {count}")
    print("  transaction_items: embedded in transactions")


if __name__ == "__main__":
    main()
