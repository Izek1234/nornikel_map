"""Fact & Entity versioning for the Knowledge Map.

Provides:
- Fact versioning: create_version, get_versions, revert_to_version
- Entity versioning: log_entity_change, get_entity_history, correct_entity
- Audit log: record_change, get_audit_log, get_audit_stats
- Document versioning: log_document_version, get_document_versions
"""

import time
import uuid
from typing import Optional

import graph_db


def init_versioning_schema():
    """Create constraints and indexes for versioning. Idempotent."""
    statements = [
        "CREATE CONSTRAINT fact_version_id IF NOT EXISTS FOR (fv:FactVersion) REQUIRE fv.id IS UNIQUE",
        "CREATE CONSTRAINT audit_entry_id IF NOT EXISTS FOR (ae:AuditEntry) REQUIRE ae.id IS UNIQUE",
        "CREATE CONSTRAINT entity_change_id IF NOT EXISTS FOR (ec:EntityChange) REQUIRE ec.id IS UNIQUE",
        "CREATE CONSTRAINT doc_version_id IF NOT EXISTS FOR (dv:DocumentVersion) REQUIRE dv.id IS UNIQUE",
        "CREATE INDEX fact_version_fact_key IF NOT EXISTS FOR (fv:FactVersion) ON (fv.fact_key)",
        "CREATE INDEX audit_entry_ts IF NOT EXISTS FOR (ae:AuditEntry) ON (ae.timestamp)",
        "CREATE INDEX entity_change_key IF NOT EXISTS FOR (ec:EntityChange) ON (ec.entity_key)",
        "CREATE INDEX doc_version_doc_id IF NOT EXISTS FOR (dv:DocumentVersion) ON (dv.doc_id)",
    ]
    for stmt in statements:
        graph_db.run(stmt)


def create_fact_version(
    fact_key: str,
    subject: str,
    predicate: str,
    object_val: str,
    value_min=None,
    value_max=None,
    unit: str = None,
    unit_normalized: str = None,
    geography: str = "unknown",
    confidence: float = 0.5,
    quote: str = "",
    source_doc: str = "",
    source_chunk: str = "",
    change_type: str = "created",
    author: str = "system",
    comment: str = "",
    parent_version_id: str = None,
) -> dict:
    """Create a versioned snapshot of a fact."""
    version_id = uuid.uuid4().hex[:16]
    ts = time.time()

    existing = graph_db.run(
        "MATCH (fv:FactVersion {fact_key: $fk}) RETURN fv.version_num AS vn ORDER BY fv.version_num DESC LIMIT 1",
        fk=fact_key,
    )
    version_num = (existing[0]["vn"] + 1) if existing else 1

    graph_db.run(
        """
        CREATE (fv:FactVersion {
            id: $id,
            fact_key: $fact_key,
            version_num: $version_num,
            subject: $subject,
            predicate: $predicate,
            object: $object,
            value_min: $vmin,
            value_max: $vmax,
            unit: $unit,
            unit_normalized: $unit_norm,
            geography: $geo,
            confidence: $conf,
            quote: $quote,
            source_doc: $doc,
            source_chunk: $chunk,
            change_type: $change_type,
            author: $author,
            comment: $comment,
            parent_version_id: $parent_id,
            created_at: $ts
        })
        """,
        id=version_id,
        fact_key=fact_key,
        version_num=version_num,
        subject=subject,
        predicate=predicate,
        object=object_val,
        vmin=value_min,
        vmax=value_max,
        unit=unit,
        unit_norm=unit_normalized,
        geo=geography,
        conf=confidence,
        quote=quote,
        doc=source_doc,
        chunk=source_chunk,
        change_type=change_type,
        author=author,
        comment=comment,
        parent_id=parent_version_id,
        ts=ts,
    )

    record_audit(
        action=f"fact_{change_type}",
        target_type="fact",
        target_key=fact_key,
        author=author,
        details={
            "version_num": version_num,
            "predicate": predicate,
            "object": object_val,
            "comment": comment,
        },
    )

    return {
        "id": version_id,
        "version_num": version_num,
        "fact_key": fact_key,
        "change_type": change_type,
        "author": author,
        "comment": comment,
        "created_at": ts,
    }


