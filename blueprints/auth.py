"""
Authentication.

The unified sign-in page accepts a username or email and routes users to
the correct area after checking the credential for their role: admins use
their password, and staff use their PIN. The legacy /pos-login and
/admin-login URLs remain as compatible entry points to the same form.
Credentials are hash-checked and repeated failures trigger the shared
lockout policy.

/forgot-password and /reset-password are the OTP-based recovery flow: an
admin who forgets their password requests a 6-digit code emailed to the
address on file, then uses that code to set a new password. See
security/mailer.py for how the email is actually sent, and the README for
the one-time Gmail setup this needs.
"""
from datetime import datetime, timedelta
import hmac
import secrets

from flask import Blueprint, abort, current_app, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_db, now_str
from security.audit import log_action
from security.mailer import EmailNotConfiguredError, generate_otp, is_email_configured, send_otp_email
from security.validators import is_valid_email, is_valid_password, is_valid_pin, is_valid_username

auth_bp = Blueprint("auth", __name__)

OTP_VALID_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN_SECONDS = 60


def _is_locked(user):
    if not user["locked_until"]:
        return False
    return datetime.now() < datetime.strptime(user["locked_until"], "%Y-%m-%d %H:%M:%S")


def _register_failure(db, user):
    attempts = user["failed_attempts"] + 1
    locked_until = None
    max_attempts = current_app.config["MAX_FAILED_ATTEMPTS"]
    lockout_minutes = current_app.config["LOCKOUT_MINUTES"]
    locked = attempts >= max_attempts
    if locked:
        locked_until = (datetime.now() + timedelta(minutes=lockout_minutes)).strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
        (attempts, locked_until, user["id"]),
    )
    db.commit()
    if locked:
        log_action(db, user["id"], user["full_name"], "ACCOUNT_LOCKED",
                   f"{attempts} failed attempts, locked {lockout_minutes} min")
    return locked


def _register_success(db, user):
    db.execute(
        "UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = ?",
        (user["id"],),
    )
    db.commit()


def admin_exists(db):
    """Whether the system currently has a usable owner/admin account.

    Checked before every step of the admin login/setup flow, in both
    directions: it's what makes /admin-setup close itself off once an
    admin exists, and what makes /admin-login send a fresh install to
    setup instead of showing a login form for an account that isn't
    there yet. Filtering on is_active also means that if every admin
    were ever deactivated, setup would reopen rather than locking
    everyone out permanently.
    """
    return db.execute(
        "SELECT COUNT(*) AS c FROM users WHERE role = 'admin' AND is_active = 1"
    ).fetchone()["c"] > 0


@auth_bp.route("/", methods=["GET", "POST"])
def landing():
    if request.method == "POST":
        return _login()
    if "user_id" in session:
        return redirect(url_for("admin.dashboard") if session["role"] == "admin" else url_for("pos.terminal"))
    return _login_page()


def _login_page(error=None, identifier=""):
    left = secrets.randbelow(8) + 2
    right = secrets.randbelow(8) + 2
    session["login_captcha_answer"] = str(left + right)
    return render_template(
        "landing.html", error=error, identifier=identifier,
        captcha_question=f"{left} + {right} = ?",
        needs_admin_setup=not admin_exists(get_db()),
    )


