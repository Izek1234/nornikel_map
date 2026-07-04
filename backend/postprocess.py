"""Post-processing: number/unit normalization, ranges, confidence scoring,
RU/EN synonym canonicalization, Fact model assembly."""

import re

# ---------- Unit normalization ----------

UNIT_MAP = {
    "мг/л": "mg/L", "мг/дм3": "mg/L", "мг/дм³": "mg/L", "mg/l": "mg/L", "mg/dm3": "mg/L",
    "г/л": "g/L", "г/дм3": "g/L", "г/дм³": "g/L", "g/l": "g/L",
    "г/т": "g/t", "g/t": "g/t",
    "кг/т": "kg/t", "kg/t": "kg/t",
    "т/сут": "t/day", "т/сутки": "t/day", "t/day": "t/day", "тонн/сут": "t/day",
    "т/год": "t/year", "t/year": "t/year", "тыс. т/год": "kt/year", "тыс.т/год": "kt/year",
    "°c": "degC", "°с": "degC", "градусов цельсия": "degC", "град": "degC", "c": "degC", "с": "degC",
    "k": "K", "к": "K",
    "мпа": "MPa", "mpa": "MPa", "кпа": "kPa", "kpa": "kPa", "па": "Pa", "атм": "atm", "бар": "bar", "bar": "bar",
    "а/м2": "A/m2", "а/м²": "A/m2", "a/m2": "A/m2", "ка/м2": "kA/m2",
    "в": "V", "v": "V", "мв": "mV", "mv": "mV",
    "квт": "kW", "kw": "kW", "мвт": "MW", "mw": "MW",
    "квт·ч": "kWh", "квт*ч": "kWh", "квтч": "kWh", "kwh": "kWh", "квт·ч/т": "kWh/t", "kwh/t": "kWh/t",
    "%": "%", "проц": "%", "процентов": "%", "масс.%": "wt%", "мас.%": "wt%", "wt%": "wt%", "об.%": "vol%",
    "мкм": "um", "um": "um", "мм": "mm", "mm": "mm", "см": "cm", "м": "m", "нм": "nm",
    "об/мин": "rpm", "rpm": "rpm",
    "ч": "h", "час": "h", "часов": "h", "h": "h",
    "мин": "min", "минут": "min", "min": "min",
    "сут": "day", "суток": "day",
    "ph": "pH", "рн": "pH",
    "м3/ч": "m3/h", "м³/ч": "m3/h", "m3/h": "m3/h",
    "л/мин": "L/min", "l/min": "L/min",
    "мг": "mg", "г": "g", "кг": "kg", "т": "t", "тонн": "t",
}


def normalize_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    key = unit.strip().lower().replace(" ", "")
    return UNIT_MAP.get(key, unit.strip())


# ---------- Numeric value / range parsing ----------

_NUM = r"[-+]?\d{1,3}(?:[ \u00a0]\d{3})*(?:[.,]\d+)?|[-+]?\d+(?:[.,]\d+)?"


def _to_float(s: str) -> float | None:
    try:
        return float(s.replace(" ", "").replace("\u00a0", "").replace(",", "."))
    except (ValueError, AttributeError):
        return None


def parse_value(raw) -> tuple[float | None, float | None]:
    """Parse '200–300', '≤1000', '>=5', '~50', '3,5' → (min, max)."""
    if raw is None:
        return None, None
    if isinstance(raw, (int, float)):
        return float(raw), float(raw)
    s = str(raw).strip()

    m = re.search(rf"({_NUM})\s*[–—\-…]+\s*({_NUM})", s)
    if m:
        lo, hi = _to_float(m.group(1)), _to_float(m.group(2))
        if lo is not None and hi is not None:
            return min(lo, hi), max(lo, hi)

    m = re.search(rf"(?:≤|<=|не более|до|менее|<)\s*({_NUM})", s, re.IGNORECASE)
    if m:
        v = _to_float(m.group(1))
        return None, v

    m = re.search(rf"(?:≥|>=|не менее|более|свыше|от|>)\s*({_NUM})", s, re.IGNORECASE)
    if m:
        v = _to_float(m.group(1))
        return v, None

    m = re.search(rf"[~≈около]*\s*({_NUM})", s)
    if m:
        v = _to_float(m.group(1))
        return v, v

    return None, None


# ---------- RU/EN synonym canonicalization ----------

