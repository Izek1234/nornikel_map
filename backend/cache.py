"""CAG layer: cached answers (normalized question -> answer) stored in Neo4j.
Chunk-level extraction dedup lives in graph_db.chunk_exists (SHA-256 hashes)."""

import hashlib
import json
import re
import time

import graph_db

CACHE_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days


def normalize_question(q: str) -> str:
    q = q.strip().lower()
    q = re.sub(r"[^\wа-яё%°/.,\- ]", " ", q)
    q = re.sub(r"\s+", " ", q)
    return q


def question_hash(q: str) -> str:
    return hashlib.sha256(normalize_question(q).encode("utf-8")).hexdigest()


def get_cached_answer(question: str) -> dict | None:
    qhash = question_hash(question)
    rows = graph_db.run(
        """
        MATCH (a:CachedAnswer {qhash: $h})
        WHERE a.created_at > $min_ts
        RETURN a.answer AS answer, a.sources AS sources, a.facts_json AS facts_json,
               a.created_at AS created_at
        LIMIT 1
        """,
        h=qhash, min_ts=time.time() - CACHE_TTL_SECONDS,
    )
    if not rows:
        return None
    row = rows[0]
    try:
        facts = json.loads(row.get("facts_json") or "[]")
    except json.JSONDecodeError:
        facts = []
    return {"answer": row["answer"], "sources": row.get("sources") or [], "facts": facts}


def save_answer(question: str, answer: str, sources: list[str], facts: list[dict]):
    graph_db.run(
        """
        MERGE (a:CachedAnswer {qhash: $h})
        SET a.question = $q, a.answer = $answer, a.sources = $sources,
            a.facts_json = $facts_json, a.created_at = $ts
        """,
        h=question_hash(question), q=normalize_question(question),
        answer=answer, sources=sources,
        facts_json=json.dumps(facts, ensure_ascii=False)[:30000], ts=time.time(),
    )


def invalidate_all():
    """Called after new document ingestion so stale answers don't survive."""
    graph_db.run("MATCH (a:CachedAnswer) DETACH DELETE a")
