"""Emergency blood request routes."""

from flask import Blueprint, request, jsonify
from models.models import db, EmergencyRequest

emergency_bp = Blueprint("emergencies", __name__, url_prefix="/api/emergencies")


@emergency_bp.route("", methods=["GET"])
def list_emergencies():
    """List emergency requests with optional filters: status, blood_type, city, urgency."""
    q = EmergencyRequest.query
    status = request.args.get("status")
    blood_type = request.args.get("blood_type")
    city = request.args.get("city")
    urgency = request.args.get("urgency")
    if status:
        q = q.filter(EmergencyRequest.status == status)
    if blood_type:
        q = q.filter(EmergencyRequest.blood_type == blood_type.upper())
    if city:
        q = q.filter(EmergencyRequest.city.ilike(f"%{city}%"))
    if urgency:
        q = q.filter(EmergencyRequest.urgency == urgency)
    reqs = q.order_by(EmergencyRequest.created_at.desc()).all()
    return jsonify({"count": len(reqs), "requests": [r.to_dict() for r in reqs]})


@emergency_bp.route("/<int:req_id>", methods=["GET"])
def get_emergency(req_id):
    req = EmergencyRequest.query.get_or_404(req_id)
    return jsonify(req.to_dict())


@emergency_bp.route("", methods=["POST"])
def create_emergency():
    data = request.get_json(silent=True) or {}
    required = ["patient_name", "blood_type", "hospital", "city", "contact_phone"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400
    req = EmergencyRequest(
        patient_name=data["patient_name"],
        blood_type=data["blood_type"].upper(),
        units_needed=int(data.get("units_needed", 1)),
        hospital=data["hospital"],
        city=data["city"],
        contact_phone=data["contact_phone"],
        urgency=data.get("urgency", "urgent"),
        notes=data.get("notes"),
    )
    db.session.add(req)
    db.session.commit()
    return jsonify(req.to_dict()), 201


@emergency_bp.route("/<int:req_id>", methods=["PUT"])
def update_emergency(req_id):
    req = EmergencyRequest.query.get_or_404(req_id)
    data = request.get_json(silent=True) or {}
    for field in ["patient_name", "blood_type", "units_needed", "hospital", "city",
                  "contact_phone", "urgency", "status", "notes"]:
        if field in data:
            setattr(req, field, data[field])
    if "blood_type" in data:
        req.blood_type = data["blood_type"].upper()
    db.session.commit()
    return jsonify(req.to_dict())


@emergency_bp.route("/<int:req_id>", methods=["DELETE"])
def delete_emergency(req_id):
    req = EmergencyRequest.query.get_or_404(req_id)
    db.session.delete(req)
    db.session.commit()
    return jsonify({"deleted": req_id}), 200


@emergency_bp.route("/open", methods=["GET"])
def open_emergencies():
    """Convenience: list only open emergencies, most urgent first."""
    urgency_order = {"critical": 0, "urgent": 1, "normal": 2}
    reqs = EmergencyRequest.query.filter_by(status="open").all()
    reqs.sort(key=lambda r: (urgency_order.get(r.urgency, 3), r.created_at))
    return jsonify({"count": len(reqs), "requests": [r.to_dict() for r in reqs]})
