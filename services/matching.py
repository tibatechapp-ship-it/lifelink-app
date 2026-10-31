"""Geographic donor matching — Week-1 milestone of the productization plan.

الدلالة المعلنة: أعلى مطابقة = **فصيلة متوافقة × الأقرب × آخر تبرع سليم**.

- توافق ABO/Rh القياسي هو المرشّح الأول (COMPATIBLE_DONORS).
- النداء بإحداثيات: تُحتسب المسافة بـ haversine، ويُستبعد من تجاوز ``max_km``
  ومن لا يملك إحداثيات (لا يمكن إثبات المسافة له).
- النداء بلا إحداثيات: fallback بالمدينة (نفس دلالة القوائم الحالية) و
  ``distance_km`` يعود ``None``.
- «آخر تبرع سليم» = مرّت 56 يوماً (8 أسابيع) أو لم يتبرع بعد.

الحمولة عمداً **PII-minimal**: donor_id/فصيلة/مدينة/مسافة فقط — لا اسم ولا
هاتف ولا بريد؛ التواصل يبقى عبر قنوات المشغّل الحالية.
"""
from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

# المستلم ← الفصائل التي يمكنه قبول الدم منها (قاعدة ABO/Rh القياسية)
COMPATIBLE_DONORS: dict[str, tuple[str, ...]] = {
    "O-": ("O-",),
    "O+": ("O-", "O+"),
    "A-": ("O-", "A-"),
    "A+": ("O-", "O+", "A-", "A+"),
    "B-": ("O-", "B-"),
    "B+": ("O-", "O+", "B-", "B+"),
    "AB-": ("O-", "A-", "B-", "AB-"),
    "AB+": ("O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"),
}

MIN_DONATION_INTERVAL_DAYS = 56   # 8 أسابيع — المعيار الصحي العالمي
DEFAULT_MAX_KM = 25.0
DEFAULT_LIMIT = 10
_EARTH_RADIUS_KM = 6371.0088      # متوسط نصف قطر الأرض (IUGG)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """المسافة العظمى-الدائرية بالكيلومتر بين نقطتين (الإدخال بالدرجات)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2)
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def compatible_types(recipient: str) -> tuple[str, ...]:
    """الفصائل التي يستطيع المستلم ``recipient`` قبولها — فارغة إن كان الإدخال غير صالح."""
    return COMPATIBLE_DONORS.get((recipient or "").strip().upper(), ())


def can_donate_now(last_donation: datetime | None,
                   now: datetime | None = None) -> bool:
    """``True`` إن كان المتبرع مؤهلاً زمنياً (لم يتبرع خلال 56 يوماً أو إطلاقاً)."""
    if last_donation is None:
        return True
    now = now or datetime.now(UTC)
    if last_donation.tzinfo is None:
        last_donation = last_donation.replace(tzinfo=UTC)
    return now - last_donation >= timedelta(days=MIN_DONATION_INTERVAL_DAYS)


def find_matching_donors(emergency: Any, *,
                         max_km: float = DEFAULT_MAX_KM,
                         limit: int = DEFAULT_LIMIT,
                         now: datetime | None = None) -> list[dict[str, Any]]:
    """أفضل المتبرعين لنداء معين: متوافقون، مؤهلون زمنياً، الأقرب أولاً.

    قراءة-فقط: لا تنفّذ ولا تعدّل أي سجل، وتُرجع حمولة خالية من بيانات الاتصال.
    """
    from models.encryption import decrypt_field
    from models.models import Donor

    types = compatible_types(getattr(emergency, "blood_type", ""))
    if not types:
        return []
    now = now or datetime.now(UTC)
    rows = Donor.query.filter(
        Donor.available.is_(True),
        Donor.blood_type.in_(list(types)),
    ).all()

    has_geo = (getattr(emergency, "latitude", None) is not None
               and getattr(emergency, "longitude", None) is not None)
    req_city = (getattr(emergency, "city", "") or "").strip().lower()

    matches: list[dict[str, Any]] = []
    for d in rows:
        if not can_donate_now(d.last_donation, now):
            continue
        if has_geo:
            if d.latitude is None or d.longitude is None:
                continue          # بلا إحداثيات لا يمكن إثبات المسافة
            dist = haversine_km(emergency.latitude, emergency.longitude,
                                d.latitude, d.longitude)
            if dist > max_km:
                continue
        else:
            if ((d.city or "").strip().lower() != req_city):
                continue
            dist = None
        matches.append({
            "donor_id": d.id,
            "blood_type": d.blood_type,
            "city": decrypt_field(d.city),
            "distance_km": round(dist, 3) if dist is not None else None,
        })

    matches.sort(key=lambda m: (m["distance_km"] is None,
                                m["distance_km"] or 0.0))
    return matches[:limit]


__all__ = [
    "COMPATIBLE_DONORS",
    "DEFAULT_LIMIT",
    "DEFAULT_MAX_KM",
    "MIN_DONATION_INTERVAL_DAYS",
    "can_donate_now",
    "compatible_types",
    "find_matching_donors",
    "haversine_km",
]