def _login():
    db = get_db()
    error = None
    identifier = ""
    if request.method == "POST":
        identifier = (request.form.get("identifier") or request.form.get("email")
                      or request.form.get("staff_id") or "").strip()
        credential = (request.form.get("credential") or request.form.get("password")
                      or request.form.get("pin") or "")
        expected_answer = session.pop("login_captcha_answer", "")
        answer = (request.form.get("captcha_answer") or "").strip()
        user = None

        if not expected_answer or not hmac.compare_digest(answer, expected_answer):
            error = "The addition answer is incorrect. Please try again."
            log_action(db, None, identifier or "Unknown user", "LOGIN_FAILED", "Incorrect arithmetic CAPTCHA")
        else:
            normalized = identifier.lower()
            user = db.execute(
                "SELECT * FROM users WHERE (lower(username) = ? OR lower(email) = ?) "
                "AND is_active = 1 AND approval_status = 'approved'",
                (normalized, normalized),
            ).fetchone()
            valid_credential = False
            if user and not _is_locked(user):
                if user["role"] == "admin":
                    valid_credential = bool(
                        user["password_hash"]
                        and check_password_hash(user["password_hash"], credential)
                    )
                else:
                    valid_credential = bool(
                        len(credential) == 4
                        and credential.isascii()
                        and credential.isdigit()
                        and check_password_hash(user["pin_hash"], credential)
                    )

            if user and _is_locked(user):
                error = "Unable to sign in. Check your details or contact an administrator."
            elif user and valid_credential:
                session.clear()
                session["user_id"] = user["id"]
                session["full_name"] = user["full_name"]
                session["role"] = user["role"]
                session.permanent = True
                _register_success(db, user)
                log_action(
                    db, user["id"], user["full_name"], "LOGIN_SUCCESS",
                    "Admin dashboard login" if user["role"] == "admin" else "POS terminal login",
                )
                if user["role"] == "admin":
                    return redirect(request.args.get("next") or url_for("admin.dashboard"))
                return redirect(url_for("pos.terminal"))
            else:
                locked = _register_failure(db, user) if user else False
                error = (
                    "Unable to sign in. Check your details or contact an administrator."
                    if locked else
                    "Invalid username/email or password/PIN. Please try again."
                )
            log_action(
                db, user["id"] if user else None,
                user["full_name"] if user else "Unknown user",
                "LOGIN_FAILED", "Unified username/email credential login attempt",
            )

    return _login_page(error=error, identifier=identifier)


@auth_bp.route("/pos-login", methods=["GET", "POST"])
def pos_login():
    return _login()


@auth_bp.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    db = get_db()
    if request.method == "GET" and not admin_exists(db):
        # Nothing to log into yet — send whoever lands here to create
        # the first owner account instead of showing an empty login form.
        return redirect(url_for("auth.admin_setup"))

    return _login()


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if "user_id" in session:
        return redirect(url_for("admin.dashboard") if session["role"] == "admin" else url_for("pos.terminal"))

    db = get_db()
    error = None
    submitted = False
    full_name = ""
    username = ""
    email = ""
    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        pin = request.form.get("pin") or ""
        expected_answer = session.pop("signup_captcha_answer", "")
        answer = (request.form.get("captcha_answer") or "").strip()

        if not expected_answer or not hmac.compare_digest(answer, expected_answer):
            error = "The addition answer is incorrect. Please try again."
        elif not full_name or len(full_name) > 60:
            error = "Enter your full name (60 characters or fewer)."
        elif not is_valid_username(username):
            error = "Username must be 3–20 characters: letters, numbers, or underscore."
        elif not is_valid_email(email):
            error = "Enter a valid email address."
        elif not is_valid_pin(pin):
            error = "PIN must be exactly 4 digits and not an easily guessed pattern."
        else:
            normalized_username = username.lower()
            existing = db.execute(
                "SELECT 1 FROM users WHERE lower(username) IN (?, ?) "
                "OR lower(email) IN (?, ?) LIMIT 1",
                (normalized_username, email, normalized_username, email),
            ).fetchone()
            if existing:
                error = "That username or email is already in use."
            else:
                db.execute(
                    "INSERT INTO users "
                    "(username, email, pin_hash, full_name, role, approval_status, is_active, created_at) "
                    "VALUES (?, ?, ?, ?, 'cashier', 'pending', 0, ?)",
                    (username, email, generate_password_hash(pin), full_name, now_str()),
                )
                db.commit()
                log_action(db, None, full_name, "STAFF_SIGNUP_REQUESTED",
                           f"Staff signup awaiting approval: {username}")
                submitted = True

    left = secrets.randbelow(8) + 2
    right = secrets.randbelow(8) + 2
    session["signup_captcha_answer"] = str(left + right)
    return render_template(
        "signup.html", error=error, submitted=submitted, full_name=full_name,
        username=username, email=email, captcha_question=f"{left} + {right} = ?",
    )


