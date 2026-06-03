"""
Agent Team System — OWL Agent v3.0
Позволяет создавать команды агентов для выполнения сложных задач.
"""

import json
import time
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


TEAM_DB_PATH = Path(__file__).parent.parent / "memory" / "agent_teams.db"


class AgentTeam:
    """Команда агентов для выполнения задачи."""

    def __init__(self, team_id: str, name: str, task: str, agent_roles: list,
                 status: str = "created", created_at: str = None):
        self.team_id = team_id
        self.name = name
        self.task = task
        self.agent_roles = agent_roles
        self.status = status
        self.created_at = created_at or datetime.now().isoformat()
        self.results = {}
        self.log = []

    @staticmethod
    def _init_db():
        db = sqlite3.connect(str(TEAM_DB_PATH), check_same_thread=False)
        db.row_factory = sqlite3.Row
        db.executescript("""
            CREATE TABLE IF NOT EXISTS agent_teams (
                team_id TEXT PRIMARY KEY, name TEXT NOT NULL, task TEXT NOT NULL,
                agent_roles TEXT NOT NULL, status TEXT DEFAULT 'created',
                results TEXT DEFAULT '{}', log TEXT DEFAULT '[]',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS team_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, team_id TEXT NOT NULL,
                agent_name TEXT NOT NULL, role TEXT NOT NULL,
                content TEXT NOT NULL, msg_type TEXT DEFAULT 'info',
                timestamp TEXT NOT NULL
            );
        """)
        db.commit()
        return db

    @classmethod
    def create(cls, name: str, task: str, agent_roles: list) -> "AgentTeam":
        team_id = f"team_{int(time.time())}_{name[:20].replace(' ', '_').lower()}"
        team = cls(team_id=team_id, name=name, task=task, agent_roles=agent_roles)
        team._save()
        team._log("system", "Team created", f"{len(agent_roles)} agents")
        return team

    @classmethod
    def get(cls, team_id: str) -> Optional["AgentTeam"]:
        db = cls._init_db()
        row = db.execute("SELECT * FROM agent_teams WHERE team_id = ?", (team_id,)).fetchone()
        if not row:
            db.close()
            return None
        team = cls(
            team_id=row["team_id"], name=row["name"], task=row["task"],
            agent_roles=json.loads(row["agent_roles"]), status=row["status"],
            created_at=row["created_at"],
        )
        team.results = json.loads(row["results"])
        team.log = json.loads(row["log"])
        db.close()
        return team

    @classmethod
    def list_teams(cls, limit: int = 20) -> list:
        db = cls._init_db()
        rows = db.execute("SELECT * FROM agent_teams ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        db.close()
        return [dict(r) for r in rows]

    def _save(self):
        db = self._init_db()
        now = datetime.now().isoformat()
        db.execute("""
            INSERT OR REPLACE INTO agent_teams
            (team_id, name, task, agent_roles, status, results, log, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (self.team_id, self.name, self.task,
              json.dumps(self.agent_roles, ensure_ascii=False), self.status,
              json.dumps(self.results, ensure_ascii=False),
              json.dumps(self.log, ensure_ascii=False),
              self.created_at, now))
        db.commit()
        db.close()

    def _log(self, agent_name: str, role: str, content: str, msg_type: str = "info"):
        entry = {"agent": agent_name, "role": role, "content": content[:500],
                 "type": msg_type, "time": datetime.now().isoformat()}
        self.log.append(entry)
        db = self._init_db()
        db.execute("""
            INSERT INTO team_messages (team_id, agent_name, role, content, msg_type, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (self.team_id, agent_name, role, content[:2000], msg_type, entry["time"]))
        db.commit()
        db.close()

    def get_messages(self, limit: int = 50) -> list:
        db = self._init_db()
        rows = db.execute(
            "SELECT * FROM team_messages WHERE team_id = ? ORDER BY id DESC LIMIT ?",
            (self.team_id, limit)).fetchall()
        db.close()
        return [dict(r) for r in reversed(rows)]

    def delete(self):
        db = self._init_db()
        db.execute("DELETE FROM team_messages WHERE team_id = ?", (self.team_id,))
        db.execute("DELETE FROM agent_teams WHERE team_id = ?", (self.team_id,))
        db.commit()
        db.close()

    def to_dict(self) -> dict:
        return {
            "team_id": self.team_id, "name": self.name, "task": self.task,
            "agent_roles": self.agent_roles, "status": self.status,
            "results": self.results, "log": self.log[-10:],
            "created_at": self.created_at,
        }

    @staticmethod
    def load_skill(skill_name: str) -> Optional[dict]:
        """Load skill content by name from skills folder."""
        skills_dir = Path(__file__).parent.parent / "skills"
        if not skills_dir.exists():
            return None
        for d in skills_dir.iterdir():
            if not d.is_dir():
                continue
            dir_name = d.name.lower().replace("-", " ").replace("_", " ")
            if dir_name == skill_name.lower().replace("-", " ").replace("_", " "):
                md = d / "SKILL.md"
                if md.exists():
                    content = md.read_text(encoding="utf-8")
                    name = d.name.replace("-", " ").replace("_", " ").title()
                    # Parse name from content
                    for line in content.split("\n"):
                        ls = line.strip()
                        if ls.startswith("# "):
                            name = ls[2:].strip()
                            break
                    return {"name": name, "content": content}
        return None


class TeamRunner:
    """Исполнитель команды агентов."""

    def __init__(self, team: AgentTeam):
        self.team = team

    def run(self, max_steps: int = 10) -> dict:
        """Run the team to complete the task. Returns results dict."""
        self.team.status = "running"
        self.team._log("lead", "Team Lead", f"Starting: {self.team.task}")
        self.team._save()

        results = {"task": self.team.task, "steps": []}

        try:
            # Step 1: Decompose task
            lead = self._make_agent("lead", "Team Lead", [])
            decomp = lead.chat(
                f"Декомпозируй задачу на подзадачи для команды.\n"
                f"Задача: {self.team.task}\n"
                f"Роли: {json.dumps([r['role'] for r in self.team.agent_roles], ensure_ascii=False)}\n"
                f"Верни список подзадач для каждой роли."
            )
            results["decomposition"] = decomp.get("response", "")
            results["steps"].append({"step": 1, "agent": "lead", "action": "decompose",
                                      "result": results["decomposition"][:500]})

            # Step 2: Execute each agent's subtask
            step_num = 2
            for role_info in self.team.agent_roles:
                if step_num > max_steps:
                    break
                agent_name = role_info.get("name", "worker")
                agent_role = role_info.get("role", "Worker")
                agent_skills = role_info.get("skills", [])

                self.team._log(agent_name, agent_role, "Starting work...")

                worker = self._make_agent(agent_name, agent_role, agent_skills)

                prev = "\n".join([
                    f"- {s['agent']}: {s.get('result', '')[:300]}"
                    for s in results["steps"]
                ])

                prompt = (
                    f"Ты — {agent_role} в команде.\n"
                    f"Задача команды: {self.team.task}\n"
                )
                if agent_skills:
                    prompt += f"Твои скиллы: {', '.join(agent_skills)}\n"
                if prev:
                    prompt += f"\nРезультаты предыдущих агентов:\n{prev}\n"
                prompt += "\nВыполни свою часть задачи."

                resp = worker.chat(prompt)
                result_text = resp.get("response", "")

                self.team.results[agent_name] = result_text
                results["steps"].append({
                    "step": step_num, "agent": agent_name,
                    "role": agent_role, "skills": agent_skills,
                    "result": result_text[:1000]
                })
                self.team._log(agent_name, agent_role, f"Done: {result_text[:200]}...")
                step_num += 1

            self.team.status = "completed"
            self.team._log("lead", "Team Lead", "Task completed!")
            self.team.results = results
            self.team._save()

        except Exception as e:
            self.team.status = "error"
            self.team._log("system", "Error", str(e), "error")
            self.team._save()
            results["error"] = str(e)

        return results

    def _make_agent(self, name: str, role: str, skills: list):
        """Create an Agent for a team role with skill instructions."""
        from agent.core import Agent

        prompt = (
            f"Ты — {role} в команде агентов '{self.team.name}'.\n"
            f"Задача команды: {self.team.task}\n"
        )
        if skills:
            prompt += f"Можешь использовать скиллы: {', '.join(skills)}.\n"

        prompt += "\nИнструменты: run_command, read_file, write_file, edit_file, list_dir, execute_code, calculator, web_search, use_skill."

        # Append skill instructions
        for sk in skills:
            skill_data = AgentTeam.load_skill(sk)
            if skill_data:
                content = skill_data.get("content", "")[:800]
                prompt += f"\n\n## Скилл: {skill_data['name']}\n{content}"

        return Agent(system_prompt=prompt)
