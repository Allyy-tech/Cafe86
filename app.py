"""
Secure Cafe Point of Sale System
ITE 302 - Information Assurance and Security 1

Run with:  python app.py
Then open: http://127.0.0.1:5000
"""
import os
from datetime import timedelta

from flask import Flask, jsonify, render_template, request, session

from config import Config
from database import db as database
from database.db import get_db
from database.seed_data import ensure_seed_data, init_schema
from security.csrf import get_csrf_token, validate_csrf


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.permanent_session_lifetime = timedelta(seconds=app.config["PERMANENT_SESSION_LIFETIME"])

    os.makedirs(os.path.dirname(app.config["DATABASE_PATH"]), exist_ok=True)

    database.init_app(app)

    from blueprints.admin import admin_bp
    from blueprints.auth import auth_bp
    from blueprints.pos import pos_bp
    from blueprints.sync import sync_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(pos_bp, url_prefix="/pos")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(sync_bp)

    # ---------------------------------------------------------- CSRF
    @app.before_request
    def csrf_protect():
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
            if not validate_csrf(token):
                if request.path.startswith("/api") or request.is_json:
                    return jsonify(error="Your session expired. Please refresh the page and try again."), 400
                return render_template("errors/400.html"), 400

    @app.context_processor
    def inject_globals():
        return {"csrf_token": get_csrf_token, "current_user": session}

    @app.route("/api/csrf-token")
    def csrf_token_endpoint():
        return jsonify(token=get_csrf_token())

    # ---------------------------------------------------------- security headers
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; script-src 'self'"
        )
        return response

    # ---------------------------------------------------------- generic errors
    # Users see a friendly, non-specific message. Real details go to the
    # server log only — never leak stack traces or SQL to the browser.
    @app.errorhandler(400)
    def bad_request(e):
        return render_template("errors/400.html"), 400

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception("Unhandled server error")
        return render_template("errors/500.html"), 500

    with app.app_context():
        init_schema(app)
        ensure_seed_data()

    return app


app = create_app()

if __name__ == "__main__":
    # debug=False keeps the interactive debugger (which can execute
    # arbitrary code) off. Set FLASK_DEBUG=1 only while developing.
    app.run(host="127.0.0.1", port=5000, debug=os.environ.get("FLASK_DEBUG") == "1")
