"""Neo4j driver, retrieval helpers, sync state, and GraphRAG primitives."""

import json
import re
import time
import threading

from neo4j import GraphDatabase, exceptions as neo4j_exceptions

from config import settings
import logging

logger = logging.getLogger(__name__)

import experiment_store

_driver = None
_write_lock = threading.Lock()

ENTITY_TYPES = [
    "Material",
    "Process",
    "Equipment",
    "Property",
    "Experiment",
    "Publication",
    "Expert",
    "Facility",
]


def get_driver():
    global _driver
    if _driver is None:
        uri = settings.neo4j_uri
        user = settings.neo4j_user
        pwd = settings.neo4j_password
        if not uri or not pwd:
            logger.error("NEO4J_URI or NEO4J_PASSWORD missing!")
            raise RuntimeError("NEO4J_URI / NEO4J_PASSWORD are not set")
        _driver = GraphDatabase.driver(uri, auth=(user, pwd))
    return _driver


def run(query: str, **params):
    with get_driver().session() as session:
        result = session.run(query, **params)
        return [r.data() for r in result]


def _is_constraint_error(exc: Exception) -> bool:
    """Detect constraint violations across all Neo4j exception types."""
    if isinstance(exc, neo4j_exceptions.ConstraintError):
        return True
    # ClientError with ConstraintValidationFailed code
    code = getattr(exc, "code", "") or ""
    if "ConstraintValidationFailed" in code:
        return True
    # Fallback: check message
    msg = str(exc)
    if "already exists with label" in msg or "ConstraintValidationFailed" in msg:
        return True
    return False


def run_with_retry(query: str, max_retries: int = 5, **params):
    """Run a write query with retry on constraint violations (race conditions)."""
    for attempt in range(max_retries):
        try:
            return run(query, **params)
        except Exception as exc:
            if _is_constraint_error(exc):
                if attempt < max_retries - 1:
                    time.sleep(0.1 * (2 ** attempt))  # exponential backoff
                else:
                    raise
            else:
                raise


def _execute_write_with_retry(tx_fn, max_retries: int = 5):
    """Execute a write transaction function via session.execute_write() with retry on constraint violations."""
    for attempt in range(max_retries):
        try:
            with get_driver().session() as session:
                session.execute_write(tx_fn)
            return
        except Exception as exc:
            if _is_constraint_error(exc):
                if attempt < max_retries - 1:
                    time.sleep(0.1 * (2 ** attempt))  # exponential backoff
                else:
                    # Constraint violation on last attempt — node already exists, safe to ignore
                    return
            else:
                raise


def init_schema():
    """Constraints + full-text indexes. Idempotent."""
    statements = [
        "CREATE CONSTRAINT entity_key IF NOT EXISTS FOR (e:Entity) REQUIRE e.key IS UNIQUE",
        "CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
        "CREATE CONSTRAINT chunk_hash IF NOT EXISTS FOR (c:Chunk) REQUIRE c.hash IS UNIQUE",
        "CREATE CONSTRAINT cached_q IF NOT EXISTS FOR (a:CachedAnswer) REQUIRE a.qhash IS UNIQUE",
        "CREATE CONSTRAINT chat_message_id IF NOT EXISTS FOR (m:ChatMessage) REQUIRE m.id IS UNIQUE",
        "CREATE CONSTRAINT sync_state_name IF NOT EXISTS FOR (s:SyncState) REQUIRE s.name IS UNIQUE",
        "CREATE FULLTEXT INDEX entity_search IF NOT EXISTS FOR (e:Entity) ON EACH [e.name, e.description, e.aliases_text]",
        "CREATE FULLTEXT INDEX chunk_search IF NOT EXISTS FOR (c:Chunk) ON EACH [c.text]",
        "CREATE FULLTEXT INDEX fact_search IF NOT EXISTS FOR (f:Fact) ON EACH [f.subject, f.predicate, f.object, f.quote]",
        "CREATE INDEX entity_domain IF NOT EXISTS FOR (e:Entity) ON (e.domains)",
        "CREATE INDEX doc_domain IF NOT EXISTS FOR (d:Document) ON (d.domains)",
    ]
    for stmt in statements:
        run(stmt)
    repair_graph()


def repair_graph():
    """Remove malformed graph fragments and stale ontology violations."""
    allowed_types = ENTITY_TYPES
    allowed_relations = [
        "USES_MATERIAL",
        "USES_PROCESS",
        "USES_EQUIPMENT",
        "PERFORMED_AT",
        "VALIDATED_BY",
        "DESCRIBES",
        "PRODUCES_OUTPUT",
        "CONTRADICTS",
        "OPERATES_AT_CONDITION",
    ]
    run(
        """
        MATCH (e:Entity)
        WHERE e.key IS NULL OR e.name IS NULL OR trim(e.name) = ''
           OR e.type IS NULL OR NOT e.type IN $allowed_types
        DETACH DELETE e
        """,
        allowed_types=allowed_types,
    )
    run(
        """
        MATCH (:Entity)-[r:RELATED]->(:Entity)
        WHERE r.type IS NULL OR NOT r.type IN $allowed_relations
        DELETE r
        """,
        allowed_relations=allowed_relations,
    )


# ---------- Documents & chunks ----------

