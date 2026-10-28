"""WSGI entry point for a production Python host."""
import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

os.environ.setdefault("APP_ENV", "production")
os.environ.setdefault("SEED_DEMO_USERS", "0")
os.environ.setdefault("SESSION_COOKIE_SECURE", "1")
os.environ.setdefault("PUBLIC_DEMO", "1")

from app import app as application
