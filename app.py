"""LifeLink — Blood donation & emergency rescue network."""

import os

import sqlalchemy as sa
from flask import Flask, jsonify, render_template

from models.database import database_uri, engine_options
from models.models import db
from routes.auth_routes import auth_bp, require_role
from routes.donor_routes import donor_bp
from routes.emergency_routes import emergency_bp
from routes.middleware import register_middleware

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
VERSION = "1.0.0"
DB_PATH = os.environ.get("LIFELINK_DB_PATH", os.path.join(BASE_DIR, "lifelink.db"))


def create_app():
    app = Flask(__name__)
    uri = database_uri(DB_PATH)
    app.config["SQLALCHEMY_DATABASE_URI"] = uri
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_options(uri)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    secret = os.environ.get("SECRET_KEY")
    if not secret:
        import secrets
        import warnings
        if os.environ.get("FLASK_ENV") == "production":
            raise RuntimeError("SECRET_KEY must be set in production (FLASK_ENV=production).")
        warnings.warn("SECRET_KEY not set; generating ephemeral secret (tokens will not survive restart). Set SECRET_KEY in production.", stacklevel=2)
        secret = secrets.token_hex(32)
    app.config["SECRET_KEY"] = secret
    app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", secret)
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = False

    db.init_app(app)

    app.register_blueprint(donor_bp)
    app.register_blueprint(emergency_bp)
    app.register_blueprint(auth_bp)
    register_middleware(app)

    # SQLite (local dev, tests) has no migration step — tables are created here.
    # Postgres is owned by Alembic: create_all() would silently create missing
    # tables instead of failing, so a container that skipped `alembic upgrade`
    # would look healthy while running an outdated schema.
    if uri.startswith("sqlite"):
        with app.app_context():
            db.create_all()

    # ---- Page routes ----
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/register")
    def register_page():
        return render_template("register.html")

    @app.route("/emergencies")
    def emergencies_page():
        return render_template("emergencies.html")

    # ---- Public stats (UX audit L-1: footer/hero counters were dead because
    # they fetched auth-gated endpoints and swallowed 401s forever) ----
    @app.route("/api/stats")
    def stats():
        from models.models import Donor, EmergencyRequest
        return jsonify({
            "donors": Donor.query.count(),
            "open_emergencies": EmergencyRequest.query.filter_by(status="open").count(),
        })

    # ---- إحصاءات المشغّل (خارطة المنتَجة أسبوع 2): نداءات، فصائل مطلوبة،
    # زمن استجابة متوسط. للـadmin فقط — 401 للمجرّد، 403 لأي دور آخر. ----
    @app.route("/admin/stats")
    @require_role("admin")
    def admin_stats():
        from models.models import Donor, EmergencyRequest

        by_blood: dict[str, int] = {}
        by_blood_open: dict[str, int] = {}
        for bt, total, opened in (
            db.session.query(
                EmergencyRequest.blood_type,
                sa.func.count(EmergencyRequest.id),
                sa.func.sum(sa.case((EmergencyRequest.status == "open", 1), else_=0)),
            ).group_by(EmergencyRequest.blood_type).all()
        ):
            by_blood[bt] = int(total)
            by_blood_open[bt] = int(opened or 0)

        # زمن استجابة متوسط: (fulfilled_at − created_at) على النداءات المُلبّاة
        # المختومة فقط — النداءات القديمة بلا ختم لا تزوّر المتوسط.
        rows = db.session.query(
            EmergencyRequest.created_at, EmergencyRequest.fulfilled_at
        ).filter(
            EmergencyRequest.status == "fulfilled",
            EmergencyRequest.fulfilled_at.isnot(None),
        ).all()
        deltas = [
            (f - c).total_seconds() / 3600.0
            for c, f in rows if f >= c
        ]
        avg_response_hours = round(sum(deltas) / len(deltas), 2) if deltas else None

        return jsonify({
            "requests_total": sum(by_blood.values()),
            "requests_open": sum(by_blood_open.values()),
            "requests_fulfilled": EmergencyRequest.query.filter_by(status="fulfilled").count(),
            "requests_by_blood_type": by_blood,
            "open_by_blood_type": by_blood_open,
            "avg_response_hours": avg_response_hours,
            "donors_total": Donor.query.count(),
            "donors_available": Donor.query.filter_by(available=True).count(),
        })

    # Liveness: the process answers, with or without a database. A healthcheck
    # that needs Postgres turns a database outage into a restart loop.
    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "service": "lifelink", "version": VERSION})

    # Readiness: may traffic be sent here? Same body shape on both paths so one
    # log line explains a failing rollout.
    @app.route("/ready")
    def ready():
        import time

        from sqlalchemy import text

        started = time.monotonic()
        checks = []
        try:
            db.session.execute(text("SELECT 1"))
            checks.append({"name": "database", "ok": True, "detail": "SELECT 1"})
        except Exception as exc:  # noqa: BLE001 - a probe must never raise
            checks.append({"name": "database", "ok": False, "error": f"{type(exc).__name__}: {exc}"})
        finally:
            db.session.rollback()
        is_ready = all(check["ok"] for check in checks)
        return (
            jsonify(
                {
                    "ready": is_ready,
                    "status": "ready" if is_ready else "not_ready",
                    "version": VERSION,
                    "checks": checks,
                    "latency_ms": round((time.monotonic() - started) * 1000, 1),
                }
            ),
            200 if is_ready else 503,
        )

    return app


app = create_app()

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")), debug=debug)
