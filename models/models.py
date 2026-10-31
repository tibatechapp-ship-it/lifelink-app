"""SQLAlchemy models for LifeLink."""

from datetime import UTC, datetime

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


def _decrypt(value):
    """Decrypt a field, importing the crypto backend lazily.

    The model module is the schema definition: migrations and metadata work must
    not require a native crypto extension just to read columns.
    """
    from models.encryption import decrypt_field

    return decrypt_field(value)


class Donor(db.Model):
    """A registered blood donor."""
    __tablename__ = "donors"
    __table_args__ = (
        db.Index("ix_donors_blood_city_avail", "blood_type", "city", "available"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=False)
    blood_type = db.Column(db.String(5), nullable=False, index=True)
    city = db.Column(db.String(80), nullable=False, index=True)
    age = db.Column(db.Integer, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    password_hash = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(20), default="donor", nullable=False, index=True)  # donor/center/hospital/admin
    last_donation = db.Column(db.DateTime, nullable=True)
    available = db.Column(db.Boolean, default=True, nullable=False)
    # مطابقة جغرافية اختيارية — بدونها تعمل المطابقة بالمدينة (خارطة المنتَجة أسبوع 1)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "name": _decrypt(self.name),
            "email": self.email,
            "phone": _decrypt(self.phone),
            "blood_type": self.blood_type,
            "city": _decrypt(self.city),
            "age": self.age,
            "weight": self.weight,
            "last_donation": self.last_donation.isoformat() if self.last_donation else None,
            "available": self.available,
            "role": self.role,
            "created_at": self.created_at.isoformat(),
        }


class EmergencyRequest(db.Model):
    """An urgent blood request."""
    __tablename__ = "emergency_requests"
    __table_args__ = (
        db.Index("ix_emerg_blood_city_status", "blood_type", "city", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    patient_name = db.Column(db.String(120), nullable=False)
    blood_type = db.Column(db.String(5), nullable=False, index=True)
    units_needed = db.Column(db.Integer, nullable=False, default=1)
    hospital = db.Column(db.String(150), nullable=False)
    city = db.Column(db.String(80), nullable=False, index=True)
    contact_phone = db.Column(db.String(30), nullable=False)
    urgency = db.Column(db.String(20), default="urgent", nullable=False, index=True)  # critical/urgent/normal
    status = db.Column(db.String(20), default="open", nullable=False, index=True)  # open/fulfilled/closed
    notes = db.Column(db.Text, nullable=True)
    # مطابقة جغرافية اختيارية — موقع المستشفى/النداء (خارطة المنتَجة أسبوع 1)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "patient_name": _decrypt(self.patient_name),
            "blood_type": self.blood_type,
            "units_needed": self.units_needed,
            "hospital": _decrypt(self.hospital),
            "city": self.city,
            "contact_phone": _decrypt(self.contact_phone),
            "urgency": self.urgency,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
        }
