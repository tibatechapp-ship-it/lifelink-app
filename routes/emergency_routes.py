"""Emergency blood request routes."""

import re
from flask import Blueprint, request, jsonify
from routes.auth_routes import current_donor, jwt_required
from models.models import db, EmergencyRequest

emergency_bp = Blueprint("emergencies", __name__, url_prefix="/api/emergencies")

VALID_BLOOD_TYPES = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}
VALID_URGENCY = {"critical", "urgent", "normal"}
VALID_STATUS = {"open", "fulfilled", "closed"}
PHONE_RE = re.compile(r"^[\d\s\+\-\(\)]{6,30}$")


def _err(msg, code=400):
    return jsonify({"error": msg}), code


def _validate_emergency(data, partial=False):
    errors = []
    if not partial or "patient_name" in data:
        pn = (data.get("patient_name") or "").strip()
        if not pn or len(pn) > 120:
            errors.append("patient_name must be 1-120 chars")
    if not partial or "blood_type" in data:
        bt = (data.get("blood_type") or "").strip().upper()
        if bt not in VALID_BLOOD_TYPES:
            errors.append("invalid blood_type")
    if not partial or "hospital" in data:
        h = (data.get("hospital") or "").strip()
        if not h or len(h) > 150:
            errors.append("hospital must be 1-150 chars")
    if not partial or "city" in data:
        c = (data.get("city") or "").strip()
        if not c or len(c) > 80:
            errors.append("city must be 1-80 chars")
    if not partial or "contact_phone" in data:
        ph = (data.get("contact_phone") or "").strip()
        if not ph or not PHONE_RE.match(ph):
            errors.append("invalid contact_phone")
    if "units_needed" in data:
        try:
            u = int(data["units_needed"])
        except (TypeError, ValueError):
            errors.append("units_needed must be an integer")
        else:
            if u < 1 or u > 100:
                errors.append("units_needed must be between 1 and 100")
    if "urgency" in data:
        if str(data["urgency"]).strip().lower() not in VALID_URGENCY:
            errors.append("invalid urgency")
    if "status" in data:
        if str(data["status"]).strip().lower() not in VALID_STATUS:
            errors.append("invalid status")
    if "notes" in data and data["notes"] is not None:
        if not isinstance(data["notes"], str) or len(data["notes"]) > 2000:
            errors.append("notes must be <=2000 chars")
    return errors


@emergency_bp.route("", methods=["GET"])
def list_emergencies():
    q = EmergencyRequest.query
    status = request.args.get("status")
    blood_type = request.args.get("blood_type")
    city = request.args.get("city")
    urgency = request.args.get("urgency")
    if status:
        s = status.strip().lower()
        if s in VALID_STATUS:
            q = q.filter(EmergencyRequest.status == s)
    if blood_type:
        bt = blood_type.strip().upper()
        if bt in VALID_BLOOD_TYPES:
            q = q.filter(EmergencyRequest.blood_type == bt)
    if city:
        q = q.filter(EmergencyRequest.city.ilike(f"%{city.strip()[:80]}%"))
    if urgency:
        u = urgency.strip().lower()
        if u in VALID_URGENCY:
            q = q.filter(EmergencyRequest.urgency == u)
    reqs = q.order_by(EmergencyRequest.created_at.desc()).limit(500).all()
    return jsonify({"count": len(reqs), "requests": [r.to_dict() for r in reqs]})


@emergency_bp.route("/<int:req_id>", methods=["GET"])
def get_emergency(req_id):
    req = EmergencyRequest.query.get_or_404(req_id)
    return jsonify(req.to_dict())


@emergency_bp.route("", methods=["POST"])
@jwt_required
def create_emergency():
    data = request.get_json(silent=True) or {}
    required = ["patient_name", "blood_type", "hospital", "city", "contact_phone"]
    missing = [f for f in required if f not in data or data.get(f) in (None, "")]
    if missing:
        return _err(f"Missing fields: {', '.join(missing)}")
    errors = _validate_emergency(data)
    if errors:
        return _err("; ".join(errors))
    try:
        req = EmergencyRequest(
            patient_name=str(data["patient_name"]).strip(),
            blood_type=str(data["blood_type"]).strip().upper(),
            units_needed=int(data.get("units_needed", 1)),
            hospital=str(data["hospital"]).strip(),
            city=str(data["city"]).strip(),
            contact_phone=str(data["contact_phone"]).strip(),
            urgency=str(data.get("urgency", "urgent")).strip().lower(),
            notes=(str(data["notes"]).strip() if data.get("notes") is not None else None),
        )
        db.session.add(req)
        db.session.commit()
    except (ValueError, TypeError) as e:
        db.session.rollback()
        return _err(f"Invalid data: {e}")
    return jsonify(req.to_dict()), 201


@emergency_bp.route("/<int:req_id>", methods=["PUT"])
@jwt_required
def update_emergency(req_id):
    req = EmergencyRequest.query.get_or_404(req_id)
    current = current_donor()
    if current is None or current.role not in ("center", "hospital", "admin"):
        return _err("Forbidden", 403)
    data = request.get_json(silent=True) or {}
    if not data:
        return _err("No data provided")
    errors = _validate_emergency(data, partial=True)
    if errors:
        return _err("; ".join(errors))
    field_map = {
        "patient_name": lambda v: str(v).strip(),
        "blood_type": lambda v: str(v).strip().upper(),
        "units_needed": lambda v: int(v),
        "hospital": lambda v: str(v).strip(),
        "city": lambda v: str(v).strip(),
        "contact_phone": lambda v: str(v).strip(),
        "urgency": lambda v: str(v).strip().lower(),
        "status": lambda v: str(v).strip().lower(),
        "notes": lambda v: (str(v).strip() if v is not None else None),
    }
    for field, transform in field_map.items():
        if field in data:
            try:
                setattr(req, field, transform(data[field]))
            except (ValueError, TypeError) as e:
                db.session.rollback()
                return _err(f"Invalid {field}: {e}")
    db.session.commit()
    return jsonify(req.to_dict())


@emergency_bp.route("/<int:req_id>", methods=["DELETE"])
@jwt_required
def delete_emergency(req_id):
    req = EmergencyRequest.query.get_or_404(req_id)
    current = current_donor()
    if current is None or current.role not in ("center", "admin"):
        return _err("Forbidden", 403)
    db.session.delete(req)
    db.session.commit()
    return jsonify({"deleted": req_id}), 200


@emergency_bp.route("/open", methods=["GET"])
def open_emergencies():
    """Convenience: list only open emergencies, most urgent first."""
    from sqlalchemy import case
    urgency_order = case(
        (EmergencyRequest.urgency == "critical", 0),
        (EmergencyRequest.urgency == "urgent", 1),
        (EmergencyRequest.urgency == "normal", 2),
        else_=3,
    )
    reqs = (EmergencyRequest.query
            .filter_by(status="open")
            .order_by(urgency_order, EmergencyRequest.created_at.asc())
            .limit(500).all())
    return jsonify({"count": len(reqs), "requests": [r.to_dict() for r in reqs]})
