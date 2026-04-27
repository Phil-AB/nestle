"""
Reducto extraction schemas for all document types.

These schemas define the structure of data to extract from each document type
using Reducto's /extract endpoint.
"""

from typing import Dict, Any


# ==============================================================================
# INVOICE SCHEMA
# ==============================================================================

INVOICE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "invoice_number": {"type": "string"},
        "invoice_date": {"type": "string"},  # Reducto returns string, we parse as date
        "consignee_name": {"type": "string"},
        "consignee_address": {"type": "string"},
        "shipper_name": {"type": "string"},
        "shipper_address": {"type": "string"},
        "incoterm": {"type": "string"},
        "currency": {"type": "string"},
        "total_fob_value": {"type": "number"},
        "freight_value": {"type": ["number", "null"]},
        "insurance_value": {"type": ["number", "null"]},
        "total_invoice_value": {"type": "number"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "line_number": {"type": "number"},
                    "product_description": {"type": "string"},
                    "hs_code": {"type": "string"},
                    "country_of_origin": {"type": "string"},
                    "quantity": {"type": "number"},
                    "unit_of_measure": {"type": "string"},
                    "unit_price": {"type": "number"},
                    "total_value": {"type": "number"},
                }
            }
        }
    }
}


# ==============================================================================
# BILL OF ENTRY SCHEMA
# ==============================================================================

BOE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "declaration_number": {"type": "string"},
        "declaration_date": {"type": "string"},
        "consignee_name": {"type": "string"},
        "consignee_address": {"type": "string"},
        "shipper_name": {"type": "string"},
        "shipper_address": {"type": "string"},
        "fob_value": {"type": "number"},
        "freight_value": {"type": "number"},
        "insurance_value": {"type": "number"},
        "cif_value": {"type": "number"},
        "duty_value": {"type": ["number", "null"]},
        "currency": {"type": "string"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "line_number": {"type": "number"},
                    "product_description": {"type": "string"},
                    "hs_code": {"type": "string"},
                    "country_of_origin": {"type": "string"},
                    "quantity": {"type": "number"},
                    "unit_of_measure": {"type": "string"},
                    "unit_value": {"type": "number"},
                    "total_value": {"type": "number"},
                }
            }
        }
    }
}


# ==============================================================================
# PACKING LIST SCHEMA
# ==============================================================================

PACKING_LIST_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "packing_list_number": {"type": "string"},
        "packing_date": {"type": "string"},
        "consignee_name": {"type": "string"},
        "shipper_name": {"type": "string"},
        "total_packages": {"type": "number"},
        "total_gross_weight": {"type": "number"},
        "total_net_weight": {"type": "number"},
        "weight_unit": {"type": "string"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "line_number": {"type": "number"},
                    "product_description": {"type": "string"},
                    "quantity": {"type": "number"},
                    "unit_of_measure": {"type": "string"},
                    "package_number": {"type": "string"},
                    "gross_weight": {"type": "number"},
                    "net_weight": {"type": "number"},
                }
            }
        }
    }
}


# ==============================================================================
# CERTIFICATE OF ORIGIN SCHEMA
# ==============================================================================

COO_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "certificate_number": {"type": "string"},
        "issue_date": {"type": "string"},
        "issuing_authority": {"type": "string"},
        "exporter_name": {"type": "string"},
        "exporter_address": {"type": "string"},
        "consignee_name": {"type": "string"},
        "consignee_address": {"type": "string"},
        "country_of_origin": {"type": "string"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "line_number": {"type": "number"},
                    "product_description": {"type": "string"},
                    "hs_code": {"type": "string"},
                    "country_of_origin": {"type": "string"},
                    "quantity": {"type": "number"},
                }
            }
        }
    }
}


# ==============================================================================
# FREIGHT DOCUMENT SCHEMA
# ==============================================================================

FREIGHT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "contract_number": {"type": "string"},
        "contract_period_start": {"type": "string"},
        "contract_period_end": {"type": "string"},
        "base_freight": {"type": "number"},
        "bunker_adjustment": {"type": "number"},
        "total_freight": {"type": "number"},
        "currency": {"type": "string"},
        "transport_mode": {"type": "string"},
    }
}


