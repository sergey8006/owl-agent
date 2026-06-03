"""
Secrets Manager — безопасное хранение API-ключей и секретов.
Шифрование через Fernet (AES-128-CBC).
"""
import json
import os
import re
import base64
from pathlib import Path
from threading import Lock

BASE_DIR = Path(__file__).resolve().parent.parent
SECRETS_DIR = BASE_DIR / "memory" / "secrets"
SECRETS_DIR.mkdir(parents=True, exist_ok=True)
SECRETS_FILE = SECRETS_DIR / "vault.enc"
LOCK = Lock()

_fernet = None
_master_key = None


def _get_fernet():
    global _fernet, _master_key
    if _fernet is not None:
        return _fernet

    try:
        from cryptography.fernet import Fernet
    except ImportError:
        raise ImportError("Install cryptography: pip install cryptography")

    key_file = SECRETS_DIR / ".master_key"
    if key_file.exists():
        _master_key = key_file.read_bytes()
    else:
        _master_key = os.urandom(32)
        key_file.write_bytes(_master_key)
        key_file.chmod(0o600)

    fernet_key = base64.urlsafe_b64encode(_master_key[:32].ljust(32, b'\0'))
    _fernet = Fernet(fernet_key)
    return _fernet


def _load_vault() -> dict:
    if not SECRETS_FILE.exists():
        return {}
    try:
        f = _get_fernet()
        encrypted = SECRETS_FILE.read_bytes()
        decrypted = f.decrypt(encrypted)
        return json.loads(decrypted.decode("utf-8"))
    except Exception:
        return {}


def _save_vault(vault: dict):
    f = _get_fernet()
    data = json.dumps(vault).encode("utf-8")
    encrypted = f.encrypt(data)
    SECRETS_FILE.write_bytes(encrypted)
    SECRETS_FILE.chmod(0o600)


def set_secret(key: str, value: str):
    """Сохранить секрет."""
    with LOCK:
        vault = _load_vault()
        vault[key] = value
        _save_vault(vault)


def get_secret(key: str, default: str = "") -> str:
    """Получить секрет."""
    with LOCK:
        vault = _load_vault()
        return vault.get(key, default)


def delete_secret(key: str):
    """Удалить секрет."""
    with LOCK:
        vault = _load_vault()
        vault.pop(key, None)
        _save_vault(vault)


def list_secrets() -> list:
    """Список ключей (без значений)."""
    with LOCK:
        vault = _load_vault()
        return list(vault.keys())


def resolve_secrets(text: str) -> str:
    """
    Заменить {{secrets.KEY}} на значение из vault.
    Пример: "Bearer {{secrets.openai_key}}" -> "Bearer sk-xxx..."
    """
    def replacer(m):
        key = m.group(1)
        return get_secret(key, f"{{{{secrets.{key}}}}}")
    return re.sub(r'\{\{secrets\.(\w+)\}\}', replacer, text)
