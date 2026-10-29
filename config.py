"""
Application configuration.

SECURE DEFAULTS (see Secure Coding & Defensive Programming Plan, section IV
of the project documentation):
- SECRET_KEY falls back to a random value for local development. Production
  mode requires an explicitly configured secret so sessions remain stable
  across restarts.
- Cookies are HttpOnly (not readable by JavaScript, blocks a class of XSS
  cookie-theft attacks) and SameSite=Lax (blocks basic cross-site request
  forgery vectors on top of the app's own CSRF tokens).
- Sessions expire after 30 minutes of inactivity so a terminal left unlocked
  doesn't stay logged in indefinitely.
"""
import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    APP_ENV = os.environ.get("APP_ENV", "development")
    if APP_ENV == "production" and not os.environ.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY must be set when APP_ENV=production.")
    if APP_ENV == "production" and not os.environ.get("DATABASE_PATH") and not os.environ.get("MONGODB_URI"):
        raise RuntimeError("Set DATABASE_PATH or MONGODB_URI for persistent storage in production.")
    if APP_ENV == "production" and not os.environ.get("ADMIN_SETUP_TOKEN"):
        raise RuntimeError("ADMIN_SETUP_TOKEN must be set for protected first-admin setup.")

    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

    DATABASE_PATH = os.environ.get(
        "DATABASE_PATH", os.path.join(BASE_DIR, "instance", "cafe.db")
    )
    MONGODB_URI = os.environ.get("MONGODB_URI")
    MONGODB_DATABASE = os.environ.get("MONGODB_DATABASE", "cafe_pos")
    PRODUCT_IMAGE_DIR = os.path.join(BASE_DIR, "instance", "product_images")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    SCHEMA_PATH = os.path.join(BASE_DIR, "database", "schema.sql")
    SEED_DEMO_USERS = os.environ.get("SEED_DEMO_USERS", "1") == "1"
    PUBLIC_DEMO = os.environ.get("PUBLIC_DEMO", "0") == "1"
    ADMIN_SETUP_TOKEN = os.environ.get("ADMIN_SETUP_TOKEN")
    MERCHANT_QR_PATH = os.environ.get(
        "MERCHANT_QR_PATH",
        os.path.join(BASE_DIR, "private", "instapay-merchant-qr.jpg"),
    )

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get(
        "SESSION_COOKIE_SECURE", "1" if APP_ENV == "production" else "0"
    ) == "1"

    PERMANENT_SESSION_LIFETIME = 30 * 60  # 30 minutes, in seconds

    # Login lockout policy (brute-force defense)
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_MINUTES = 15

    # VAT rate used for the receipt breakdown. Menu prices are treated as
    # VAT-inclusive, matching how Philippine food-service menus are usually
    # priced and receipted.
    VAT_RATE = 0.12
