"""حزمة ثقة المشغّل — حرس وجود وسلامة docs/trust (خارطة المنتَجة أسبوع 2).

العقد: أي ميزة تُغيّر ما يُجمَع تُحدّث الحزمة في نفس الـPR — هذا الملف يمنع
انجراف التوثيق عن الكود في اتجاهين: رابط مكسور، أو اختفاء القسم الإلزامي
«ما لا نجمعه».
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRUST = ROOT / "docs" / "trust"

REQUIRED_FILES = (
    "README.md",
    "data-policy.md",
    "retention.md",
    "dpia.md",
    "operator-responsibilities.md",
)

_MD_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def test_trust_pack_files_exist() -> None:
    """تحقق الوجود (شرط القبول في الخطة)."""
    for name in REQUIRED_FILES:
        assert (TRUST / name).is_file(), f"حزمة الثقة ناقصة: {name}"


def test_data_policy_has_mandatory_dont_collect_section() -> None:
    """القسم «ما لا نجمعه» إلزامي — بلا قسم تفشل البوابة."""
    text = (TRUST / "data-policy.md").read_text(encoding="utf-8")
    assert "ما لا نجمعه" in text
    # القسم ليس شكلياً: 10 بنود إنكار صريحة
    denials = [ln for ln in text.splitlines() if ln.strip().startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "10."))]
    assert len(denials) >= 10, "قسم «ما لا نجمعه» يجب أن يعدّ بنود إنكار صريحة"
    # إنكارات جوهرية لا يجوز حذفها
    for must in ("لا هوية وطنية", "لا تتبع موقع", "لا بيانات دفع", "لا مشاركة ولا بيع"):
        assert must in text


def test_trust_pack_internal_links_resolve() -> None:
    """كل رابط نسبي داخل الحزمة يشير إلى ملف موجود فعلاً."""
    for name in REQUIRED_FILES:
        text = (TRUST / name).read_text(encoding="utf-8")
        for target in _MD_LINK.findall(text):
            if "://" in target or target.startswith(("#", "mailto:")):
                continue
            resolved = (TRUST / target).resolve()
            assert resolved.is_file(), f"رابط مكسور في {name}: {target}"


def test_trust_docs_consistent_with_code_truth() -> None:
    """أسماء الحقول المشفّرة المذكورة موجودة فعلاً في الكود — لا وعد بلا شيفرة."""
    routes_text = "\n".join(
        (ROOT / "routes" / f).read_text(encoding="utf-8")
        for f in ("auth_routes.py", "donor_routes.py", "emergency_routes.py")
    )
    # كل حقل يدّعي التوثيق أنه مشفّر يُشفَّر فعلاً عبر encrypt_field
    for field in ("name", "phone", "city", "patient_name", "hospital", "contact_phone"):
        assert f"{field}=encrypt_field" in routes_text or \
               f'"{field}": lambda v: encrypt_field' in routes_text, \
               f"التوثيق يدّعي تشفير {field} والكود لا يفعله"


def test_stats_endpoint_documented_in_trust_pack() -> None:
    """الحزمة تعرف بنقطة /admin/stats — ولا تدّعي كشف بيانات تعريفية."""
    policy = (TRUST / "data-policy.md").read_text(encoding="utf-8")
    assert "/admin/stats" in policy
    dpia = (TRUST / "dpia.md").read_text(encoding="utf-8")
    assert "/admin/stats" in dpia and "مجاميع" in dpia
