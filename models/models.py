"""SQLAlchemy models for LifeLink."""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Donor(db.Model):
    """A registered blood donor."""
    __tablename__ = "donors"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    blood_type = db.Column(db.String(5), nullable=False, index=True)
    city = db.Column(db.String(80), nullable=False, index=True)
    age = db.Column(db.Integer, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    last_donation = db.Column(db.DateTime, nullable=True)
    available = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "blood_type": self.blood_type,
            "city": self.city,
            "age": self.age,
            "weight": self.weight,
            "last_donation": self.last_donation.isoformat() if self.last_donation else None,
            "available": self.available,
            "created_at": self.created_at.isoformat(),
        }


class EmergencyRequest(db.Model):
    """An urgent blood request."""
    __tablename__ = "emergency_requests"

    id = db.Column(db.Integer, primary_key=True)
    patient_name = db.Column(db.String(120), nullable=False)
    blood_type = db.Column(db.String(5), nullable=False, index=True)
    units_needed = db.Column(db.Integer, nullable=False, default=1)
    hospital = db.Column(db.String(150), nullable=False)
    city = db.Column(db.String(80), nullable=False, index=True)
    contact_phone = db.Column(db.String(30), nullable=False)
    urgency = db.Column(db.String(20), default="urgent", nullable=False)  # critical/urgent/normal
    status = db.Column(db.String(20), default="open", nullable=False)  # open/fulfilled/closed
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "patient_name": self.patient_name,
            "blood_type": self.blood_type,
            "units_needed": self.units_needed,
            "hospital": self.hospital,
            "city": self.city,
            "contact_phone": self.contact_phone,
            "urgency": self.urgency,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
        }