def upsert_document(doc_id: str, name: str, size: int, mime: str, source_meta: dict | None = None):
    import ontology
    domain = ontology.classify_domain(name)
    source_meta = source_meta or {}
    run(
        """
        MERGE (d:Document {id: $id})
        SET d.name = $name, d.size = $size, d.mime = $mime,
            d.status = 'processing', d.uploaded_at = $ts,
            d.chunks_total = 0, d.chunks_done = 0, d.error = null,
            d.source_provider = $source_provider,
            d.source_external_id = $source_external_id,
            d.source_path = $source_path,
            d.source_url = $source_url,
            d.source_etag = $source_etag,
            d.source_modified = $source_modified,
            d.sync_status = $sync_status,
            d.last_synced_at = $last_synced_at,
            d.uploaded_by = $uploaded_by,
            d.domain = $domain
        """,
        id=doc_id,
        name=name,
        size=size,
        mime=mime,
        ts=time.time(),
        source_provider=source_meta.get("source_provider"),
        source_external_id=source_meta.get("source_external_id"),
        source_path=source_meta.get("source_path"),
        source_url=source_meta.get("source_url"),
        source_etag=source_meta.get("source_etag"),
        source_modified=source_meta.get("source_modified"),
        sync_status=source_meta.get("sync_status"),
        last_synced_at=source_meta.get("last_synced_at"),
        uploaded_by=source_meta.get("uploaded_by", "system"),
        domain=domain,
    )


def set_document_status(doc_id: str, status: str, error: str | None = None):
    run(
        """
        MATCH (d:Document {id: $id})
        SET d.status = $status, d.error = $error,
            d.sync_status = CASE
                WHEN d.source_provider IS NULL THEN d.sync_status
                WHEN $status = 'completed' THEN 'completed'
                WHEN $status = 'failed' THEN 'failed'
                ELSE d.sync_status
            END,
            d.last_synced_at = CASE
                WHEN d.source_provider IS NULL THEN d.last_synced_at
                ELSE $ts
            END
        """,
        id=doc_id, status=status, error=error,
        ts=time.time(),
    )


def set_document_progress(doc_id: str, total: int, done: int):
    run(
        "MATCH (d:Document {id: $id}) SET d.chunks_total = $total, d.chunks_done = $done",
        id=doc_id, total=total, done=done,
    )


def chunk_exists(chunk_hash: str) -> bool:
    rows = run(
        "MATCH (c:Chunk {hash: $h}) WHERE c.processed = true RETURN c.hash AS h LIMIT 1",
        h=chunk_hash,
    )
    return len(rows) > 0


def upsert_chunk(chunk_hash: str, text: str, index: int, doc_id: str):
    run(
        """
        MERGE (c:Chunk {hash: $h})
        ON CREATE SET c.text = $text, c.processed = false
        SET c.index = $index
        WITH c
        MATCH (d:Document {id: $doc_id})
        MERGE (c)-[:PART_OF]->(d)
        """,
        h=chunk_hash, text=text[:8000], index=index, doc_id=doc_id,
    )


def mark_chunk_processed(chunk_hash: str):
    run("MATCH (c:Chunk {hash: $h}) SET c.processed = true", h=chunk_hash)


def get_document_by_source(source_provider: str, source_external_id: str):
    rows = run(
        """
        MATCH (d:Document)
        WHERE d.source_provider = $source_provider AND d.source_external_id = $source_external_id
        RETURN d.id AS id, d.name AS name, d.status AS status,
               d.source_etag AS source_etag,
               d.source_modified AS source_modified,
               d.uploaded_at AS uploaded_at
        ORDER BY d.uploaded_at DESC
        LIMIT 1
        """,
        source_provider=source_provider,
        source_external_id=source_external_id,
    )
    return rows[0] if rows else None


# ---------- Entities, relations, facts ----------

def upsert_entity(key: str, name: str, etype: str, description: str, aliases: list[str], chunk_hash: str, domains: list[str] | None = None):
    if etype not in ENTITY_TYPES:
        etype = "Property"

    domain_list = domains or []

    def _tx(tx):
        tx.run(
            """
            MERGE (e:Entity {key: $key})
            ON CREATE SET e.name = $name, e.type = $etype, e.description = $desc,
                          e.aliases = $aliases, e.domains = $domains, e.created_at = $ts
            ON MATCH SET  e.description = CASE WHEN size(coalesce(e.description,'')) < size($desc)
                                               THEN $desc ELSE e.description END,
                          e.aliases = reduce(out = [], x IN coalesce(e.aliases, []) + $aliases |
                              CASE WHEN x IN out THEN out ELSE out + x END),
                          e.domains = reduce(out = [], x IN coalesce(e.domains, []) + $domains |
                              CASE WHEN x IN out THEN out ELSE out + x END)
            SET e.aliases_text = reduce(s = '', a IN e.aliases | s + ' ' + a)
            WITH e
            MATCH (c:Chunk {hash: $chunk})
            MERGE (e)-[:MENTIONED_IN]->(c)
            """,
            key=key, name=name, etype=etype, desc=description or "",
            aliases=aliases or [], domains=domain_list, ts=time.time(), chunk=chunk_hash,
        )

    _execute_write_with_retry(_tx)