# ==============================================================================
# TODO(human): Replace hardcoded schema registry with dynamic loading
# DYNAMIC SCHEMA REGISTRY FOR UNIVERSAL DOCUMENT SUPPORT
# ==============================================================================

def _get_dynamic_schema_registry() -> Dict[str, Dict[str, Any]]:
    """
    Dynamically load schemas for all configured document types.

    Returns:
        Dictionary mapping document types to their schemas
    """
    from shared.utils.document_type_detector import get_configured_document_types

    schemas = {}
    document_types = get_configured_document_types()

    # Add explicitly defined schemas (legacy trade documents)
    explicit_schemas = {
        "invoice": INVOICE_SCHEMA,
        "boe": BOE_SCHEMA,
        "bill_of_entry": BOE_SCHEMA,  # Alias
        "packing_list": PACKING_LIST_SCHEMA,
        "coo": COO_SCHEMA,
        "certificate_of_origin": COO_SCHEMA,  # Alias
        "freight": FREIGHT_SCHEMA,
        "freight_document": FREIGHT_SCHEMA,  # Alias
    }

    # Add explicit schemas for configured document types
    for doc_type, schema in explicit_schemas.items():
        if doc_type in document_types:
            schemas[doc_type] = schema

    # Generate basic schemas for document types without explicit schemas
    for doc_type in document_types:
        if doc_type not in schemas:
            schemas[doc_type] = _generate_basic_schema(doc_type)

    return schemas

def _generate_basic_schema(document_type: str) -> Dict[str, Any]:
    """
    Generate a basic extraction schema for any document type.

    Args:
        document_type: Document type identifier

    Returns:
        Basic schema for the document type
    """
    # Generic schema that captures common document fields
    return {
        "type": "object",
        "properties": {
            "document_number": {
                "type": "string",
                "description": f"{document_type.replace('_', ' ').title()} number"
            },
            "document_date": {
                "type": "string",
                "description": f"{document_type.replace('_', ' ').title()} date"
            },
            "title": {
                "type": "string",
                "description": f"Document title or subject"
            },
            "parties": {
                "type": "array",
                "description": "Involved parties (names, organizations)",
                "items": {"type": "string"}
            },
            "amounts": {
                "type": "array",
                "description": "Monetary values",
                "items": {"type": "string"}
            },
            "dates": {
                "type": "array",
                "description": "Important dates",
                "items": {"type": "string"}
            },
            "key_terms": {
                "type": "array",
                "description": "Key terms and conditions",
                "items": {"type": "string"}
            }
        },
        "required": ["document_number"]
    }

# Cache loaded schemas for performance
_cached_schema_registry = None

def get_schema_registry() -> Dict[str, Dict[str, Any]]:
    """Get the schema registry, using cache if available."""
    global _cached_schema_registry

    if _cached_schema_registry is None:
        _cached_schema_registry = _get_dynamic_schema_registry()

    return _cached_schema_registry

# For backward compatibility
SCHEMA_REGISTRY = get_schema_registry()


def get_schema(document_type: str) -> Dict[str, Any]:
    """
    Get extraction schema for any document type.

    Args:
        document_type: Type of document (any configured type)

    Returns:
        Extraction schema for the document type

    Raises:
        ValueError: If document type is not configured
    """
    # Get dynamic schema registry
    schema_registry = get_schema_registry()

    # Try to find schema (case-insensitive)
    schema = schema_registry.get(document_type.lower())

    if not schema:
        # Try common aliases
        aliases = {
            "bill_of_entry": "boe",
            "certificate_of_origin": "coo",
            "freight_document": "freight",
            "purchase_order": "purchase_order",
            "power_of_attorney": "power_of_attorney",
        }

        doc_type_key = aliases.get(document_type.lower(), document_type.lower())
        schema = schema_registry.get(doc_type_key)

    if not schema:
        # Generate basic schema for unknown types (backward compatibility)
        from shared.utils.logger import setup_logger
        logger = setup_logger(__name__)
        logger.warning(f"No schema found for document type '{document_type}', generating basic schema")
        return _generate_basic_schema(document_type)

    return schema
