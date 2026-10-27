# Security Policy

## Supported Versions
| Version | Supported |
|---|---|
| 1.x | ✅ |
| < 1.0 | ❌ |

## Authentication
- JWT-like tokens via itsdangerous (URLSafeTimedSerializer), signed with JWT_SECRET_KEY (or SECRET_KEY).
- Token TTL: 24h (access), 7 days (refresh).
- No token revocation (MVP limitation — tokens valid until expiry). Set JWT_SECRET_KEY in production.
- Passwords: PBKDF2-SHA256 via werkzeug.security (default 260k iterations).

## Rate Limiting
- Per-IP sliding window: 60 req/min (GET), 10 req/min (POST/PUT/DELETE).
- Disabled via RATE_LIMIT_ENABLED=0 (tests only).

## PII Encryption
- Sensitive donor/emergency fields (name, phone, city, patient_name, contact_phone, hospital) encrypted at rest with Fernet (AES-128-CBC + HMAC).
- Key: FIELD_ENCRYPTION_KEY env var (separate from JWT_SECRET_KEY). Falls back to derived key (dev only).

## Reporting a Vulnerability
- Do NOT open a public issue.
- Email: security@vixona.dev
- Response target: 72 hours, resolution within 30 days.
- Coordinated disclosure appreciated.

## Known Limitations (v1)
- No field-level search on encrypted fields (city search uses plaintext city).
- No audit log (v2).
- No GDPR-grade compliance (v2).
- Tokens cannot be revoked before expiry (v2).
