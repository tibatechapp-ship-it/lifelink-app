"""Donor registration, search, and management routes."""

from flask import Blueprint, request, jsonify
from models.models import db, Donor

donor_bp = Blueprint("donors", __name__, url_prefix="/api/donors")


@donor_bp.route("", methods=["GET"])
def list_donors():
    """List donors with optional filters: blood_type, city, available."""
    q = Donor.query
    blood_type = request.args.get("blood_type")
    city = request.args.get("city")
    available = request.args.get("available")
    if blood_type:
        q = q.filter(Donor.blood_type == blood_type.upper())
    if city:
        q = q.filter(Donor.city.ilike(f"%{city}%"))
    if available is not None:
        q = q.filter(Donor.available == (available.lower() == "true"))
    donors = q.order_by(Donor.created_at.desc()).all()
    return jsonify({"count": len(donors), "donors": [d.to_dict() for d in donors]})


@donor_bp.route("/<int:donor_id>", methods=["GET"])
def get_donor(donor_id):
    donor = Donor.query.get_or_404(donor_id)
    return jsonify(donor.to_dict())


@donor_bp.route("", methods=["POST"])
def create_donor():
    data = request.get_json(silent=True) or {}
    required = ["name", "email", "phone", "blood_type", "city", "age", "weight"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400
    if Donor.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email already registered"}), 409
    donor = Donor(
        name=data["name"],
        email=data["email"],
        phone=data["phone"],
        blood_type=data["blood_type"].upper(),
        city=data["city"],
        age=int(data["age"]),
        weight=float(data["weight"]),
        available=data.get("available", True),
    )
    db.session.add(donor)
    db.session.commit()
    return jsonify(donor.to_dict()), 201


@donor_bp.route("/<int:donor_id>", methods=["PUT"])
def update_donor(donor_id):
    donor = Donor.query.get_or_404(donor_id)
    data = request.get_json(silent=True) or {}
    for field in ["name", "phone", "blood_type", "city", "age", "weight", "available"]:
        if field in data:
            setattr(donor, field, data[field])
    if "blood_type" in data:
        donor.blood_type = data["blood_type"].upper()
    db.session.commit()
    return jsonify(donor.to_dict())


@donor_bp.route("/<int:donor_id>", methods=["DELETE"])
def delete_donor(donor_id):
    donor = Donor.query.get_or_404(donor_id)
    db.session.delete(donor)
    db.session.commit()
    return jsonify({"deleted": donor_id}), 200


@donor_bp.route("/search", methods=["GET"])
def search_donors():
    """Search donors by blood type and city (for matching emergency requests)."""
    blood_type = request.args.get("blood_type", "").upper()
    city = request.args.get("city", "")
    q = Donor.query.filter_by(available=True)
    if blood_type:
        q = q.filter(Donor.blood_type == blood_type)
    if city:
        q = q.filter(Donor.city.ilike(f"%{city}%"))
    donors = q.all()
    return jsonify({"count": len(donors), "donors": [d.to_dict() for d in donors]})
