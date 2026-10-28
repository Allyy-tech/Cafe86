"""
Recovery tool for admin accounts that existed before email-based login was
added. The schema migration preserves those accounts exactly as they were
(see database/db.py's run_migrations) but can't invent an email for them —
and since /admin-login now looks accounts up by email, an admin with none
on file would otherwise have no way back in.

This is deliberately a command-line script, not a web page: fixing it
needs the same trust level as editing instance/cafe.db directly, which is
already the highest privilege level there is for this app — anyone who can
run this can already do anything to the database. Keeping it off the web
keeps that access where it already lives (the server's own filesystem)
rather than adding a new web-facing route for it.

Run from the project root:

    python set_admin_email.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app  # noqa: E402
from database.db import get_db  # noqa: E402
from security.validators import is_valid_email  # noqa: E402


def main():
    app = create_app()
    with app.app_context():
        db = get_db()
        missing = db.execute(
            "SELECT id, username, full_name FROM users "
            "WHERE role = 'admin' AND is_active = 1 AND (email IS NULL OR email = '') "
            "ORDER BY full_name"
        ).fetchall()

        if not missing:
            print("Every admin account already has an email on file. Nothing to do.")
            return

        print(f"{len(missing)} admin account(s) have no email on file "
              f"(likely created before this feature existed):\n")
        for row in missing:
            print(f"  - {row['full_name']}  (username: {row['username']})")
        print()

        for row in missing:
            while True:
                email = input(f"Email for {row['full_name']} ({row['username']}), "
                             f"or leave blank to skip: ").strip().lower()
                if not email:
                    print("  Skipped.\n")
                    break
                if not is_valid_email(email):
                    print("  That doesn't look like a valid email address. Try again.")
                    continue
                taken = db.execute(
                    "SELECT 1 FROM users WHERE email = ? AND id != ?", (email, row["id"])
                ).fetchone()
                if taken:
                    print("  That email is already used by another account. Try again.")
                    continue

                db.execute("UPDATE users SET email = ? WHERE id = ?", (email, row["id"]))
                db.commit()
                print(f"  Done — {row['full_name']} can now sign in with {email}.\n")
                break


if __name__ == "__main__":
    main()
