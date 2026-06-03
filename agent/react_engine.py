"""
ReAct Engine — Reasoning + Acting loop for the agent.
Implements the ReAct pattern: Think → Act → Observe → Think → ...
Also includes Task Creation and Prioritization (BabyAGI-style).
"""
import json
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from threading import Lock

BASE_DIR = Path(__file__).resolve().parent.parent
TASKS_DIR = BASE_DIR / "memory" / "tasks"
TASKS_DIR.mkdir(parents=True, exist_ok=True)
TASKS_FILE = TASKS_DIR / "task_queue.json"

_lock = Lock()


# ── Task Queue (BabyAGI-style) ──

def load_tasks() -> list:
    if TASKS_FILE.exists():
        try:
            return json.loads(TASKS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_tasks(tasks: list):
    TASKS_FILE.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")


def create_task(description: str, priority: int = 5, parent_id: str = None) -> dict:
    """Create a new task."""
    task = {
        "id": str(uuid.uuid4())[:8],
        "description": description,
        "status": "pending",  # pending, in_progress, completed, failed
        "priority": priority,  # 1=highest, 10=lowest
        "parent_id": parent_id,
        "created_at": datetime.now().isoformat(),
        "completed_at": None,
        "result": None,
    }
    with _lock:
        tasks = load_tasks()
        tasks.append(task)
        save_tasks(tasks)
    return task


def get_next_task() -> dict:
    """Get highest priority pending task."""
    with _lock:
        tasks = load_tasks()
        pending = [t for t in tasks if t["status"] == "pending"]
        if not pending:
            return None
        pending.sort(key=lambda t: t["priority"])
        return pending[0]


def update_task(task_id: str, **kwargs):
    """Update task fields."""
    with _lock:
        tasks = load_tasks()
        for t in tasks:
            if t["id"] == task_id:
                t.update(kwargs)
                break
        save_tasks(tasks)


def complete_task(task_id: str, result: str):
    """Mark task as completed with result."""
    update_task(task_id, status="completed", completed_at=datetime.now().isoformat(), result=result)


def fail_task(task_id: str, error: str):
    """Mark task as failed."""
    update_task(task_id, status="failed", result=error)


def list_tasks(status: str = None) -> list:
    """List tasks, optionally filtered by status."""
    tasks = load_tasks()
    if status:
        tasks = [t for t in tasks if t["status"] == status]
    return tasks


def prioritize_tasks(objective: str, llm_client, model: str) -> list:
    """
    Use LLM to reprioritize tasks based on the objective.
    Returns reordered list of task descriptions.
    """
    tasks = load_tasks()
    pending = [t for t in tasks if t["status"] == "pending"]
    if not pending:
        return []

    task_list = "\n".join([f"{i+1}. [{t['id']}] {t['description']}" for i, t in enumerate(pending)])
    prompt = f"""Objective: {objective}

Current task list:
{task_list}

Reorder and reprioritize these tasks. Return JSON array of task IDs in priority order (most important first).
Only return the JSON array, nothing else."""

    try:
        resp = llm_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
        )
        content = resp.choices[0].message.content.strip()
        # Extract JSON array
        match = re.search(r'\[.*\]', content, re.DOTALL)
        if match:
            ids = json.loads(match.group())
            # Reorder tasks
            id_to_task = {t["id"]: t for t in pending}
            reordered = []
            for tid in ids:
                if tid in id_to_task:
                    reordered.append(id_to_task[tid])
            return reordered
    except Exception as e:
        print(f"[prioritize] error: {e}")
    return pending


def generate_subtasks(objective: str, llm_client, model: str, max_tasks: int = 5) -> list:
    """
    Use LLM to generate subtasks from a high-level objective.
    BabyAGI-style task creation.
    """
    existing = load_tasks()
    existing_desc = "\n".join([f"- {t['description']}" for t in existing if t["status"] == "pending"])

    prompt = f"""Objective: {objective}

Existing pending tasks:
{existing_desc if existing_desc else "(none)"}

Generate up to {max_tasks} specific, actionable subtasks to achieve this objective.
Return JSON array of task descriptions (strings).
Only return the JSON array, nothing else."""

    try:
        resp = llm_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
        )
        content = resp.choices[0].message.content.strip()
        match = re.search(r'\[.*\]', content, re.DOTALL)
        if match:
            descriptions = json.loads(match.group())
            tasks = []
            for desc in descriptions[:max_tasks]:
                t = create_task(str(desc))
                tasks.append(t)
            return tasks
    except Exception as e:
        print(f"[generate_subtasks] error: {e}")
    return []


# ── ReAct Loop ──

