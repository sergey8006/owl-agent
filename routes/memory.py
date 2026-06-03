"""
Memory routes: /api/facts, /api/facts/search, /api/conversations/search,
               /api/facts/tags, /api/facts/dedup, /api/preferences, /api/reflections, /api/export
"""
from flask import Blueprint, request, jsonify

from middleware import rate_limit, require_auth

memory_bp = Blueprint("memory", __name__)


def _get_agent():
    import server
    return server.get_agent()


@memory_bp.route("/api/facts", methods=["GET"])
@rate_limit
def api_facts():
    _, mem, _ = _get_agent()
    query = request.args.get("q", "")
    tag = request.args.get("tag", "")
    limit = int(request.args.get("limit", "50"))
    if query:
        facts = mem.get_relevant_facts(query, limit=limit, tag_filter=tag or None)
    elif tag:
        facts = mem.get_facts_by_tag(tag, limit=limit)
    else:
        facts = mem.get_all_facts(limit=limit)
    return jsonify({"facts": facts})


@memory_bp.route("/api/facts/search", methods=["GET"])
@rate_limit
def api_facts_search():
    _, mem, _ = _get_agent()
    query = request.args.get("q", "")
    limit = int(request.args.get("limit", "20"))
    if not query:
        return jsonify({"error": "q parameter required"}), 400
    results = mem.search_facts_fts(query, limit=limit)
    return jsonify({"results": results, "query": query})


@memory_bp.route("/api/conversations/search", methods=["GET"])
@rate_limit
def api_conversations_search():
    _, mem, _ = _get_agent()
    query = request.args.get("q", "")
    limit = int(request.args.get("limit", "20"))
    if not query:
        return jsonify({"error": "q parameter required"}), 400
    results = mem.search_conversations_fts(query, limit=limit)
    return jsonify({"results": results, "query": query})


@memory_bp.route("/api/facts/tags", methods=["GET"])
@rate_limit
def api_facts_tags():
    _, mem, _ = _get_agent()
    tags = mem.get_all_tags()
    return jsonify({"tags": tags})


@memory_bp.route("/api/facts/dedup", methods=["POST"])
@rate_limit
@require_auth
def api_facts_dedup():
    _, mem, _ = _get_agent()
    data = request.json or {}
    threshold = float(data.get("threshold", 0.85))
    removed = mem.semantic_dedup_facts(similarity_threshold=threshold)
    return jsonify({"removed": removed, "threshold": threshold})


@memory_bp.route("/api/preferences", methods=["GET", "POST"])
@rate_limit
def api_preferences():
    _, mem, _ = _get_agent()
    if request.method == "POST":
        data = request.json
        mem.set_preference(data["key"], data["value"])
        return jsonify({"ok": True})
    prefs = mem.get_all_preferences()
    return jsonify({"preferences": prefs})


@memory_bp.route("/api/reflections", methods=["GET"])
@rate_limit
def api_reflections():
    _, mem, _ = _get_agent()
    reflections = mem.get_reflections()
    return jsonify({"reflections": reflections})


@memory_bp.route("/api/export", methods=["GET"])
@rate_limit
@require_auth
def api_export():
    _, mem, _ = _get_agent()
    data = mem.export_memory()
    return jsonify(data)
