"""
Skills routes: /api/skills, /api/skill_toggle, /api/skill_detail
"""
from flask import Blueprint, request, jsonify

from middleware import rate_limit

skills_bp = Blueprint("skills", __name__)


def _get_agent():
    import server
    return server.get_agent()


@skills_bp.route("/api/skills", methods=["GET"])
@rate_limit
def api_skills():
    _, mem, _ = _get_agent()
    skills = mem.get_all_skills()
    return jsonify({"skills": skills})


@skills_bp.route("/api/skill_toggle", methods=["GET"])
@rate_limit
def api_skill_toggle():
    skill_id = request.args.get("id", type=int)
    enabled = request.args.get("enabled", type=int)
    if skill_id is None:
        return jsonify({"error": "missing id"}), 400
    _, mem, _ = _get_agent()
    mem.set_skill_enabled(skill_id, bool(enabled))
    return jsonify({"ok": True})


@skills_bp.route("/api/skill_detail", methods=["GET"])
@rate_limit
def api_skill_detail():
    skill_id = request.args.get("id", type=int)
    if skill_id is None:
        return jsonify({"error": "missing id"}), 400
    _, mem, _ = _get_agent()
    skill = mem.get_skill_detail(skill_id)
    return jsonify({"skill": skill})