def get_fact_versions(fact_key: str) -> list[dict]:
    """Get all versions of a fact, newest first."""
    return graph_db.run(
        """
        MATCH (fv:FactVersion {fact_key: $fk})
        RETURN fv.id AS id, fv.version_num AS version_num,
               fv.subject AS subject, fv.predicate AS predicate,
               fv.object AS object, fv.value_min AS value_min,
               fv.value_max AS value_max, fv.unit AS unit,
               fv.unit_normalized AS unit_normalized,
               fv.geography AS geography, fv.confidence AS confidence,
               fv.quote AS quote, fv.source_doc AS source_doc,
               fv.change_type AS change_type, fv.author AS author,
               fv.comment AS comment, fv.parent_version_id AS parent_version_id,
               fv.created_at AS created_at
        ORDER BY fv.version_num DESC
        """,
        fk=fact_key,
    )


def get_latest_fact_version(fact_key: str) -> Optional[dict]:
    """Get the latest version of a fact."""
    versions = get_fact_versions(fact_key)
    return versions[0] if versions else None


def log_entity_change(
    entity_key: str,
    change_type: str,
    author: str = "system",
    comment: str = "",
    old_values: dict = None,
    new_values: dict = None,
):
    """Log a change to an entity."""
    entry_id = uuid.uuid4().hex[:16]
    ts = time.time()

    graph_db.run(
        """
        CREATE (ec:EntityChange {
            id: $id,
            entity_key: $entity_key,
            change_type: $change_type,
            author: $author,
            comment: $comment,
            old_values_json: $old_json,
            new_values_json: $new_json,
            created_at: $ts
        })
        """,
        id=entry_id,
        entity_key=entity_key,
        change_type=change_type,
        author=author,
        comment=comment,
        old_json=_safe_json(old_values or {}),
        new_json=_safe_json(new_values or {}),
        ts=ts,
    )

    record_audit(
        action=f"entity_{change_type}",
        target_type="entity",
        target_key=entity_key,
        author=author,
        details={
          "change_type": change_type,
          "comment": comment,
          "old_values": old_values or {},
          "new_values": new_values or {},
        },
    )


def get_entity_history(entity_key: str) -> list[dict]:
    """Get change history for an entity."""
    rows = graph_db.run(
        """
        MATCH (ec:EntityChange {entity_key: $ek})
        RETURN ec.id AS id, ec.change_type AS change_type,
               ec.author AS author, ec.comment AS comment,
               ec.old_values_json AS old_values_json,
               ec.new_values_json AS new_values_json,
               ec.created_at AS created_at
        ORDER BY ec.created_at DESC
        """,
        ek=entity_key,
    )
    result = []
    for row in rows:
        result.append({
            "id": row["id"],
            "change_type": row["change_type"],
            "author": row["author"],
            "comment": row["comment"],
            "old_values": _parse_json(row.get("old_values_json")),
            "new_values": _parse_json(row.get("new_values_json")),
            "created_at": row["created_at"],
        })
    return result


def record_audit(
    action: str,
    target_type: str,
    target_key: str,
    author: str = "system",
    details: dict = None,
):
    """Record an audit entry."""
    entry_id = uuid.uuid4().hex[:16]
    ts = time.time()

    graph_db.run(
        """
        CREATE (ae:AuditEntry {
            id: $id,
            action: $action,
            target_type: $target_type,
            target_key: $target_key,
            author: $author,
            details_json: $details_json,
            timestamp: $ts
        })
        """,
        id=entry_id,
        action=action,
        target_type=target_type,
        target_key=target_key,
        author=author,
        details_json=_safe_json(details or {}),
        ts=ts,
    )


def get_audit_log(
    limit: int = 100,
    target_type: str = None,
    target_key: str = None,
    author: str = None,
    action: str = None,
) -> list[dict]:
    """Query the audit log with optional filters."""
    conditions = []
    params = {"limit": limit}

    if target_type:
        conditions.append("ae.target_type = $target_type")
        params["target_type"] = target_type
    if target_key:
        conditions.append("ae.target_key = $target_key")
        params["target_key"] = target_key
    if author:
        conditions.append("ae.author = $author")
        params["author"] = author
    if action:
        conditions.append("ae.action = $action")
        params["action"] = action

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    rows = graph_db.run(
        f"""
        MATCH (ae:AuditEntry)
        {where}
        RETURN ae.id AS id, ae.action AS action,
               ae.target_type AS target_type, ae.target_key AS target_key,
               ae.author AS author, ae.details_json AS details_json,
               ae.timestamp AS timestamp
        ORDER BY ae.timestamp DESC
        LIMIT $limit
        """,
        **params,
    )
    result = []
    for row in rows:
        result.append({
            "id": row["id"],
            "action": row["action"],
            "target_type": row["target_type"],
            "target_key": row["target_key"],
            "author": row["author"],
            "details": _parse_json(row.get("details_json")),
            "timestamp": row["timestamp"],
        })
    return result


