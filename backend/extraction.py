"""Compatibility wrapper around the active LLM client."""

from llm_client import LLMError, answer_question, check_health, extract_graph, list_models

__all__ = [
    "LLMError",
    "answer_question",
    "check_health",
    "extract_graph",
    "list_models",
]
