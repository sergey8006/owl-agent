"""
Chat routes: /api/chat, /api/chat/stream, /api/new_session, /api/history, /api/sessions, /api/stats
"""
import json

from flask import Blueprint, request, jsonify, Response, stream_with_context

from middleware import rate_limit

chat_bp = Blueprint("chat", __name__)


def _get_agent():
    import server
    return server.get_agent()


def _handle_command(msg, agent_obj, mem):
    from routes.system import handle_command
    return handle_command(msg, agent_obj, mem)


@chat_bp.route("/api/chat", methods=["POST"])
@rate_limit
def api_chat():
    data = request.json or {}
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Empty message"}), 400

    agent_obj, mem, _ = _get_agent()
    if message.startswith("/"):
        response_text = _handle_command(message, agent_obj, mem)
        return jsonify({"response": response_text, "model": "system", "tool_calls": [], "session_id": agent_obj.session_id})

    result = agent_obj.chat(message)
    return jsonify(result)


@chat_bp.route("/api/chat/stream", methods=["POST"])
@rate_limit
def api_chat_stream():
    data = request.json or {}
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Empty message"}), 400

    agent_obj, mem, _ = _get_agent()

    if message.startswith("/"):
        response_text = _handle_command(message, agent_obj, mem)
        def gen():
            yield f"data: {json.dumps({'type': 'text', 'content': response_text})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'session_id': agent_obj.session_id, 'model': 'system'})}\n\n"
        return Response(stream_with_context(gen()), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    def generate():
        try:
            for event in agent_obj.chat_stream(message):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@chat_bp.route("/api/history", methods=["GET"])
@rate_limit
def api_history():
    agent_obj, mem, _ = _get_agent()
    session_id = request.args.get("session", agent_obj.session_id)
    history = mem.get_history(session_id) if mem else []
    return jsonify({"history": history, "session_id": session_id})


@chat_bp.route("/api/sessions", methods=["GET"])
@rate_limit
def api_sessions():
    _, mem, _ = _get_agent()
    sessions = mem.get_all_sessions()
    return jsonify({"sessions": sessions})


@chat_bp.route("/api/stats", methods=["GET"])
@rate_limit
def api_stats():
    _, mem, _ = _get_agent()
    stats = mem.get_stats()
    agent_obj, _, _ = _get_agent()
    stats["active_model"] = agent_obj.model
    stats["active_session"] = agent_obj.session_id
    return jsonify(stats)


@chat_bp.route("/api/new_session", methods=["POST"])
@rate_limit
def api_new_session():
    agent_obj, _, _ = _get_agent()
    agent_obj.clear_conversation()
    return jsonify({"session_id": agent_obj.session_id})
