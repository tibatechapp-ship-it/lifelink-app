# ── LifeLink: production image ──────────────────────────────────────────────
# Same image runs in compose and on a platform: migrations are applied by the
# entrypoint, then gunicorn serves the app. Nothing here needs a build step.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=5000

WORKDIR /app

# Dependencies first so a source change does not reinstall the world.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Fixed unprivileged uid/gid: the SQLite fallback and any mounted volume are
# then writable in a predictable way. No shell, no home directory.
RUN groupadd --gid 10001 lifelink \
 && useradd --uid 10001 --gid lifelink --no-create-home --shell /usr/sbin/nologin lifelink \
 && mkdir -p /app/instance /app/data \
 && chown -R lifelink:lifelink /app \
 && chmod +x /app/scripts/entrypoint.sh

USER lifelink

EXPOSE 5000

# Liveness only — /ready is the dependency check, and a healthcheck that needs
# Postgres turns a database outage into a restart loop.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import sys,urllib.request; r=urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=4); sys.exit(0 if r.status==200 else 1)"

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
