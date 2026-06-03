"""
ReAct, RAG, and Task management routes.
"""
from flask import Blueprint, request, jsonify

react_bp = Blueprint("react", __name__)


def _get_agent():
    import server
    return server.get_agent()


# ── ReAct --

@react_bp.route("/api/react/run", methods=["POST"])
def api_react_run():
    """Run a task using the ReAct engine."""
    from agent.react_engine import ReActEngine
    data = request.json or {}
    task = data.get("task", "")
    max_steps = data.get("max_steps", 10)
    if not task:
        return jsonify({"error": "task required"}), 400
    agent_obj, _, _ = _get_agent()
    engine = ReActEngine(agent_obj)
    result = engine.run(task, max_steps=max_steps)
    return jsonify(result)


# ── Task Management --

@react_bp.route("/api/tasks/list", methods=["GET"])
def api_tasks_list():
    from agent.react_engine import list_tasks
    status = request.args.get("status")
    tasks = list_tasks(status=status)
    return jsonify({"tasks": tasks})


@react_bp.route("/api/tasks/create", methods=["POST"])
def api_tasks_create():
    from agent.react_engine import create_task
    data = request.json or {}
    desc = data.get("description", "")
    priority = data.get("priority", 5)
    if not desc:
        return jsonify({"error": "description required"}), 400
    task = create_task(desc, priority=priority)
    return jsonify({"task": task})


@react_bp.route("/api/tasks/<task_id>/complete", methods=["POST"])
def api_tasks_complete(task_id):
    from agent.react_engine import complete_task
    data = request.json or {}
    complete_task(task_id, data.get("result", "completed"))
    return jsonify({"ok": True})


@react_bp.route("/api/tasks/<task_id>/fail", methods=["POST"])
def api_tasks_fail(task_id):
    from agent.react_engine import fail_task
    data = request.json or {}
    fail_task(task_id, data.get("error", "failed"))
    return jsonify({"ok": True})


@react_bp.route("/api/tasks/generate", methods=["POST"])
def api_tasks_generate():
    """Generate subtasks from an objective (BabyAGI-style)."""
    from agent.react_engine import generate_subtasks
    data = request.json or {}
    objective = data.get("objective", "")
    max_tasks = data.get("max_tasks", 5)
    if not objective:
        return jsonify({"error": "objective required"}), 400
    agent_obj, _, _ = _get_agent()
    tasks = generate_subtasks(objective, agent_obj.client, agent_obj.model, max_tasks=max_tasks)
    return jsonify({"tasks": tasks})


# ── RAG --

@react_bp.route("/api/rag/search", methods=["POST"])
def api_rag_search():
    from agent.rag_engine import search
    data = request.json or {}
    query = data.get("query", "")
    top_k = data.get("top_k", 5)
    if not query:
        return jsonify({"error": "query required"}), 400
    results = search(query, top_k=top_k)
    return jsonify({"results": results})


@react_bp.route("/api/rag/ask", methods=["POST"])
def api_rag_ask():
    from agent.rag_engine import search_and_generate
    data = request.json or {}
    question = data.get("question", "")
    top_k = data.get("top_k", 3)
    if not question:
        return jsonify({"error": "question required"}), 400
    agent_obj, _, _ = _get_agent()
    result = search_and_generate(question, agent_obj.client, agent_obj.model, top_k=top_k)
    return jsonify(result)


@react_bp.route("/api/rag/index-file", methods=["POST"])
def api_rag_index_file():
    from agent.rag_engine import load_file
    data = request.json or {}
    path = data.get("path", "")
    if not path:
        return jsonify({"error": "path required"}), 400
    result = load_file(path)
    return jsonify(result)


@react_bp.route("/api/rag/index-dir", methods=["POST"])
def api_rag_index_dir():
    from agent.rag_engine import load_directory
    data = request.json or {}
    path = data.get("path", "")
    recursive = data.get("recursive", True)
    if not path:
        return jsonify({"error": "path required"}), 400
    result = load_directory(path, recursive=recursive)
    return jsonify(result)


@react_bp.route("/api/rag/documents", methods=["GET"])
def api_rag_documents():
    from agent.rag_engine import list_documents
    docs = list_documents()
    return jsonify({"documents": docs})


@react_bp.route("/api/rag/document/<doc_id>", methods=["DELETE"])
def api_rag_document_delete(doc_id):
    from agent.rag_engine import remove_document
    if remove_document(doc_id):
        return jsonify({"ok": True})
    return jsonify({"error": "not found"}), 404
