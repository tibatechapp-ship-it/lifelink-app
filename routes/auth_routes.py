"""Authentication & authorization routes (itsdangerous-signed tokens, no heavy crypto)."""

import os
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from models.models import db, Donor

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

VALID_ROLES = {"donor", "center", "hospital", "admin"}
TOKEN_TTL = 3600 * 24  # 24h

_serializer = None


def get_serializer():
    global _serializer
    if _serializer is None:
        secret = os.environ.get("JWT_SECRET_KEY") or os.environ.get("SECRET_KEY") or "lifelink-dev-secret-change-in-prod"
        _serializer = URLSafeTimedSerializer(secret, salt="lifelink-auth")
    return _serializer


def make_token(donor_id, role, refresh=False):
    s = get_serializer()
    payload = {"sub": str(donor_id), "role": role, "typ": "refresh" if refresh else "access"}
    return s.dumps(payload)


def verify_token(token, refresh=False):
    s = get_serializer()
    try:
        data = s.loads(token, max_age=TOKEN_TTL if not refresh else TOKEN_TTL * 7)
    except (BadSignature, SignatureExpired):
        return None
    if (data.get("typ") == "refresh") != refresh:
        return None
    return data


def current_donor():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    data = verify_token(auth.split(" ", 1)[1])
    if not data:
        return None
    return Donor.query.get(int(data["sub"]))


def jwt_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        donor = current_donor()
        if donor is None:
            return jsonify({"error": "Unauthorized"}), 401
        request._current_donor = donor
        return fn(*args, **kwargs)
    return wrapper


def require_role(*roles):
    from functools import wraps
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            donor = current_donor()
            if donor is None:
                return jsonify({"error": "Unauthorized"}), 401
            if donor.role not in roles:
                return jsonify({"error": "Forbidden"}), 403
            request._current_donor = donor
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def _err(msg, code=400):
    return jsonify({"error": msg}), code


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    required = ["name", "email", "phone", "blood_type", "city", "age", "weight", "password"]
    missing = [f for f in required if f not in data or data.get(f) in (None, "")]
    if missing:
        return _err(f"Missing fields: {', '.join(missing)}")
    email = str(data["email"]).strip().lower()
    if Donor.query.filter_by(email=email).first():
        return _err("Email already registered", 409)
    role = str(data.get("role", "donor")).strip().lower()
    if role not in VALID_ROLES or role not in ("donor", "center", "hospital", "admin"):
        return _err("invalid role")
    # only admin can create non-donor roles (bootstrap: first user becomes admin if none exist)
    if role != "donor" and Donor.query.filter(Donor.role != "donor").count() == 0 and role != "admin":
        role = "donor"
    try:
        donor = Donor(
            name=str(data["name"]).strip(),
            email=email,
            phone=str(data["phone"]).strip(),
            blood_type=str(data["blood_type"]).strip().upper(),
            city=str(data["city"]).strip(),
            age=int(data["age"]),
            weight=float(data["weight"]),
            role=role,
        )
        donor.set_password(str(data["password"]))
        db.session.add(donor)
        db.session.commit()
    except (ValueError, TypeError) as e:
        db.session.rollback()
        return _err(f"Invalid data: {e}")
    access = make_token(donor.id, donor.role, refresh=False)
    refresh = make_token(donor.id, donor.role, refresh=True)
    return jsonify({"access_token": access, "refresh_token": refresh, "donor": donor.to_dict()}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    donor = Donor.query.filter_by(email=email).first()
    if not donor or not donor.check_password(password):
        return _err("Invalid credentials", 401)
    access = make_token(donor.id, donor.role, refresh=False)
    refresh = make_token(donor.id, donor.role, refresh=True)
    return jsonify({"access_token": access, "refresh_token": refresh, "donor": donor.to_dict()})


@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    data = request.get_json(silent=True) or {}
    token = data.get("refresh_token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    parsed = verify_token(token, refresh=True)
    if not parsed:
        return _err("Invalid or expired refresh token", 401)
    donor = Donor.query.get(int(parsed["sub"]))
    if not donor:
        return _err("User not found", 404)
    access = make_token(donor.id, donor.role, refresh=False)
    return jsonify({"access_token": access})


@auth_bp.route("/me", methods=["GET"])
def me():
    donor = current_donor()
    if donor is None:
        return _err("Unauthorized", 401)
    return jsonify(donor.to_dict())
