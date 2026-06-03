"""
Self-learning memory system for the agent.
Stores conversations, learned facts, preferences, and skills.
All stored locally in JSON/SQLite for offline operation.
"""

import json
import os
import re
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path

MEMORY_DIR = Path(__file__).parent.parent / "memory"
MEMORY_DIR.mkdir(exist_ok=True)
DB_PATH = MEMORY_DIR / "agent_memory.db"
FACTS_PATH = MEMORY_DIR / "learned_facts.json"
PREFS_PATH = MEMORY_DIR / "user_preferences.json"
SKILLS_PATH = MEMORY_DIR / "learned_skills.json"


class MemorySystem:
    def __init__(self, skills_dir=None):
        self.skills_dir = skills_dir
        self._init_db()
        self._load_json_files()
        if skills_dir:
            self.import_skills_from_folder(skills_dir)

    def import_skills_from_folder(self, skills_dir):
        """Import skills from SKILL.md files in a folder."""
        skills_path = Path(skills_dir)
        print(f"  [skills] Checking: {skills_path}")
        if not skills_path.exists():
            print(f"  [skills] NOT FOUND: {skills_path}")
            return
        imported = 0
        skill_dirs = sorted(skills_path.iterdir())
        print(f"  [skills] Found {len(skill_dirs)} items")
        for skill_dir in skill_dirs:
            if not skill_dir.is_dir():
                continue
            md_file = skill_dir / "SKILL.md"
            if not md_file.exists():
                print(f"  [skills] Skip: {skill_dir.name} (no SKILL.md)")
                continue
            try:
                content = md_file.read_text(encoding="utf-8")
                name = skill_dir.name.replace("-", " ").replace("_", " ").title()
                description = ""
                steps = []
                for line in content.split("\n"):
                    line = line.strip()
                    if line.startswith("# "):
                        name = line[2:].strip()
                    elif line and not line.startswith("#"):
                        description = line[:200]
                        break
                cursor = self.conn.cursor()
                cursor.execute("SELECT id FROM learned_skills WHERE name = ?", (name,))
                if cursor.fetchone():
                    print(f"  [skills] Skip: {name} (already exists)")
                    continue
                now = datetime.now().isoformat()
                cursor.execute(
                    "INSERT INTO learned_skills (name, description, steps, times_used, success_rate, created_at, last_used) "
                    "VALUES (?, ?, ?, 0, 0.5, ?, ?)",
                    (name, description, json.dumps(steps), now, now)
                )
                imported += 1
                print(f"  [skills] New skill: {name}")
            except Exception as e:
                print(f"  [skills] Error: {e}")
        if imported > 0:
            self.conn.commit()
            print(f"  Imported {imported} skills from {skills_dir}")
        else:
            print(f"  [skills] No new skills to import")

    def _init_db(self):
        """Initialize SQLite database for conversation history and facts."""
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        cursor = self.conn.cursor()
        
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT DEFAULT '{}'
            );
            
            CREATE TABLE IF NOT EXISTS learned_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact TEXT NOT NULL,
                source TEXT DEFAULT 'conversation',
                confidence REAL DEFAULT 0.5,
                times_reinforced INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                last_used TEXT NOT NULL,
                tags TEXT DEFAULT '[]',
                hash TEXT UNIQUE NOT NULL
            );
            
            CREATE TABLE IF NOT EXISTS user_preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                source TEXT DEFAULT 'inferred'
            );
            
            CREATE TABLE IF NOT EXISTS learned_skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT NOT NULL,
                steps TEXT NOT NULL,
                times_used INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 0.5,
                enabled INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                last_used TEXT NOT NULL
            );
            
            CREATE TABLE IF NOT EXISTS self_reflections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trigger TEXT NOT NULL,
                reflection TEXT NOT NULL,
                action_taken TEXT DEFAULT '',
                timestamp TEXT NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_conversations_session 
                ON conversations(session_id);
            CREATE INDEX IF NOT EXISTS idx_facts_hash 
                ON learned_facts(hash);
            CREATE INDEX IF NOT EXISTS idx_facts_confidence 
                ON learned_facts(confidence DESC);
        """)
        
        # FTS5 for full-text search on facts
        cursor.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS learned_facts_fts USING fts5(
                fact, 
                tags,
                content=learned_facts,
                content_rowid=id
            );
            -- Triggers to keep FTS index in sync
            CREATE TRIGGER IF NOT EXISTS learned_facts_ai AFTER INSERT ON learned_facts BEGIN
                INSERT INTO learned_facts_fts(rowid, fact, tags) VALUES (new.id, new.fact, new.tags);
            END;
            CREATE TRIGGER IF NOT EXISTS learned_facts_ad AFTER DELETE ON learned_facts BEGIN
                INSERT INTO learned_facts_fts(learned_facts_fts, rowid, fact, tags) VALUES ('delete', old.id, old.fact, old.tags);
            END;
            CREATE TRIGGER IF NOT EXISTS learned_facts_au AFTER UPDATE ON learned_facts BEGIN
                INSERT INTO learned_facts_fts(learned_facts_fts, rowid, fact, tags) VALUES ('delete', old.id, old.fact, old.tags);
                INSERT INTO learned_facts_fts(rowid, fact, tags) VALUES (new.id, new.fact, new.tags);
            END;
        """)
        
        # FTS5 for conversation search
        cursor.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts USING fts5(
                content,
                role,
                content=conversations,
                content_rowid=id
            );
            CREATE TRIGGER IF NOT EXISTS conversations_ai AFTER INSERT ON conversations BEGIN
                INSERT INTO conversations_fts(rowid, content, role) VALUES (new.id, new.content, new.role);
            END;
            CREATE TRIGGER IF NOT EXISTS conversations_ad AFTER DELETE ON conversations BEGIN
                INSERT INTO conversations_fts(conversations_fts, rowid, content, role) VALUES ('delete', old.id, old.content, old.role);
            END;
        """)
        
        self.conn.commit()

        # Schema migrations
        self._migrate_add_enabled_column()

    def _migrate_add_enabled_column(self):
        """Add 'enabled' column to learned_skills if it doesn't exist."""
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA table_info(learned_skills)")
        cols = [r[1] for r in cursor.fetchall()]
        if 'enabled' not in cols:
            cursor.execute("ALTER TABLE learned_skills ADD COLUMN enabled INTEGER DEFAULT 1")
            self.conn.commit()

    def _load_json_files(self):
        """Load JSON-based memory files as fallback/cache."""
        self.facts_cache = self._load_json(FACTS_PATH, [])
        self.prefs_cache = self._load_json(PREFS_PATH, {})
        self.skills_cache = self._load_json(SKILLS_PATH, [])

    @staticmethod
    def _load_json(path, default):
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
        return default

    @staticmethod
    def _save_json(path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _hash_fact(self, fact: str) -> str:
        return hashlib.md5(fact.strip().lower().encode()).hexdigest()

    # --- Conversation History ---

    def add_message(self, session_id: str, role: str, content: str, metadata: dict = None):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO conversations (session_id, role, content, timestamp, metadata) VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, datetime.now().isoformat(), json.dumps(metadata or {}))
        )
        self.conn.commit()

    def get_history(self, session_id: str, limit: int = 50) -> list:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT role, content, timestamp FROM conversations WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit)
        )
        rows = cursor.fetchall()
        return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in reversed(rows)]

    def get_all_sessions(self) -> list:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT session_id, COUNT(*) as msg_count, MIN(timestamp) as started, MAX(timestamp) as last_msg "
            "FROM conversations GROUP BY session_id ORDER BY last_msg DESC"
        )
        return [dict(r) for r in cursor.fetchall()]

    def search_conversations(self, query: str, limit: int = 10) -> list:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT session_id, role, content, timestamp FROM conversations "
            "WHERE content LIKE ? ORDER BY timestamp DESC LIMIT ?",
            (f"%{query}%", limit)
        )
        return [dict(r) for r in cursor.fetchall()]

    # --- Self-Learning: Facts ---

    def learn_fact(self, fact: str, source: str = "conversation", confidence: float = 0.5, tags: list = None):
        """Learn or reinforce a fact. Skip garbage."""
        fact = fact.strip()
        if not fact or len(fact) < 4 or len(fact) > 150:
            return
        if fact.count('\n') > 1:
            return
        if fact[0] in '.,;:!?-—– \t':
            return
        h = self._hash_fact(fact)
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        
        cursor.execute("SELECT id, times_reinforced, confidence FROM learned_facts WHERE hash = ?", (h,))
        existing = cursor.fetchone()
        
        if existing:
            new_confidence = min(1.0, existing["confidence"] + 0.1)
            cursor.execute(
                "UPDATE learned_facts SET times_reinforced = ?, confidence = ?, last_used = ? WHERE id = ?",
                (existing["times_reinforced"] + 1, new_confidence, now, existing["id"])
            )
        else:
            cursor.execute(
                "INSERT INTO learned_facts (fact, source, confidence, times_reinforced, created_at, last_used, tags, hash) "
                "VALUES (?, ?, ?, 1, ?, ?, ?, ?)",
                (fact, source, confidence, now, now, json.dumps(tags or []), h)
            )
        self.conn.commit()

    def get_relevant_facts(self, query: str, limit: int = 5, tag_filter: str = None) -> list:
        """Get facts relevant to a query using FTS5 full-text search + keyword fallback.
        Optionally filter by tag."""
        cursor = self.conn.cursor()
        
        # Try FTS5 first
        try:
            # Clean query for FTS5 (remove special chars that break FTS)
            fts_query = re.sub(r'[^\w\s]', ' ', query).strip()
            if fts_query:
                if tag_filter:
                    cursor.execute("""
                        SELECT f.fact, f.confidence, f.times_reinforced, f.tags
                        FROM learned_facts_fts 
                        JOIN learned_facts f ON f.id = learned_facts_fts.rowid
                        WHERE learned_facts_fts MATCH ?
                          AND f.tags LIKE ?
                        ORDER BY rank
                        LIMIT ?
                    """, (f'{fts_query}', f'%"{tag_filter}"%', limit))
                else:
                    cursor.execute("""
                        SELECT f.fact, f.confidence, f.times_reinforced, f.tags
                        FROM learned_facts_fts 
                        JOIN learned_facts f ON f.id = learned_facts_fts.rowid
                        WHERE learned_facts_fts MATCH ?
                        ORDER BY rank
                        LIMIT ?
                    """, (f'{fts_query}', limit))
                rows = cursor.fetchall()
                if rows:
                    return [{"fact": r["fact"], "confidence": r["confidence"],
                             "reinforced": r["times_reinforced"],
                             "tags": json.loads(r["tags"])} for r in rows]
        except Exception:
            pass  # FTS5 might fail on syntax, fall through
        
        # Fallback: keyword matching
        keywords = query.lower().split()
        cursor.execute(
            "SELECT fact, confidence, times_reinforced, tags FROM learned_facts "
            "ORDER BY confidence DESC, times_reinforced DESC LIMIT 100"
        )
        rows = cursor.fetchall()
        
        scored = []
        for row in rows:
            if tag_filter and tag_filter not in json.loads(row["tags"]):
                continue
            score = 0
            fact_lower = row["fact"].lower()
            for kw in keywords:
                if kw in fact_lower:
                    score += 1
            if score > 0:
                scored.append((score, row))
        
        scored.sort(key=lambda x: (x[0], x[1]["confidence"]), reverse=True)
        return [{"fact": s[1]["fact"], "confidence": s[1]["confidence"],
                 "reinforced": s[1]["times_reinforced"],
                 "tags": json.loads(s[1]["tags"])} for s in scored[:limit]]

    def search_facts_fts(self, query: str, limit: int = 20) -> list:
        """Raw FTS5 search over facts. Supports FTS5 syntax (AND, OR, phrases)."""
        cursor = self.conn.cursor()
        try:
            # Sanitize: keep only word chars and spaces for FTS5
            safe_query = re.sub(r'[^\w\s"]', ' ', query).strip()
            if not safe_query:
                return []
            cursor.execute("""
                SELECT f.fact, f.confidence, f.times_reinforced, f.tags, rank
                FROM learned_facts_fts 
                JOIN learned_facts f ON f.id = learned_facts_fts.rowid
                WHERE learned_facts_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (safe_query, limit))
            return [{"fact": r["fact"], "confidence": r["confidence"],
                     "reinforced": r["times_reinforced"],
                     "tags": json.loads(r["tags"])} for r in cursor.fetchall()]
        except Exception as e:
            return []

    def search_conversations_fts(self, query: str, limit: int = 20) -> list:
        """Raw FTS5 search over conversation history."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT c.session_id, c.role, c.content, c.timestamp, rank
                FROM conversations_fts 
                JOIN conversations c ON c.id = conversations_fts.rowid
                WHERE conversations_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit))
            return [dict(r) for r in cursor.fetchall()]
        except Exception as e:
            return []

    def get_facts_by_tag(self, tag: str, limit: int = 20) -> list:
        """Get all facts with a specific tag."""
        cursor = self.conn.cursor()
        # Search for tag in JSON array format: ["tag", ...] or ["...", "tag", ...]
        cursor.execute(
            "SELECT fact, confidence, times_reinforced, tags FROM learned_facts "
            "WHERE tags LIKE ? OR tags LIKE ? OR tags LIKE ? ORDER BY confidence DESC LIMIT ?",
            (f'["{tag}"]', f'["{tag}",%', f'%%,"{tag}"]', limit)
        )
        return [{"fact": r["fact"], "confidence": r["confidence"],
                 "reinforced": r["times_reinforced"],
                 "tags": json.loads(r["tags"])} for r in cursor.fetchall()]

    def get_all_tags(self) -> dict:
        """Get all tags with their counts."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT tags FROM learned_facts WHERE tags != '[]'")
        tag_counts = {}
        for r in cursor.fetchall():
            try:
                for t in json.loads(r["tags"]):
                    if len(t) > 1:  # Skip single-char artifacts
                        tag_counts[t] = tag_counts.get(t, 0) + 1
            except Exception:
                pass
        return tag_counts

    def add_fact_tag(self, fact_hash: str, tag: str):
        """Add a tag to an existing fact."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, tags FROM learned_facts WHERE hash = ?", (fact_hash,))
        row = cursor.fetchone()
        if row:
            tags = json.loads(row["tags"]) if row["tags"] else []
            if tag not in tags:
                tags.append(tag)
                cursor.execute("UPDATE learned_facts SET tags = ? WHERE id = ?",
                             (json.dumps(tags), row["id"]))
                self.conn.commit()

    def semantic_dedup_facts(self, similarity_threshold: float = 0.85):
        """Remove near-duplicate facts using Jaccard similarity on word sets."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, fact, confidence, times_reinforced FROM learned_facts ORDER BY id")
        rows = cursor.fetchall()
        
        def word_set(text):
            return set(re.findall(r'\w+', text.lower().strip()))
        
        def jaccard(a, b):
            sa, sb = word_set(a), word_set(b)
            if not sa or not sb:
                return 0.0
            return len(sa & sb) / len(sa | sb)
        
        to_remove = set()
        for i in range(len(rows)):
            if rows[i]["id"] in to_remove:
                continue
            for j in range(i + 1, len(rows)):
                if rows[j]["id"] in to_remove:
                    continue
                sim = jaccard(rows[i]["fact"], rows[j]["fact"])
                if sim >= similarity_threshold:
                    # Keep the one with higher confidence * reinforcement
                    score_i = rows[i]["confidence"] * rows[i]["times_reinforced"]
                    score_j = rows[j]["confidence"] * rows[j]["times_reinforced"]
                    if score_i >= score_j:
                        to_remove.add(rows[j]["id"])
                    else:
                        to_remove.add(rows[i]["id"])
                        break
        
        if to_remove:
            for fid in to_remove:
                cursor.execute("DELETE FROM learned_facts WHERE id = ?", (fid,))
            self.conn.commit()
        return len(to_remove)

    def get_all_facts(self, limit: int = 100) -> list:
        cursor = self.conn.cursor()
        cursor.execute("SELECT fact, confidence, times_reinforced FROM learned_facts ORDER BY confidence DESC LIMIT ?", (limit,))
        return [dict(r) for r in cursor.fetchall()]

    # --- User Preferences ---

    def set_preference(self, key: str, value: str, source: str = "inferred"):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO user_preferences (key, value, updated_at, source) VALUES (?, ?, ?, ?)",
            (key, value, datetime.now().isoformat(), source)
        )
        self.conn.commit()
        self.prefs_cache[key] = value
        self._save_json(PREFS_PATH, self.prefs_cache)

    def get_preference(self, key: str, default: str = None) -> str:
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM user_preferences WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default

    def get_all_preferences(self) -> dict:
        cursor = self.conn.cursor()
        cursor.execute("SELECT key, value FROM user_preferences")
        return {r["key"]: r["value"] for r in cursor.fetchall()}

    # --- Learned Skills ---

    def learn_skill(self, name: str, description: str, steps: list):
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute(
            "INSERT OR REPLACE INTO learned_skills (name, description, steps, created_at, last_used) VALUES (?, ?, ?, ?, ?)",
            (name, description, json.dumps(steps), now, now)
        )
        self.conn.commit()

    def get_skill(self, name: str) -> dict:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM learned_skills WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            return {"name": row["name"], "description": row["description"], 
                    "steps": json.loads(row["steps"]), "times_used": row["times_used"],
                    "success_rate": row["success_rate"]}
        return None

    def get_all_skills(self) -> list:
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, description, times_used, success_rate, enabled FROM learned_skills ORDER BY times_used DESC")
        skills = []
        for r in cursor.fetchall():
            d = dict(r)
            d["has_scripts"] = False
            d["enabled"] = bool(d.get("enabled", 1))
            skills.append(d)
        return skills

    def set_skill_enabled(self, skill_id: int, enabled: bool):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE learned_skills SET enabled = ? WHERE id = ?", (1 if enabled else 0, skill_id))
        self.conn.commit()

    def get_skill_detail(self, skill_id: int) -> dict:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM learned_skills WHERE id = ?", (skill_id,))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        d["enabled"] = bool(d.get("enabled", 1))
        d["steps"] = json.loads(d.get("steps", "[]"))
        d["scripts"] = []
        d["content"] = ""
        # Check for SKILL.md content
        skill_dir = self.skills_dir if hasattr(self, 'skills_dir') else None
        if skill_dir:
            for sd in Path(skill_dir).iterdir():
                if sd.is_dir() and sd.name.replace("-", " ").replace("_", " ").title() == d["name"]:
                    md = sd / "SKILL.md"
                    if md.exists():
                        d["content"] = md.read_text(encoding="utf-8")
                    for sub in sd.iterdir():
                        if sub.is_dir() and sub.name in ("scripts", "templates", "assets"):
                            d["scripts"].extend(f"{sub.name}/{f.name}" for f in sub.iterdir() if f.is_file())
                    break
        d["has_scripts"] = len(d["scripts"]) > 0
        return d

    def use_skill(self, name: str, success: bool = True):
        cursor = self.conn.cursor()
        cursor.execute("SELECT times_used, success_rate FROM learned_skills WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            total = row["times_used"] + 1
            new_rate = (row["success_rate"] * row["times_used"] + (1.0 if success else 0.0)) / total
            cursor.execute(
                "UPDATE learned_skills SET times_used = ?, success_rate = ?, last_used = ? WHERE name = ?",
                (total, new_rate, datetime.now().isoformat(), name)
            )
            self.conn.commit()

    # --- Self-Reflection ---

    def reflect(self, trigger: str, reflection: str, action: str = ""):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO self_reflections (trigger, reflection, action_taken, timestamp) VALUES (?, ?, ?, ?)",
            (trigger, reflection, action, datetime.now().isoformat())
        )
        self.conn.commit()

    def get_reflections(self, limit: int = 20) -> list:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM self_reflections ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in cursor.fetchall()]

    # --- Context Building ---

    def build_context(self, session_id: str, query: str) -> str:
        """Build context string from memory for injection into LLM prompt."""
        parts = []
        
        # User preferences
        prefs = self.get_all_preferences()
        if prefs:
            parts.append("User preferences:")
            for k, v in prefs.items():
                parts.append(f"  - {k}: {v}")
        
        # Relevant facts
        facts = self.get_relevant_facts(query)
        if facts:
            parts.append("\nRelevant learned facts:")
            for f in facts:
                parts.append(f"  - {f['fact']} (confidence: {f['confidence']:.1f})")
        
        # Recent conversation history
        history = self.get_history(session_id, limit=10)
        if history:
            parts.append("\nRecent conversation:")
            for msg in history[-6:]:
                parts.append(f"  {msg['role']}: {msg['content'][:200]}")
        
        return "\n".join(parts)

    # --- Stats ---

    def get_stats(self) -> dict:
        cursor = self.conn.cursor()
        stats = {}
        cursor.execute("SELECT COUNT(*) as c FROM conversations")
        stats["total_messages"] = cursor.fetchone()["c"]
        cursor.execute("SELECT COUNT(*) as c FROM learned_facts")
        stats["total_facts"] = cursor.fetchone()["c"]
        cursor.execute("SELECT COUNT(*) as c FROM user_preferences")
        stats["total_preferences"] = cursor.fetchone()["c"]
        cursor.execute("SELECT COUNT(*) as c FROM learned_skills")
        stats["total_skills"] = cursor.fetchone()["c"]
        cursor.execute("SELECT COUNT(*) as c FROM self_reflections")
        stats["total_reflections"] = cursor.fetchone()["c"]
        cursor.execute("SELECT COUNT(DISTINCT session_id) as c FROM conversations")
        stats["total_sessions"] = cursor.fetchone()["c"]
        return stats

    # --- Export/Import ---

    def export_memory(self) -> dict:
        cursor = self.conn.cursor()
        data = {
            "facts": self.get_all_facts(),
            "preferences": self.get_all_preferences(),
            "skills": self.get_all_skills(),
            "reflections": self.get_reflections(limit=1000),
            "stats": self.get_stats(),
            "exported_at": datetime.now().isoformat()
        }
        return data

    def close(self):
        self.conn.close()
