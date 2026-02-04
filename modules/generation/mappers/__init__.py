"""
Data mappers for generation module.

Mappers transform source data to template format.
"""

# Import all mappers to trigger self-registration
from modules.generation.mappers.field_mapper import FieldMapper

__all__ = [
    "FieldMapper",
]
