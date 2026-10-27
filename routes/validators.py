"""Pydantic validation models for LifeLink inputs."""

from pydantic import BaseModel, Field, field_validator, ValidationError
from typing import Optional


VALID_BLOOD_TYPES = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}
VALID_URGENCY = {"critical", "urgent", "normal"}
VALID_STATUS = {"open", "fulfilled", "closed"}


class DonorIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: str = Field(..., min_length=3, max_length=120)
    phone: str = Field(..., min_length=1, max_length=30)
    blood_type: str
    city: str = Field(..., min_length=1, max_length=80)
    age: int = Field(..., ge=18, le=65)
    weight: float = Field(..., ge=45, le=250)
    available: Optional[bool] = True

    @field_validator("blood_type")
    @classmethod
    def bt_valid(cls, v):
        v = v.strip().upper()
        if v not in VALID_BLOOD_TYPES:
            raise ValueError("invalid blood_type")
        return v

    @field_validator("email")
    @classmethod
    def email_valid(cls, v):
        v = v.strip()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("invalid email")
        return v


class EmergencyIn(BaseModel):
    patient_name: str = Field(..., min_length=1, max_length=120)
    blood_type: str
    hospital: str = Field(..., min_length=1, max_length=150)
    city: str = Field(..., min_length=1, max_length=80)
    contact_phone: str = Field(..., min_length=6, max_length=30)
    units_needed: int = Field(default=1, ge=1, le=100)
    urgency: str = Field(default="urgent")
    status: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("blood_type")
    @classmethod
    def bt_valid(cls, v):
        v = v.strip().upper()
        if v not in VALID_BLOOD_TYPES:
            raise ValueError("invalid blood_type")
        return v

    @field_validator("urgency")
    @classmethod
    def urg_valid(cls, v):
        v = (v or "urgent").strip().lower()
        if v not in VALID_URGENCY:
            raise ValueError("invalid urgency")
        return v

    @field_validator("status")
    @classmethod
    def status_valid(cls, v):
        if v is None:
            return v
        v = v.strip().lower()
        if v not in VALID_STATUS:
            raise ValueError("invalid status")
        return v


def validate(model_cls, data):
    """Return (obj, errors_list)."""
    try:
        return model_cls.model_validate(data), []
    except ValidationError as e:
        return None, [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]


__all__ = ["DonorIn", "EmergencyIn", "validate", "VALID_BLOOD_TYPES", "VALID_URGENCY", "VALID_STATUS"]
