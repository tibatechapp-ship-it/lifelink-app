# LifeLink — Security Closeout (Day 5)

**Date:** 2026-10-27
**Version:** 1.0.0 (security-hardened)
**Repo:** tibatechapp-ship-it/lifelink-app

## Findings closed (10/10)

| # | Finding | Severity | Status | Evidence |
|---|---|---|---|---|
| L1 | No auth on REST API | CRITICAL | CLOSED | @jwt_required on all mutating + PII GET routes |
| L2 | No authorization | CRITICAL | CLOSED | role-based: donor/center/hospital/admin |
| L3 | Partial validation | HIGH | CLOSED | Pydantic (DonorIn/EmergencyIn), 13 validation tests |
| L4 | No rate limiting | HIGH | CLOSED | per-IP sliding window (60 GET / 10 POST per min), 4 tests |
| L5 | HTTPS undocumented | HIGH | DOCUMENTED | docs/deployment.md (nginx/Caddy reverse proxy) |
| L6 | Secret default | MEDIUM | CLOSED | ephemeral fallback + RuntimeError if FLASK_ENV=production & no SECRET_KEY |
| L7 | CORS open | MEDIUM | CLOSED | CORS_ORIGINS env, restricted origins |
| L8 | Docker root | MEDIUM | CLOSED | non-root user + healthcheck |
| L9 | No tests | HIGH | CLOSED | 38 tests (17 auth + 13 validation + 4 ratelimit + 4 integration) |
| L10 | PII plaintext | HIGH | CLOSED | Fernet field-level encryption (name/phone/city/patient_name/contact_phone/hospital) verified at rest |

## Remaining / known risks
- L5 (HTTPS) depends on reverse proxy deployment (operator responsibility).
- Token revocation not implemented (tokens valid until expiry). Documented in SECURITY.md.
- Field-level search on encrypted fields not supported (city search uses plaintext city).
- No audit log (v2).
- No GDPR-grade compliance (v2).

## CI
- Workflow: .github/workflows/ci.yml (strict, no tolerant fallback).
- Tests: 38 passed.
- Badge: https://github.com/tibatechapp-ship-it/lifelink-app/actions/workflows/ci.yml/badge.svg

## Commits (D1-D4)
- f151fd9 feat(auth): add JWT auth + roles + authorization (D2)
- 218600d fix(auth): harden secrets, protect PII GET routes, separate salts, role escalation guard
- b6df4e2 feat(security): D3 - Pydantic + rate limiting + CORS + PII encryption + tests
- e21841d docs(security): add SECURITY.md
- 873b26b docs(deploy): Docker hardening + HTTPS deployment guide (D4)
- 197a4a7 feat(security): D4 - integration tests + PII encryption verified
- (this commit) docs(security): closeout report

## Threat model
docs/security/threat-model-lifelink.md
