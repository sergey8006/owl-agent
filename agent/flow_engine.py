"""
Flow Engine — система сценариев с памятью, переменными и rollback.

Возможности:
- Создание сценариев из текста пользователя (LLM генерирует JSON-план)
- Последовательное выполнение шагов с проверкой
- Flow Variables — передача данных между шагами ($VAR)
- Flow Run History — пропуск уже выполненных шагов
- Step Snapshot / Rollback — .backup перед изменением, восстановление при ошибке
"""

import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MEMORY_DIR = BASE_DIR / "memory"
MEMORY_DIR.mkdir(exist_ok=True)
DB_PATH = MEMORY_DIR / "flow_engine.db"

MUTATING_ACTIONS = {"file_create", "file_write", "file_delete", "script_exec"}


class FlowEngine:
    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS flows (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                steps TEXT NOT NULL,
                variables TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS flow_run_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flow_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                action TEXT NOT NULL,
                status TEXT NOT NULL,
                output TEXT DEFAULT '',
                executed_at TEXT NOT NULL,
                UNIQUE(flow_id, step_index)
            );
            CREATE TABLE IF NOT EXISTS flow_checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flow_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                variables TEXT NOT NULL,
                log TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                UNIQUE(flow_id)
            );
            CREATE TABLE IF NOT EXISTS flow_execution_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flow_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                steps_completed INTEGER DEFAULT 0,
                steps_failed INTEGER DEFAULT 0,
                log TEXT DEFAULT '',
                error TEXT DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_execution_log_flow ON flow_execution_log(flow_id);
            CREATE INDEX IF NOT EXISTS idx_execution_log_run ON flow_execution_log(run_id);
        """)
        self.conn.commit()

    # -- CRUD --

    def create_flow(self, flow_id, name, steps, description="", variables=None):
        now = datetime.now().isoformat()
        self.conn.execute(
            "INSERT OR REPLACE INTO flows (id, name, description, steps, variables, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (flow_id, name, description, json.dumps(steps, ensure_ascii=False),
             json.dumps(variables or {}), now, now)
        )
        self.conn.commit()
        return {"id": flow_id, "name": name, "steps_count": len(steps)}

    def get_flow(self, flow_id):
        row = self.conn.execute("SELECT * FROM flows WHERE id = ?", (flow_id,)).fetchone()
        if not row:
            return None
        return {
            "id": row["id"], "name": row["name"], "description": row["description"],
            "steps": json.loads(row["steps"]), "variables": json.loads(row["variables"]),
            "created_at": row["created_at"], "updated_at": row["updated_at"],
        }

    def list_flows(self):
        rows = self.conn.execute(
            "SELECT id, name, description, created_at FROM flows ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_flow(self, flow_id):
        self.conn.execute("DELETE FROM flows WHERE id = ?", (flow_id,))
        self.conn.execute("DELETE FROM flow_run_history WHERE flow_id = ?", (flow_id,))
        self.conn.execute("DELETE FROM flow_snapshots WHERE flow_id = ?", (flow_id,))
        self.conn.execute("DELETE FROM flow_checkpoints WHERE flow_id = ?", (flow_id,))
        self.conn.execute("DELETE FROM flow_execution_log WHERE flow_id = ?", (flow_id,))
        self.conn.commit()
        return True

    # -- Checkpointing --

    def save_checkpoint(self, flow_id: str, step_index: int, variables: dict, log: list):
        """Сохранить прогресс flow для восстановления."""
        now = datetime.now().isoformat()
        self.conn.execute(
            "INSERT OR REPLACE INTO flow_checkpoints (flow_id, step_index, variables, log, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (flow_id, step_index, json.dumps(variables, ensure_ascii=False),
             json.dumps(log, ensure_ascii=False), now)
        )
        self.conn.commit()

    def load_checkpoint(self, flow_id: str) -> dict:
        """Загрузить последний checkpoint."""
        row = self.conn.execute(
            "SELECT * FROM flow_checkpoints WHERE flow_id = ? ORDER BY created_at DESC LIMIT 1",
            (flow_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "step_index": row["step_index"],
            "variables": json.loads(row["variables"]),
            "log": json.loads(row["log"]),
            "created_at": row["created_at"],
        }

    def clear_checkpoint(self, flow_id: str):
        self.conn.execute("DELETE FROM flow_checkpoints WHERE flow_id = ?", (flow_id,))
        self.conn.commit()

    # -- Execution Log --

    def start_execution(self, flow_id: str, run_id: str):
        """Начать запись выполнения."""
        self.conn.execute(
            "INSERT INTO flow_execution_log (flow_id, run_id, status, started_at) VALUES (?, ?, ?, ?)",
            (flow_id, run_id, "running", datetime.now().isoformat())
        )
        self.conn.commit()

    def finish_execution(self, run_id: str, status: str, steps_completed: int,
                         steps_failed: int, log: list, error: str = ""):
        """Завершить запись выполнения."""
        self.conn.execute(
            "UPDATE flow_execution_log SET status=?, finished_at=?, steps_completed=?, "
            "steps_failed=?, log=?, error=? WHERE run_id=?",
            (status, datetime.now().isoformat(), steps_completed, steps_failed,
             json.dumps(log, ensure_ascii=False), error, run_id)
        )
        self.conn.commit()

    def get_execution_log(self, flow_id: str, limit: int = 20) -> list:
        """Получить историю выполнений flow."""
        rows = self.conn.execute(
            "SELECT * FROM flow_execution_log WHERE flow_id = ? ORDER BY started_at DESC LIMIT ?",
            (flow_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]

    # -- Run --

    def run_flow(self, flow_id, skip_completed=True, dry_run=False, max_parallel=4, inputs=None, resume=False):
        flow = self.get_flow(flow_id)
        if not flow:
            return {"status": "error", "error": f"Flow '{flow_id}' not found"}

        steps = flow["steps"]
        variables = dict(flow.get("variables", {}))
        if inputs:
            variables.update(inputs)
        log = []
        completed = 0
        skipped = 0
        failed = 0

        # Generate run_id for execution tracking
        import uuid as _uuid
        run_id = str(_uuid.uuid4())[:12]

        # Check for resume from checkpoint
        resume_from = 0
        checkpoint = self.load_checkpoint(flow_id)
        if checkpoint and resume:
            resume_from = checkpoint["step_index"]
            variables.update(checkpoint["variables"])
            log = list(checkpoint.get("log", []))
            log.append(f"[resume] from step {resume_from}")

        # Start execution log
        self.start_execution(flow_id, run_id)

        completed_steps = set()
        if skip_completed:
            completed_steps = self._get_completed_steps(flow_id)

        i = resume_from
        while i < len(steps):
            step = steps[i]
            action = step.get("action", "unknown")
            step = self._resolve_vars(step, variables)

            # --- Branch: if/else block ---
            if action == "if":
                branch_result = self._execute_branch(step, steps, i, variables,
                                                     completed_steps, dry_run,
                                                     skip_completed, flow_id,
                                                     log)
                if branch_result["status"] == "failed":
                    return {
                        "status": "failed", "error": branch_result["error"],
                        "failed_step": branch_result.get("failed_step", i),
                        "steps_completed": completed,
                        "steps_skipped": skipped,
                        "steps_failed": failed,
                        "variables": variables, "log": log,
                    }
                # Advance past the entire block
                block_end = branch_result.get("next_index", i + 1)
                completed += branch_result.get("completed", 0)
                skipped += branch_result.get("skipped", 0)
                failed += branch_result.get("failed", 0)
                i = block_end
                continue

            # --- Loop block ---
            if action == "loop":
                loop_result = self._execute_loop(step, variables, dry_run,
                                                  skip_completed, flow_id,
                                                  completed_steps, log)
                if loop_result["status"] == "failed":
                    return {
                        "status": "failed", "error": loop_result["error"],
                        "failed_step": loop_result.get("failed_step", i),
                        "steps_completed": completed,
                        "steps_skipped": skipped,
                        "steps_failed": failed,
                        "variables": variables, "log": log,
                    }
                completed += loop_result.get("completed", 0)
                skipped += loop_result.get("skipped", 0)
                failed += loop_result.get("failed", 0)
                i += 1
                continue

            # --- Parallel block ---
            if action == "parallel":
                par_result = self._execute_parallel(step, variables, dry_run,
                                                     flow_id, completed_steps,
                                                     max_parallel, log)
                if par_result["status"] == "failed":
                    return {
                        "status": "failed", "error": par_result["error"],
                        "failed_step": par_result.get("failed_step", i),
                        "steps_completed": completed,
                        "steps_skipped": skipped,
                        "steps_failed": failed,
                        "variables": variables, "log": log,
                    }
                completed += par_result.get("completed", 0)
                skipped += par_result.get("skipped", 0)
                failed += par_result.get("failed", 0)
                i += 1
                continue

            # --- Standard step ---
            if "condition" in step:
                if not self._check_condition(step["condition"], variables):
                    log.append(f"[step {i}] SKIP (condition not met): {action}")
                    skipped += 1
                    i += 1
                    continue

            if i in completed_steps:
                log.append(f"[step {i}] SKIP (already done): {action}")
                skipped += 1
                i += 1
                continue

            if dry_run:
                log.append(f"[step {i}] DRY RUN: {action}")
                i += 1
                continue

            snapshot_paths = []
            if action in MUTATING_ACTIONS:
                snapshot_paths = self._create_snapshots(flow_id, i, step)

            # Retry logic: step can specify "retry": {"count": 3, "delay": 2}
            retry_config = step.get("retry", {})
            max_retries = retry_config.get("count", 0) if isinstance(retry_config, dict) else 0
            retry_delay = retry_config.get("delay", 1) if isinstance(retry_config, dict) else 1

            output = None
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    output = self._execute_step(step, variables)
                    status = "success"
                    if "set_var" in step:
                        variables[step["set_var"]] = str(output).strip()
                    completed += 1
                    if attempt > 0:
                        log.append(f"[step {i}] OK (attempt {attempt+1}): {action} -> {str(output)[:80]}")
                    else:
                        log.append(f"[step {i}] OK: {action} -> {str(output)[:80]}")
                    break
                except Exception as e:
                    last_error = str(e)
                    if attempt < max_retries:
                        log.append(f"[step {i}] RETRY {attempt+1}/{max_retries}: {action} -> {last_error}")
                        time.sleep(retry_delay)
                    else:
                        status = "failed"
                        error_msg = last_error
                        log.append(f"[step {i}] FAIL: {action} -> {error_msg}")
                        self._rollback_all_snapshots(flow_id)
                        log.append(f"[step {i}] ROLLBACK done")
                        failed += 1
                        self._save_history(flow_id, i, action, status, error_msg)
                        self.finish_execution(run_id, "failed", completed, failed, log, error_msg)
                        return {
                            "status": "failed", "error": error_msg,
                            "run_id": run_id,
                            "failed_step": i, "steps_completed": completed,
                            "steps_skipped": skipped, "steps_failed": failed,
                            "variables": variables, "log": log,
                        }

            self._save_history(flow_id, i, action, status, str(output)[:500])
            # Save checkpoint after each successful step
            self.save_checkpoint(flow_id, i + 1, variables, log)
            i += 1

        # Finish execution log
        final_status = "success" if failed == 0 else "partial"
        self.finish_execution(run_id, final_status, completed, failed, log)
        # Clear checkpoint on successful completion
        if failed == 0:
            self.clear_checkpoint(flow_id)

        return {
            "status": final_status,
            "run_id": run_id,
            "steps_completed": completed, "steps_skipped": skipped,
            "steps_failed": failed, "variables": variables, "log": log,
        }

    # -- Step execution --

    def _execute_step(self, step, variables):
        action = step.get("action", "")
        handler = {
            "file_create": self._step_file_create,
            "file_write": self._step_file_write,
            "file_read": self._step_file_read,
            "file_delete": self._step_file_delete,
            "file_mkdir": self._step_file_mkdir,
            "file_exists": self._step_file_exists,
            "script_exec": self._step_script_exec,
            "command": self._step_script_exec,
            "set_variable": self._step_set_variable,
            "api_call": self._step_api_call,
            "wait": self._step_wait,
            "notify": self._step_notify,
        }.get(action)
        if not handler:
            raise ValueError(f"Unknown action: {action}")
        return handler(step, variables)

    def _step_file_create(self, step, _):
        path = Path(step["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(step.get("content", ""), encoding="utf-8")
        return f"Created: {path}"

    def _step_file_write(self, step, _):
        path = Path(step["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        if step.get("mode") == "append":
            with open(path, "a", encoding="utf-8") as f:
                f.write(step.get("content", ""))
        else:
            path.write_text(step.get("content", ""), encoding="utf-8")
        return f"Written: {path}"

    def _step_file_read(self, step, _):
        path = Path(step["path"])
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        content = path.read_text(encoding="utf-8")
        return content[:step.get("limit", 10000)]

    def _step_file_delete(self, step, _):
        path = Path(step["path"])
        if path.exists():
            path.unlink()
            return f"Deleted: {path}"
        return f"Already absent: {path}"

    def _step_file_mkdir(self, step, _):
        path = Path(step["path"])
        path.mkdir(parents=True, exist_ok=True)
        return f"Directory ready: {path}"

    def _step_file_exists(self, step, _):
        path = Path(step["path"])
        return json.dumps({"exists": path.exists(), "path": str(path)})

    def _step_script_exec(self, step, _):
        code = step.get("code", "")
        if not code:
            raise ValueError("No code provided")
        result = subprocess.run(
            code, shell=True, capture_output=True, text=True,
            timeout=step.get("timeout", 30), cwd=step.get("workdir", str(BASE_DIR))
        )
        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR: {result.stderr}"
        if result.returncode != 0:
            output += f"\nExit code: {result.returncode}"
            raise RuntimeError(f"Script failed (exit {result.returncode}): {output[:500]}")
        return output[:5000] if output else "(no output)"

    def _step_set_variable(self, step, variables):
        variables[step["name"]] = step.get("value", "")
        return f"{step['name']} = {step.get('value', '')}"

    def _step_api_call(self, step, _):
        import urllib.request
        url = step["url"]
        method = step.get("method", "GET").upper()
        data = step.get("data")
        headers = step.get("headers", {})
        if data and method in ("POST", "PUT"):
            data = json.dumps(data).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=step.get("timeout", 15)) as resp:
            return resp.read().decode("utf-8", errors="replace")[:5000]

    def _step_wait(self, step, _):
        time.sleep(step.get("seconds", 1))
        return f"Waited {step.get('seconds', 1)}s"

    def _step_notify(self, step, _):
        return f"NOTIFY: {step.get('message', '')}"

    # -- Variables --

    def _resolve_vars(self, data, variables):
        if isinstance(data, str):
            def replacer(m):
                key = m.group(1) or m.group(2)
                return str(variables.get(key, m.group(0)))
            return re.sub(r'\$\{(\w+)\}|\$(\w+)', replacer, data)
        elif isinstance(data, dict):
            return {k: self._resolve_vars(v, variables) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._resolve_vars(item, variables) for item in data]
        return data

    # -- Branch (if/else) execution --

    def _execute_branch(self, step, all_steps, current_index, variables,
                        completed_steps, dry_run, skip_completed, flow_id, log):
        """Execute an if/else block.
        Step format:
        {"action":"if", "condition": {...}, "then": [...steps], "else": [...steps]}
        Returns dict with status, next_index, completed, skipped, failed.
        """
        condition = step.get("condition", {})
        if self._check_condition(condition, variables):
            branch_steps = step.get("then", [])
            branch_label = "then"
        else:
            branch_steps = step.get("else", [])
            branch_label = "else"

        log.append(f"[step {current_index}] IF -> {branch_label} ({len(branch_steps)} steps)")
        completed = 0
        skipped = 0
        failed = 0

        for j, sub in enumerate(branch_steps):
            action = sub.get("action", "unknown")
            sub = self._resolve_vars(sub, variables)
            idx = f"{current_index}.{j}"

            if dry_run:
                log.append(f"  [step {idx}] DRY RUN: {action}")
                continue

            snapshot_paths = []
            if action in MUTATING_ACTIONS:
                snapshot_paths = self._create_snapshots(f"{flow_id}_{current_index}_{branch_label}", j, sub)

            try:
                output = self._execute_step(sub, variables)
                if "set_var" in sub:
                    variables[sub["set_var"]] = str(output).strip()
                completed += 1
                log.append(f"  [step {idx}] OK: {action} -> {str(output)[:60]}")
            except Exception as e:
                error_msg = str(e)
                log.append(f"  [step {idx}] FAIL: {action} -> {error_msg}")
                self._rollback_all_snapshots(flow_id)
                log.append(f"  [step {idx}] ROLLBACK")
                return {"status": "failed", "error": error_msg,
                        "failed_step": idx, "completed": completed,
                        "skipped": skipped, "failed": 1,
                        "next_index": current_index + 1}

        return {"status": "success", "next_index": current_index + 1,
                "completed": completed, "skipped": skipped, "failed": failed}

    # -- Loop execution --

    def _execute_loop(self, step, variables, dry_run, skip_completed,
                      flow_id, completed_steps, log):
        """Execute a loop block.
        Step format:
        {"action":"loop", "count": 5, "variable": "i", "steps": [...]}
        or
        {"action":"loop", "while": {"condition": {...}}, "steps": [...]}
        or
        {"action":"loop", "items": "$MY_LIST", "variable": "item", "steps": [...]}
        """
        loop_steps = step.get("steps", [])
        max_iterations = step.get("max_iterations", 100)
        loop_var = step.get("variable", "_idx")
        items_key = step.get("items")

        if items_key:
            items_str = str(variables.get(items_key, ""))
            try:
                items = json.loads(items_str)
            except Exception:
                items = items_str.split(",")
            iterations = min(len(items), max_iterations)
        elif "while" in step:
            iterations = max_iterations  # bounded
        elif "count" in step:
            iterations = min(int(step["count"]), max_iterations)
        else:
            log.append(f"  [loop] Skipped: no count/while/items")
            return {"status": "success", "completed": 0, "skipped": 1, "failed": 0}

        loop_step_index = getattr(self, '_loop_step_counter', 0)
        completed = 0
        skipped = 0
        failed = 0

        for it in range(iterations):
            variables[loop_var] = items[it] if items_key else str(it)

            if "while" in step:
                if not self._check_condition(step["while"], variables):
                    log.append(f"  [loop] While condition false at iteration {it}, stopping")
                    break

            for j, sub in enumerate(loop_steps):
                action = sub.get("action", "unknown")
                sub = self._resolve_vars(sub, variables)

                if dry_run:
                    log.append(f"  [loop {it}] DRY RUN: {action}")
                    continue

                try:
                    output = self._execute_step(sub, variables)
                    if "set_var" in sub:
                        variables[sub["set_var"]] = str(output).strip()
                    completed += 1
                    log.append(f"  [loop {it}] OK: {action} -> {str(output)[:50]}")
                except Exception as e:
                    error_msg = str(e)
                    log.append(f"  [loop {it}] FAIL: {action} -> {error_msg}")
                    self._rollback_all_snapshots(flow_id)
                    return {"status": "failed", "error": error_msg,
                            "failed_step": f"loop.{it}.{j}",
                            "completed": completed, "skipped": skipped, "failed": 1}

            if "while" in step and it >= max_iterations - 1:
                log.append(f"  [loop] Max iterations ({max_iterations}) reached")
                break

        if items_key:
            del variables[loop_var]

        return {"status": "success", "completed": completed,
                "skipped": skipped, "failed": failed}

    # -- Parallel execution --

    def _execute_parallel(self, step, variables, dry_run, flow_id,
                          completed_steps, max_workers, log):
        """Execute steps in parallel using threads.
        Step format:
        {"action":"parallel", "steps": [...], "max_workers": 4, "fail_fast": true}
        Each inner step is a non-mutating action (script_exec, api_call, command).
        """
        par_steps = step.get("steps", [])
        fail_fast = step.get("fail_fast", True)
        workers = min(int(step.get("max_workers", max_workers)), 8)

        log.append(f"[parallel] Running {len(par_steps)} steps with {workers} workers")
        completed = 0
        failed = 0

        if dry_run:
            for j, sub in enumerate(par_steps):
                log.append(f"  [parallel {j}] DRY RUN: {sub.get('action', '?')}")
            return {"status": "success", "completed": 0,
                    "skipped": len(par_steps), "failed": 0}

        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading

        lock = threading.Lock()
        shared_output = {}

        def run_par_step(j, sub):
            action = sub.get("action", "unknown")
            sub = self._resolve_vars(sub, variables)
            try:
                output = self._execute_step(sub, variables)
                return j, "success", str(output)[:200], action
            except Exception as e:
                return j, "failed", str(e)[:200], action

        results = [None] * len(par_steps)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(run_par_step, j, par_steps[j]): j
                       for j in range(len(par_steps))}
            for future in as_completed(futures):
                j, status, output, action = future.result()
                results[j] = (status, output, action)
                if status == "success":
                    completed += 1
                    log.append(f"  [parallel {j}] OK: {action}")
                else:
                    failed += 1
                    log.append(f"  [parallel {j}] FAIL: {action} -> {output}")
                    if fail_fast:
                        # Cancel remaining
                        for f in futures:
                            f.cancel()
                        self._rollback_all_snapshots(flow_id)
                        return {"status": "failed", "error": output,
                                "failed_step": f"parallel.{j}",
                                "completed": completed, "skipped": 0, "failed": failed}

        return {"status": "success" if failed == 0 else "partial",
                "completed": completed, "skipped": 0, "failed": failed}

    # -- Conditions --

    def _check_condition(self, condition, variables):
        cond_type = condition.get("type", "")
        if cond_type == "file_exists":
            return Path(condition["path"]).exists()
        elif cond_type == "file_not_exists":
            return not Path(condition["path"]).exists()
        elif cond_type == "var_equals":
            return variables.get(condition["name"]) == condition.get("value")
        elif cond_type == "var_not_equals":
            return variables.get(condition["name"]) != condition.get("value")
        elif cond_type == "var_contains":
            return condition.get("value", "") in str(variables.get(condition["name"], ""))
        elif cond_type == "var_greater":
            try:
                return float(variables.get(condition["name"], 0)) > float(condition.get("value", 0))
            except (ValueError, TypeError):
                return False
        elif cond_type == "command_success":
            try:
                subprocess.run(condition["command"], shell=True,
                             capture_output=True, timeout=10).check_returncode()
                return True
            except Exception:
                return False
        return True

    # -- Snapshots / Rollback --

    def _create_snapshots(self, flow_id, step_index, step):
        paths = []
        action = step.get("action", "")
        target = step.get("path", "")
        if not target:
            return paths
        p = Path(target)
        # Для file_create файла может не быть — помечаем что создали
        if action == "file_create" and not p.exists():
            self.conn.execute(
                "INSERT INTO flow_snapshots (flow_id, step_index, original_path, backup_path, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (flow_id, step_index, str(p), "__CREATED__", datetime.now().isoformat())
            )
            self.conn.commit()
            paths.append("__CREATED__")
        elif action in ("file_write", "file_delete") and p.exists():
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup = Path(str(p) + f".flow_backup_{flow_id}_{step_index}_{ts}")
            shutil.copy2(str(p), str(backup))
            self.conn.execute(
                "INSERT INTO flow_snapshots (flow_id, step_index, original_path, backup_path, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (flow_id, step_index, str(p), str(backup), datetime.now().isoformat())
            )
            self.conn.commit()
            paths.append(str(backup))
        return paths

    def _rollback_snapshots(self, flow_id, step_index):
        rows = self.conn.execute(
            "SELECT original_path, backup_path FROM flow_snapshots "
            "WHERE flow_id = ? AND step_index = ? ORDER BY id DESC",
            (flow_id, step_index)
        ).fetchall()
        for row in rows:
            try:
                shutil.copy2(row["backup_path"], row["original_path"])
            except Exception:
                pass

    def _rollback_all_snapshots(self, flow_id):
        """Откатить ВСЕ снапшоты для flow (полный откат к состоянию до запуска)."""
        rows = self.conn.execute(
            "SELECT original_path, backup_path FROM flow_snapshots "
            "WHERE flow_id = ? ORDER BY step_index DESC, id DESC",
            (flow_id,)
        ).fetchall()
        restored = set()
        for row in rows:
            orig = row["original_path"]
            backup = row["backup_path"]
            if orig in restored:
                continue
            try:
                if backup == "__CREATED__":
                    # Файл был создан — удаляем
                    Path(orig).unlink(missing_ok=True)
                else:
                    shutil.copy2(backup, orig)
                restored.add(orig)
            except Exception:
                pass

    def cleanup_snapshots(self, flow_id):
        rows = self.conn.execute(
            "SELECT backup_path FROM flow_snapshots WHERE flow_id = ?", (flow_id,)
        ).fetchall()
        for row in rows:
            try:
                Path(row["backup_path"]).unlink(missing_ok=True)
            except Exception:
                pass
        self.conn.execute("DELETE FROM flow_snapshots WHERE flow_id = ?", (flow_id,))
        self.conn.commit()

    # -- History --

    def _get_completed_steps(self, flow_id):
        rows = self.conn.execute(
            "SELECT step_index FROM flow_run_history "
            "WHERE flow_id = ? AND status = 'success'",
            (flow_id,)
        ).fetchall()
        return {r["step_index"] for r in rows}

    def _save_history(self, flow_id, step_index, action, status, output):
        self.conn.execute(
            "INSERT OR REPLACE INTO flow_run_history (flow_id, step_index, action, status, output, executed_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (flow_id, step_index, action, status, output, datetime.now().isoformat())
        )
        self.conn.commit()

    def get_history(self, flow_id):
        rows = self.conn.execute(
            "SELECT step_index, action, status, output, executed_at "
            "FROM flow_run_history WHERE flow_id = ? ORDER BY step_index",
            (flow_id,)
        ).fetchall()
        return [dict(r) for r in rows]
