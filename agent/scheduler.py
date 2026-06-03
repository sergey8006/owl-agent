"""
Cron Scheduler — встроенный планировщик задач.
Поддерживает: interval (каждые N сек), cron-выражение, one-shot (run_at).
"""
import json
import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCHEDULER_DIR = BASE_DIR / "memory" / "scheduler"
SCHEDULER_DIR.mkdir(parents=True, exist_ok=True)
JOBS_FILE = SCHEDULER_DIR / "jobs.json"

_lock = threading.Lock()
_jobs = {}
_running = False
_thread = None


def _load_jobs():
    global _jobs
    if JOBS_FILE.exists():
        try:
            _jobs = json.loads(JOBS_FILE.read_text(encoding="utf-8"))
        except Exception:
            _jobs = {}


def _save_jobs():
    JOBS_FILE.write_text(json.dumps(_jobs, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_agent():
    import server
    return server.get_agent()


def _execute_job(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        return
    try:
        agent_obj, _, fe = _get_agent()
        if job.get("flow_id"):
            result = fe.run_flow(job["flow_id"], inputs=job.get("inputs", {}))
            print(f"[scheduler] job {job_id} flow result: {result.get('status')}")
        elif job.get("command"):
            response = agent_obj.chat(f"[Scheduled Task] {job['command']}")
            print(f"[scheduler] job {job_id} response: {response[:100]}")
        job["last_run"] = datetime.now().isoformat()
        job["last_status"] = "success"
    except Exception as e:
        print(f"[scheduler] job {job_id} ERROR: {e}")
        job["last_run"] = datetime.now().isoformat()
        job["last_status"] = f"error: {e}"
    finally:
        job["run_count"] = job.get("run_count", 0) + 1
        # One-shot: disable after run
        if job.get("type") == "oneshot":
            job["enabled"] = False
        with _lock:
            _save_jobs()


def _parse_cron_field(field: str, min_val: int, max_val: int) -> set:
    """Парсинг одного поля cron-выражения (*, 5, 1-3, */2, 1,3,5)."""
    values = set()
    if field == "*":
        return set(range(min_val, max_val + 1))
    for part in field.split(","):
        if "/" in part:
            base, step = part.split("/", 1)
            step = int(step)
            start = min_val if base == "*" else int(base)
            values.update(range(start, max_val + 1, step))
        elif "-" in part:
            start, end = part.split("-", 1)
            values.update(range(int(start), int(end) + 1))
        else:
            values.add(int(part))
    return values


def _matches_cron(cron_expr: str, dt: datetime) -> bool:
    """Проверяет, совпадает ли datetime с cron-выражением (мин час день мес день_недели)."""
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        return False
    minute, hour, day, month, weekday = parts
    return (
        dt.minute in _parse_cron_field(minute, 0, 59)
        and dt.hour in _parse_cron_field(hour, 0, 23)
        and dt.day in _parse_cron_field(day, 1, 31)
        and dt.month in _parse_cron_field(month, 1, 12)
        and dt.weekday() in _parse_cron_field(weekday, 0, 6)
    )


def _scheduler_loop():
    global _running
    while _running:
        now = datetime.now()
        with _lock:
            jobs_copy = dict(_jobs)
        for job_id, job in jobs_copy.items():
            if not job.get("enabled", True):
                continue
            try:
                if job["type"] == "interval":
                    interval = job.get("interval_seconds", 60)
                    last = job.get("last_run")
                    if last:
                        last_dt = datetime.fromisoformat(last)
                        elapsed = (now - last_dt).total_seconds()
                        if elapsed < interval:
                            continue
                    threading.Thread(target=_execute_job, args=(job_id,), daemon=True).start()
                elif job["type"] == "cron":
                    cron_expr = job.get("cron", "0 * * * *")
                    if _matches_cron(cron_expr, now):
                        # Check we didn't run this minute
                        last = job.get("last_run")
                        if last:
                            last_dt = datetime.fromisoformat(last)
                            if (now - last_dt).total_seconds() < 60:
                                continue
                        threading.Thread(target=_execute_job, args=(job_id,), daemon=True).start()
                elif job["type"] == "oneshot":
                    run_at = job.get("run_at")
                    if run_at:
                        run_dt = datetime.fromisoformat(run_at)
                        if now >= run_dt:
                            threading.Thread(target=_execute_job, args=(job_id,), daemon=True).start()
            except Exception as e:
                print(f"[scheduler] check error for {job_id}: {e}")
        time.sleep(10)  # check every 10 seconds


def start_scheduler():
    global _running, _thread
    if _running:
        return
    _load_jobs()
    _running = True
    _thread = threading.Thread(target=_scheduler_loop, daemon=True)
    _thread.start()
    print("[scheduler] started")


def stop_scheduler():
    global _running
    _running = False


def add_job(name: str, job_type: str, **kwargs) -> dict:
    """Добавить задачу.
    job_type: 'interval' (interval_seconds), 'cron' (cron), 'oneshot' (run_at)
    kwargs: flow_id, command, inputs, enabled
    """
    job_id = str(uuid.uuid4())[:8]
    job = {
        "id": job_id,
        "name": name,
        "type": job_type,
        "enabled": True,
        "created_at": datetime.now().isoformat(),
        "run_count": 0,
        "last_run": None,
        "last_status": None,
    }
    job.update(kwargs)
    with _lock:
        _jobs[job_id] = job
        _save_jobs()
    return job


def remove_job(job_id: str) -> bool:
    with _lock:
        if job_id in _jobs:
            del _jobs[job_id]
            _save_jobs()
            return True
    return False


def toggle_job(job_id: str) -> bool:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id]["enabled"] = not _jobs[job_id].get("enabled", True)
            _save_jobs()
            return _jobs[job_id]["enabled"]
    return False


def list_jobs() -> list:
    with _lock:
        return list(_jobs.values())


def run_job_now(job_id: str):
    """Запустить задачу немедленно."""
    threading.Thread(target=_execute_job, args=(job_id,), daemon=True).start()
