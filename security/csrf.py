"""
Minimal CSRF protection.

Every state-changing request (POST/PUT/PATCH/DELETE) must carry a token that
matches the one stored in the user's own session. Traditional HTML forms
send it as a hidden field (see templates + app.py's context processor);
JavaScript fetch() calls fetch a fresh token from /api/csrf-token and send
it as an X-CSRF-Token header instead. Both are checked the same way.
"""
import secrets

from flask import session


def get_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


def validate_csrf(token):
    real = session.get("csrf_token")
    return bool(real) and bool(token) and secrets.compare_digest(real, token)