def create_experiment(key: str, name: str, properties: dict | None, source: dict | None, description: str = ""):
    query, params = experiment_store.build_experiment_cypher(
        key=key,
        name=name,
        description=description,
        properties=properties,
        source=source,
        confidence=0.7,
    )
    exp_props = {
        "temperature": params["temperature"],
        "pressure": params["pressure"],
        "time": params["time"],
        "atmosphere": params["atmosphere"],
        "cooling_rate": params["cooling_rate"],
        "heating_rate": params["heating_rate"],
        "gas": params["gas"],
        "sample_mass": params["sample_mass"],
        "ph": params["ph"],
        "voltage": params["voltage"],
        "current_density": params["current_density"],
        "flow_rate": params["flow_rate"],
        "concentration": params["concentration"],
        "source_document_id": params["source_document_id"],
        "source_page": params["source_page"],
        "source_chunk_id": params["source_chunk_id"],
        "source_original_text": params["source_original_text"],
        "confidence": params["confidence"],
    }

    def _tx(tx):
        tx.run(
            """
            MERGE (e:Entity {key: $key})
            ON CREATE SET e.name = $name, e.type = 'Experiment', e.description = $description,
                          e.created_at = $created_at
            ON MATCH SET e.type = 'Experiment',
                         e.description = CASE WHEN size(coalesce(e.description,'')) < size($description)
                                              THEN $description ELSE e.description END
            SET e:Experiment, e += $props
            WITH e
            OPTIONAL MATCH (c:Chunk {hash: $chunk_hash})
            WITH e, c WHERE c IS NOT NULL
            MERGE (e)-[:MENTIONED_IN]->(c)
            """,
            key=key,
            name=name,
            description=description or "",
            created_at=params["created_at"],
            props=exp_props,
            chunk_hash=params["source_chunk_id"],
        )

    _execute_write_with_retry(_tx)


def upsert_relation(source_key: str, target_key: str, rel_type: str, chunk_hash: str):
    def _tx(tx):
        tx.run(
            """
            MATCH (a:Entity {key: $src}), (b:Entity {key: $dst})
            MERGE (a)-[r:RELATED {type: $type}]->(b)
            ON CREATE SET r.count = 1, r.source_chunk = $chunk
            ON MATCH SET r.count = r.count + 1
            """,
            src=source_key, dst=target_key, type=rel_type, chunk=chunk_hash,
        )

    _execute_write_with_retry(_tx)


def create_fact(fact: dict, subject_key: str, chunk_hash: str, doc_id: str):
    import hashlib
    raw_key = f"{subject_key}_{fact.get('predicate', '')}_{fact.get('object', '')}_{chunk_hash}"
    fact_key = hashlib.sha256(raw_key.encode()).hexdigest()[:16]
    run(
        """
        MATCH (s:Entity {key: $skey})
        CREATE (f:Fact {
            key: $fkey,
            subject: $subject, predicate: $predicate, object: $object,
            value_min: $vmin, value_max: $vmax,
            unit: $unit, unit_normalized: $unit_norm,
            geography: $geo, time: $time, confidence: $conf,
            quote: $quote, source_doc: $doc, source_chunk: $chunk,
            extracted_at: $ts
        })
        CREATE (s)-[:HAS_FACT]->(f)
        WITH f
        MATCH (c:Chunk {hash: $chunk})
        CREATE (f)-[:DESCRIBED_IN]->(c)
        """,
        skey=subject_key,
        fkey=fact_key,
        subject=fact["subject"], predicate=fact["predicate"], object=fact["object"],
        vmin=fact.get("value_min"), vmax=fact.get("value_max"),
        unit=fact.get("unit"), unit_norm=fact.get("unit_normalized"),
        geo=fact.get("geography", "unknown"), time=fact.get("time"), conf=fact.get("confidence", 0.5),
        quote=fact.get("quote", ""), doc=doc_id, chunk=chunk_hash, ts=time.time(),
    )


# ---------- Read queries ----------

def list_documents():
    return run(
        """
        MATCH (d:Document)
        OPTIONAL MATCH (c:Chunk)-[:PART_OF]->(d)
        RETURN d.id AS id, d.name AS name, d.size AS size, d.status AS status,
               d.error AS error, d.uploaded_at AS uploaded_at,
               d.chunks_total AS chunks_total, d.chunks_done AS chunks_done,
               d.source_provider AS source_provider,
               d.source_path AS source_path,
               d.source_url AS source_url,
               d.sync_status AS sync_status,
               d.last_synced_at AS last_synced_at,
               d.uploaded_by AS uploaded_by,
               count(c) AS chunks
        ORDER BY d.uploaded_at DESC
        """
    )


def get_document_details(doc_id: str) -> dict | None:
    """Get full document info with all related entities and facts."""
    doc_rows = run(
        """
        MATCH (d:Document {id: $id})
        OPTIONAL MATCH (c:Chunk)-[:PART_OF]->(d)
        RETURN d.id AS id, d.name AS name, d.size AS size, d.status AS status,
               d.error AS error, d.uploaded_at AS uploaded_at,
               d.chunks_total AS chunks_total, d.chunks_done AS chunks_done,
               d.mime AS mime,
               d.source_provider AS source_provider,
               d.source_path AS source_path,
               d.source_url AS source_url,
               d.source_external_id AS source_external_id,
               d.sync_status AS sync_status,
               d.last_synced_at AS last_synced_at,
               d.uploaded_by AS uploaded_by,
               collect(DISTINCT c.hash) AS chunk_hashes,
               count(c) AS chunks
        LIMIT 1
        """,
        id=doc_id,
    )
    if not doc_rows:
        return None

    doc = doc_rows[0]
    chunk_hashes = doc.get("chunk_hashes") or []

    if not chunk_hashes:
        return {**doc, "entities": [], "facts": []}

    entities = run(
        """
        MATCH (e:Entity)-[:MENTIONED_IN]->(c:Chunk)
        WHERE c.hash IN $hashes
        RETURN DISTINCT e.key AS key, e.name AS name, e.type AS type,
               e.description AS description
        ORDER BY e.name
        """,
        hashes=chunk_hashes,
    )

    entity_keys = [e["key"] for e in entities if e.get("key")]
    facts = []
    if entity_keys:
        fact_rows = run(
            """
            MATCH (e:Entity)-[:HAS_FACT]->(f:Fact)
            WHERE e.key IN $keys
            RETURN e.name AS subject, f.predicate AS predicate,
                   f.object AS object, f.value_min AS value_min,
                   f.value_max AS value_max, f.unit_normalized AS unit,
                   f.geography AS geography, f.confidence AS confidence,
                   f.quote AS quote
            ORDER BY e.name, f.predicate
            """,
            keys=entity_keys,
        )
        facts = [r for r in fact_rows if r.get("predicate")]

    return {
        **doc,
        "chunk_hashes": chunk_hashes,
        "entities": entities,
        "facts": facts,
    }


