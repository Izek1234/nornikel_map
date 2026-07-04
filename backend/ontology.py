"""Fixed ontology for materials science domain.
Defines allowed node types, relationship types, and validation."""

# ── Allowed node types ─────────────────────────────────────────

NODE_TYPES = frozenset({
    "Material",
    "Process",
    "Equipment",
    "Property",
    "Experiment",
    "Publication",
    "Expert",
    "Facility",
})

# ── Allowed relationship types ─────────────────────────────────

RELATION_TYPES = frozenset({
    "USES_MATERIAL",
    "USES_PROCESS",
    "USES_EQUIPMENT",
    "PERFORMED_AT",
    "OPERATES_AT_CONDITION",
    "VALIDATED_BY",
    "DESCRIBES",
    "PRODUCES_OUTPUT",
    "CONTRADICTS",
})

# ── Relationship source → target constraints ───────────────────

RELATION_CONSTRAINTS: dict[str, str] = {
    "USES_MATERIAL": "Process",       # source must be Experiment or Process
    "USES_PROCESS": "Process",
    "USES_EQUIPMENT": "Equipment",
    "PERFORMED_AT": "Facility",
    "OPERATES_AT_CONDITION": "Property",  # Equipment operates under Property conditions
    "VALIDATED_BY": "Expert",
    "DESCRIBES": "Experiment",        # source must be Publication
    "PRODUCES_OUTPUT": "Property",
    "CONTRADICTS": "Experiment",      # source/target can be Experiment or Publication
}

RELATION_SOURCES: dict[str, frozenset[str]] = {
    "USES_MATERIAL": frozenset({"Experiment", "Process"}),
    "USES_PROCESS": frozenset({"Experiment"}),
    "USES_EQUIPMENT": frozenset({"Process"}),
    "PERFORMED_AT": frozenset({"Experiment"}),
    "OPERATES_AT_CONDITION": frozenset({"Equipment", "Process"}),
    "VALIDATED_BY": frozenset({"Experiment"}),
    "DESCRIBES": frozenset({"Publication"}),
    "PRODUCES_OUTPUT": frozenset({"Experiment"}),
    "CONTRADICTS": frozenset({"Experiment", "Publication"}),
}

RELATION_TARGETS: dict[str, frozenset[str]] = {
    "USES_MATERIAL": frozenset({"Material"}),
    "USES_PROCESS": frozenset({"Process"}),
    "USES_EQUIPMENT": frozenset({"Equipment"}),
    "PERFORMED_AT": frozenset({"Facility"}),
    "OPERATES_AT_CONDITION": frozenset({"Property"}),
    "VALIDATED_BY": frozenset({"Expert"}),
    "DESCRIBES": frozenset({"Experiment"}),
    "PRODUCES_OUTPUT": frozenset({"Property"}),
    "CONTRADICTS": frozenset({"Experiment", "Publication"}),
}

# ── Experiment parameters that MUST be stored as properties ────

EXPERIMENT_PARAM_PROPERTIES = frozenset({
    "temperature", "pressure", "time", "atmosphere", "cooling_rate",
    "heating_rate", "gas", "sample_mass", "ph", "voltage",
    "current_density", "flow_rate", "concentration",
})

# ── Validation functions ───────────────────────────────────────

def validate_node_type(etype: str) -> str:
    """Return canonical type or map to nearest allowed type."""
    e = etype.strip().title()
    if e in NODE_TYPES:
        return e
    # Fuzzy mapping for common variations
    mapping = {
        "Material": {"Materials", "Substance", "Substances", "Chemical", "Compound", "Alloy", "Mineral"},
        "Process": {"Method", "Technique", "Technology", "Operation", "Treatment"},
        "Equipment": {"Apparatus", "Device", "Instrument", "Machine", "Reactor", "Furnace"},
        "Property": {"Parameter", "Characteristic", "Attribute", "Metric", "Value"},
        "Experiment": {"Test", "Trial", "Run", "Measurement", "Analysis", "Protocol"},
        "Publication": {"Paper", "Article", "Report", "Patent", "Thesis", "Document"},
        "Expert": {"Researcher", "Scientist", "Author", "Engineer", "Investigator"},
        "Facility": {"Lab", "Laboratory", "Plant", "Factory", "Site", "Mine"},
    }
    for canon, variants in mapping.items():
        if e in variants or e.lower() in {v.lower() for v in variants}:
            return canon
    # Default to Property if unrecognized
    return "Property"


def validate_relation(rel_type: str, source_type: str, target_type: str) -> str | None:
    """Validate and normalize a relation. Returns None if invalid."""
    rt = rel_type.upper().strip().replace(" ", "_")
    if rt not in RELATION_TYPES:
        return None
    src_ok = source_type in RELATION_SOURCES.get(rt, frozenset())
    tgt_ok = target_type in RELATION_TARGETS.get(rt, frozenset())
    if not (src_ok and tgt_ok):
        return None
    return rt


def extract_experiment_properties(facts: list[dict]) -> dict:
    """Extract experiment parameters that should be properties, not nodes."""
    import postprocess
    props = {}
    for f in facts:
        pred = (f.get("predicate") or "").strip().lower()
        if pred in EXPERIMENT_PARAM_PROPERTIES:
            props[pred] = postprocess.format_fact_value(f)
    return props

def classify_domain(name: str) -> str:
    """Classify document domain by its name."""
    name_lower = name.lower()
    domains = {
        "hydrometallurgy": ["гидрометалл", "hydrometallurg", "выщелач", "раствор"],
        "pyrometallurgy": ["пирометалл", "pyrometallurg", "плавк", "шлак", "концентрат"],
        "ecology": ["эколог", "ecolog", "выброс", "загрязн", "мониторинг"],
        "waste": ["отход", "waste", "переработ", "хвост", "шлам", "гипс"],
    }
    for dom, keywords in domains.items():
        if any(kw in name_lower for kw in keywords):
            return dom
    return "general"
