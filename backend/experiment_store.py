"""Experiment storage — parameters as properties, source tracking."""
import time

# Experiment parameters are stored as properties on the Experiment node,
# NOT as separate nodes. This module provides helpers for Cypher queries.

EXPERIMENT_PARAMS = {
    "temperature": None,      # float or str with unit
    "pressure": None,
    "time": None,
    "atmosphere": None,
    "cooling_rate": None,
    "heating_rate": None,
    "gas": None,
    "sample_mass": None,
    "ph": None,
    "voltage": None,
    "current_density": None,
    "flow_rate": None,
    "concentration": None,
}

# ── Cypher query templates ─────────────────────────────────────

CREATE_EXPERIMENT = """
CREATE (e:Experiment {
    key: $key,
    name: $name,
    description: $description,
    temperature: $temperature,
    pressure: $pressure,
    time: $time,
    atmosphere: $atmosphere,
    cooling_rate: $cooling_rate,
    heating_rate: $heating_rate,
    gas: $gas,
    sample_mass: $sample_mass,
    ph: $ph,
    voltage: $voltage,
    current_density: $current_density,
    flow_rate: $flow_rate,
    concentration: $concentration,
    source_document_id: $source_document_id,
    source_page: $source_page,
    source_chunk_id: $source_chunk_id,
    source_original_text: $source_original_text,
    confidence: $confidence,
    created_at: $created_at
})
RETURN e
"""

MERGE_EXPERIMENT = """
MERGE (e:Experiment {key: $key})
ON CREATE SET
    e.name = $name,
    e.description = $description,
    e.temperature = $temperature,
    e.pressure = $pressure,
    e.time = $time,
    e.atmosphere = $atmosphere,
    e.cooling_rate = $cooling_rate,
    e.heating_rate = $heating_rate,
    e.gas = $gas,
    e.sample_mass = $sample_mass,
    e.ph = $ph,
    e.voltage = $voltage,
    e.current_density = $current_density,
    e.flow_rate = $flow_rate,
    e.concentration = $concentration,
    e.source_document_id = $source_document_id,
    e.source_page = $source_page,
    e.source_chunk_id = $source_chunk_id,
    e.source_original_text = $source_original_text,
    e.confidence = $confidence,
    e.created_at = $created_at
RETURN e
"""

# ── Helper functions ───────────────────────────────────────────

def build_experiment_params(properties: dict) -> dict:
    """Build Neo4j-compatible params dict, filling defaults."""
    params = {k: None for k in EXPERIMENT_PARAMS}
    if properties:
        for k, v in properties.items():
            key = k.strip().lower().replace(" ", "_")
            if key in params:
                params[key] = str(v) if v is not None else None
    return params


def build_experiment_cypher(
    key: str,
    name: str,
    description: str = "",
    properties: dict | None = None,
    source: dict | None = None,
    confidence: float = 0.5,
) -> tuple[str, dict]:
    """Return (cypher_query, params_dict) for creating an Experiment node."""
    params = build_experiment_params(properties)
    params.update({
        "key": key,
        "name": name,
        "description": description,
        "source_document_id": (source or {}).get("document_id"),
        "source_page": (source or {}).get("page"),
        "source_chunk_id": (source or {}).get("chunk_id"),
        "source_original_text": (source or {}).get("original_text"),
        "confidence": confidence,
        "created_at": time.time(),
    })
    return MERGE_EXPERIMENT, params


# ── In-memory demo store ───────────────────────────────────────

class ExperimentStore:
    """In-memory experiment storage for demo mode."""

    def __init__(self):
        self._experiments: dict[str, dict] = {}
        self._entities: list[dict] = []
        self._relations: list[dict] = []

    def add_experiment(self, exp: dict) -> str:
        key = exp.get("key", f"exp-{len(self._experiments)}")
        self._experiments[key] = exp
        return key

    def get_experiment(self, key: str) -> dict | None:
        return self._experiments.get(key)

    def list_experiments(self) -> list[dict]:
        return list(self._experiments.values())

    def stats(self) -> dict:
        return {
            "experiments": len(self._experiments),
            "entities": len(self._entities),
            "relations": len(self._relations),
        }


DEMO_STORE = ExperimentStore()
