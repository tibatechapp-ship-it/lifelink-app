"""Rate limiting (in-memory, per-IP) + CORS for LifeLink."""

import os
import time
from collections import defaultdict, deque
from flask import request, jsonify

# --- Rate limiter ---
# Simple sliding-window per-IP counter. Not distributed (single process).
_WINDOW = 60  # seconds
_LIMITS = {
    "GET": 60,
    "POST": 10,
    "PUT": 10,
    "DELETE": 10,
}
_buckets = defaultdict(lambda: deque())  # ip -> deque of timestamps


def _client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()


def check_rate_limit():
    if os.environ.get("RATE_LIMIT_ENABLED", "1") == "0":
        return True
    ip = _client_ip()
    method = request.method.upper()
    limit = _LIMITS.get(method, 60)
    now = time.time()
    bucket = _buckets[ip]
    # drop old
    while bucket and bucket[0] < now - _WINDOW:
        bucket.popleft()
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True


def rate_limit_middleware():
    if not check_rate_limit():
        return jsonify({"error": "Rate limit exceeded. Try again later."}), 429


# --- CORS ---
_ALLOWED_ORIGINS = os.environ.get("CORS_ORIGINS", "").split(",") if os.environ.get("CORS_ORIGINS") else []


def cors_headers(response):
    origin = request.headers.get("Origin")
    if origin and (not _ALLOWED_ORIGINS or origin in _ALLOWED_ORIGINS):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Max-Age"] = "3600"
    if request.method == "OPTIONS":
        response.status_code = 204
    return response


def register_middleware(app):
    @app.before_request
    def _rl():
        if request.method == "OPTIONS":
            return None
        return rate_limit_middleware()

    @app.after_request
    def _cors(response):
        return cors_headers(response)