def get_document_content(name: str):
    rows = run(
        """
        MATCH (d:Document {name: $name})<-[:PART_OF]-(c:Chunk)
        RETURN c.text AS text, c.index AS index
        ORDER BY c.index ASC
        """,
        name=name,
    )
    if not rows:
        return None
    return "\n\n".join(row["text"] for row in rows if row.get("text"))


def get_stats():
    rows = run(
        """
        OPTIONAL MATCH (e:Entity) WITH count(e) AS entities
        OPTIONAL MATCH (f:Fact) WITH entities, count(f) AS facts
        OPTIONAL MATCH (d:Document) WITH entities, facts, count(d) AS documents
        OPTIONAL MATCH (c:Chunk) WITH entities, facts, documents, count(c) AS chunks
        OPTIONAL MATCH ()-[r:RELATED]->()
        RETURN entities, facts, documents, chunks, count(r) AS relations
        """
    )
    return rows[0] if rows else {}


def get_stats_detailed():
    stats = get_stats()
    type_rows = run(
        """
        MATCH (e:Entity)
        RETURN e.type AS type, count(*) AS count
        """
    )
    by_type = {row["type"]: row["count"] for row in type_rows if row.get("type")}
    stats.update({
        "experiments": by_type.get("Experiment", 0),
        "materials": by_type.get("Material", 0),
        "publications": by_type.get("Publication", 0),
        "experts": by_type.get("Expert", 0),
        "facilities": by_type.get("Facility", 0),
    })

    # Domain stats — real counts from graph
    domains = {
        "hydrometallurgy": ["гидрометалл", "hydrometallurg", "выщелач", "раствор"],
        "pyrometallurgy": ["пирометалл", "pyrometallurg", "плавк", "шлак", "концентрат"],
        "ecology": ["эколог", "ecolog", "выброс", "загрязн", "мониторинг"],
        "waste": ["отход", "waste", "переработ", "хвост", "шлам", "гипс"],
    }

    domain_stats = {}
    for dom, keywords in domains.items():
        # Entities whose name OR description matches
        e_conditions = " OR ".join(
            f"toLower(e.name) CONTAINS '{kw}' OR toLower(coalesce(e.description,'')) CONTAINS '{kw}'"
            for kw in keywords
        )
        # Total domain entities
        rows_e_total = run(f"MATCH (e:Entity) WHERE {e_conditions} RETURN count(e) AS cnt")
        cnt_e_total = rows_e_total[0]["cnt"] if rows_e_total else 0

        # Domain entities that have at least one Fact
        rows_e_with_facts = run(
            f"MATCH (e:Entity) WHERE {e_conditions} "
            f"AND EXISTS {{ MATCH (e)-[:HAS_FACT]->(:Fact) }} "
            f"RETURN count(e) AS cnt"
        )
        cnt_e_with_facts = rows_e_with_facts[0]["cnt"] if rows_e_with_facts else 0

        # Documents whose chunks mention domain keywords
        c_conditions = " OR ".join(
            f"toLower(coalesce(c.text,'')) CONTAINS '{kw}' OR toLower(coalesce(d.name,'')) CONTAINS '{kw}'"
            for kw in keywords
        )
        rows_d = run(
            f"MATCH (c:Chunk)-[:PART_OF]->(d:Document) "
            f"WHERE {c_conditions} "
            f"RETURN count(DISTINCT d) AS cnt"
        )
        cnt_d = rows_d[0]["cnt"] if rows_d else 0

        # Real coverage = % of domain entities that have at least one fact
        if cnt_e_total > 0:
            coverage_pct = round((cnt_e_with_facts / cnt_e_total) * 100)
        else:
            coverage_pct = 0

        domain_stats[dom] = {
            "entities": cnt_e_total,
            "entities_with_facts": cnt_e_with_facts,
            "documents": cnt_d,
            "coverage": coverage_pct,
        }

    # Manual corrections count
    cnt_corr = 0
    try:
        corr_rows = run("MATCH (fv:FactVersion {change_type: 'corrected'}) RETURN count(fv) AS count")
        cnt_corr += corr_rows[0]["count"] if corr_rows else 0
    except Exception:
        pass
    try:
        ec_rows = run("MATCH (ec:EntityChange {change_type: 'corrected'}) RETURN count(ec) AS count")
        cnt_corr += ec_rows[0]["count"] if ec_rows else 0
    except Exception:
        pass

    stats.update({
        "domains": domain_stats,
        "activity": {
            "active_experts": max(3, stats.get("experts", 0)),
            "manual_corrections": cnt_corr,
        }
    })
    return stats


