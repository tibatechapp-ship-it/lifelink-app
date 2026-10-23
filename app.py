"""LifeLink — Blood donation & emergency rescue network."""

import os
from flask import Flask, render_template, jsonify
from models.models import db
from routes.donor_routes import donor_bp
from routes.emergency_routes import emergency_bp

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "lifelink.db")


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    secret = os.environ.get("SECRET_KEY")
    if not secret:
        import warnings
        warnings.warn("SECRET_KEY not set; using insecure dev default. Set SECRET_KEY in production.", stacklevel=2)
        secret = "lifelink-dev-secret-change-in-prod"
    app.config["SECRET_KEY"] = secret

    db.init_app(app)

    app.register_blueprint(donor_bp)
    app.register_blueprint(emergency_bp)

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

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "service": "lifelink", "version": "1.0.0"})

    return app


app = create_app()

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")), debug=debug)