class ReActEngine:
    """
    ReAct (Reasoning + Acting) execution loop.
    The agent thinks about what to do, takes an action, observes the result,
    and repeats until the task is complete.
    """

    def __init__(self, agent):
        self.agent = agent
        self.max_steps = 15
        self.log = []

    def run(self, task: str, context: str = "", max_steps: int = 15) -> dict:
        """
        Execute a task using the ReAct loop.
        Returns dict with status, result, steps, log.
        """
        self.log = []
        steps = []

        # System prompt for ReAct
        react_prompt = f"""You are an AI agent using the ReAct (Reasoning + Acting) pattern.

For each step, output EXACTLY one of:

1. THOUGHT: [your reasoning about what to do next]
2. ACTION: [tool_name] with parameters
3. OBSERVATION: [result of the action — filled in by system]
4. DONE: [final answer when task is complete]

Available tools:
- run_command(cmd): execute shell command
- read_file(path): read file
- write_file(path, content): write file
- edit_file(path, oldText, newText): edit file
- list_dir(path): list directory
- execute_code(code): run Python code
- web_search(query): search web
- calculator(expr): evaluate math
- create_task(desc): create a subtask
- complete_task(id, result): mark subtask done

Rules:
- Always start with THOUGHT
- After ACTION, wait for OBSERVATION before continuing
- Use tools to gather information before answering
- Break complex tasks into subtasks with create_task
- When done, output DONE: followed by the final result

Task: {task}
{context and f'Context: {context}' or ''}"""

        messages = [
            {"role": "system", "content": react_prompt},
            {"role": "user", "content": f"Begin working on: {task}"},
        ]

        for step_num in range(max_steps):
            try:
                resp = self.agent.client.chat.completions.create(
                    model=self.agent.model,
                    messages=messages,
                    max_tokens=1024,
                    temperature=0.3,
                )
                content = resp.choices[0].message.content.strip()
                self.log.append(f"[step {step_num + 1}] {content[:200]}")
                messages.append({"role": "assistant", "content": content})

                # Parse the response
                if content.startswith("DONE:") or content.startswith("DONE"):
                    result = content[5:].strip() if content.startswith("DONE:") else content[4:].strip()
                    return {
                        "status": "completed",
                        "result": result,
                        "steps": steps,
                        "log": self.log,
                    }

                elif content.startswith("THOUGHT:") or content.startswith("THOUGHT"):
                    thought = content.split(":", 1)[1].strip() if ":" in content else content
                    steps.append({"step": step_num + 1, "type": "thought", "content": thought})
                    # Continue to next iteration — agent will output ACTION next
                    # But we need to prompt it to continue
                    messages.append({"role": "user", "content": "Continue. Output your next ACTION or DONE."})
                    continue

                elif content.startswith("ACTION:") or content.startswith("ACTION"):
                    action_str = content.split(":", 1)[1].strip() if ":" in content else content
                    steps.append({"step": step_num + 1, "type": "action", "content": action_str})

                    # Execute the action
                    observation = self._execute_action(action_str)
                    steps.append({"step": step_num + 1, "type": "observation", "content": observation})

                    messages.append({
                        "role": "user",
                        "content": f"OBSERVATION: {observation}\n\nContinue with THOUGHT, ACTION, or DONE.",
                    })

                elif content.startswith("OBSERVATION:"):
                    # Agent is reflecting on observation
                    obs = content.split(":", 1)[1].strip()
                    steps.append({"step": step_num + 1, "type": "observation", "content": obs})
                    messages.append({"role": "user", "content": "Continue with THOUGHT, ACTION, or DONE."})

                else:
                    # Try to interpret as a direct response
                    steps.append({"step": step_num + 1, "type": "response", "content": content})
                    messages.append({"role": "user", "content": "Continue with THOUGHT, ACTION, or DONE."})

            except Exception as e:
                self.log.append(f"[step {step_num + 1}] ERROR: {e}")
                return {
                    "status": "error",
                    "error": str(e),
                    "steps": steps,
                    "log": self.log,
                }

        return {
            "status": "max_steps",
            "result": "Maximum steps reached",
            "steps": steps,
            "log": self.log,
        }

    def _execute_action(self, action_str: str) -> str:
        """Parse and execute an action string. Returns observation."""
        action_str = action_str.strip()

        # Parse: tool_name(param1, param2, ...)
        match = re.match(r'(\w+)\((.*)\)', action_str, re.DOTALL)
        if not match:
            return f"ERROR: Cannot parse action: {action_str}"

        tool_name = match.group(1).lower()
        args_str = match.group(2).strip()

        # Simple arg parsing (handles quoted strings and plain values)
        args = []
        for arg in re.findall(r'"([^"]*)"|\'([^\']*)\'|(\S+)', args_str):
            args.append(arg[0] or arg[1] or arg[2])

        try:
            if tool_name == "run_command":
                import subprocess
                result = subprocess.run(args[0], shell=True, capture_output=True, text=True, timeout=30)
                return result.stdout[:1000] if result.stdout else result.stderr[:500]

            elif tool_name == "read_file":
                from pathlib import Path
                p = Path(args[0])
                if p.exists():
                    return p.read_text(encoding="utf-8")[:2000]
                return f"File not found: {args[0]}"

            elif tool_name == "write_file":
                from pathlib import Path
                p = Path(args[0])
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(args[1] if len(args) > 1 else "", encoding="utf-8")
                return f"Written: {args[0]}"

            elif tool_name == "list_dir":
                from pathlib import Path
                p = Path(args[0]) if args else Path(".")
                items = list(p.iterdir())[:50]
                return "\n".join([f"{'D' if d.is_dir() else 'F'} {d.name}" for d in items])

            elif tool_name == "execute_code":
                import subprocess
                code = args[0] if args else action_str[action_str.find("(")+1:action_str.rfind(")")]
                r = subprocess.run(["python3", "-c", code], capture_output=True, text=True, timeout=30)
                return r.stdout[:1000] if r.stdout else r.stderr[:500]

            elif tool_name == "web_search":
                from agent.core import Agent
                # Use the agent's web search capability
                return f"Web search for: {args[0] if args else ''} (not implemented in ReAct sandbox)"

            elif tool_name == "calculator":
                expr = args[0] if args else ""
                try:
                    result = eval(expr, {"__builtins__": {}}, {})
                    return str(result)
                except Exception as e:
                    return f"Math error: {e}"

            elif tool_name == "create_task":
                desc = args[0] if args else action_str
                t = create_task(desc)
                return f"Task created: [{t['id']}] {t['description']}"

            elif tool_name == "complete_task":
                tid = args[0] if args else ""
                result = args[1] if len(args) > 1 else "completed"
                complete_task(tid, result)
                return f"Task {tid} completed"

            else:
                return f"Unknown tool: {tool_name}"

        except Exception as e:
            return f"ERROR executing {tool_name}: {e}"