def _extract_years_from_graph_fact(fact: dict) -> list[int]:
    text = " ".join(
        str(fact.get(field, "") or "")
        for field in ("predicate", "object", "quote", "source_doc", "time")
    )
    return [int(match) for match in re.findall(r"\b(?:19|20)\d{2}\b", text)]


def _graph_fact_matches_filters(
    fact: dict,
    region: str | None = None,
    min_confidence: float | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    month_from: int | None = None,
    month_to: int | None = None,
) -> bool:
    if region and region.lower() not in ("all", "any", ""):
        geography = (fact.get("geography") or "").lower().strip()
        normalized_region = region.lower()
        if normalized_region == "domestic":
            normalized_region = "ru"
        elif normalized_region in ("foreign", "world_excl_ru"):
            normalized_region = "world"
        # When filtering by region, facts with unknown geography do NOT match
        if geography in ("unknown", "none", ""):
            return False
        if geography != normalized_region:
            return False

    if min_confidence is not None and (fact.get("confidence") or 0.0) < min_confidence:
        return False

    if year_from is not None or year_to is not None:
        years = _extract_years_from_graph_fact(fact)
        if years:
            if year_from is not None and all(year < year_from for year in years):
                return False
            if year_to is not None and all(year > year_to for year in years):
                return False

    if month_from is not None or month_to is not None:
        if fact.get("unit") == "month":
            values = [v for v in (fact.get("value_min"), fact.get("value_max")) if isinstance(v, (int, float))]
            if values:
                low = min(values)
                high = max(values)
                if month_from is not None and high < month_from:
                    return False
                if month_to is not None and low > month_to:
                    return False

    return True


def get_subgraph(
    search: str | None,
    etypes: list[str] | None,
    limit: int = 150,
    region: str | None = None,
    min_confidence: float | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    month_from: int | None = None,
    month_to: int | None = None,
    domain: str | None = None,
):
    cond_sql = "($etypes IS NULL OR node.type IN $etypes)"
    domain_filter = ""
    if domain:
        domain_filter = f"AND ($domain IS NULL OR $domain IN node.domains)"

    if search:
        safe = _lucene_escape(search)
        query = f"""
            CALL db.index.fulltext.queryNodes('entity_search', $q) YIELD node, score
            WHERE {cond_sql} {domain_filter}
            WITH node LIMIT $lim
            OPTIONAL MATCH (node)-[r:RELATED]-(m:Entity)
            RETURN collect(DISTINCT {{key: node.key, name: node.name, type: node.type, description: node.description, domains: node.domains}}) +
                   collect(DISTINCT {{key: m.key, name: m.name, type: m.type, description: m.description, domains: m.domains}}) AS nodes,
                   collect(DISTINCT {{source: startNode(r).key, target: endNode(r).key, type: r.type}}) AS links
        """
        rows = run(query, q=safe + "~", etypes=etypes, lim=limit, domain=domain)
    else:
        query = f"""
            MATCH (node:Entity)
            WHERE {cond_sql} {domain_filter}
            WITH node LIMIT $lim
            OPTIONAL MATCH (node)-[r:RELATED]-(m:Entity)
            RETURN collect(DISTINCT {{key: node.key, name: node.name, type: node.type, description: node.description, domains: node.domains}}) +
                   collect(DISTINCT {{key: m.key, name: m.name, type: m.type, description: m.description, domains: m.domains}}) AS nodes,
                   collect(DISTINCT {{source: startNode(r).key, target: endNode(r).key, type: r.type}}) AS links
        """
        rows = run(query, etypes=etypes, lim=limit, domain=domain)
    raw = rows[0]
    seen, nodes = set(), []
    for n in raw["nodes"]:
        if n and n.get("key") and n["key"] not in seen:
            seen.add(n["key"])
            nodes.append(n)
    links = [l for l in raw["links"] if l and l.get("source") and l.get("target")]

    if any(v is not None for v in (region, min_confidence, year_from, year_to, month_from, month_to)) and nodes:
        year_start = min(year_from, year_to) if year_from is not None and year_to is not None else year_from
        year_end = max(year_from, year_to) if year_from is not None and year_to is not None else year_to
        month_start = min(month_from, month_to) if month_from is not None and month_to is not None else month_from
        month_end = max(month_from, month_to) if month_from is not None and month_to is not None else month_to
        node_keys = [n["key"] for n in nodes]
        fact_rows = run(
            """
            MATCH (e:Entity)-[:HAS_FACT]->(f:Fact)
            WHERE e.key IN $keys
            RETURN e.key AS key,
                   collect({
                       predicate: f.predicate,
                       object: f.object,
                       value_min: f.value_min,
                       value_max: f.value_max,
                       unit: f.unit_normalized,
                       geography: f.geography,
                       confidence: f.confidence,
                       quote: f.quote,
                       source_doc: f.source_doc,
                       time: f.time
                   }) AS facts
            """,
            keys=node_keys,
        )
        facts_by_key = {row["key"]: row.get("facts") or [] for row in fact_rows}
        allowed_keys = set()
        for node in nodes:
            key = node["key"]
            facts = facts_by_key.get(key, [])
            if not facts:
                # Node has no facts at all — we can't determine region, include it
                allowed_keys.add(key)
            elif any(
                _graph_fact_matches_filters(
                    fact,
                    region=region,
                    min_confidence=min_confidence,
                    year_from=year_start,
                    year_to=year_end,
                    month_from=month_start,
                    month_to=month_end,
                )
                for fact in facts
            ):
                allowed_keys.add(key)
        nodes = [node for node in nodes if node["key"] in allowed_keys]
        links = [
            link for link in links
            if link["source"] in allowed_keys and link["target"] in allowed_keys
        ]
    return {"nodes": nodes, "links": links}


