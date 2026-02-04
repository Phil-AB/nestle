"""
Universal Document Type Detector

Detects document types based on configurable field patterns.
Supports ANY document type, not just trade documents.
"""

import yaml
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
from shared.utils.logger import setup_logger
from shared.utils.config import settings

logger = setup_logger(__name__)


def _load_document_types_config() -> Dict[str, Any]:
    """Load document types configuration."""
    config_path = Path(__file__).parent.parent.parent / "config" / "document_types.yaml"

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config  # Return full config, not just document_types
    except Exception as e:
        logger.error(f"Failed to load document types config: {e}")
        return {}


def get_configured_document_types() -> Set[str]:
    """
    Get list of all configured document types.

    Returns:
        Set of document type identifiers
    """
    config = _load_document_types_config()
    return set(config.get('document_types', {}).keys())


def get_default_document_type() -> str:
    """
    Get the default document type for unknown documents.

    Returns:
        Default document type identifier
    """
    config = _load_document_types_config()
    return config.get('default_document_type', 'document')


def detect_document_type_from_fields(fields: Dict[str, Any]) -> Optional[str]:
    """
    Detect document type based on field patterns using configurable rules.

    Args:
        fields: Extracted fields from document

    Returns:
        Detected document type or None if no match found
    """
    if not fields:
        return None

    config = _load_document_types_config()
    detection_rules = config.get('detection_rules', {})

    logger.debug(f"Detecting document type from fields: {list(fields.keys())}")

    # Score each document type based on matching fields
    scores = {}

    for doc_type, rules in detection_rules.items():
        score = 0
        required_fields = rules.get('required_fields', [])
        optional_fields = rules.get('optional_fields', [])
        excluded_fields = rules.get('excluded_fields', [])

        # Check required fields
        required_matches = sum(1 for field in required_fields if field in fields)
        if required_matches == len(required_fields) and required_matches > 0:
            score += required_matches * 10  # Weight required fields heavily

        # Check optional fields
        optional_matches = sum(1 for field in optional_fields if field in fields)
        score += optional_matches * 2  # Weight optional fields lightly

        # Penalize excluded fields
        excluded_matches = sum(1 for field in excluded_fields if field in fields)
        if excluded_matches > 0:
            score -= excluded_matches * 5

        scores[doc_type] = score

    # Return document type with highest score (if positive)
    if scores:
        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]

        logger.debug(f"Document type scores: {scores}")

        if best_score > 0:
            logger.info(f"Detected document type: {best_type} (score: {best_score})")
            return best_type

    logger.debug("No confident document type detection found")
    return None


def get_document_type_info(document_type: str) -> Dict[str, Any]:
    """
    Get information about a specific document type or all types.

    Args:
        document_type: Document type identifier or "all"

    Returns:
        Document type configuration or all configurations
    """
    config = _load_document_types_config()

    if document_type == "all":
        # Return all document types with their detection rules
        all_types = config.get('document_types', {})
        detection_rules = config.get('detection_rules', {})

        # Combine type info with detection rules
        result = {}
        for doc_type, type_info in all_types.items():
            result[doc_type] = {
                **type_info,
                "detection_rules": detection_rules.get(doc_type, {})
            }

        return result
    else:
        # Return specific document type
        type_info = config.get('document_types', {}).get(document_type, {})
        detection_rules = config.get('detection_rules', {}).get(document_type, {})

        return {
            **type_info,
            "detection_rules": detection_rules
        }


def validate_document_type(document_type: str) -> bool:
    """
    Validate if document type is configured.

    Args:
        document_type: Document type identifier

    Returns:
        True if valid, False otherwise
    """
    return document_type in get_configured_document_types()


# Cache configuration to avoid repeated file reads
_cached_config = None
_config_cache_time = None

def _get_cached_config() -> Dict[str, Any]:
    """Get cached configuration or reload if necessary."""
    global _cached_config, _config_cache_time

    import time
    current_time = time.time()

    # Reload config every 5 minutes or if not cached
    if _cached_config is None or (_config_cache_time and current_time - _config_cache_time > 300):
        _cached_config = _load_document_types_config()
        _config_cache_time = current_time

    return _cached_config