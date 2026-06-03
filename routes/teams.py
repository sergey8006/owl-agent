"""
Agent Team routes: /api/teams/* — управление командами агентов
"""
import json
from flask import Blueprint, request, jsonify
from middleware import rate_limit

teams_bp = Blueprint("teams", __name__)


def _get_agent():
    import server
    return server.get_agent()


@teams_bp.route("/api/teams", methods=["GET"])
def api_teams_list():
    from agent.agent_team import AgentTeam
    teams = AgentTeam.list_teams()
    return jsonify({"teams": teams})


@teams_bp.route("/api/teams/create", methods=["POST"])
def api_teams_create():
    from agent.agent_team import AgentTeam, TeamRunner

    data = request.json or {}
    name = data.get("name", "").strip()
    task = data.get("task", "").strip()
    agent_roles = data.get("agents", [])

    if not name or not task:
        return jsonify({"error": "name and task required"}), 400

    if not agent_roles:
        return jsonify({"error": "at least one agent role required"}), 400

    team = AgentTeam.create(name=name, task=task, agent_roles=agent_roles)
    return jsonify({"ok": True, "team": team.to_dict()})


@teams_bp.route("/api/teams/<team_id>", methods=["GET"])
def api_teams_get(team_id):
    from agent.agent_team import AgentTeam
    team = AgentTeam.get(team_id)
    if not team:
        return jsonify({"error": "team not found"}), 404
    return jsonify({"team": team.to_dict()})


@teams_bp.route("/api/teams/<team_id>/run", methods=["POST"])
def api_teams_run(team_id):
    from agent.agent_team import AgentTeam, TeamRunner

    team = AgentTeam.get(team_id)
    if not team:
        return jsonify({"error": "team not found"}), 404

    if team.status == "running":
        return jsonify({"error": "team is already running"}), 409

    runner = TeamRunner(team)
    results = runner.run()
    return jsonify({"ok": True, "results": results})


@teams_bp.route("/api/teams/<team_id>/messages", methods=["GET"])
def api_teams_messages(team_id):
    from agent.agent_team import AgentTeam
    team = AgentTeam.get(team_id)
    if not team:
        return jsonify({"error": "team not found"}), 404
    limit = request.args.get("limit", 50, type=int)
    messages = team.get_messages(limit=limit)
    return jsonify({"messages": messages})


@teams_bp.route("/api/teams/<team_id>", methods=["DELETE"])
def api_teams_delete(team_id):
    from agent.agent_team import AgentTeam
    team = AgentTeam.get(team_id)
    if not team:
        return jsonify({"error": "team not found"}), 404
    team.delete()
    return jsonify({"ok": True})


@teams_bp.route("/api/teams/templates", methods=["GET"])
def api_teams_templates():
    """Return predefined team templates."""
    templates = [
        {
            "name": "Web Research",
            "description": "Поиск и анализ информации в интернете",
            "agents": [
                {"name": "researcher", "role": "Исследователь", "skills": ["web-scraper", "search-tools"]},
                {"name": "analyst", "role": "Аналитик", "skills": ["data-analyzer"]},
                {"name": "writer", "role": "Редактор", "skills": ["text-tools"]},
            ]
        },
        {
            "name": "Code Review",
            "description": "Ревью и улучшение кода",
            "agents": [
                {"name": "reviewer", "role": "Ревьюер кода", "skills": ["code-reviewer"]},
                {"name": "tester", "role": "Тестировщик", "skills": ["code-reviewer"]},
                {"name": "documenter", "role": "Документация", "skills": ["text-tools"]},
            ]
        },
        {
            "name": "Data Pipeline",
            "description": "Обработка и анализ данных",
            "agents": [
                {"name": "collector", "role": "Сбор данных", "skills": ["web-scraper", "data-tools"]},
                {"name": "processor", "role": "Обработка данных", "skills": ["data-tools", "database-tools"]},
                {"name": "visualizer", "role": "Визуализация", "skills": ["data-analyzer"]},
            ]
        },
        {
            "name": "Project Setup",
            "description": "Создание и настройка проекта",
            "agents": [
                {"name": "architect", "role": "Архитектор", "skills": ["project_manager"]},
                {"name": "developer", "role": "Разработчик", "skills": ["code-reviewer", "git-tools"]},
                {"name": "deployer", "role": "Деплой", "skills": ["system-monitor"]},
            ]
        },
    ]
    return jsonify({"templates": templates})