SYNONYMS = {
    "electrowinning": "электроэкстракция",
    "electroextraction": "электроэкстракция",
    "электролиз никеля": "электроэкстракция",
    "flash smelting": "взвешенная плавка",
    "пвп": "взвешенная плавка",
    "печь взвешенной плавки": "взвешенная плавка",
    "desalination": "обессоливание",
    "водоподготовка обессоливание": "обессоливание",
    "matte": "штейн",
    "никелевый штейн": "штейн",
    "slag": "шлак",
    "converter slag": "конвертерный шлак",
    "leaching": "выщелачивание",
    "pressure leaching": "автоклавное выщелачивание",
    "автоклавное окислительное выщелачивание": "автоклавное выщелачивание",
    "flotation": "флотация",
    "reverse osmosis": "обратный осмос",
    "ро": "обратный осмос",
    "nickel": "никель",
    "ni": "никель",
    "copper": "медь",
    "cu": "медь",
    "cobalt": "кобальт",
    "co": "кобальт",
    "pgm": "мпг",
    "platinum group metals": "мпг",
    "металлы платиновой группы": "мпг",
    "palladium": "палладий",
    "pd": "палладий",
    "platinum": "платина",
    "pt": "платина",
    "sulfuric acid": "серная кислота",
    "h2so4": "серная кислота",
    "anode": "анод",
    "cathode": "катод",
    "electrolyte": "электролит",
    "tailings": "хвосты",
}


def canonical_key(name: str) -> str:
    """Stable dedup key for an entity name."""
    k = name.strip().lower()
    k = re.sub(r"\s+", " ", k)
    k = SYNONYMS.get(k, k)
    return k


def collect_aliases(name: str) -> list[str]:
    key = canonical_key(name)
    aliases = {name.strip()}
    for syn, canon in SYNONYMS.items():
        if canon == key:
            aliases.add(syn)
    return sorted(aliases)


# ---------- Confidence scoring ----------

def score_confidence(fact: dict, has_quote: bool) -> float:
    conf = 0.45
    if fact.get("value_min") is not None or fact.get("value_max") is not None:
        conf += 0.20
    if fact.get("unit_normalized") and fact["unit_normalized"] in set(UNIT_MAP.values()):
        conf += 0.15
    if has_quote:
        conf += 0.10
    if fact.get("geography") in ("RU", "world"):
        conf += 0.05
    return round(min(conf, 0.95), 2)


# ---------- Fact assembly ----------

def _safe_float(val) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    return _to_float(str(val))


def build_fact(raw: dict) -> dict | None:
    subject = (raw.get("subject") or "").strip()
    predicate = (raw.get("predicate") or "").strip()
    obj = (raw.get("object") or "").strip()
    if not subject or not predicate:
        return None

    vmin = _safe_float(raw.get("value_min"))
    vmax = _safe_float(raw.get("value_max"))

    if vmin is None and vmax is None:
        vmin, vmax = parse_value(raw.get("value"))
    if vmin is None and vmax is None:
        vmin, vmax = parse_value(obj)

    if not obj:
        if vmin is not None and vmax is not None:
            obj = f"{vmin:g}" if vmin == vmax else f"{vmin:g}–{vmax:g}"
        elif vmin is not None:
            obj = f"≥{vmin:g}"
        elif vmax is not None:
            obj = f"≤{vmax:g}"

    if not obj and vmin is None and vmax is None:
        return None

    unit = raw.get("unit")
    unit_norm = normalize_unit(unit)
    quote = (raw.get("quote") or "").strip()[:500]
    geo = (raw.get("geography") or "").strip()
    geo_lower = geo.lower()
    if geo_lower in ("ru", "russia", "россий", "россия", "russian", "domestic"):
        geo = "RU"
    elif geo_lower in ("world", "worldwide", "зарубеж", "foreign", "international", "миров"):
        geo = "world"
    elif geo_lower in ("unknown", ""):
        geo = "unknown"
    else:
        geo = "unknown"

    fact = {
        "subject": subject,
        "predicate": predicate,
        "object": obj or str(raw.get("value", "")),
        "value_min": vmin,
        "value_max": vmax,
        "unit": unit,
        "unit_normalized": unit_norm,
        "geography": geo,
        "quote": quote,
    }
    fact["confidence"] = score_confidence(fact, bool(quote))
    return fact


def format_fact_value(fact: dict) -> str:
    vmin = _safe_float(fact.get("value_min"))
    vmax = _safe_float(fact.get("value_max"))
    unit = fact.get("unit_normalized") or fact.get("unit") or ""
    if vmin is not None and vmax is not None:
        val = f"{vmin:g}" if vmin == vmax else f"{vmin:g}–{vmax:g}"
    elif vmax is not None:
        val = f"≤{vmax:g}"
    elif vmin is not None:
        val = f"≥{vmin:g}"
    else:
        return fact.get("object", "")
    return f"{val} {unit}".strip()


