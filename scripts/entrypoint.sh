#!/bin/sh
# Container entrypoint: bring the schema up to date, then serve.
#
# Migrations run FIRST and in the foreground on purpose — a container that
# starts serving before its schema is ready answers 500s while the platform
# considers it healthy. If `alembic upgrade` fails, the container dies loudly
# and the platform keeps the previous version live.
set -eu

echo "entrypoint: applying migrations (alembic upgrade head)"
alembic upgrade head

echo "entrypoint: starting gunicorn on 0.0.0.0:${PORT:-5000}"
exec gunicorn \
    --bind "0.0.0.0:${PORT:-5000}" \
    --workers "${WEB_CONCURRENCY:-2}" \
    --threads "${WEB_THREADS:-4}" \
    --timeout "${WEB_TIMEOUT:-60}" \
    --access-logfile - \
    --error-logfile - \
    "app:create_app()"
