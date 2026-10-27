"""Donor registration, search, and management routes."""

import re
from flask import Blueprint, request, jsonify
from models.models import db, Donor
from routes.auth_routes import current_donor, jwt_required, require_role
from models.encryption import encrypt_field

donor_bp = Blueprint("donors", __name__, url_prefix="/api/donors")

VALID_BLOOD_TYPES = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _err(msg, code=400):
    return jsonify({"error": msg}), code


def _validate_donor(data, partial=False):
    errors = []
    if not partial or "name" in data:
        name = (data.get("name") or "").strip()
        if not name or len(name) > 120:
            errors.append("name must be 1-120 chars")
    if not partial or "email" in data:
        email = (data.get("email") or "").strip()
        if not email or not EMAIL_RE.match(email) or len(email) > 120:
            errors.append("invalid email")
    if not partial or "phone" in data:
        phone = (data.get("phone") or "").strip()
        if not phone or len(phone) > 30:
            errors.append("phone must be 1-30 chars")
    if not partial or "blood_type" in data:
        bt = (data.get("blood_type") or "").strip().upper()
        if bt not in VALID_BLOOD_TYPES:
            errors.append("invalid blood_type")
    if not partial or "city" in data:
        city = (data.get("city") or "").strip()
        if not city or len(city) > 80:
            errors.append("city must be 1-80 chars")
    if not partial or "age" in data:
        try:
            age = int(data.get("age"))
        except (TypeError, ValueError):
            errors.append("age must be an integer")
        else:
            if age < 18 or age > 65:
                errors.append("age must be between 18 and 65")
    if not partial or "weight" in data:
        try:
            weight = float(data.get("weight"))
        except (TypeError, ValueError):
            errors.append("weight must be a number")
        else:
            if weight < 45 or weight > 250:
                errors.append("weight must be between 45 and 250")
    if "available" in data and not isinstance(data["available"], bool):
        # accept truthy strings from forms
        if str(data["available"]).lower() not in ("true", "false", "1", "0"):
            errors.append("available must be boolean")
    return errors


@donor_bp.route("", methods=["GET"])
@jwt_required
def list_donors():
    """List donors with optional filters: blood_type, city, available."""
    q = Donor.query
    blood_type = request.args.get("blood_type")
    city = request.args.get("city")
    available = request.args.get("available")
    if blood_type:
        bt = blood_type.strip().upper()
        if bt in VALID_BLOOD_TYPES:
            q = q.filter(Donor.blood_type == bt)
    if city:
        safe_city = city.strip()[:80]
        q = q.filter(Donor.city.ilike(f"%{safe_city}%"))
    if available is not None:
        q = q.filter(Donor.available == (str(available).lower() == "true"))
    donors = q.order_by(Donor.created_at.desc()).limit(500).all()
    return jsonify({"count": len(donors), "donors": [d.to_dict() for d in donors]})


@donor_bp.route("/<int:donor_id>", methods=["GET"])
@jwt_required
def get_donor(donor_id):
    donor = Donor.query.get_or_404(donor_id)
    return jsonify(donor.to_dict())


@donor_bp.route("", methods=["POST"])
@jwt_required
def create_donor():
    data = request.get_json(silent=True) or {}
    required = ["name", "email", "phone", "blood_type", "city", "age", "weight"]
    missing = [f for f in required if f not in data or data.get(f) in (None, "")]
    if missing:
        return _err(f"Missing fields: {', '.join(missing)}")
    errors = _validate_donor(data)
    if errors:
        return _err("; ".join(errors))
    if Donor.query.filter_by(email=str(data["email"]).strip()).first():
        return _err("Email already registered", 409)
    try:
        donor = Donor(
            name=encrypt_field(str(data["name"]).strip()),
            email=str(data["email"]).strip(),
            phone=encrypt_field(str(data["phone"]).strip()),
            blood_type=str(data["blood_type"]).strip().upper(),
            city=str(data["city"]).strip(),
            age=int(data["age"]),
            weight=float(data["weight"]),
            available=_to_bool(data.get("available", True)),
        )
        db.session.add(donor)
        db.session.commit()
    except (ValueError, TypeError) as e:
        db.session.rollback()
        return _err(f"Invalid data: {e}")
    return jsonify(donor.to_dict()), 201


def _to_bool(v):
    if isinstance(v, bool):
        return v
    return str(v).lower() in ("true", "1", "yes", "on")


@donor_bp.route("/<int:donor_id>", methods=["PUT"])
@jwt_required
def update_donor(donor_id):
    donor = Donor.query.get_or_404(donor_id)
    current = current_donor()
    if current is None or (current.id != donor.id and current.role not in ("admin", "center")):
        return _err("Forbidden", 403)
    data = request.get_json(silent=True) or {}
    if not data:
        return _err("No data provided")
    errors = _validate_donor(data, partial=True)
    if errors:
        return _err("; ".join(errors))
    field_map = {
        "name": lambda v: encrypt_field(str(v).strip()),
        "phone": lambda v: encrypt_field(str(v).strip()),
        "blood_type": lambda v: str(v).strip().upper(),
        "city": lambda v: str(v).strip(),
        "age": lambda v: int(v),
        "weight": lambda v: float(v),
        "available": _to_bool,
    }
    for field, transform in field_map.items():
        if field in data:
            try:
                setattr(donor, field, transform(data[field]))
            except (ValueError, TypeError) as e:
                db.session.rollback()
                return _err(f"Invalid {field}: {e}")
    db.session.commit()
    return jsonify(donor.to_dict())


@donor_bp.route("/<int:donor_id>", methods=["DELETE"])
@jwt_required
def delete_donor(donor_id):
    donor = Donor.query.get_or_404(donor_id)
    current = current_donor()
    if current is None or (current.id != donor.id and current.role not in ("admin",)):
        return _err("Forbidden", 403)
    db.session.delete(donor)
    db.session.commit()
    return jsonify({"deleted": donor_id}), 200


@donor_bp.route("/search", methods=["GET"])
def search_donors():
    """Search donors by blood type and city (for matching emergency requests)."""
    blood_type = request.args.get("blood_type", "").upper().strip()
    city = request.args.get("city", "").strip()
    q = Donor.query.filter_by(available=True)
    if blood_type:
        if blood_type in VALID_BLOOD_TYPES:
            q = q.filter(Donor.blood_type == blood_type)
    if city:
        q = q.filter(Donor.city.ilike(f"%{city[:80]}%"))
    donors = q.limit(200).all()
    return jsonify({"count": len(donors), "donors": [d.to_dict() for d in donors]})