def correct_fact(
    fact_key: str,
    new_values: dict,
    author: str = "expert",
    comment: str = "",
) -> dict:
    """Expert correction of a fact — creates new version, archives old."""
    current = get_latest_fact_version(fact_key)
    if not current:
        current = {
            "subject": new_values.get("subject", ""),
            "predicate": new_values.get("predicate", ""),
            "object": new_values.get("object", ""),
            "value_min": new_values.get("value_min"),
            "value_max": new_values.get("value_max"),
            "unit": new_values.get("unit"),
            "unit_normalized": new_values.get("unit_normalized"),
            "geography": new_values.get("geography", "unknown"),
            "confidence": new_values.get("confidence", 0.5),
            "quote": new_values.get("quote", ""),
            "source_doc": new_values.get("source_doc", ""),
            "source_chunk": new_values.get("source_chunk", ""),
        }

    merged = {**current, **{k: v for k, v in new_values.items() if v is not None}}
    version = create_fact_version(
        fact_key=fact_key,
        subject=merged["subject"],
        predicate=merged["predicate"],
        object_val=merged["object"],
        value_min=merged.get("value_min"),
        value_max=merged.get("value_max"),
        unit=merged.get("unit"),
        unit_normalized=merged.get("unit_normalized"),
        geography=merged.get("geography", "unknown"),
        confidence=merged.get("confidence", 0.5),
        quote=merged.get("quote", ""),
        source_doc=merged.get("source_doc", ""),
        source_chunk=merged.get("source_chunk", ""),
        change_type="corrected",
        author=author,
        comment=comment,
        parent_version_id=current.get("id"),
    )

    return {
        "version": version,
        "previous_version": current,
        "message": f"Fact corrected by {author}: {comment}",
    }


def correct_entity(
    entity_key: str,
    new_values: dict,
    author: str = "expert",
    comment: str = "",
) -> dict:
    """Expert correction of an entity — updates in graph and logs change."""
    rows = graph_db.run(
        "MATCH (e:Entity {key: $k}) RETURN e.name AS name, e.description AS desc, e.aliases AS aliases",
        k=entity_key,
    )
    if not rows:
        return {"error": "Entity not found"}

    current = rows[0]
    old_values = {
        "name": current.get("name"),
        "description": current.get("desc"),
        "aliases": current.get("aliases"),
    }

    updates = []
    params = {"key": entity_key, "ts": time.time()}
    if "name" in new_values and new_values["name"]:
        updates.append("e.name = $name")
        params["name"] = new_values["name"]
    if "description" in new_values and new_values["description"] is not None:
        updates.append("e.description = $desc")
        params["desc"] = new_values["description"]
    if "aliases" in new_values and new_values["aliases"] is not None:
        updates.append("e.aliases = $aliases")
        params["aliases"] = new_values["aliases"]

    if updates:
        updates.append("e.last_modified_at = $ts")
        updates.append("e.last_modified_by = $author")
        params["author"] = author
        graph_db.run(f"MATCH (e:Entity {{key: $key}}) SET {', '.join(updates)}", **params)

    log_entity_change(
        entity_key=entity_key,
        change_type="corrected",
        author=author,
        comment=comment,
        old_values=old_values,
        new_values=new_values,
    )

    return {
        "entity_key": entity_key,
        "author": author,
        "comment": comment,
        "old_values": old_values,
        "new_values": new_values,
        "message": f"Entity corrected by {author}: {comment}",
    }