def get_entity_details(key: str):
    rows = run(
        """
        MATCH (e:Entity {key: $key})
        OPTIONAL MATCH (e)-[:HAS_FACT]->(f:Fact)
        OPTIONAL MATCH (e)-[:MENTIONED_IN]->(:Chunk)-[:PART_OF]->(d:Document)
        OPTIONAL MATCH (e)-[r:RELATED]-(m:Entity)
        RETURN e.name AS name, e.type AS type, e.description AS description,
               e.aliases AS aliases,
               collect(DISTINCT {key: coalesce(f.key, toString(id(f))), predicate: f.predicate, object: f.object,
                       value_min: f.value_min, value_max: f.value_max,
                       unit: f.unit_normalized, geography: f.geography,
                       confidence: f.confidence, quote: f.quote}) AS facts,
               collect(DISTINCT d.name) AS documents,
               collect(DISTINCT {
                   type: r.type,
                   direction: CASE WHEN startNode(r).key = e.key THEN 'out' ELSE 'in' END,
                   key: m.key,
                   name: m.name,
                   entity_type: m.type
               }) AS relations
        """,
        key=key,
    )
    return rows[0] if rows else None


def list_experiments(search: str | None = None):
    if search:
        safe = _lucene_escape(search)
        rows = run(
            """
            CALL db.index.fulltext.queryNodes('entity_search', $q) YIELD node, score
            WHERE node.type = 'Experiment'
            RETURN node.key AS key, node.name AS name, node.description AS description,
                   node.temperature AS temperature, node.pressure AS pressure,
                   node.time AS time, node.atmosphere AS atmosphere,
                   node.source_document_id AS document_id,
                   node.source_page AS page,
                   node.source_chunk_id AS chunk_id
            ORDER BY score DESC LIMIT 50
            """,
            q=safe + "~",
        )
    else:
        rows = run(
            """
            MATCH (node:Entity)
            WHERE node.type = 'Experiment'
            RETURN node.key AS key, node.name AS name, node.description AS description,
                   node.temperature AS temperature, node.pressure AS pressure,
                   node.time AS time, node.atmosphere AS atmosphere,
                   node.source_document_id AS document_id,
                   node.source_page AS page,
                   node.source_chunk_id AS chunk_id
            ORDER BY node.created_at DESC LIMIT 100
            """
        )
    experiments = []
    for row in rows:
        props = {
            k: row[k]
            for k in ("temperature", "pressure", "time", "atmosphere")
            if row.get(k) is not None
        }
        experiments.append({
            "key": row["key"],
            "name": row["name"],
            "description": row.get("description") or "",
            "properties": props,
            "source": {
                "document_id": row.get("document_id"),
                "page": row.get("page"),
                "chunk_id": row.get("chunk_id"),
            },
        })
    return {"experiments": experiments, "total": len(experiments)}


def get_experiment_card(exp_key: str):
    rows = run(
        """
        MATCH (e:Entity {key: $key})
        WHERE e.type = 'Experiment'
        OPTIONAL MATCH (e)-[r:RELATED]->(m:Entity)
        RETURN e.key AS key, e.name AS name, e.description AS description,
               e.temperature AS temperature, e.pressure AS pressure,
               e.time AS time, e.atmosphere AS atmosphere,
               e.source_document_id AS document_id,
               e.source_page AS page,
               e.source_chunk_id AS chunk_id,
               collect(DISTINCT {type: r.type, key: m.key, name: m.name, entity_type: m.type}) AS related
        LIMIT 1
        """,
        key=exp_key,
    )
    if not rows:
        return None
    row = rows[0]
    return {
        "key": row["key"],
        "name": row["name"],
        "description": row.get("description") or "",
        "properties": {
            k: row[k]
            for k in ("temperature", "pressure", "time", "atmosphere")
            if row.get(k) is not None
        },
        "source": {
            "document_id": row.get("document_id"),
            "page": row.get("page"),
            "chunk_id": row.get("chunk_id"),
        },
        "related": [item for item in row.get("related", []) if item.get("key")],
    }


def search_facts(
    query: str,
    geography: str | None = None,
    min_confidence: float = 0.0,
    value_min: float | None = None,
    value_max: float | None = None,
    unit: str | None = None,
    limit: int = 25,
):
    safe = _lucene_escape(query)
    where_clauses = ["$geo IS NULL OR node.geography = $geo"]
    params: dict = {"q": safe, "geo": geography, "lim": limit, "min_conf": min_confidence}

    if min_confidence > 0:
        where_clauses.append("coalesce(node.confidence, 0.5) >= $min_conf")
    if value_min is not None:
        where_clauses.append("(node.value_min IS NOT NULL AND node.value_min >= $vmin)")
        params["vmin"] = value_min
    if value_max is not None:
        where_clauses.append("(node.value_max IS NOT NULL AND node.value_max <= $vmax)")
        params["vmax"] = value_max
    if unit:
        where_clauses.append("toLower(node.unit_normalized) CONTAINS toLower($unit)")
        params["unit"] = unit

    where = " AND ".join(where_clauses)
    cypher = f"""
        CALL db.index.fulltext.queryNodes('fact_search', $q) YIELD node, score
        WHERE {where}
        RETURN node.subject AS subject, node.predicate AS predicate, node.object AS object,
               node.value_min AS value_min, node.value_max AS value_max,
               node.unit_normalized AS unit, node.geography AS geography,
               node.time AS time, node.confidence AS confidence, node.quote AS quote,
               node.source_doc AS source_doc, score
        ORDER BY score DESC LIMIT $lim
    """
    return run(cypher, **params)


