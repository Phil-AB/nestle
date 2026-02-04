"""
Type definitions for the PDF Population module.

This module defines all types used throughout the population system.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from pathlib import Path


@dataclass
class PopulationResult:
    """
    Result of a PDF form population operation.

    Attributes:
        success: Whether population succeeded
        output_path: Path to populated PDF file (if successful)
        form_id: ID of the form template used
        metadata: Additional information about the operation
        error: Error message (if failed)
    """
    success: bool
    form_id: str
    output_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "success": self.success,
            "form_id": self.form_id,
            "output_path": self.output_path,
            "metadata": self.metadata,
            "error": self.error
        }


@dataclass
class FormConfig:
    """
    Configuration for a PDF form template.

    Attributes:
        form_id: Unique identifier for the form
        form_name: Human-readable form name
        template_path: Path to fillable PDF template
        mapping_config: Path to field mapping configuration
        merge_strategy: Strategy for merging multi-document data
    """
    form_id: str
    form_name: str
    template_path: Path
    mapping_config: Path
    merge_strategy: str = "prioritized"


@dataclass
class FieldMapping:
    """
    Mapping configuration for a single field.

    Attributes:
        pdf_field_name: Name of field in PDF form
        source: Source path in database data (dot notation)
        fallback: Alternative source paths to try
        default: Default value if source not found
        transformation: Name of transformation to apply
        transformation_params: Parameters for transformation
    """
    pdf_field_name: str
    source: str
    fallback: Optional[list] = None
    default: Optional[Any] = None
    transformation: Optional[str] = None
    transformation_params: Optional[Dict[str, Any]] = None
