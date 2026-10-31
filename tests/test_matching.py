"""Geographic donor matching tests (Week-1 productization milestone).

Covers: haversine anchors (non-circular), ABO/Rh compatibility table,
donation-interval eligibility, distance filtering + ordering, city fallback
when the emergency has no coordinates, and the public PII-minimal endpoint.
"""

import os
from datetime import UTC, datetime, timedelta

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("FLASK_DEBUG", "0")

from app import create_app
from models.models import db
from services.matching import (
    COMPATIBLE_DONORS,
    MIN_DONATION_INTERVAL_DAYS,
    can_donate_now,
    compatible_types,
    haversine_km,
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    dbfile = str(tmp_path / "test.db")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{dbfile}")
    monkeypatch.setenv("LIFELINK_DB_PATH", dbfile)
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    monkeypatch.setenv("FIELD_ENCRYPTION_KEY", "integration-test-key-32bytes!!!!")
    from routes import middleware
    middleware._buckets.clear()
    app = create_app()
    app.config["TESTING"] = True
    with app.app_context():
        db.drop_all()
        db.create_all()
    with app.test_client() as c:
        yield c, app


_email_seq = iter(range(1, 100000))


def _add_donor(app, *, blood_type="O-", city="Sanaa", lat=None, lng=None,
               available=True, last_donation=None, email=None):
    with app.app_context():
        from models.models import Donor
        donor = Donor(
            name="X", email=email or f"donor-{next(_email_seq)}@test.io",
            phone="+967700000000", blood_type=blood_type, city=city,
            age=30, weight=70, available=available,
            last_donation=last_donation, latitude=lat, longitude=lng,
        )
        db.session.add(donor)
        db.session.commit()
        return donor.id


def _add_emergency(app, *, blood_type="O-", city="Sanaa", lat=None, lng=None):
    with app.app_context():
        from models.models import EmergencyRequest
        req = EmergencyRequest(
            patient_name="P", blood_type=blood_type, units_needed=1,
            hospital="H", city=city, contact_phone="+967700000000",
            urgency="critical", status="open", latitude=lat, longitude=lng,
        )
        db.session.add(req)
        db.session.commit()
        return req.id


# ───────────────────────── haversine (non-circular anchors) ─────────────────────────

def test_haversine_zero_distance():
    assert haversine_km(24.7, 46.7, 24.7, 46.7) == pytest.approx(0.0, abs=1e-9)


def test_haversine_one_degree_longitude_at_equator():
    # 1 degree of longitude at the equator = 2*pi*R/360 ≈ 111.195 km (IUGG R)
    assert haversine_km(0.0, 0.0, 0.0, 1.0) == pytest.approx(111.195, abs=0.01)


def test_haversine_quarter_meridian():
    # equator → north pole = half of the polar circumference ≈ 10007.5 km
    assert haversine_km(0.0, 0.0, 90.0, 0.0) == pytest.approx(10007.543, abs=0.5)


def test_haversine_symmetric_and_monotonic():
    a, b, c = (24.7, 46.7), (24.0, 46.0), (21.4, 39.2)   # Sanaa-ish → Jeddah-ish
    assert haversine_km(*a, *b) == pytest.approx(haversine_km(*b, *a))
    assert haversine_km(*a, *c) > haversine_km(*a, *b)


# ───────────────────────── blood compatibility ─────────────────────────

def test_compatibility_table_is_complete_and_valid():
    types = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}
    assert set(COMPATIBLE_DONORS) == types
    for donors in COMPATIBLE_DONORS.values():
        assert set(donors) <= types
        assert "O-" in donors          # universal donor fits everyone
    assert COMPATIBLE_DONORS["O-"] == ("O-",)                     # most restrictive
    assert set(COMPATIBLE_DONORS["AB+"]) == types                 # universal recipient


def test_compatible_types_normalizes_and_rejects():
    assert compatible_types("a+") == COMPATIBLE_DONORS["A+"]
    assert compatible_types(" o- ") == ("O-",)
    assert compatible_types("Z+") == ()
    assert compatible_types("") == ()


# ───────────────────────── donation interval ─────────────────────────

def test_can_donate_now_rules():
    now = datetime.now(UTC)
    assert can_donate_now(None, now) is True
    assert can_donate_now(now - timedelta(days=10), now) is False
    assert can_donate_now(now - timedelta(days=90), now) is True
    assert can_donate_now(now - timedelta(days=MIN_DONATION_INTERVAL_DAYS), now) is True
    # naive datetime (DB reality) is treated as UTC, not a crash
    assert can_donate_now(datetime(2026, 1, 1), now) is True


# ───────────────────────── service-level matching ─────────────────────────

def test_matching_filters_incompatible_blood(client):
    c, app = client
    _add_donor(app, blood_type="A+", city="Sanaa", lat=24.7, lng=46.7)
    ok_id = _add_donor(app, blood_type="O-", city="Sanaa", lat=24.71, lng=46.71)
    req_id = _add_emergency(app, blood_type="O-", city="Sanaa", lat=24.7, lng=46.7)
    r = c.get(f"/api/emergencies/{req_id}/matches")
    assert r.status_code == 200
    ids = [m["donor_id"] for m in r.get_json()["matches"]]
    assert ok_id in ids and all(
        m["blood_type"] == "O-" for m in r.get_json()["matches"])


