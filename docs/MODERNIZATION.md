# MODERNIZATION — chore/modernize (2026-10-30)

Safe, high-impact modernization pass. No major-version bumps, no API changes,
no `git push` from this branch without review.

---

## 0. App-breaking crash fixed (P0 — found during this pass)

**`routes/donor_routes.py` — the app could not be imported at all.**
Commit `06c6205` ("hide PII from public endpoints") added the `/donors/search`
route decorated as `@jwt_required()`, but the decorator is a plain function
(`def jwt_required(fn)` — no parenthesized form; the other 9 usages are bare).
Every `import app` — server boot, gunicorn entrypoint, pytest collection —
raised `TypeError: jwt_required() missing 1 required positional argument: 'fn'`.

* CI on `main` has been **failing** since that merge (verified via Actions
  history; last green run predates it).
* **Fix:** `@jwt_required()` → `@jwt_required` (one line, restores the
  decorator contract used everywhere else).
* **Evidence:** pristine tree → `4 errors during collection`; this branch →
  **68/68 passed**.

## 1. Security patches (pip-audit)

`pip-audit` on `requirements.txt` + `requirements-dev.txt` found real CVEs:

| Package | Before | After | Advisories fixed |
|---|---|---|---|
| `Werkzeug` | 3.1.3 | **3.1.9** (same 3.x major) | PYSEC-2026-2046 (→3.1.4), PYSEC-2026-2044 (→3.1.5), PYSEC-2026-2320 (→3.1.6), PYSEC-2026-4312 (→3.1.9) |

Post-bump audit: **No known vulnerabilities** on both files. The Docker image
inherits the fix on next build (it installs `requirements.txt`).

## 2. Unused dependencies

Import scan across the repo: **nothing to remove.**

* `pydantic` — used (`routes/validators.py`, the Pydantic validation layer).
* `psycopg[binary]` — the SQLAlchemy driver for the normalized
  `postgresql+psycopg://` URLs (`models/database.py`); imported by SQLAlchemy,
  not by app code.
* `gunicorn` — the container WSGI server (`scripts/entrypoint.sh` → gunicorn).
* `cryptography` — field-level Fernet encryption (`models/encryption.py`).

## 3. Dev experience (added)

| File | Purpose |
|---|---|
| `Makefile` | `make install` / `make test` / `make lint` / `make check` (lint+tests = "green") / `make run` / `make clean` |
| `.editorconfig` | Repo-wide format contract (4-space Python, 2-space YAML/TOML/JS, tabs for Makefile) |
| `.pre-commit-config.yaml` | ruff on staged files **+ full pytest on every commit** (safe here: the suite runs in ~4 s, unlike nexus-core's two-minute suite) |

**Second pass:** `make test` and the pytest pre-commit hook are now
**hermetic** — both run with `DATABASE_URL=` (blank, which the app's own
contract treats as unset → sqlite). A platform shell that exports an ambient
`DATABASE_URL` (exactly what happened during verification) can no longer
divert the suite's writes or crash collection; every test that needs a
specific URL still pins it via `monkeypatch`.

## 4. Performance — database indexes

**Verified end-to-end (models → migration → queries):** the B-tree indexes the
brief asked for already exist and are migrated, not just declared:
`ix_donors_blood_city_avail (blood_type, city, available)`,
`ix_emerg_blood_city_status (blood_type, city, status)`, plus single-column
indexes on `blood_type` / `city` / `status` / `urgency` / `role` / `email`.

**The real gap was elsewhere:** all three city searches use
`Donor.city.ilike('%<city>%')` — a **leading wildcard, which no B-tree index
can serve** (the planner sequential-scans; the composite indexes only help the
`blood_type` equality part of the query).

**New migration `a1f2c3d4e5b6`** adds GIN trigram indexes on `lower(city)` for
`donors` and `emergency_requests` — the standard index type that serves
`ILIKE '%…%'` — without touching any query or its substring semantics.

* PostgreSQL-only (dialect guard); sqlite dev/tests unaffected (verified:
  `alembic upgrade head` → `downgrade -1` → `upgrade head` walks cleanly).
* If a managed host refuses `CREATE EXTENSION pg_trgm`, the migration logs a
  warning and completes — the app keeps working, and re-running
  `alembic upgrade head` once the extension is granted picks the indexes up.
* `downgrade` drops the indexes and leaves the extension installed.

## 5. Verification

* `make test` — **68/68 passed**, including with a polluted ambient
  `DATABASE_URL` (the hermetic guard now covers that case).
* `make lint` (`ruff check .`) — all checks passed (CI lint gate).
* `alembic` up/down/up cycle — clean.
* `pip-audit` on `requirements.txt` and `requirements-dev.txt` — no known
  vulnerabilities.
* No test was modified; the only code changes are the one-line decorator fix
  (first pass) and the hermetic `make test` / pre-commit guard (second pass).

## 6. يحتاج قرار (needs decision)

* **Module-level `app = create_app()`** (`app.py`): the app object is built at
  import time, so an invalid `DATABASE_URL` in the environment crashes
  *collection* of any test module that imports `app`. The practical impact is
  now contained — `make test` and the pytest hook run hermetically — but the
  underlying coupling remains: moving construction into the
  `if __name__ == "__main__"` block (or a lazy factory pattern) would decouple
  import from environment validity. Deferred as it touches the WSGI contract
  (gunicorn points at `app:app`). Note the fail-fast behavior itself is
  correct: silently falling back to sqlite when an operator named a real
  database would misroute data.
* **City search semantics**: the trigram index makes the current
  substring search fast. If you'd rather have exact/prefix matching (faster
  still, and uses the existing B-tree), that is a product behavior change and
  was deliberately not made here.
