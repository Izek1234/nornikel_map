"""Deterministic entity comparison shared by demo and Neo4j modes."""
import re


def normalize_predicate(value: str) -> str:
    value = re.sub(r"^(?:сравнение|противоречие)\s*:\s*", "", value.strip(), flags=re.I)
    value = re.sub(r"\s*\([^)]*\)\s*$", "", value)
    value = re.sub(r"\s+главн\w*\s+напряжен\w*$", "", value, flags=re.I)
    return re.sub(r"\s+", " ", value).casefold()


def format_value(fact: dict) -> str:
    if fact.get("object") not in (None, ""):
        return str(fact["object"])
    low, high = fact.get("value_min"), fact.get("value_max")
    if low is None and high is None:
        return "—"
    value = f"{low}–{high}" if low is not None and high is not None and low != high else str(low if low is not None else high)
    return f"{value} {fact.get('unit') or fact.get('unit_normalized') or ''}".strip()


def build_comparison(entity_a: dict, facts_a: list[dict], entity_b: dict, facts_b: list[dict]) -> dict:
    def group(facts: list[dict]) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for fact in facts:
            predicate = (fact.get("predicate") or "").strip()
            if not predicate:
                continue
            key = normalize_predicate(predicate)
            item = result.setdefault(key, {"label": predicate, "values": [], "confidence": []})
            value = format_value(fact)
            if value not in item["values"]:
                item["values"].append(value)
            if fact.get("confidence") is not None:
                item["confidence"].append(float(fact["confidence"]))
        return result

    grouped_a, grouped_b = group(facts_a), group(facts_b)
    rows = []
    for key in sorted(set(grouped_a) | set(grouped_b)):
        left, right = grouped_a.get(key), grouped_b.get(key)
        rows.append({
            "parameter": (left or right)["label"],
            "value_a": "; ".join(left["values"]) if left else "—",
            "value_b": "; ".join(right["values"]) if right else "—",
            "status": "common" if left and right else "only_a" if left else "only_b",
        })
    common = sum(row["status"] == "common" for row in rows)
    return {
        "entity_a": entity_a,
        "entity_b": entity_b,
        "rows": rows,
        "stats": {"facts_a": len(facts_a), "facts_b": len(facts_b), "parameters": len(rows), "common": common},
    }