@auth_bp.route("/admin-setup", methods=["GET", "POST"])
def admin_setup():
    """First-run bootstrap: the only way an admin/owner account can ever be
    created without already being logged in as one.

    This route is intentionally narrow — it always creates role='admin'
    with no way to choose otherwise, and it only works at all while zero
    active admins exist (admin_exists() guards both branches below). The
    moment one admin account exists, this becomes permanently unreachable:
    every later account, admin or cashier, has to go through
    /admin/users/create, which requires an authenticated admin session.
    That's what keeps "admin-only signup" from turning into "anyone can
    make themselves an admin.\""""
    db = get_db()
    if admin_exists(db):
        return redirect(url_for("auth.admin_login"))

    errors = []
    if request.method == "POST":
        expected_setup_token = current_app.config.get("ADMIN_SETUP_TOKEN")
        if expected_setup_token and not hmac.compare_digest(
            request.form.get("setup_token") or "", expected_setup_token
        ):
            errors.append("Setup authorization failed.")

        full_name = (request.form.get("full_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password")
        pin = request.form.get("pin")

        if not full_name or len(full_name) > 60:
            errors.append("Full name is required.")
        if not is_valid_email(email):
            errors.append("Enter a valid email address.")
        if not is_valid_password(password):
            errors.append("Password must be at least 8 characters with a letter and a number.")
        if not is_valid_pin(pin):
            errors.append("PIN must be exactly 4 digits and not an easily-guessed pattern (e.g. 1234, 0000).")
        if not errors and db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            errors.append("An account with that email already exists.")

        if not errors:
            # Re-check right before writing: closes almost all of the gap
            # where two setup submissions race each other for "first" admin.
            if admin_exists(db):
                return redirect(url_for("auth.admin_login"))

            # username stays NOT NULL/UNIQUE at the schema level (cashier
            # accounts still use it as their handle), so admin accounts
            # simply use their email as that value too — nothing the person
            # setting up needs to think about, there's just one field to fill in.
            cur = db.execute(
                "INSERT INTO users (username, email, password_hash, pin_hash, full_name, role, is_active, created_at) "
                "VALUES (?, ?, ?, ?, ?, 'admin', 1, ?)",
                (email, email, generate_password_hash(password), generate_password_hash(pin), full_name, now_str()),
            )
            db.commit()
            new_id = cur.lastrowid

            session.clear()
            session["user_id"] = new_id
            session["full_name"] = full_name
            session["role"] = "admin"
            session.permanent = True

            log_action(db, new_id, full_name, "USER_CREATED",
                       f"Owner account created via first-run setup: {full_name} ({email})")
            return redirect(url_for("admin.dashboard"))

    return render_template("admin_setup.html", errors=errors)


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Step 1 of recovery: request a code.

    The config check happens BEFORE any database lookup, on purpose: if it
    ran after, a misconfigured server would show a different message for a
    registered email than for one that doesn't exist — leaking exactly the
    thing the generic message further down is designed to hide. Checking
    first means every visitor sees the same thing in that state, and only
    once real sending is possible does whether-the-email-exists start
    mattering at all — and even then, both cases show the same result.
    """
    message = None
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()

        if not is_email_configured():
            message = ("Email sending isn't configured on this server yet. Ask whoever "
                       "manages this app to set GMAIL_ADDRESS and GMAIL_APP_PASSWORD "
                       "(see the README).")
        else:
            db = get_db()
            user = db.execute(
                "SELECT * FROM users WHERE email = ? AND role = 'admin' AND is_active = 1",
                (email,),
            ).fetchone()

            if user:
                recent = db.execute(
                    "SELECT created_at FROM password_resets WHERE user_id = ? "
                    "ORDER BY created_at DESC LIMIT 1", (user["id"],),
                ).fetchone()
                cooled_down = True
                if recent:
                    elapsed = (datetime.now() - datetime.strptime(
                        recent["created_at"], "%Y-%m-%d %H:%M:%S")).total_seconds()
                    cooled_down = elapsed >= OTP_RESEND_COOLDOWN_SECONDS

                if cooled_down:
                    # A fresh code retires any earlier unused one, so only
                    # ever one code is live at a time.
                    db.execute("UPDATE password_resets SET used = 1 WHERE user_id = ? AND used = 0",
                               (user["id"],))
                    otp = generate_otp()
                    expires_at = (datetime.now() + timedelta(minutes=OTP_VALID_MINUTES)).strftime(
                        "%Y-%m-%d %H:%M:%S")
                    db.execute(
                        "INSERT INTO password_resets (user_id, otp_hash, expires_at, created_at) "
                        "VALUES (?, ?, ?, ?)",
                        (user["id"], generate_password_hash(otp), expires_at, now_str()),
                    )
                    db.commit()

                    try:
                        send_otp_email(email, otp, user["full_name"])
                        log_action(db, user["id"], user["full_name"], "PASSWORD_RESET_REQUESTED",
                                   f"OTP emailed to {email}")
                    except Exception:
                        # Config was confirmed present above, so a failure
                        # here is a transient send problem, not a missing
                        # setup step. Logged for the developer; the visitor
                        # still sees the same generic message either way —
                        # revealing "sending failed" would itself confirm
                        # this email belongs to a real account.
                        current_app.logger.exception("failed to send OTP email")
                        log_action(db, user["id"], user["full_name"], "PASSWORD_RESET_REQUESTED",
                                   f"OTP generated for {email} but sending failed")

            message = "If that email is registered, a reset code has been sent to it. Check your inbox."

    return render_template("forgot_password.html", message=message)


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    """Step 2: verify the code and set a new password.

    One error message covers wrong code, expired code, too many attempts,
    and an email that isn't registered at all — the same reasoning as
    /admin-login's generic 'Invalid email or password.'
    """
    GENERIC_ERROR = "That code is invalid or has expired. Request a new one."
    error = None
    prefill_email = request.args.get("email", "")

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        otp = (request.form.get("otp") or "").strip()
        new_password = request.form.get("new_password")
        prefill_email = email

        if not is_valid_password(new_password):
            error = "New password must be at least 8 characters with a letter and a number."
        else:
            db = get_db()
            user = db.execute(
                "SELECT * FROM users WHERE email = ? AND role = 'admin' AND is_active = 1",
                (email,),
            ).fetchone()

            reset_row = None
            if user:
                reset_row = db.execute(
                    "SELECT * FROM password_resets WHERE user_id = ? AND used = 0 "
                    "ORDER BY created_at DESC LIMIT 1", (user["id"],),
                ).fetchone()

            if not user or not reset_row:
                error = GENERIC_ERROR
            elif datetime.now() > datetime.strptime(reset_row["expires_at"], "%Y-%m-%d %H:%M:%S"):
                error = GENERIC_ERROR
            elif reset_row["attempts"] >= OTP_MAX_ATTEMPTS:
                error = GENERIC_ERROR
            elif not check_password_hash(reset_row["otp_hash"], otp):
                db.execute("UPDATE password_resets SET attempts = attempts + 1 WHERE id = ?",
                           (reset_row["id"],))
                db.commit()
                log_action(db, user["id"], user["full_name"], "PASSWORD_RESET_FAILED",
                           "Incorrect reset code entered")
                error = GENERIC_ERROR
            else:
                db.execute(
                    "UPDATE users SET password_hash = ?, failed_attempts = 0, locked_until = NULL WHERE id = ?",
                    (generate_password_hash(new_password), user["id"]),
                )
                db.execute("UPDATE password_resets SET used = 1 WHERE id = ?", (reset_row["id"],))
                db.commit()
                log_action(db, user["id"], user["full_name"], "PASSWORD_RESET_COMPLETED",
                           "Password changed via emailed reset code")

                session.clear()
                session["user_id"] = user["id"]
                session["full_name"] = user["full_name"]
                session["role"] = user["role"]
                session.permanent = True
                return redirect(url_for("admin.dashboard"))

    return render_template("reset_password.html", error=error, prefill_email=prefill_email)


@auth_bp.route("/logout")
def logout():
    if "user_id" in session:
        db = get_db()
        log_action(db, session["user_id"], session.get("full_name"), "LOGOUT", "")
    session.clear()
    return redirect(url_for("auth.landing"))
