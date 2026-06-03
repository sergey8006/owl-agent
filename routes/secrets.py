"""
Secrets routes: /api/secrets/list, /api/secrets/set, /api/secrets/get, /api/secrets/delete
"""
from flask import Blueprint, request, jsonify
from agent.secrets import set_secret, get_secret, delete_secret, list_secrets

secrets_bp = Blueprint("secrets", __name__)


@secrets_bp.route("/api/secrets/list", methods=["GET"])
def api_secrets_list():
    return jsonify({"keys": list_secrets()})


@secrets_bp.route("/api/secrets/set", methods=["POST"])
def api_secrets_set():
    data = request.json or {}
    key = data.get("key", "")
    value = data.get("value", "")
    if not key:
        return jsonify({"error": "key required"}), 400
    set_secret(key, value)
    return jsonify({"ok": True})


@secrets_bp.route("/api/secrets/get", methods=["GET"])
def api_secrets_get():
    key = request.args.get("key", "")
    if not key:
        return jsonify({"error": "key required"}), 400
    value = get_secret(key)
    return jsonify({"key": key, "value": value})


@secrets_bp.route("/api/secrets/delete", methods=["POST"])
def api_secrets_delete():
    data = request.json or {}
    key = data.get("key", "")
    if not key:
        return jsonify({"error": "key required"}), 400
    delete_secret(key)
    return jsonify({"ok": True})
