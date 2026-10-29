"""
POS terminal: ringing up sales, taking payment, receipts, and voiding.

Two secure-coding practices are load-bearing in this file:

  1. Prices are ALWAYS re-read from the database at checkout time, never
     trusted from the client's request body. A tampered request claiming a
     latte costs 1 peso is simply ignored. The change due is likewise
     computed on the server, so a modified browser can't manufacture change.

  2. Voiding a completed sale requires step-up authentication: a manager or
     admin PIN, checked independently of whoever is logged in at the
     terminal (Integrity + Non-repudiation).
"""
import os

from flask import (
    Blueprint, abort, current_app, jsonify, render_template, request, send_file,
    send_from_directory, session,
)
from werkzeug.security import check_password_hash

from database.db import get_db, now_str
from database.seed_data import ensure_demo_sales
from security.audit import log_action
from security.decorators import login_required
from security.validators import is_positive_int

pos_bp = Blueprint("pos", __name__)

VALID_PAYMENT_METHODS = ("cash", "ewallet")
VALID_SERVICE_TYPES = ("dine_in", "takeout")
MENU_CATEGORIES = ("Coffee Drinks", "Freshie Drinks", "Meals", "Pastry")


@pos_bp.route("/")
@login_required
def terminal():
    db = get_db()
    items = db.execute(
        "SELECT * FROM menu_items WHERE is_active = 1 ORDER BY "
        "CASE category WHEN 'Coffee Drinks' THEN 1 WHEN 'Freshie Drinks' THEN 2 "
        "WHEN 'Meals' THEN 3 WHEN 'Pastry' THEN 4 ELSE 5 END, name"
    ).fetchall()
    return render_template("pos_terminal.html", items=items, categories=MENU_CATEGORIES)


@pos_bp.route("/merchant-qr")
@login_required
def merchant_qr():
    if current_app.config["PUBLIC_DEMO"]:
        abort(404)
    qr_path = current_app.config["MERCHANT_QR_PATH"]
    if not os.path.isfile(qr_path):
        abort(404)
    return send_file(qr_path, mimetype="image/jpeg", max_age=0)


@pos_bp.route("/product-image/<path:image_filename>")
@login_required
def product_image(image_filename):
    """Serve catalog images only to signed-in staff and admins."""
    return send_from_directory(current_app.config["PRODUCT_IMAGE_DIR"], image_filename)


@pos_bp.route("/checkout", methods=["POST"])
@login_required
def checkout():
    data = request.get_json(silent=True) or {}
    cart = data.get("cart", [])
    payment_method = data.get("payment_method", "cash")
    service_type = data.get("service_type")
    tendered_raw = data.get("amount_tendered", 0)

    if not cart or not isinstance(cart, list):
        return jsonify(error="Your cart is empty."), 400
    if payment_method not in VALID_PAYMENT_METHODS:
        return jsonify(error="Invalid payment method."), 400
    if current_app.config["PUBLIC_DEMO"] and payment_method != "cash":
        return jsonify(error="E-wallet payments are disabled in the public demo."), 400
    if service_type not in VALID_SERVICE_TYPES:
        return jsonify(error="Choose Dine In or Take Out."), 400

    db = get_db()
    vat_rate = current_app.config["VAT_RATE"]

    line_items = []
    subtotal = 0.0

    for line in cart:
        if not is_positive_int(line.get("quantity"), max_value=50):
            return jsonify(error="Invalid item quantity."), 400

        # Authoritative lookup — the client's price, if it sent one, is ignored.
        item = db.execute(
            "SELECT * FROM menu_items WHERE id = ? AND is_active = 1",
            (line.get("menu_item_id"),),
        ).fetchone()
        if not item:
            return jsonify(error="One of the items in your cart is no longer available."), 400

        qty = int(line["quantity"])
        line_total = round(item["price"] * qty, 2)
        subtotal += line_total
        line_items.append({
            "menu_item_id": item["id"],
            "name": item["name"],
            "price": item["price"],
            "cost": item["cost_price"],
            "quantity": qty,
            "line_total": line_total,
        })

    subtotal = round(subtotal, 2)
    vat_amount = round(subtotal - (subtotal / (1 + vat_rate)), 2)
    total = subtotal  # prices are VAT-inclusive; vat_amount is a receipt breakdown only

    # Payment validation. Change is computed here, on the server.
    if payment_method == "cash":
        try:
            tendered = round(float(tendered_raw), 2)
        except (TypeError, ValueError):
            return jsonify(error="Enter a valid cash amount."), 400
        if tendered < total:
            return jsonify(error="Cash received is less than the total due."), 400
        if tendered > 100000:
            return jsonify(error="That cash amount looks incorrect. Please re-enter it."), 400
        change_due = round(tendered - total, 2)
    else:
        tendered = total
        change_due = 0.0

    try:
        cur = db.execute(
            "INSERT INTO transactions "
            "(cashier_id, created_at, subtotal, vat_amount, total, payment_method, "
            " service_type, amount_tendered, change_due, status, sync_status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed', 'pending')",
            (session["user_id"], now_str(), subtotal, vat_amount, total,
             payment_method, service_type, tendered, change_due),
        )
        transaction_id = cur.lastrowid

        for li in line_items:
            db.execute(
                "INSERT INTO transaction_items "
                "(transaction_id, menu_item_id, item_name, unit_price, unit_cost, quantity, line_total) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (transaction_id, li["menu_item_id"], li["name"], li["price"],
                 li["cost"], li["quantity"], li["line_total"]),
            )

        db.commit()
    except Exception:
        db.rollback()
        current_app.logger.exception("checkout failed")
        return jsonify(error="Something went wrong while processing the sale. Please try again."), 500

    log_action(
        db, session["user_id"], session.get("full_name"), "SALE_COMPLETED",
        f"Transaction #{transaction_id}, total \u20b1{total:.2f}, {len(line_items)} item(s), {payment_method}",
    )

    return jsonify(success=True, transaction_id=transaction_id, change_due=change_due)