def get_knowledge_gaps() -> dict:
    """Find entities with few facts or low average confidence."""
    rows = run("""
        MATCH (e:Entity)
        OPTIONAL MATCH (e)-[:HAS_FACT]->(f:Fact)
        RETURN e.name AS name, e.type AS type,
               count(f) AS fact_count,
               avg(coalesce(f.confidence, 0.5)) AS avg_conf
        ORDER BY fact_count ASC, avg_conf ASC
    """)
    gaps = []
    total_entities = len(rows)
    for row in rows:
        count = row.get("fact_count") or 0
        avg_conf = row.get("avg_conf") or 0.5
        if count < 2 or avg_conf < 0.75:
            gaps.append({
                "topic": row["name"],
                "type": row.get("type", ""),
                "description": f"Мало фактов о сущности ({count} ед.)" if count < 2 else f"Низкая достоверность фактов (avg: {round(float(avg_conf), 2)})",
                "severity": "high" if count == 0 else "medium",
            })
    gaps.sort(key=lambda x: x["severity"] == "high", reverse=True)
    coverage = round(1 - len(gaps) / max(total_entities, 1), 2)
    return {"gaps": gaps[:20], "total_gaps": len(gaps), "coverage": coverage}


def compare_topics(topic_a: str, topic_b: str) -> dict:
    from comparison import build_comparison
    def load(value: str) -> tuple[dict, list[dict]]:
        rows = run("""
            MATCH (e:Entity) WHERE e.key = $value OR toLower(e.name) = toLower($value)
            OPTIONAL MATCH (e)-[:HAS_FACT]->(f:Fact)
            RETURN e.key AS key, e.name AS name, e.type AS type,
                   collect(CASE WHEN f IS NULL THEN NULL ELSE {predicate:f.predicate, object:f.object,
                   value_min:f.value_min, value_max:f.value_max, unit:f.unit_normalized,
                   confidence:f.confidence, geography:f.geography} END) AS facts
            LIMIT 1
        """, value=value)
        if not rows:
            raise ValueError(f"Сущность не найдена: {value}")
        row = rows[0]
        return {"key": row["key"], "name": row["name"], "type": row["type"]}, [f for f in row["facts"] if f]
    a, facts_a = load(topic_a)
    b, facts_b = load(topic_b)
    return build_comparison(a, facts_a, b, facts_b)


def suggest_entities(query: str, limit: int = 8) -> list[dict]:
    return run("""
        MATCH (e:Entity)-[:HAS_FACT]->(f:Fact)
        WHERE $search_text = '' OR toLower(e.name) CONTAINS toLower($search_text)
        RETURN e.key AS key, e.name AS name, e.type AS type, count(f) AS fact_count
        ORDER BY CASE WHEN toLower(e.name) STARTS WITH toLower($search_text) THEN 0 ELSE 1 END,
                 fact_count DESC, e.name LIMIT $limit
    """, search_text=query.strip(), limit=limit)


def search_context(question: str, region: str | None = None):
    safe = _lucene_escape(question)
    entity_rows = run(
        """
        CALL db.index.fulltext.queryNodes('entity_search', $q) YIELD node, score
        RETURN node.key AS key, node.name AS name, node.type AS type,
               node.description AS description, node.aliases AS aliases, score
        ORDER BY score DESC LIMIT 10
        """,
        q=safe + "~",
    )
    keys = [row["key"] for row in entity_rows if row.get("key")]
    entities = [
        {
            "key": row["key"],
            "name": row["name"],
            "type": row["type"],
            "description": row.get("description") or "",
        }
        for row in entity_rows
        if row.get("key") and row.get("name") and row.get("type")
    ]

    facts = []
    if keys:
        fact_rows = run(
            """
            MATCH (e:Entity)
            WHERE e.key IN $keys
            OPTIONAL MATCH (e)-[:HAS_FACT]->(f:Fact)
            WHERE ($region IS NULL OR $region = 'world' OR f.geography IS NULL OR f.geography = 'unknown' OR f.geography = $region)
            RETURN e.name AS subject,
                   collect({
                       predicate: f.predicate,
                       object: f.object,
                       value_min: f.value_min,
                       value_max: f.value_max,
                       unit_normalized: f.unit_normalized,
                       unit: f.unit,
                       geography: f.geography,
                       confidence: f.confidence,
                       quote: f.quote
                   })[..8] AS facts
            """,
            keys=keys,
            region=region,
        )
        for row in fact_rows:
            for fact in row.get("facts") or []:
                if fact and fact.get("predicate"):
                    facts.append({**fact, "subject": row["subject"]})

    chunk_rows = run(
        """
        CALL db.index.fulltext.queryNodes('chunk_search', $q) YIELD node, score
        OPTIONAL MATCH (node)-[:PART_OF]->(d:Document)
        RETURN node.text AS text, d.name AS doc, score
        ORDER BY score DESC LIMIT 6
        """,
        q=safe,
    )

    doc_names = sorted({row["doc"] for row in chunk_rows if row.get("doc")})
    return {
        "entities": entities,
        "facts": facts[:30],
        "chunks": chunk_rows,
        "sources": doc_names,
    }


