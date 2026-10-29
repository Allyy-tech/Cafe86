"""MongoDB access helpers for the POS application."""
from datetime import datetime

from flask import current_app, g
from pymongo import MongoClient, ReturnDocument


def get_db():
    if "mongo_db" not in g:
        client = MongoClient(current_app.config["MONGODB_URI"], serverSelectionTimeoutMS=10000)
        g.mongo_client = client
        g.mongo_db = client[current_app.config["MONGODB_DATABASE"]]
    return g.mongo_db


def close_db(error=None):
    client = g.pop("mongo_client", None)
    g.pop("mongo_db", None)
    if client is not None:
        client.close()


def init_app(app):
    app.teardown_appcontext(close_db)


def next_id(db, collection_name):
    """Allocate integer ids compatible with IDs retained from SQLite."""
    result = db.counters.find_one_and_update(
        {"_id": collection_name}, {"$inc": {"value": 1}},
        upsert=True, return_document=ReturnDocument.AFTER,
    )
    return result["value"]


def initialize_counters(db):
    for name in ("users", "menu_items", "transactions", "audit_log", "password_resets"):
        highest = db[name].find_one(sort=[("id", -1)], projection={"id": 1})
        value = highest["id"] if highest else 0
        db.counters.update_one(
            {"_id": name}, {"$max": {"value": value}}, upsert=True
        )


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
