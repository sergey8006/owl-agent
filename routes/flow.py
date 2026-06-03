"""
Flow routes: /api/flow/list, /api/flow/get, /api/flow/create,
             /api/flow/run, /api/flow/delete, /api/flow/history,
             /api/flow/snapshot/cleanup, /api/flow/resume, /api/flow/execution-log
             /api/flow/checkpoint/save, /api/flow/checkpoint/clear
"""
from flask import Blueprint, request, jsonify

flow_bp = Blueprint("flow", __name__)


def _get_agent():
    import server
    return server.get_agent()


@flow_bp.route("/api/flow/list", methods=["GET"])
def api_flow_list():
    _, _, fe = _get_agent()
    return jsonify({"flows": fe.list_flows()})


@flow_bp.route("/api/flow/get", methods=["GET"])
def api_flow_get():
    _, _, fe = _get_agent()
    flow_id = request.args.get("id", "")
    flow = fe.get_flow(flow_id)
    if not flow:
        return jsonify({"error": "flow not found"}), 404
    return jsonify({"flow": flow})


@flow_bp.route("/api/flow/create", methods=["POST"])
def api_flow_create():
    _, _, fe = _get_agent()
    data = request.json or {}
    name = data.get("name", "")
    description = data.get("description", "")
    steps = data.get("steps", [])
    if not name:
        return jsonify({"error": "name required"}), 400
    flow = fe.create_flow(name, description, steps)
    return jsonify({"flow": flow})


@flow_bp.route("/api/flow/run", methods=["POST"])
def api_flow_run():
    _, _, fe = _get_agent()
    data = request.json or {}
    flow_id = data.get("id", "")
    inputs = data.get("inputs", {})
    resume = data.get("resume", False)
    if not flow_id:
        return jsonify({"error": "id required"}), 400
    result = fe.run_flow(flow_id, inputs=inputs, resume=resume)
    return jsonify(result)


@flow_bp.route("/api/flow/delete", methods=["POST"])
def api_flow_delete():
    _, _, fe = _get_agent()
    data = request.json or {}
    flow_id = data.get("id", "")
    if not flow_id:
        return jsonify({"error": "id required"}), 400
    fe.delete_flow(flow_id)
    return jsonify({"ok": True})


@flow_bp.route("/api/flow/history", methods=["GET"])
def api_flow_history():
    _, _, fe = _get_agent()
    flow_id = request.args.get("id", "")
    history = fe.get_flow_history(flow_id)
    return jsonify({"history": history})


@flow_bp.route("/api/flow/snapshot/cleanup", methods=["POST"])
def api_flow_snapshot_cleanup():
    _, _, fe = _get_agent()
    data = request.json or {}
    flow_id = data.get("id", "")
    if not flow_id:
        return jsonify({"error": "id required"}), 400
    fe.cleanup_snapshots(flow_id)
    return jsonify({"ok": True})


# -- Checkpointing --

@flow_bp.route("/api/flow/checkpoint/save", methods=["POST"])
def api_flow_checkpoint_save():
    _, _, fe = _get_agent()
    data = request.json or {}
    flow_id = data.get("id", "")
    step_index = data.get("step_index", 0)
    variables = data.get("variables", {})
    log = data.get("log", [])
    if not flow_id:
        return jsonify({"error": "id required"}), 400
    fe.save_checkpoint(flow_id, step_index, variables, log)
    return jsonify({"ok": True})


@flow_bp.route("/api/flow/checkpoint/clear", methods=["POST"])
def api_flow_checkpoint_clear():
    _, _, fe = _get_agent()
    data = request.json or {}
    flow_id = data.get("id", "")
    if not flow_id:
        return jsonify({"error": "id required"}), 400
    fe.clear_checkpoint(flow_id)
    return jsonify({"ok": True})


# -- Execution Log --

@flow_bp.route("/api/flow/execution-log", methods=["GET"])
def api_flow_execution_log():
    _, _, fe = _get_agent()
    flow_id = request.args.get("id", "")
    limit = request.args.get("limit", 20, type=int)
    if not flow_id:
        return jsonify({"error": "id required"}), 400
    log = fe.get_execution_log(flow_id, limit)
    return jsonify({"executions": log})
