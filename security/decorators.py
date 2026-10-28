"""
Route guards.

login_required  -> Authentication: any signed-in user (cashier or admin).
admin_required   -> Least privilege: only the admin/owner role may proceed.
                    Everyone else gets a generic 403, never a hint about
                    what's behind the door.
"""
from functools import wraps

from flask import abort, redirect, request, session, url_for


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.pos_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.admin_login", next=request.path))
        if session.get("role") != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped
