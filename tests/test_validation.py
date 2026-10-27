"""Validation tests for LifeLink (Pydantic)."""

import os

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("FLASK_DEBUG", "0")

from routes.validators import DonorIn, EmergencyIn, validate


def test_donor_valid():
    obj, errs = validate(DonorIn, {
        "name": "Ali", "email": "a@b.com", "phone": "+967700000000",
        "blood_type": "O+", "city": "Sanaa", "age": 25, "weight": 70.0,
    })
    assert errs == []
    assert obj.name == "Ali"


def test_donor_missing_name():
    _, errs = validate(DonorIn, {"email": "a@b.com", "phone": "1", "blood_type": "O+", "city": "c", "age": 25, "weight": 70})
    assert any("name" in e for e in errs)


def test_donor_invalid_blood_type():
    _, errs = validate(DonorIn, {"name": "A", "email": "a@b.com", "phone": "1", "blood_type": "Z+", "city": "c", "age": 25, "weight": 70})
    assert any("blood_type" in e for e in errs)


def test_donor_age_too_young():
    _, errs = validate(DonorIn, {"name": "A", "email": "a@b.com", "phone": "1", "blood_type": "O+", "city": "c", "age": 10, "weight": 70})
    assert any("age" in e for e in errs)


def test_donor_age_too_old():
    _, errs = validate(DonorIn, {"name": "A", "email": "a@b.com", "phone": "1", "blood_type": "O+", "city": "c", "age": 90, "weight": 70})
    assert any("age" in e for e in errs)


def test_donor_weight_too_low():
    _, errs = validate(DonorIn, {"name": "A", "email": "a@b.com", "phone": "1", "blood_type": "O+", "city": "c", "age": 25, "weight": 10})
    assert any("weight" in e for e in errs)


def test_donor_name_too_long():
    _, errs = validate(DonorIn, {"name": "A" * 200, "email": "a@b.com", "phone": "1", "blood_type": "O+", "city": "c", "age": 25, "weight": 70})
    assert any("name" in e for e in errs)


def test_donor_invalid_email():
    _, errs = validate(DonorIn, {"name": "A", "email": "notanemail", "phone": "1", "blood_type": "O+", "city": "c", "age": 25, "weight": 70})
    assert any("email" in e for e in errs)


def test_emergency_valid():
    _obj, errs = validate(EmergencyIn, {
        "patient_name": "X", "blood_type": "O+", "hospital": "H", "city": "C", "contact_phone": "+967700000000",
    })
    assert errs == []


def test_emergency_invalid_blood_type():
    _, errs = validate(EmergencyIn, {"patient_name": "X", "blood_type": "Z+", "hospital": "H", "city": "C", "contact_phone": "+967700000000"})
    assert any("blood_type" in e for e in errs)


def test_emergency_units_out_of_range():
    _, errs = validate(EmergencyIn, {"patient_name": "X", "blood_type": "O+", "hospital": "H", "city": "C", "contact_phone": "+967700000000", "units_needed": 500})
    assert any("units_needed" in e for e in errs)


def test_emergency_notes_too_long():
    _, errs = validate(EmergencyIn, {"patient_name": "X", "blood_type": "O+", "hospital": "H", "city": "C", "contact_phone": "+967700000000", "notes": "x" * 3000})
    assert any("notes" in e for e in errs)


def test_emergency_invalid_urgency():
    _, errs = validate(EmergencyIn, {"patient_name": "X", "blood_type": "O+", "hospital": "H", "city": "C", "contact_phone": "+967700000000", "urgency": "super"})
    assert any("urgency" in e for e in errs)
