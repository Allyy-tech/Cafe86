"""
Offline mode / Availability blueprint.

This is the code behind the Availability principle in section III of the
documentation. The key design decision: NOTHING in the sale path calls
is_internet_available(). Ringing up a sale, taking payment and printing a
receipt read and write only the local SQLite file over the local network, so
they keep working with the internet completely down.

What the internet is used for is the *optional* extra: pushing a copy of
completed sales to off-site backup. Rows are marked sync_status='pending'
the moment they're created and only flipped to 'synced' once that push
succeeds — so an outage can delay the backup but can never lose a sale.

/api/status is polled by the browser every 15 seconds purely to show the
ONLINE / OFFLINE badge in the header. If that poll itself fails, the badge
falls back to OFFLINE and the terminal carries on working.
"""
from flask import Blueprint, jsonify, session

from database.db import get_db, now_str
from security.audit import log_action
from security.connectivity import is_internet_available
from security.decorators import admin_required, login_required

sync_bp = Blueprint("sync", __name__)


@sync_bp.route("/api/status")
@login_required
def status():
    db = get_db()
    pending = db.execute(
        "SELECT COUNT(*) AS c FROM transactions WHERE sync_status = 'pending' AND is_demo=0"
    ).fetchone()["c"]
    return jsonify(online=is_internet_available(), pending=pending)


@sync_bp.route("/api/sync", methods=["POST"])
@admin_required
def sync_now():
    """Push every pending transaction to off-site backup.

    In this project the 'upload' is simulated — there's no real cloud
    account to talk to. What is NOT simulated is everything around it: the
    pending queue, the refusal to mark anything synced while offline, and
    the audit entry. To make this real you would replace the marked block
    below with an HTTPS POST to your backup endpoint and only flip the rows
    that the server acknowledged.
    """
    if not is_internet_available():
        return jsonify(error="Still offline. Sales are safe in the local queue and will sync automatically once the connection returns."), 503

    db = get_db()
    pending = db.execute(
        "SELECT id FROM transactions WHERE sync_status = 'pending' AND is_demo=0 ORDER BY id"
    ).fetchall()

    if not pending:
        return jsonify(success=True, synced=0, message="Everything is already backed up.")

    # ---- replace this block with a real HTTPS upload ----
    synced_ids = [row["id"] for row in pending]
    # -----------------------------------------------------

    stamp = now_str()
    for txn_id in synced_ids:
        db.execute(
            "UPDATE transactions SET sync_status = 'synced', synced_at = ? WHERE id = ?",
            (stamp, txn_id),
        )
    db.commit()

    log_action(db, session["user_id"], session.get("full_name"), "SYNC_COMPLETED",
               f"Backed up {len(synced_ids)} transaction(s) to off-site storage")

    return jsonify(success=True, synced=len(synced_ids))
