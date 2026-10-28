"""Deploy-artefact guards.

Local Termux has no Docker, so the real build is proven in CI (the `image` job).
What can be checked anywhere is the CONTRACT between the files: one migration
path, fail-closed secrets, and a database the entrypoint migrates before the
server starts listening. Each of these guards a failure that is silent in
production but obvious here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
DOCKERFILE = (ROOT / "Dockerfile").read_text()
ENTRYPOINT = (ROOT / "scripts" / "entrypoint.sh").read_text()


def test_compose_app_depends_on_a_healthy_database() -> None:
    app = COMPOSE["services"]["app"]
    assert app["depends_on"]["postgres"]["condition"] == "service_healthy"


def test_postgres_has_a_real_healthcheck() -> None:
    pg = COMPOSE["services"]["postgres"]
    assert "pg_isready" in " ".join(pg["healthcheck"]["test"])


def test_secrets_are_fail_closed() -> None:
    """`:?` makes compose refuse to start — never boot prod with a random key."""
    env = COMPOSE["services"]["app"]["environment"]
    assert "${SECRET_KEY:?" in env["SECRET_KEY"]
    assert "${DB_PASSWORD:?" in env["DATABASE_URL"]
    assert "${DB_PASSWORD:?" in COMPOSE["services"]["postgres"]["environment"]["POSTGRES_PASSWORD"]


def test_compose_does_not_hardcode_credentials_or_urls() -> None:
    text = (ROOT / "docker-compose.yml").read_text()
    assert "postgresql+psycopg://user:password" not in text
    assert "localhost:5432" not in text
    # The app must reach Postgres by service name inside the compose network.
    assert "@postgres:5432/" in COMPOSE["services"]["app"]["environment"]["DATABASE_URL"]


def test_compose_publishes_only_the_app_port() -> None:
    assert COMPOSE["services"]["app"]["ports"] == ["${APP_PORT:-5000}:5000"]
    assert "ports" not in COMPOSE["services"]["postgres"]
    assert COMPOSE["services"]["postgres"]["expose"] == ["5432"]


def test_image_runs_the_entrypoint_not_the_dev_server() -> None:
    assert 'ENTRYPOINT ["/app/scripts/entrypoint.sh"]' in DOCKERFILE
    assert "python app.py" not in DOCKERFILE
    assert "gunicorn" in ENTRYPOINT
    # Migrations BEFORE the server: a container that serves first answers 500s
    # while the platform still calls it healthy.
    assert ENTRYPOINT.index("alembic upgrade head") < ENTRYPOINT.index("exec gunicorn")


def test_entrypoint_fails_loudly() -> None:
    assert re.search(r"^set -eu$", ENTRYPOINT, re.MULTILINE), "a failing migration must abort the container"
    assert "exec gunicorn" in ENTRYPOINT, "gunicorn must replace the shell to receive SIGTERM"


def test_image_runs_unprivileged() -> None:
    assert re.search(r"^USER lifelink$", DOCKERFILE, re.MULTILINE)
    assert "no-new-privileges:true" in (ROOT / "docker-compose.yml").read_text()


def test_healthcheck_does_not_check_the_database() -> None:
    """/health must stay dependency-free, or a DB outage becomes a restart loop."""
    assert '"/health"' in DOCKERFILE or "/health" in DOCKERFILE
    assert "/ready" not in DOCKERFILE.split("HEALTHCHECK")[1].split("ENTRYPOINT")[0]


def test_dockerignore_keeps_state_and_secrets_out_of_the_image() -> None:
    ignored = {(ROOT / ".dockerignore").read_text()}
    body = "\n".join(ignored)
    for needle in (".git", ".env", "*.db", "**/__pycache__"):
        assert needle in body


def test_env_example_documents_every_required_secret() -> None:
    example = (ROOT / ".env.example").read_text()
    for key in ("SECRET_KEY=", "DB_PASSWORD=", "DATABASE_URL=", "FIELD_ENCRYPTION_KEY="):
        assert key in example


def test_alembic_carries_no_committed_url() -> None:
    ini = (ROOT / "alembic.ini").read_text()
    active = [ln for ln in ini.splitlines() if ln.strip().startswith("sqlalchemy.url")]
    assert active == [], "a committed URL is how a laptop migrates production by accident"


def test_migration_env_resolves_the_url_from_the_app_code() -> None:
    env = (ROOT / "migrations" / "env.py").read_text()
    assert "from models.database import database_uri" in env
    assert "target_metadata = db.metadata" in env


def test_exactly_one_revision_is_the_head() -> None:
    """Two heads = `alembic upgrade head` fails in the middle of a deploy."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1, f"multiple migration heads: {heads}"
    base = script.get_base()
    assert base is not None, "no base revision"
    assert script.get_revision(heads[0]).down_revision is None or base != heads[0]
