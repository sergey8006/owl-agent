"""
RAG (Retrieval Augmented Generation) Engine.
Document loading → chunking → embedding → search → generation.
Uses SQLite for storage, TF-IDF for lightweight search (no heavy dependencies).
"""
import json
import math
import re
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from threading import Lock

BASE_DIR = Path(__file__).resolve().parent.parent
RAG_DIR = BASE_DIR / "memory" / "rag"
RAG_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = RAG_DIR / "rag.db"
LOCK = Lock()


def _get_db():
    db = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            title TEXT DEFAULT '',
            content TEXT NOT NULL,
            chunk_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL,
            content TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            word_count INTEGER DEFAULT 0,
            FOREIGN KEY (doc_id) REFERENCES documents(id)
        );
        CREATE TABLE IF NOT EXISTS terms (
            term TEXT NOT NULL,
            chunk_id TEXT NOT NULL,
            tf REAL DEFAULT 0,
            PRIMARY KEY (term, chunk_id),
            FOREIGN KEY (chunk_id) REFERENCES chunks(id)
        );
        CREATE INDEX IF NOT EXISTS idx_terms_term ON terms(term);
        CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
    """)
    db.commit()
    return db


# ── Text Processing ──

def _tokenize(text: str) -> list:
    """Simple tokenizer: lowercase, split on non-alpha, filter short."""
    text = text.lower()
    tokens = re.findall(r'[a-zа-яё]+', text)
    # Filter very short tokens
    return [t for t in tokens if len(t) > 2]


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list:
    """Split text into overlapping chunks by words."""
    words = text.split()
    if not words:
        return []

    chunks = []
    step = chunk_size - overlap
    if step <= 0:
        step = chunk_size

    for i in range(0, len(words), step):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        if i + chunk_size >= len(words):
            break

    return chunks


def _compute_tf(tokens: list) -> dict:
    """Compute term frequency."""
    tf = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1
    total = len(tokens) if tokens else 1
    for t in tf:
        tf[t] /= total
    return tf


def _compute_idf(db) -> dict:
    """Compute inverse document frequency for all terms."""
    total_chunks = db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    if total_chunks == 0:
        return {}

    rows = db.execute("""
        SELECT term, COUNT(DISTINCT chunk_id) as df
        FROM terms GROUP BY term
    """).fetchall()

    idf = {}
    for row in rows:
        idf[row["term"]] = math.log((total_chunks + 1) / (row["df"] + 1)) + 1
    return idf


# ── Document Management ──

def add_document(source: str, content: str, title: str = "", chunk_size: int = 500) -> dict:
    """Add a document: chunk it, compute TF, store in DB."""
    doc_id = hashlib.md5(f"{source}:{content[:100]}".encode()).hexdigest()[:12]
    now = datetime.now().isoformat()

    with LOCK:
        db = _get_db()

        # Check if already exists
        existing = db.execute("SELECT id FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if existing:
            db.execute("DELETE FROM terms WHERE chunk_id IN (SELECT id FROM chunks WHERE doc_id = ?)", (doc_id,))
            db.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
            db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

        # Chunk
        chunks = _chunk_text(content, chunk_size=chunk_size)
        db.execute(
            "INSERT INTO documents (id, source, title, content, chunk_count, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (doc_id, source, title or source, content[:1000], len(chunks), now)
        )

        for i, chunk_text in enumerate(chunks):
            chunk_id = f"{doc_id}_{i}"
            tokens = _tokenize(chunk_text)
            tf = _compute_tf(tokens)

            db.execute(
                "INSERT INTO chunks (id, doc_id, content, chunk_index, word_count) VALUES (?, ?, ?, ?, ?)",
                (chunk_id, doc_id, chunk_text, i, len(tokens))
            )

            for term, freq in tf.items():
                db.execute(
                    "INSERT OR REPLACE INTO terms (term, chunk_id, tf) VALUES (?, ?, ?)",
                    (term, chunk_id, freq)
                )

        db.commit()
        db.close()

    return {"id": doc_id, "source": source, "chunks": len(chunks)}


def remove_document(doc_id: str) -> bool:
    with LOCK:
        db = _get_db()
        row = db.execute("SELECT id FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if not row:
            db.close()
            return False
        db.execute("DELETE FROM terms WHERE chunk_id IN (SELECT id FROM chunks WHERE doc_id = ?)", (doc_id,))
        db.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
        db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        db.commit()
        db.close()
    return True


def list_documents() -> list:
    db = _get_db()
    rows = db.execute("SELECT id, source, title, chunk_count, created_at FROM documents ORDER BY created_at DESC").fetchall()
    db.close()
    return [dict(r) for r in rows]


# ── Search ──

def search(query: str, top_k: int = 5) -> list:
    """TF-IDF search. Returns top_k chunks with scores."""
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    with LOCK:
        db = _get_db()
        idf = _compute_idf(db)

        # Find candidate chunks (chunks containing any query term)
        placeholders = ",".join(["?"] * len(query_tokens))
        rows = db.execute(f"""
            SELECT DISTINCT c.id, c.content, c.doc_id, d.source, d.title
            FROM terms t
            JOIN chunks c ON c.id = t.chunk_id
            JOIN documents d ON d.id = c.doc_id
            WHERE t.term IN ({placeholders})
        """, query_tokens).fetchall()

        if not rows:
            db.close()
            return []

        # Score each chunk
        scores = []
        for row in rows:
            chunk_id = row["id"]
            # Get TF for all terms in this chunk
            tf_rows = db.execute("SELECT term, tf FROM terms WHERE chunk_id = ?", (chunk_id,)).fetchall()
            tf = {r["term"]: r["tf"] for r in tf_rows}

            # Compute TF-IDF score
            score = 0
            for qt in query_tokens:
                if qt in tf and qt in idf:
                    score += tf[qt] * idf[qt]

            scores.append({
                "chunk_id": chunk_id,
                "content": row["content"],
                "doc_id": row["doc_id"],
                "source": row["source"],
                "title": row["title"],
                "score": score,
            })

        db.close()

    # Sort by score
    scores.sort(key=lambda x: x["score"], reverse=True)
    return scores[:top_k]


def search_and_generate(query: str, llm_client, model: str, top_k: int = 3) -> dict:
    """RAG: search for context, then generate answer using LLM."""
    results = search(query, top_k=top_k)

    if not results:
        return {
            "answer": "No relevant documents found.",
            "sources": [],
            "query": query,
        }

    # Build context from top chunks
    context_parts = []
    sources = []
    for r in results:
        context_parts.append(f"[{r['source']}]: {r['content']}")
        sources.append({"source": r["source"], "title": r["title"], "score": round(r["score"], 4)})

    context = "\n\n".join(context_parts)

    prompt = f"""Based on the following context, answer the question concisely.

