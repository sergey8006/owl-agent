"""
System routes: /api/health, handle_command (slash commands)
"""
import json
from pathlib import Path

from flask import Blueprint, jsonify

import middleware

system_bp = Blueprint("system", __name__)


def _get_agent():
    import server
    return server.get_agent()


@system_bp.route("/api/health", methods=["GET"])
def api_health():
    from time import time as _time

    from config import SERVER_DIR

    agent_obj, _, _ = _get_agent()
    return jsonify({
        "ok": True,
        "version": "3.0.0",
        "uptime_seconds": int(_time() - server._server_start_time),
        "active_model": agent_obj.model,
        "active_provider": agent_obj.provider,
        "active_session": agent_obj.session_id,
        "skills_dir": str(SERVER_DIR / "skills"),
        "auth_enabled": len(middleware._api_keys) > 0,
    })


def handle_command(cmd: str, agent_obj, mem) -> str:
    """Handle slash commands. Returns a human-readable string."""
    parts = cmd.lower().split()
    command = parts[0]

    if command == "/stats":
        try:
            stats = mem.get_stats()
            lines = ["Memory Statistics:"]
            for k, v in stats.items():
                lines.append(f"  {k}: {v}")
            return "\n".join(lines)
        except Exception as e:
            return f"Stats error: {e}"

    elif command == "/facts":
        try:
            facts = mem.get_all_facts(limit=20)
            if not facts:
                return "No facts learned yet."
            lines = [f"Learned Facts ({len(facts)}):"]
            for f in facts:
                lines.append(
                    f"  • {f['fact']} (confidence: {f['confidence']:.1f},"
                    f" reinforced: {f.get('times_reinforced', 0)}x)"
                )
            return "\n".join(lines)
        except Exception as e:
            return f"Facts error: {e}"

    elif command == "/prefs":
        try:
            prefs = mem.get_all_preferences()
            if not prefs:
                return "No preferences learned yet."
            lines = ["User Preferences:"]
            for k, v in prefs.items():
                lines.append(f"  • {k}: {v}")
            return "\n".join(lines)
        except Exception as e:
            return f"Prefs error: {e}"

    elif command == "/skills":
        try:
            skills = mem.get_all_skills()
            if not skills:
                return "No skills learned yet."
            lines = ["Learned Skills:"]
            for s in skills:
                lines.append(
                    f"  • {s['name']}: {s.get('description', '')}"
                    f" (used: {s.get('times_used', 0)}x)"
                )
            return "\n".join(lines)
        except Exception as e:
            return f"Skills error: {e}"

    elif command == "/reflect":
        try:
            reflections = mem.get_reflections(limit=10)
            if not reflections:
                return "No reflections yet."
            lines = ["Recent Self-Reflections:"]
            for r in reflections:
                lines.append(f"  [{r['trigger']}] {r['reflection']}")
            return "\n".join(lines)
        except Exception as e:
            return f"Reflect error: {e}"

    elif command == "/models":
        try:
            models = agent_obj.list_models()
            current = agent_obj.model
            lines = ["Available Models:"]
            for m in models:
                marker = " (active)" if m == current else ""
                lines.append(f"  • {m}{marker}")
            lines.append("\nUse /switch <model_name> to change")
            return "\n".join(lines)
        except Exception as e:
            return f"Models error: {e}"

    elif command == "/switch" and len(parts) > 1:
        model_name = " ".join(parts[1:])
        agent_obj.change_model(model_name)
        return f"Switched to model: {model_name}"

    elif command in ("/new", "/reset"):
        agent_obj.clear_conversation()
        return "New conversation started."

    elif command == "/export":
        try:
            data = mem.export_memory()
            export_path = Path("memory") / "export.json"
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return f"Memory exported to {export_path}"
        except Exception as e:
            return f"Export error: {e}"

    elif command == "/flow":
        from agent.flow_engine import FlowEngine

        _, _, fe = _get_agent()
        if len(parts) < 2:
            return "Usage: /flow list | /flow run <id> | /flow history <id>"
        sub = parts[1]
        if sub == "list":
            flows = fe.list_flows()
            if not flows:
                return "No flows yet."
            lines = [
                f"  {f['id']}: {f['name']} ({f.get('description', '')})"
                for f in flows
            ]
            return "Flows:\n" + "\n".join(lines)
        elif sub == "run" and len(parts) > 2:
            flow_id = parts[2]
            result = fe.run_flow(flow_id)
            status = result.get("status", "?")
            log = result.get("log", [])
            return f"Flow '{flow_id}' → {status}\n" + "\n".join(log[-10:])
        elif sub == "history" and len(parts) > 2:
            flow_id = parts[2]
            history = fe.get_flow_history(flow_id)
            if not history:
                return f"No history for '{flow_id}'"
            lines = [
                f"  [{h['step_index']}] {h['action']} → {h['status']} at {h['executed_at'][:16]}"
                for h in history
            ]
            return f"History for '{flow_id}':\n" + "\n".join(lines)

    elif command == "/help":
        return (
            "Available commands:\n"
            "/stats — Memory statistics\n"
            "/facts — Show learned facts\n"
            "/preferences — Show user preferences\n"
            "/skills — Show learned skills\n"
            "/reflect — Show self-reflections\n"
            "/models — List available models\n"
            "/switch <name> — Switch model\n"
            "/new or /reset — New conversation\n"
            "/export — Export memory to JSON\n"
            "/flow list — List flows\n"
            "/flow run <id> — Run flow\n"
            "/flow history <id> — Flow history\n"
            "/help — Show this help\n"
            "\nOr just type a message to chat!\n"
        )

    return f"Unknown command: {cmd}. Type /help for available commands."
