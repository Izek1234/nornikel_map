"""Legacy GraphRAG helper built on top of the active LLM client."""

import re

import cache
import llm_client as llm
import graph_db
import postprocess

STOPWORDS = {
    "и", "в", "на", "с", "по", "для", "из", "как", "что", "это", "при", "или",
    "не", "к", "о", "об", "от", "до", "за", "же", "ли", "бы", "то", "у", "а",
    "какой", "какая", "какие", "каких", "чем", "где", "когда", "почему", "сколько",
    "можно", "нужно", "есть", "будет", "был", "была", "были",
    "the", "a", "an", "is", "are", "what", "which", "how", "of", "in", "on", "for",
    "and", "or", "to", "with", "at", "by",
}


def _extract_terms(question: str) -> list[str]:
    words = re.findall(r"[\wа-яё\-]{3,}", question.lower())
    terms = []
    for w in words:
        if w in STOPWORDS:
            continue
        w = postprocess.SYNONYMS.get(w, w)
        if w not in terms:
            terms.append(w)
    return terms[:10]


def _lucene_query(terms: list[str]) -> str:
    parts = []
    for t in terms:
        safe = graph_db._lucene_escape(t)
        parts.append(f"{safe}~1")
    return " OR ".join(parts)


def _retrieve(question: str, region: str | None = None) -> dict:
    terms = _extract_terms(question)
    if not terms:
        return {"entities": [], "facts": [], "chunks": [], "sources": []}
    q = _lucene_query(terms)

    # 1) seed entities via full-text
    seeds = graph_db.run(
        """
        CALL db.index.fulltext.queryNodes('entity_search', $q) YIELD node, score
        RETURN node.key AS key, node.name AS name, node.type AS type,
               node.description AS description, score
        ORDER BY score DESC LIMIT 8
        """,
        q=q,
    )
    seed_keys = [s["key"] for s in seeds]

    # 2) expand 2 hops + collect facts of seeds and neighbors
    facts, neighbors = [], []
    if seed_keys:
        rows = graph_db.run(
            """
            MATCH (e:Entity) WHERE e.key IN $keys
            OPTIONAL MATCH (e)-[r1:RELATED]-(n1:Entity)
            OPTIONAL MATCH (n1)-[r2:RELATED]-(n2:Entity)
            WITH e, collect(DISTINCT n1)[..10] AS h1, collect(DISTINCT n2)[..10] AS h2
            WITH collect(e) + reduce(a=[], x IN collect(h1) | a + x) + reduce(a=[], x IN collect(h2) | a + x) AS all_nodes
            UNWIND all_nodes AS node
            WITH DISTINCT node LIMIT 40
            OPTIONAL MATCH (node)-[:HAS_FACT]->(f:Fact)
            RETURN node.name AS name, node.type AS type, node.description AS description,
                   collect({predicate: f.predicate, object: f.object,
                            value_min: f.value_min, value_max: f.value_max,
                            unit_normalized: f.unit_normalized, geography: f.geography,
                            confidence: f.confidence, source_doc: f.source_doc,
                            quote: f.quote})[..8] AS facts
            """,
            keys=seed_keys,
        )
        for row in rows:
            neighbors.append({"name": row["name"], "type": row["type"], "description": row["description"]})
            for f in row["facts"]:
                if f and f.get("predicate"):
                    # Region filtering
                    if region and region.lower() != "all" and f.get("geography") and f["geography"] != "unknown":
                        if region.lower() not in f["geography"].lower() and f["geography"].lower() not in region.lower():
                            continue
                    facts.append({**f, "subject": row["name"]})

    # 3) top raw chunks for extra grounding
    chunks = graph_db.run(
        """
        CALL db.index.fulltext.queryNodes('chunk_search', $q) YIELD node, score
        OPTIONAL MATCH (node)-[:PART_OF]->(d:Document)
        RETURN node.text AS text, d.name AS doc, score
        ORDER BY score DESC LIMIT 4
        """,
        q=q,
    )

    doc_ids = {f.get("source_doc") for f in facts if f.get("source_doc")}
    doc_names = set(c["doc"] for c in chunks if c.get("doc"))
    if doc_ids:
        rows = graph_db.run(
            "MATCH (d:Document) WHERE d.id IN $ids RETURN d.name AS name", ids=list(doc_ids)
        )
        doc_names.update(r["name"] for r in rows)

    return {"entities": neighbors, "facts": facts[:30], "chunks": chunks, "sources": sorted(doc_names)}


def _build_context(retrieved: dict) -> str:
    parts = []
    if retrieved["entities"]:
        ents = [f"- {e['name']} ({e['type']}): {e.get('description') or ''}".strip()
                for e in retrieved["entities"][:20]]
        parts.append("СУЩНОСТИ:\n" + "\n".join(ents))
    if retrieved["facts"]:
        lines = []
        for f in retrieved["facts"]:
            val = postprocess.format_fact_value(f)
            geo = f.get("geography", "unknown")
            conf = f.get("confidence", 0.5)
            lines.append(f"- {f['subject']} | {f['predicate']} = {val} [гео: {geo}, conf: {conf}]")
        parts.append("ФАКТЫ (числа и единицы нормализованы):\n" + "\n".join(lines))
    if retrieved["chunks"]:
        frs = [f"[{c.get('doc') or 'документ'}] {c['text'][:800]}" for c in retrieved["chunks"]]
        parts.append("ФРАГМЕНТЫ ДОКУМЕНТОВ:\n" + "\n\n".join(frs))
    if retrieved["sources"]:
        parts.append("ДОСТУПНЫЕ ИСТОЧНИКИ: " + ", ".join(retrieved["sources"]))
    return "\n\n".join(parts) if parts else "Граф знаний пуст."


def ask(question: str, use_cache: bool = True, region: str | None = None, history: list[dict] | None = None) -> dict:
    # CAG: answer cache
    if use_cache and not history:
        cached = cache.get_cached_answer(question)
        if cached:
            return {**cached, "cached": True}

    retrieved = _retrieve(question, region)
    context = _build_context(retrieved)
    answer = llm.answer_question(question, context, history=history)

    facts_out = [
        {
            "subject": f["subject"],
            "predicate": f["predicate"],
            "value": postprocess.format_fact_value(f),
            "geography": f.get("geography", "unknown"),
            "confidence": f.get("confidence", 0.5),
        }
        for f in retrieved["facts"][:12]
    ]
    result = {
        "answer": answer,
        "sources": retrieved["sources"],
        "facts": facts_out,
        "cached": False,
    }
    if not history:
        cache.save_answer(question, answer, retrieved["sources"], facts_out)
    return result