def test_matching_orders_by_distance_and_respects_max_km(client):
    c, app = client
    near = _add_donor(app, blood_type="O-", lat=24.709, lng=46.709)   # ~0.5 km
    mid = _add_donor(app, blood_type="O-", lat=24.72, lng=46.72)      # ~2.6 km
    _add_donor(app, blood_type="O-", lat=24.9, lng=46.9)              # ~31 km
    req_id = _add_emergency(app, blood_type="O-", lat=24.7, lng=46.7)

    r = c.get(f"/api/emergencies/{req_id}/matches").get_json()
    assert [m["donor_id"] for m in r["matches"]] == [near, mid]
    assert r["matches"][0]["distance_km"] < r["matches"][1]["distance_km"]

    r25 = c.get(f"/api/emergencies/{req_id}/matches?max_km=25").get_json()
    assert len(r25["matches"]) == 2
    r1 = c.get(f"/api/emergencies/{req_id}/matches?max_km=1").get_json()
    assert r1["count"] == 0


def test_matching_excludes_unavailable_and_recent_donors(client):
    c, app = client
    now = datetime.now(UTC)
    _add_donor(app, blood_type="O-", lat=24.7, lng=46.7, available=False)
    _add_donor(app, blood_type="O-", lat=24.7, lng=46.7,
               last_donation=now - timedelta(days=10))
    eligible = _add_donor(app, blood_type="O-", lat=24.7, lng=46.7,
                          last_donation=now - timedelta(days=90))
    req_id = _add_emergency(app, blood_type="O-", lat=24.7, lng=46.7)
    r = c.get(f"/api/emergencies/{req_id}/matches").get_json()
    assert [m["donor_id"] for m in r["matches"]] == [eligible]


def test_matching_city_fallback_without_coordinates(client):
    c, app = client
    in_city = _add_donor(app, blood_type="O-", city="Sanaa")          # no coords
    _add_donor(app, blood_type="O-", city="Aden")                     # other city
    req_id = _add_emergency(app, blood_type="O-", city="Sanaa")       # no coords
    r = c.get(f"/api/emergencies/{req_id}/matches").get_json()
    assert [m["donor_id"] for m in r["matches"]] == [in_city]
    assert r["matches"][0]["distance_km"] is None


def test_matching_geo_mode_requires_donor_coordinates(client):
    c, app = client
    _add_donor(app, blood_type="O-", city="Sanaa")                    # no coords
    req_id = _add_emergency(app, blood_type="O-", lat=24.7, lng=46.7)
    r = c.get(f"/api/emergencies/{req_id}/matches").get_json()
    assert r["count"] == 0        # cannot prove distance → excluded, honestly


# ───────────────────────── endpoint contract ─────────────────────────

def test_matches_endpoint_is_pii_minimal(client):
    c, app = client
    _add_donor(app, blood_type="O-", city="Sanaa", lat=24.7, lng=46.7)
    req_id = _add_emergency(app, blood_type="O-", lat=24.7, lng=46.7)
    r = c.get(f"/api/emergencies/{req_id}/matches")
    assert r.status_code == 200
    m = r.get_json()["matches"][0]
    assert set(m) == {"donor_id", "blood_type", "city", "distance_km"}
    for banned in ("name", "phone", "email", "contact"):
        assert banned not in m


def test_matches_endpoint_404_and_bad_max_km(client):
    c, app = client
    assert c.get("/api/emergencies/9999/matches").status_code == 404
    req_id = _add_emergency(app, blood_type="O-", lat=24.7, lng=46.7)
    assert c.get(f"/api/emergencies/{req_id}/matches?max_km=abc").status_code == 400
    assert c.get(f"/api/emergencies/{req_id}/matches?max_km=-5").status_code == 400


def test_donor_creation_accepts_and_validates_coordinates(client):
    c, _ = client
    payload = {
        "name": "Geo", "email": "geo@test.com", "phone": "+967700000000",
        "blood_type": "O+", "city": "Sanaa", "age": 25, "weight": 70,
        "latitude": 24.7136, "longitude": 46.6753,
    }
    assert c.post("/api/donors", json=payload).status_code == 201
    bad = dict(payload, email="geo2@test.com", latitude=95.0)
    assert c.post("/api/donors", json=bad).status_code == 400
    bad2 = dict(payload, email="geo3@test.com", longitude="north")
    assert c.post("/api/donors", json=bad2).status_code == 400


def test_emergency_creation_accepts_and_validates_coordinates(client):
    c, _ = client
    payload = {
        "patient_name": "P", "blood_type": "A+", "hospital": "H",
        "city": "Sanaa", "contact_phone": "+967700000000",
        "latitude": 24.7, "longitude": 46.7,
    }
    assert c.post("/api/emergencies", json=payload).status_code == 201
    bad = dict(payload, latitude=24.7, longitude=200.0)
    assert c.post("/api/emergencies", json=bad).status_code == 400