def _analyze_tech_chain(entities: list[dict], facts: list[dict]) -> str:
    """Analyze technology chain completeness and highlight gaps."""
    entity_types = {e.get("type") for e in entities if e.get("type")}
    entity_names = {e.get("name") for e in entities if e.get("name")}

    # Check which chain elements are present
    has_material = "Material" in entity_types
    has_process = "Process" in entity_types
    has_equipment = "Equipment" in entity_types
    has_experiment = "Experiment" in entity_types
    has_property = "Property" in entity_types

    missing = []
    if has_process and not has_material:
        missing.append("Материалы (для процесса не указаны материалы)")
    if has_process and not has_equipment:
        missing.append("Оборудование (процесс без указания оборудования)")
    if has_experiment and not has_property:
        missing.append("Результаты/свойства (эксперимент без измеренных параметров)")
    if has_material and not has_process:
        missing.append("Процессы (материал без описания процесса переработки)")

    # Check for low-confidence facts
    low_conf = [f for f in facts if (f.get("confidence") or 0.5) < 0.6]
    low_conf_subjects = {f.get("subject") for f in low_conf if f.get("subject")}

    lines = []
    if missing:
        lines.append("⚠️ ОТСУТСТВУЮЩИЕ ПАРАМЕТРЫ В ЦЕПОЧКЕ:")
        for m in missing:
            lines.append(f"  - {m}")

    if low_conf_subjects:
        lines.append(f"ℹ️ ОСНОВАНО НА ОГРАНИЧЕННЫХ ДАННЫХ (confidence < 0.6): {', '.join(list(low_conf_subjects)[:5])}")

    return "\n".join(lines) if lines else ""


def build_context(retrieved: dict) -> str:
    parts = []
    entities = retrieved.get("entities") or []
    facts = retrieved.get("facts") or []
    chunks = retrieved.get("chunks") or []
    sources = retrieved.get("sources") or []

    if entities:
        entity_lines = []
        for e in entities[:20]:
            if not e.get("name") or not e.get("type"):
                continue
            aliases = f" (синонимы: {', '.join(e['aliases'])})" if e.get("aliases") else ""
            desc = e.get('description') or ''
            entity_lines.append(f"- {e['name']}{aliases} ({e['type']}): {desc}".strip())
        if entity_lines:
            parts.append("СУЩНОСТИ:\n" + "\n".join(entity_lines))

    if facts:
        # Find contradictions
        grouped_facts = {}
        for fact in facts[:30]:
            subj = fact.get("subject")
            pred = fact.get("predicate")
            if not subj or not pred:
                continue
            key = (subj, pred)
            if key not in grouped_facts:
                grouped_facts[key] = []
            grouped_facts[key].append(fact)

        fact_lines = []
        for (subj, pred), grp in grouped_facts.items():
            # Check for contradiction (different format_fact_value)
            values_seen = set()
            is_contradicting = False
            for f in grp:
                v = format_fact_value(f)
                if v and v not in values_seen:
                    if len(values_seen) > 0:
                        is_contradicting = True
                    values_seen.add(v)
            
            for fact in grp:
                value = format_fact_value(fact)
                geography = fact.get("geography", "unknown")
                time_val = fact.get("time")
                confidence = fact.get("confidence", 0.5)
                
                meta = []
                if geography and geography != "unknown": meta.append(f"гео: {geography}")
                if time_val: meta.append(f"время: {time_val}")
                meta.append(f"conf: {confidence}")
                meta_str = ", ".join(meta)
                
                contradiction_mark = " [ПРОТИВОРЕЧИЕ! ВАЖНО УЧЕСТЬ]" if is_contradicting else ""
                
                fact_lines.append(
                    f"- {subj} | {pred} = {value} [{meta_str}]{contradiction_mark}"
                )
        if fact_lines:
            parts.append("ФАКТЫ (ОБРАТИТЕ ВНИМАНИЕ НА ПРОТИВОРЕЧИЯ):\n" + "\n".join(fact_lines))

    if chunks:
        chunk_lines = [
            f"[{chunk.get('doc') or 'документ'}] {(chunk.get('text') or '')[:800]}"
            for chunk in chunks[:6]
            if chunk.get("text")
        ]
        if chunk_lines:
            parts.append("ФРАГМЕНТЫ ДОКУМЕНТОВ:\n" + "\n\n".join(chunk_lines))

    # Analyze technology chain completeness
    if entities and facts:
        chain_analysis = _analyze_tech_chain(entities, facts)
        if chain_analysis:
            parts.append(chain_analysis)

    if sources:
        parts.append("ИСТОЧНИКИ: " + ", ".join(sources[:20]))

    return "\n\n".join(parts) if parts else "Граф знаний пуст."
