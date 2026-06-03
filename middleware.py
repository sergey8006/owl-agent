"""
Middleware: rate limiting and API key auth decorators.
"""
import hashlib as _hashlib
import time as _time
from functools import wraps
from threading import Lock as _Lock

from flask import request, jsonify

from config import RATE_LIMIT_PER_MINUTE

_rate_lock = _Lock()
_rate_buckets: dict = {}
_rate_limit_per_minute = RATE_LIMIT_PER_MINUTE
_api_keys: set = set()


def _check_rate_limit(client_ip: str) -> bool:
    now = _time.time()
    with _rate_lock:
        if client_ip in _rate_buckets:
            count, reset_at = _rate_buckets[client_ip]
            if now > reset_at:
                _rate_buckets[client_ip] = [1, now + 60]
                return True
            if count >= _rate_limit_per_minute:
                return False
            _rate_buckets[client_ip][0] = count + 1
            return True
        else:
            _rate_buckets[client_ip] = [1, now + 60]
            return True


def rate_limit(f):
    """Decorator: rate-limit by client IP."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if _rate_limit_per_minute > 0:
            ip = request.remote_addr or "127.0.0.1"
            if not _check_rate_limit(ip):
                return jsonify({"error": "Rate limit exceeded"}), 429
        return f(*args, **kwargs)
    return decorated


def require_auth(f):
    """Decorator: require API key (if any keys are configured)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not _api_keys:
            return f(*args, **kwargs)
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            token = request.args.get("api_key", "")
        token_hash = _hashlib.sha256(token.encode()).hexdigest()
        if token_hash not in _api_keys:
            return jsonify({"error": "Invalid or missing API key"}), 401
        return f(*args, **kwargs)
    return decorated


def set_rate_limit(limit: int):
    global _rate_limit_per_minute
    _rate_limit_per_minute = limit


def add_api_key(key: str):
    _api_keys.add(_hashlib.sha256(key.encode()).hexdigest())


def create_api_key(key_name: str = "default") -> str:
    import secrets
    key = f"owl-{secrets.token_hex(16)}"
    _api_keys.add(_hashlib.sha256(key.encode()).hexdigest())
    return key