@pos_bp.route("/receipt/<int:transaction_id>")
@login_required
def receipt(transaction_id):
    db = get_db()
    txn = db.execute(
        "SELECT t.*, u.full_name AS cashier_name FROM transactions t "
        "JOIN users u ON u.id = t.cashier_id WHERE t.id = ?",
        (transaction_id,),
    ).fetchone()
    if not txn:
        abort(404)
    if session["role"] != "admin" and txn["cashier_id"] != session["user_id"]:
        abort(403)  # cashiers may only view their own receipts
    items = db.execute(
        "SELECT * FROM transaction_items WHERE transaction_id = ?", (transaction_id,)
    ).fetchall()
    return render_template("pos_receipt.html", txn=txn, items=items)


@pos_bp.route("/history")
@login_required
def history():
    db = get_db()
    ensure_demo_sales()
    if session["role"] == "admin":
        txns = db.execute(
            "SELECT t.*, u.full_name AS cashier_name FROM transactions t "
            "JOIN users u ON u.id = t.cashier_id "
            "WHERE date(t.created_at) = date('now','localtime') ORDER BY t.created_at DESC"
        ).fetchall()
    else:
        txns = db.execute(
            "SELECT t.*, u.full_name AS cashier_name FROM transactions t "
            "JOIN users u ON u.id = t.cashier_id "
            "WHERE t.cashier_id = ? AND date(t.created_at) = date('now','localtime') "
            "ORDER BY t.created_at DESC",
            (session["user_id"],),
        ).fetchall()

    shift_total = sum(t["total"] for t in txns if t["status"] == "completed" and not t["is_demo"])
    return render_template("pos_history.html", txns=txns, shift_total=shift_total)


@pos_bp.route("/void/<int:transaction_id>", methods=["POST"])
@login_required
def void_transaction(transaction_id):
    data = request.get_json(silent=True) or {}
    manager_pin = data.get("manager_pin", "")
    reason = (data.get("reason") or "").strip()

    db = get_db()
    txn = db.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,)).fetchone()
    if not txn:
        return jsonify(error="Transaction not found."), 404
    if txn["status"] != "completed":
        return jsonify(error="This transaction has already been voided."), 400
    if not reason or len(reason) < 3:
        return jsonify(error="Please provide a reason for the void."), 400

    # Step-up authentication: check the PIN against every active admin
    # account, independent of who is currently logged in at this terminal.
    managers = db.execute("SELECT * FROM users WHERE role = 'admin' AND is_active = 1").fetchall()
    approver = next((m for m in managers if check_password_hash(m["pin_hash"], manager_pin)), None)

    if not approver:
        log_action(db, session["user_id"], session.get("full_name"), "VOID_DENIED",
                   f"Transaction #{transaction_id}: invalid manager PIN")
        return jsonify(error="Invalid manager PIN."), 403

    try:
        # Marked as voided, never deleted — the record stays as evidence.
        db.execute(
            "UPDATE transactions SET status='voided', voided_by=?, voided_at=?, void_reason=? WHERE id=?",
            (approver["id"], now_str(), reason, transaction_id),
        )
        db.commit()
    except Exception:
        db.rollback()
        current_app.logger.exception("void failed")
        return jsonify(error="Something went wrong while voiding this transaction."), 500

    log_action(db, session["user_id"], session.get("full_name"), "VOID_APPROVED",
               f"Transaction #{transaction_id} voided, approved by {approver['full_name']}, reason: {reason}")
    return jsonify(success=True)
