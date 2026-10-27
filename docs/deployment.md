# LifeLink — Deployment Guide

## Prerequisites
- Python 3.11+
- (Optional) Docker + reverse proxy (nginx/Caddy) for TLS

## Environment Variables
| Var | Required | Description |
|---|---|---|
| SECRET_KEY | Yes (prod) | Flask secret. Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| JWT_SECRET_KEY | Yes (prod) | Token signing key (separate from SECRET_KEY recommended). |
| FIELD_ENCRYPTION_KEY | Yes (prod) | Fernet key for PII encryption. Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| DATABASE_URL | No | SQLAlchemy URI (default: sqlite:///lifelink.db). Use PostgreSQL in prod. |
| HOST | No | Bind host (default 127.0.0.1). |
| PORT | No | Bind port (default 5000). |
| FLASK_DEBUG | No | "1" to enable debug (never in prod). |
| CORS_ORIGINS | No | Comma-separated allowed origins (empty = allow any). |

## Local run
```bash
cp .env.example .env  # fill in secrets
pip install -r requirements.txt
python app.py
```

## Docker
```bash
docker build -t lifelink .
docker run -d -p 5000:5000 \
  -e SECRET_KEY=... -e JWT_SECRET_KEY=... -e FIELD_ENCRYPTION_KEY=... \
  -v lifelink-data:/app \
  lifelink
```

## HTTPS (production)
LifeLink does NOT terminate TLS. Put a reverse proxy in front:

### nginx example
```nginx
server {
    listen 443 ssl;
    server_name lifelink.example.com;
    ssl_certificate /etc/letsencrypt/live/lifelink.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/lifelink.example.com/privkey.pem;
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Caddy example
```
lifelink.example.com {
    reverse_proxy 127.0.0.1:5000
}
```

## Security checklist
- [ ] SECRET_KEY, JWT_SECRET_KEY, FIELD_ENCRYPTION_KEY set (not defaults).
- [ ] FLASK_DEBUG=0.
- [ ] HTTPS via reverse proxy.
- [ ] CORS_ORIGINS restricted to your domain.
- [ ] Database backups (if SQLite, back up the .db file).
- [ ] Rate limiting enabled (default).