def revert_fact_version(fact_key: str, version_id: str, author: str = "expert", comment: str = "") -> dict:
    """Revert a fact to a specific previous version — creates a new 'reverted' version."""
    versions = get_fact_versions(fact_key)
    target = next((v for v in versions if v["id"] == version_id), None)
    if not target:
        return {"error": "Version not found"}

    version = create_fact_version(
        fact_key=fact_key,
        subject=target["subject"],
        predicate=target["predicate"],
        object_val=target["object"],
        value_min=target.get("value_min"),
        value_max=target.get("value_max"),
        unit=target.get("unit"),
        unit_normalized=target.get("unit_normalized"),
        geography=target.get("geography", "unknown"),
        confidence=target.get("confidence", 0.5),
        quote=target.get("quote", ""),
        source_doc=target.get("source_doc", ""),
        source_chunk=target.get("source_chunk", ""),
        change_type="reverted",
        author=author,
        comment=comment or f"Reverted to v{target['version_num']}",
        parent_version_id=version_id,
    )

    return {
        "version": version,
        "reverted_to": target,
        "message": f"Fact reverted to v{target['version_num']} by {author}",
    }


def get_audit_stats() -> dict:
    """Get summary statistics for the audit log."""
    total = graph_db.run("MATCH (ae:AuditEntry) RETURN count(*) AS cnt")
    total_count = total[0]["cnt"] if total else 0

    action_rows = graph_db.run("""
        MATCH (ae:AuditEntry)
        UNWIND [ae.action] AS a
        RETURN a AS action, count(*) AS count
        ORDER BY count DESC
    """)
    by_action = {row["action"]: row["count"] for row in action_rows}

    target_rows = graph_db.run("""
        MATCH (ae:AuditEntry)
        UNWIND [ae.target_type] AS t
        RETURN t AS target_type, count(*) AS count
        ORDER BY count DESC
    """)
    by_target = {row["target_type"]: row["count"] for row in target_rows}

    author_rows = graph_db.run("""
        MATCH (ae:AuditEntry)
        UNWIND [ae.author] AS a
        RETURN a AS author, count(*) AS count
        ORDER BY count DESC
    """)
    by_author = {row["author"]: row["count"] for row in author_rows}

    recent = graph_db.run("""
        MATCH (ae:AuditEntry)
        RETURN ae.action AS action, ae.target_type AS target_type,
               ae.author AS author, ae.timestamp AS timestamp
        ORDER BY ae.timestamp DESC LIMIT 10
    """)

    return {
        "total_entries": total_count,
        "by_action": by_action,
        "by_target_type": by_target,
        "by_author": by_author,
        "recent_activity": recent,
    }


def log_document_version(
    doc_id: str,
    doc_name: str,
    change_type: str,
    author: str = "system",
    comment: str = "",
    old_status: str = "",
    new_status: str = "",
    chunks_delta: int = 0,
):
    """Log a document-level version event (import, reprocess, status change)."""
    entry_id = uuid.uuid4().hex[:16]
    ts = time.time()

    graph_db.run(
        """
        CREATE (dv:DocumentVersion {
            id: $id,
            doc_id: $doc_id,
            doc_name: $doc_name,
            change_type: $change_type,
            author: $author,
            comment: $comment,
            old_status: $old_status,
            new_status: $new_status,
            chunks_delta: $chunks_delta,
            created_at: $ts
        })
        """,
        id=entry_id,
        doc_id=doc_id,
        doc_name=doc_name,
        change_type=change_type,
        author=author,
        comment=comment,
        old_status=old_status,
        new_status=new_status,
        chunks_delta=chunks_delta,
        ts=ts,
    )

    record_audit(
        action=f"document_{change_type}",
        target_type="document",
        target_key=doc_id,
        author=author,
        details={
            "doc_name": doc_name,
            "change_type": change_type,
            "old_status": old_status,
            "new_status": new_status,
            "chunks_delta": chunks_delta,
            "comment": comment,
        },
    )


def get_document_versions(doc_id: str) -> list[dict]:
    """Get version history for a document."""
    rows = graph_db.run(
        """
        MATCH (dv:DocumentVersion {doc_id: $doc_id})
        RETURN dv.id AS id, dv.change_type AS change_type,
               dv.author AS author, dv.comment AS comment,
               dv.old_status AS old_status, dv.new_status AS new_status,
               dv.chunks_delta AS chunks_delta, dv.created_at AS created_at
        ORDER BY dv.created_at DESC
        """,
        doc_id=doc_id,
    )
    return rows


def _safe_json(obj) -> str:
    import json

    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        return "{}"


def _parse_json(raw: str) -> dict:
    import json

    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}
