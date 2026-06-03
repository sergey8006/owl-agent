"""
Scheduler routes: /api/scheduler/list, /api/scheduler/add, /api/scheduler/remove,
                  /api/scheduler/toggle, /api/scheduler/run
"""
from flask import Blueprint, request, jsonify
from agent.scheduler import add_job, remove_job, toggle_job, list_jobs, run_job_now

scheduler_bp = Blueprint("scheduler", __name__)


@scheduler_bp.route("/api/scheduler/list", methods=["GET"])
def api_scheduler_list():
    return jsonify({"jobs": list_jobs()})


@scheduler_bp.route("/api/scheduler/add", methods=["POST"])
def api_scheduler_add():
    data = request.json or {}
    name = data.get("name", "")
    job_type = data.get("type", "interval")
    if not name:
        return jsonify({"error": "name required"}), 400

    kwargs = {}
    if data.get("flow_id"):
        kwargs["flow_id"] = data["flow_id"]
    if data.get("command"):
        kwargs["command"] = data["command"]
    if data.get("inputs"):
        kwargs["inputs"] = data["inputs"]

    if job_type == "interval":
        kwargs["interval_seconds"] = data.get("interval_seconds", 3600)
    elif job_type == "cron":
        kwargs["cron"] = data.get("cron", "0 * * * *")
    elif job_type == "oneshot":
        kwargs["run_at"] = data.get("run_at", "")
    else:
        return jsonify({"error": f"unknown type: {job_type}"}), 400

    job = add_job(name, job_type, **kwargs)
    return jsonify({"job": job})


@scheduler_bp.route("/api/scheduler/remove", methods=["POST"])
def api_scheduler_remove():
    data = request.json or {}
    job_id = data.get("id", "")
    if not job_id:
        return jsonify({"error": "id required"}), 400
    if remove_job(job_id):
        return jsonify({"ok": True})
    return jsonify({"error": "not found"}), 404


@scheduler_bp.route("/api/scheduler/toggle", methods=["POST"])
def api_scheduler_toggle():
    data = request.json or {}
    job_id = data.get("id", "")
    if not job_id:
        return jsonify({"error": "id required"}), 400
    enabled = toggle_job(job_id)
    return jsonify({"enabled": enabled})


@scheduler_bp.route("/api/scheduler/run", methods=["POST"])
def api_scheduler_run():
    data = request.json or {}
    job_id = data.get("id", "")
    if not job_id:
        return jsonify({"error": "id required"}), 400
    run_job_now(job_id)
    return jsonify({"status": "started"})