Context:
{context}

Question: {query}

Answer (cite sources):"""

    try:
        resp = llm_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.3,
        )
        answer = resp.choices[0].message.content.strip()
    except Exception as e:
        answer = f"Error generating answer: {e}"

    return {
        "answer": answer,
        "sources": sources,
        "query": query,
        "chunks_used": len(results),
    }


# ── Document Loaders ──

def load_file(path: str, title: str = "") -> dict:
    """Load a file into the RAG index."""
    p = Path(path)
    if not p.exists():
        return {"error": f"File not found: {path}"}

    content = p.read_text(encoding="utf-8", errors="replace")
    return add_document(source=str(p), content=content, title=title or p.name)


def load_directory(dir_path: str, extensions: list = None, recursive: bool = True) -> dict:
    """Load all files from a directory."""
    if extensions is None:
        extensions = [".txt", ".md", ".py", ".js", ".html", ".css", ".json", ".yaml", ".yml", ".csv"]

    p = Path(dir_path)
    if not p.exists():
        return {"error": f"Directory not found: {dir_path}"}

    loaded = 0
    errors = []

    pattern = "**/*" if recursive else "*"
    for f in p.glob(pattern):
        if f.is_file() and f.suffix.lower() in extensions:
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                add_document(source=str(f), content=content, title=f.name)
                loaded += 1
            except Exception as e:
                errors.append(f"{f.name}: {e}")

    return {"loaded": loaded, "errors": errors}
