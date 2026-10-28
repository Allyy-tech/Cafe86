"""
Non-repudiation log.

Every sensitive action — logins (success and failure), sales, voids,
menu/price changes, staff management, sync events — is written here with
who did it and when. The application code never updates or
deletes rows in this table, only inserts, so it stays an honest history
that staff can't quietly edit after the fact.
"""
from database.db import now_str


def log_action(db, user_id, actor_name, action, details=""):
    db.execute(
        "INSERT INTO audit_log (user_id, actor_name, action, details, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, actor_name, action, details, now_str()),
    )
    db.commit()
