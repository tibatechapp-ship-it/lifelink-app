# LifeLink — Security Threat Model & Remediation Plan

**Date:** 2026-10-27
**Scope:** Flask REST API + SQLite + Docker (blood donation PII: name, phone, email, blood type, city, age, weight)
**Status:** Audit findings — remediation scoped as "Full" (4 days).

## 1. Attack surface (as found)

| # | Finding | Severity | Evidence (file:line) |
|---|---|---|---|
| L1 | No authentication on REST API | CRITICAL | routes/donor_routes.py (all endpoints public); routes/emergency_routes.py (all public) |
| L2 | No authorization (who sees what) | CRITICAL | get_donor returns any donor by id; list_donors returns all |
| L3 | Input validation partial | HIGH | _validate_donor exists but no Pydantic; available field accepts truthy strings; no size limits on JSON body |
| L4 | No rate limiting | HIGH | no Flask-Limiter; enumeration of donors/emergencies trivial |
| L5 | HTTPS not documented | HIGH | Dockerfile exposes 5000; no TLS/proxy doc |
| L6 | Flask secret default + debug flag | MEDIUM | app.py:17-22 (insecure dev default secret); app.py:55 (FLASK_DEBUG env) |
| L7 | CORS not configured | MEDIUM | no CORS setup found |
| L8 | Docker runs as root, ports exposed | MEDIUM | Dockerfile: no USER, EXPOSE 5000, CMD python app.py |
| L9 | No tests | HIGH | tests/ directory absent |
| L10 | PII stored plaintext | MEDIUM | models/models.py (verify fields) — name/phone/email/city in cleartext |

## 2. Remediation plan — Full (4 days)

### Day 1 — Threat model + current-state probe
- Write this doc (done).
- Probe current behavior: unauth GET/POST, oversized payload, XSS in fields, debug mode.
- Output: gap report + SECURITY.md update.

### Day 2 — Auth + Authorization
- Add JWT (Flask-JWT-Extended) or session auth.
- Roles: donor (self), center (region), hospital (read emergencies), admin.
- Tests: tests/test_auth.py (>=10 cases: login, bad creds, expired token, role denial).

### Day 3 — Validation + Rate limit + CORS
- Pydantic models for Donor/Emergency input; reject oversized (>1MB) bodies.
- Flask-Limiter: per-IP limits on POST/GET.
- CORS: restrict to known origins.
- Tests: tests/test_validation.py, tests/test_ratelimit.py.

### Day 4 — Docker hardening + HTTPS doc + integration test
- Non-root user in Dockerfile; healthcheck; secrets via env; no debug in prod.
- docs/deployment.md (reverse proxy + TLS).
- Integration test end-to-end.
- CI green with tests.

## 3. Immediate actions (today, before code)
1. Probe current state (commands below).
2. Decide user model: donor / center / hospital / admin.
3. Decide PII encryption scope (at rest? field-level?).
4. Choose auth: JWT (stateless, mobile-friendly) vs session (simpler).

## 4. Probe commands (run now)
```bash
cd lifelink-app
grep -rn "SECRET_KEY\|DEBUG\|password\|api_key\|CORS\|Limiter" --include="*.py" .
cat models/models.py
cat routes/emergency_routes.py
```

## 5. Acceptance criteria (Full scope)
- [ ] Auth on all /api/* mutating routes; role-based read.
- [ ] Pydantic validation on POST/PUT; 400 on invalid; 413 on oversized.
- [ ] Rate limit: 60 req/min per IP on GET, 10 req/min on POST.
- [ ] CORS restricted to configured origins.
- [ ] Docker non-root + healthcheck + no debug default.
- [ ] docs/deployment.md with HTTPS via reverse proxy.
- [ ] pytest >= 20 tests, CI green.
- [ ] SECURITY.md updated with supported versions + disclosure.

## 6. Non-goals (v1)
- No field-level PII encryption (v2).
- No audit log (v2).
- No GDPR-grade compliance (v2 — Compliance-ready scope).
