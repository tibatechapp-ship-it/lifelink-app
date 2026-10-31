"""إحصاءات المشغّل /admin/stats — بوابات صلاحيات + حساب صادق (أسبوع 2).

العقد من الخطة: 401 للمجرّد، 200 للمشغّل — والأرقام صحيحة على بيانات معلومة.
"""

from __future__ import annotations

import os
import tempfile

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("FLASK_DEBUG", "0")
# بيئات المطورين أحياناً تحمل DATABASE_URL لقاعدة أخرى — الاستيراد يحتاج URL
# صالحاً لSQLAlchemy، والـfixture أدناه يعيد توجيهه لكل اختبار على حدة.
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(
    tempfile.mkdtemp(prefix="ll-stats-import-"), "import.db")

from app import create_app
from models.models import db
from routes.auth_routes import make_token


@pytest.fixture
def client(tmp_path, monkeypatch):
    dbfile = str(tmp_path / "stats.db")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{dbfile}")
    monkeypatch.setenv("LIFELINK_DB_PATH", dbfile)
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    monkeypatch.setenv("FIELD_ENCRYPTION_KEY", "stats-test-key-32bytes!!!!!!!")
    from routes import middleware
    middleware._buckets.clear()
    app = create_app()
    app.config["TESTING"] = True
    with app.app_context():
        db.drop_all()
        db.create_all()
    with app.test_client() as c:
        yield c


def _register_donor(c, email="donor@test.com", **overrides):
    body = {
        "name": "Ali", "email": email, "phone": "+967700000000",
        "blood_type": "O+", "city": "Sanaa", "age": 25, "weight": 70,
        "password": "secret123",
    }
    body.update(overrides)
    r = c.post("/api/auth/register", json=body)
    assert r.status_code == 201, r.get_json()
    return r.get_json()["donor"]                       # {"id": ..., ...}


def _promote_to_admin(email="admin@test.com"):
    """التسجيل الذاتي متبرع فقط — الترقية للـadmin يدوية من قاعدة البيانات."""
    from models.models import Donor
    d = Donor.query.filter_by(email=email).first()
    d.role = "admin"
    db.session.commit()
    return d


def _create_emergency(c, token, blood="O-", city="Sanaa"):
    r = c.post("/api/emergencies", headers={"Authorization": f"Bearer {token}"},
               json={
                   "patient_name": "مريض", "blood_type": blood, "units_needed": 2,
                   "hospital": "المستشفى المركزي", "city": city,
                   "contact_phone": "+967711111111", "urgency": "critical",
               })
    assert r.status_code == 201, r.get_json()
    return r.get_json()["id"]


# ───────────────────── بوابات الصلاحيات (عقد الخطة) ─────────────────────

def test_admin_stats_requires_auth_401(client):
    r = client.get("/admin/stats")
    assert r.status_code == 401


def test_admin_stats_forbidden_for_plain_donor_403(client):
    _register_donor(client)
    d = _register_donor(client, email="plain@test.com")
    r = client.get("/admin/stats",
                   headers={"Authorization": f"Bearer {make_token(d['id'], 'donor')}"})
    assert r.status_code == 403


def test_admin_stats_forbidden_for_center_role(client):
    _register_donor(client)
    d = _register_donor(client, email="center@test.com")
    from models.models import Donor
    with client.application.app_context():
        Donor.query.filter_by(email="center@test.com").first().role = "center"
        db.session.commit()
    r = client.get("/admin/stats",
                   headers={"Authorization": f"Bearer {make_token(d['id'], 'center')}"})
    assert r.status_code == 403


def test_admin_stats_forged_token_rejected(client):
    r = client.get("/admin/stats", headers={"Authorization": "Bearer fake.token.here"})
    assert r.status_code == 401


# ───────────────────── الأرقام صحيحة على بيانات معلومة ─────────────────────

def test_admin_stats_200_and_shape_for_admin(client):
    _register_donor(client)
    _register_donor(client, email="admin@test.com")
    with client.application.app_context():
        _promote_to_admin()
    r = client.get("/admin/stats",
                   headers={"Authorization": f"Bearer {make_token(2, 'admin')}"})
    assert r.status_code == 200
    body = r.get_json()
    for key in ("requests_total", "requests_open", "requests_fulfilled",
                "requests_by_blood_type", "open_by_blood_type",
                "avg_response_hours", "donors_total", "donors_available"):
        assert key in body
    assert body["requests_total"] == 0 and body["donors_total"] == 2
    assert body["avg_response_hours"] is None          # بلا مُلبّى = بلا رقم زائف


def test_admin_stats_counts_blood_types_and_fulfilment(client):
    from models.models import Donor

    _register_donor(client)
    d = _register_donor(client, email="center@test.com")
    with client.application.app_context():
        Donor.query.filter_by(email="center@test.com").first().role = "center"
        db.session.commit()
    center_token = make_token(d["id"], "center")

    e1 = _create_emergency(client, center_token, blood="O-")
    _create_emergency(client, center_token, blood="O-")
    _create_emergency(client, center_token, blood="A+", city="Aden")

    # سجّل المدير وروّجه (ids: 1=donor، 2=center، 3=admin)
    _register_donor(client, email="admin@test.com")
    with client.application.app_context():
        _promote_to_admin()
    admin_token = make_token(3, "admin")

    body = client.get("/admin/stats",
                      headers={"Authorization": f"Bearer {admin_token}"}).get_json()
    assert body["requests_total"] == 3
    assert body["requests_by_blood_type"] == {"O-": 2, "A+": 1}
    assert body["open_by_blood_type"] == {"O-": 2, "A+": 1}
    assert body["requests_open"] == 3 and body["requests_fulfilled"] == 0

    # تلبية نداء واحد → fulfilled_at يُختم مرة واحدة + المتوسط يصير رقماً حقيقياً
    r = client.put(f"/api/emergencies/{e1}",
                   headers={"Authorization": f"Bearer {center_token}"},
                   json={"status": "fulfilled"})
    assert r.status_code == 200
    assert r.get_json()["fulfilled_at"] is not None

    body = client.get("/admin/stats",
                      headers={"Authorization": f"Bearer {admin_token}"}).get_json()
    assert body["requests_open"] == 2 and body["requests_fulfilled"] == 1
    assert isinstance(body["avg_response_hours"], float) and body["avg_response_hours"] >= 0


def test_fulfilled_at_set_once_not_overwritten(client):
    """إعادة تغيير الحالة لاحقاً لا تُعيد ختم لحظة التلبية — الدقة أولاً."""
    from models.models import Donor

    _register_donor(client)
    d = _register_donor(client, email="center@test.com")
    with client.application.app_context():
        Donor.query.filter_by(email="center@test.com").first().role = "center"
        db.session.commit()
    center_token = make_token(d["id"], "center")
    eid = _create_emergency(client, center_token)

    client.put(f"/api/emergencies/{eid}",
               headers={"Authorization": f"Bearer {center_token}"},
               json={"status": "fulfilled"})
    first = client.get(f"/api/emergencies/{eid}",
                       headers={"Authorization": f"Bearer {center_token}"}).get_json()["fulfilled_at"]

    client.put(f"/api/emergencies/{eid}",
               headers={"Authorization": f"Bearer {center_token}"},
               json={"status": "closed"})
    closed = client.get(f"/api/emergencies/{eid}",
                        headers={"Authorization": f"Bearer {center_token}"}).get_json()
    assert closed["fulfilled_at"] == first             # الختم الأول يبقى
