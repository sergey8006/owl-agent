"""
Provider routes: /api/providers, /api/provider/switch, /api/provider/test, /api/models, /api/switch_model
"""
from flask import Blueprint, request, jsonify

from config import PROVIDERS, save_provider_config
from middleware import rate_limit

provider_bp = Blueprint("provider", __name__)


def _get_agent():
    import server
    return server.get_agent()


@provider_bp.route("/api/providers", methods=["GET"])
def api_providers():
    agent_obj, _, _ = _get_agent()
    models = agent_obj.list_models()
    return jsonify({
        "providers": PROVIDERS,
        "active_provider": agent_obj.provider,
        "active_url": agent_obj.base_url,
        "active_model": agent_obj.model,
        "models": models,
    })


@provider_bp.route("/api/provider/switch", methods=["POST"])
def api_provider_switch():
    data = request.json or {}
    provider = data.get("provider", "")
    url = data.get("url")
    api_key = data.get("api_key")

    if not provider:
        return jsonify({"error": "provider required"}), 400

    agent_obj, _, _ = _get_agent()
    try:
        result = agent_obj.switch_provider(provider, base_url=url, api_key=api_key)
        models = agent_obj.list_models()
        save_provider_config(
            provider=result["provider"],
            url=result["url"],
            api_key=agent_obj.api_key,
            model=result["model"],
        )
        return jsonify({
            "ok": True,
            "provider": result["provider"],
            "url": result["url"],
            "model": result["model"],
            "models": models,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@provider_bp.route("/api/provider/test", methods=["POST"])
def api_provider_test():
    data = request.json or {}
    url = data.get("url", "http://127.0.0.1:1234/v1")
    api_key = data.get("api_key", "lm-studio")

    from openai import OpenAI
    try:
        test_client = OpenAI(base_url=url, api_key=api_key, timeout=5)
        resp = test_client.models.list()
        models = [m.id for m in resp.data]
        return jsonify({"ok": True, "models": models, "url": url})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "url": url}), 200


@provider_bp.route("/api/models", methods=["GET"])
@rate_limit
def api_models():
    agent_obj, _, _ = _get_agent()
    models = agent_obj.list_models()
    return jsonify({"models": models, "active": agent_obj.model})


@provider_bp.route("/api/switch_model", methods=["POST"])
@rate_limit
def api_switch_model():
    data = request.json or {}
    model = data.get("model", "")
    if model:
        agent_obj, _, _ = _get_agent()
        agent_obj.change_model(model)
        return jsonify({"ok": True, "model": model})
    return jsonify({"error": "No model specified"}), 400
