"""JSON-LD export for the NORNIKEL Knowledge Map.

Converts graph entities, facts, and relations into JSON-LD format
compatible with Schema.org and custom mining/metallurgy contexts.
"""

import json
import time
from typing import Any

import graph_db

# ── Context ────────────────────────────────────────────────────
CONTEXT = {
    "@vocab": "https://schema.org/",
    "nml": "https://nornickel.ru/ontology#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "name": "rdfs:label",
    "description": "rdfs:comment",
    "type": "@type",
    "id": "@id",
    "Material": "nml:Material",
    "Process": "nml:Process",
    "Equipment": "nml:Equipment",
    "Property": "nml:Property",
    "Experiment": "nml:Experiment",
    "Publication": "nml:Publication",
    "Expert": "nml:Expert",
    "Facility": "nml:Facility",
    "Fact": "nml:Fact",
    "usesMaterial": "nml:usesMaterial",
    "usesProcess": "nml:usesProcess",
    "usesEquipment": "nml:usesEquipment",
    "performedAt": "nml:performedAt",
    "operatesAtCondition": "nml:operatesAtCondition",
    "validatedBy": "nml:validatedBy",
    "describes": "nml:describes",
    "producesOutput": "nml:producesOutput",
    "contradicts": "nml:contradicts",
    "hasFact": "nml:hasFact",
    "subject": "nml:subject",
    "predicate": "nml:predicate",
    "object": "nml:object",
    "valueMin": {"@id": "nml:valueMin", "@type": "xsd:float"},
    "valueMax": {"@id": "nml:valueMax", "@type": "xsd:float"},
    "unit": "nml:unit",
    "geography": "nml:geography",
    "confidence": {"@id": "nml:confidence", "@type": "xsd:float"},
    "quote": "nml:quote",
    "sourceDocument": "nml:sourceDocument",
    "aliases": "nml:aliases",
    "mentionedin": "nml:mentionedin",
}

# ── Relation type → JSON-LD predicate mapping ──────────────────
REL_MAP = {
    "USES_MATERIAL": "usesMaterial",
    "USES_PROCESS": "usesProcess",
    "USES_EQUIPMENT": "usesEquipment",
    "PERFORMED_AT": "performedAt",
    "OPERATES_AT_CONDITION": "operatesAtCondition",
    "VALIDATED_BY": "validatedBy",
    "DESCRIBES": "describes",
    "PRODUCES_OUTPUT": "producesOutput",
    "CONTRADICTS": "contradicts",
}


def _entity_to_jsonld(entity: dict) -> dict:
    """Convert a single entity dict to JSON-LD node."""
    node: dict[str, Any] = {
        "id": f"nml:entity/{entity.get('key', '')}",
        "type": entity.get("type", "Entity"),
        "name": entity.get("name", ""),
    }
    if entity.get("description"):
        node["description"] = entity["description"]
    if entity.get("aliases"):
        node["aliases"] = entity["aliases"]
    return node


def _fact_to_jsonld(fact: dict) -> dict:
    """Convert a fact dict to JSON-LD node."""
    node: dict[str, Any] = {
        "id": f"nml:fact/{fact.get('subject', '')}_{hash(fact.get('predicate', '') + str(fact.get('object', ''))) & 0xFFFFFF:06x}",
        "type": "Fact",
        "subject": fact.get("subject", ""),
        "predicate": fact.get("predicate", ""),
        "object": fact.get("object", ""),
    }
    if fact.get("value_min") is not None:
        node["valueMin"] = fact["value_min"]
    if fact.get("value_max") is not None:
        node["valueMax"] = fact["value_max"]
    if fact.get("unit_normalized") or fact.get("unit"):
        node["unit"] = fact.get("unit_normalized") or fact.get("unit")
    if fact.get("geography") and fact["geography"] != "unknown":
        node["geography"] = fact["geography"]
    if fact.get("confidence") is not None:
        node["confidence"] = fact["confidence"]
    if fact.get("quote"):
        node["quote"] = fact["quote"][:500]
    if fact.get("source_doc"):
        node["sourceDocument"] = fact["source_doc"]
    return node


def _relation_to_jsonld(rel: dict, subject_id: str) -> dict | None:
    """Convert a relation dict to a JSON-LD triple."""
    rel_type = rel.get("type", "")
    predicate = REL_MAP.get(rel_type)
    if not predicate:
        return None
    target_key = rel.get("key", "")
    return {
        "id": subject_id,
        predicate: f"nml:entity/{target_key}",
    }


def export_entity_graph(key: str) -> dict:
    """Export a single entity and its neighborhood as JSON-LD."""
    entity = graph_db.get_entity_details(key)
    if not entity:
        return {"error": "Entity not found"}

    graph_nodes = [_entity_to_jsonld({
        "key": key,
        "name": entity.get("name"),
        "type": entity.get("type"),
        "description": entity.get("description"),
        "aliases": entity.get("aliases"),
    })]

    graph_facts = []
    for f in entity.get("facts", []):
        if f.get("predicate"):
            graph_facts.append(_fact_to_jsonld({**f, "subject": entity.get("name", "")}))

    graph_links = []
    subject_id = f"nml:entity/{key}"
    for rel in entity.get("relations", []):
        link = _relation_to_jsonld(rel, subject_id)
        if link:
            graph_links.append(link)

    return {
        "@context": CONTEXT,
        "@graph": graph_nodes,
        "facts": graph_facts,
        "relations": graph_links,
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "NORNIKEL R&D Knowledge Map",
    }


def export_subgraph(
    search: str | None = None,
    etypes: list[str] | None = None,
    limit: int = 150,
    region: str | None = None,
    min_confidence: float | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
) -> dict:
    """Export a subgraph as JSON-LD."""
    subgraph = graph_db.get_subgraph(
        search, etypes, limit, region, min_confidence, year_from, year_to,
    )

    nodes = [_entity_to_jsonld(n) for n in subgraph.get("nodes", [])]

    links = []
    for link in subgraph.get("links", []):
        rel_type = link.get("type", "")
        predicate = REL_MAP.get(rel_type)
        if predicate:
            links.append({
                "id": f"nml:entity/{link.get('source', '')}",
                predicate: f"nml:entity/{link.get('target', '')}",
            })

    return {
        "@context": CONTEXT,
        "@graph": nodes,
        "links": links,
        "stats": {
            "node_count": len(nodes),
            "link_count": len(links),
        },
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "NORNIKEL R&D Knowledge Map",
    }


def export_all(limit: int = 500) -> dict:
    """Export the full graph as JSON-LD (capped at limit)."""
    subgraph = graph_db.get_subgraph(None, None, limit)

    nodes = [_entity_to_jsonld(n) for n in subgraph.get("nodes", [])]

    links = []
    for link in subgraph.get("links", []):
        rel_type = link.get("type", "")
        predicate = REL_MAP.get(rel_type)
        if predicate:
            links.append({
                "id": f"nml:entity/{link.get('source', '')}",
                predicate: f"nml:entity/{link.get('target', '')}",
            })

    return {
        "@context": CONTEXT,
        "@graph": nodes,
        "links": links,
        "stats": {
            "node_count": len(nodes),
            "link_count": len(links),
        },
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "NORNIKEL R&D Knowledge Map",
    }
