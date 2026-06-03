"""
Webhook routes: /api/webhook/incoming, /api/webhook/list, /api/webhook/register
Incoming webhook → запуск Flow или команды агента.
"""
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime
from threading import Thread

from flask import Blueprint, request, jsonify

webhook_bp = Blueprint("webhook", __name__)

# In-memory webhook registry (persist to DB later)
_webhooks = {}
_webhook_lock = __import__("threading").Lock()


def _get_agent():
    import server
    return server.get_agent()


@webhook_bp.route("/api/webhook/register", methods=["POST"])
def api_webhook_register():
    """Зарегистрировать новый webhook."""
    data = request.json or {}
    name = data.get("name", "")
    flow_id = data.get("flow_id", "")
    command = data.get("command", "")  # raw command for agent
    secret = data.get("secret", "")  # optional HMAC secret

    if not name:
        return jsonify({"error": "name required"}), 400

    hook_id = str(uuid.uuid4())[:8]
    token = uuid.uuid4().hex

    with _webhook_lock:
        _webhooks[hook_id] = {
            "id": hook_id,
            "name": name,
            "flow_id": flow_id,
            "command": command,
            "secret": secret,
            "token": token,
            "created_at": datetime.now().isoformat(),
            "calls": 0,
            "last_call": None,
        }

    return jsonify({
        "id": hook_id,
        "name": name,
        "url": f"/api/webhook/incoming/{hook_id}",
        "token": token,
        "hint": "POST JSON payload to this URL. Use ?token=XXX or Authorization: Bearer XXX",
    })


@webhook_bp.route("/api/webhook/list", methods=["GET"])
def api_webhook_list():
    """Список зарегистрированных webhooks."""
    with _webhook_lock:
        hooks = []
        for h in _webhooks.values():
            hooks.append({
                "id": h["id"],
                "name": h["name"],
                "flow_id": h["flow_id"],
                "command": h["command"],
                "calls": h["calls"],
                "last_call": h["last_call"],
                "created_at": h["created_at"],
            })
    return jsonify({"webhooks": hooks})


@webhook_bp.route("/api/webhook/delete", methods=["POST"])
def api_webhook_delete():
    """Удалить webhook."""
    data = request.json or {}
    hook_id = data.get("id", "")
    with _webhook_lock:
        if hook_id in _webhooks:
            del _webhooks[hook_id]
            return jsonify({"ok": True})
    return jsonify({"error": "not found"}), 404


@webhook_bp.route("/api/webhook/incoming/<hook_id>", methods=["POST", "GET"])
def api_webhook_incoming(hook_id):
    """
    Входящий webhook.
    GET — health check.
    POST — запуск flow или команды с payload.
    """
    if request.method == "GET":
        return jsonify({"status": "ok", "hook_id": hook_id})

    with _webhook_lock:
        hook = _webhooks.get(hook_id)
    if not hook:
        return jsonify({"error": "unknown webhook"}), 404

    # Auth: token in query or Authorization header
    token = request.args.get("token", "") or request.headers.get("Authorization", "").replace("Bearer ", "")
    if token != hook["token"]:
        return jsonify({"error": "unauthorized"}), 401

    # Optional HMAC verification
    if hook.get("secret"):
        sig = request.headers.get("X-Signature", "")
        body = request.get_data()
        expected = hmac.new(hook["secret"].encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return jsonify({"error": "invalid signature"}), 403

    payload = request.json or {}
    payload_str = json.dumps(payload, ensure_ascii=False)

    # Update stats
    with _webhook_lock:
        _webhooks[hook_id]["calls"] += 1
        _webhooks[hook_id]["last_call"] = datetime.now().isoformat()

    # Execute asynchronously
    def _execute():
        try:
            agent_obj, _, fe = _get_agent()
            if hook.get("flow_id"):
                result = fe.run_flow(hook["flow_id"], inputs=payload)
                print(f"[webhook:{hook_id}] flow result: {result.get('status')}")
            elif hook.get("command"):
                response = agent_obj.chat(f"[Webhook {hook['name']}] {hook['command']}\nPayload: {payload_str}")
                print(f"[webhook:{hook_id}] agent response: {response[:100]}")
            else:
                # Default: treat payload as message to agent
                msg = payload.get("message", payload_str)
                response = agent_obj.chat(f"[Webhook {hook['name']}] {msg}")
                print(f"[webhook:{hook_id}] agent response: {response[:100]}")
        except Exception as e:
            print(f"[webhook:{hook_id}] ERROR: {e}")

    Thread(target=_execute, daemon=True).start()

    return jsonify({"status": "accepted", "hook_id": hook_id})