def upsert_sync_state(
    name: str,
    enabled: bool,
    ok: bool,
    source_url: str | None = None,
    status: str | None = None,
    files_found: int = 0,
    files_downloaded: int = 0,
    files_skipped: int = 0,
    files_failed: int = 0,
    last_error: str | None = None,
):
    run(
        """
        MERGE (s:SyncState {name: $name})
        SET s.enabled = $enabled,
            s.ok = $ok,
            s.source_url = $source_url,
            s.status = $status,
            s.files_found = $files_found,
            s.files_downloaded = $files_downloaded,
            s.files_skipped = $files_skipped,
            s.files_failed = $files_failed,
            s.last_error = $last_error,
            s.last_run_at = $ts
        """,
        name=name,
        enabled=enabled,
        ok=ok,
        source_url=source_url,
        status=status,
        files_found=files_found,
        files_downloaded=files_downloaded,
        files_skipped=files_skipped,
        files_failed=files_failed,
        last_error=last_error,
        ts=time.time(),
    )


def get_sync_state(name: str = "yandex_disk_public"):
    rows = run(
        """
        MATCH (s:SyncState {name: $name})
        RETURN s.name AS name, s.enabled AS enabled, s.ok AS ok,
               s.source_url AS source_url, s.status AS status,
               s.files_found AS files_found, s.files_downloaded AS files_downloaded,
               s.files_skipped AS files_skipped, s.files_failed AS files_failed,
               s.last_error AS last_error, s.last_run_at AS last_run_at
        LIMIT 1
        """,
        name=name,
    )
    if rows:
        return rows[0]
    return {
        "name": name,
        "enabled": False,
        "ok": False,
        "source_url": None,
        "status": "idle",
        "files_found": 0,
        "files_downloaded": 0,
        "files_skipped": 0,
        "files_failed": 0,
        "last_error": None,
        "last_run_at": None,
    }


def create_chat_message(
    message_id: str,
    role: str,
    content: str,
    sources: list[str] | None = None,
    facts: list[dict] | None = None,
    cached: bool = False,
    error: bool = False,
):
    run(
        """
        CREATE (m:ChatMessage {
            id: $id,
            role: $role,
            content: $content,
            created_at: $created_at,
            sources_json: $sources_json,
            facts_json: $facts_json,
            cached: $cached,
            error: $error
        })
        """,
        id=message_id,
        role=role,
        content=content,
        created_at=time.time(),
        sources_json=json.dumps(sources or [], ensure_ascii=False),
        facts_json=json.dumps(facts or [], ensure_ascii=False),
        cached=cached,
        error=error,
    )


def list_chat_history(limit: int = 200):
    rows = run(
        """
        MATCH (m:ChatMessage)
        RETURN m.id AS id, m.role AS role, m.content AS content,
               m.created_at AS created_at, m.sources_json AS sources_json,
               m.facts_json AS facts_json, m.cached AS cached, m.error AS error
        ORDER BY m.created_at ASC, m.id ASC
        LIMIT $limit
        """,
        limit=limit,
    )
    messages = []
    for row in rows:
        try:
            sources = json.loads(row.get("sources_json") or "[]")
        except json.JSONDecodeError:
            sources = []
        try:
            facts = json.loads(row.get("facts_json") or "[]")
        except json.JSONDecodeError:
            facts = []
        messages.append({
            "id": row["id"],
            "role": row["role"],
            "content": row["content"],
            "created_at": row["created_at"],
            "sources": sources,
            "facts": facts,
            "cached": bool(row.get("cached")),
            "error": bool(row.get("error")),
        })
    return messages


def clear_chat_history():
    run("MATCH (m:ChatMessage) DETACH DELETE m")




def get_comparison(entity_a: str, entity_b: str):
    """Compare two entities."""
    return run(
        """
        MATCH (a:Entity {name: $a}), (b:Entity {name: $b})
        OPTIONAL MATCH (a)-[:HAS_FACT]->(f1:Fact)
        OPTIONAL MATCH (b)-[:HAS_FACT]->(f2:Fact)
        RETURN collect(DISTINCT f1.predicate) AS a_facts,
               collect(DISTINCT f2.predicate) AS b_facts
        """,
        a=entity_a, b=entity_b
    )


def _lucene_escape(text: str) -> str:
    specials = '+-&|!(){}[]^"~*?:\\/'
    out = []
    for ch in text:
        if ch in specials:
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


def create_notification(ntype: str, title: str, message: str):
    import time
    nid = str(time.time_ns())
    run(
        """
        CREATE (n:Notification {
            id: $nid,
            type: $ntype,
            title: $title,
            message: $message,
            timestamp: datetime(),
            unread: true
        })
        """,
        nid=nid,
        ntype=ntype,
        title=title,
        message=message
    )


def list_notifications(limit: int = 30):
    records = run(
        """
        MATCH (n:Notification)
        RETURN n.id AS id, n.type AS type, n.title AS title, n.message AS message, 
               toString(n.timestamp) AS timestamp, n.unread AS unread
        ORDER BY n.timestamp DESC
        LIMIT toInteger($limit)
        """
    )
    return [dict(r) for r in records]


def mark_notifications_read():
    run(
        """
        MATCH (n:Notification)
        SET n.unread = false
        """
    )
