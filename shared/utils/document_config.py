"""
Document configuration loader.

Loads and provides access to document extraction and storage configuration.
"""

import yaml
from pathlib import Path
from typing import Dict, List, Any
from functools import lru_cache

from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class DocumentConfig:
    """Document configuration manager."""

    def __init__(self, config_path: str | None = None):
        """
        Initialize document configuration.

        Args:
            config_path: Path to configuration file. Defaults to config/document_config.yaml
        """
        if config_path is None:
            # Default to config/document_config.yaml from project root
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "document_config.yaml"

        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, "r") as f:
                self._config = yaml.safe_load(f)
            logger.info(f"Loaded document configuration from {self.config_path}")
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {self.config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing configuration file: {e}")
            raise

    def get_required_fields(self, document_type: str) -> List[str]:
        """
        Get required fields for a document type.

        Args:
            document_type: Document type (invoice, boe, packing_list, coo, freight)

        Returns:
            List of required field names
        """
        doc_config = self._config.get(document_type, {})
        return doc_config.get("required_fields", [])

    def get_optional_fields(self, document_type: str) -> List[str]:
        """
        Get optional fields for a document type.

        Args:
            document_type: Document type

        Returns:
            List of optional field names
        """
        doc_config = self._config.get(document_type, {})
        return doc_config.get("optional_fields", [])

    def get_item_required_fields(self, document_type: str) -> List[str]:
        """
        Get required fields for document line items.

        Args:
            document_type: Document type

        Returns:
            List of required item field names
        """
        doc_config = self._config.get(document_type, {})
        return doc_config.get("item_required_fields", [])

    def get_item_optional_fields(self, document_type: str) -> List[str]:
        """
        Get optional fields for document line items.

        Args:
            document_type: Document type

        Returns:
            List of optional item field names
        """
        doc_config = self._config.get(document_type, {})
        return doc_config.get("item_optional_fields", [])

    def get_unique_field(self, document_type: str) -> str | None:
        """
        Get the unique identifier field for a document type.

        Args:
            document_type: Document type

        Returns:
            Unique field name (e.g., 'invoice_number', 'declaration_number')
        """
        doc_config = self._config.get(document_type, {})
        return doc_config.get("unique_field")

    def get_model_name(self, document_type: str) -> str | None:
        """
        Get the SQLAlchemy model class name for a document type.

        Args:
            document_type: Document type

        Returns:
            Model class name (e.g., 'Invoice', 'BillOfEntry')
        """
        doc_config = self._config.get(document_type, {})
        return doc_config.get("model_name")

    def get_items_model_name(self, document_type: str) -> str | None:
        """
        Get the SQLAlchemy items model class name for a document type.

        Args:
            document_type: Document type

        Returns:
            Items model class name (e.g., 'InvoiceItem', 'BOEItem') or None
        """
        doc_config = self._config.get(document_type, {})
        return doc_config.get("items_model_name")

    def get_table_name(self, document_type: str) -> str | None:
        """
        Get the database table name for a document type.

        Args:
            document_type: Document type

        Returns:
            Table name (e.g., 'invoices', 'bill_of_entries')
        """
        doc_config = self._config.get(document_type, {})
        return doc_config.get("table_name")

    def get_parent_fk_field(self, document_type: str) -> str | None:
        """
        Get the foreign key field name that links items to parent document.

        Args:
            document_type: Document type

        Returns:
            FK field name (e.g., 'invoice_id', 'boe_id') or None
        """
        doc_config = self._config.get(document_type, {})
        return doc_config.get("parent_fk_field")

    def has_items(self, document_type: str) -> bool:
        """
        Check if document type has line items.

        Args:
            document_type: Document type

        Returns:
            True if document has items, False otherwise
        """
        doc_config = self._config.get(document_type, {})
        return doc_config.get("has_items", False)

    def get_min_items(self, document_type: str) -> int:
        """
        Get minimum required items for a document.

        Args:
            document_type: Document type

        Returns:
            Minimum items count
        """
        doc_config = self._config.get(document_type, {})
        return doc_config.get("min_items", 0)

    def get_extraction_status_values(self) -> Dict[str, str]:
        """
        Get extraction status values.

        Returns:
            Dict with status values (complete, incomplete, failed)
        """
        return self._config.get("extraction_status", {})

    def get_confidence_thresholds(self) -> Dict[str, float]:
        """
        Get confidence thresholds.

        Returns:
            Dict with threshold values (high, medium, low)
        """
        return self._config.get("confidence_thresholds", {})

    def get_date_formats(self) -> List[str]:
        """
        Get date format strings for parsing.

        Returns:
            List of date format strings
        """
        transformation = self._config.get("transformation", {})
        return transformation.get("date_formats", [])

    def get_decimal_fields(self) -> List[str]:
        """
        Get list of fields that should be converted to Decimal.

        Returns:
            List of decimal field names
        """
        transformation = self._config.get("transformation", {})
        return transformation.get("decimal_fields", [])

    def get_integer_fields(self) -> List[str]:
        """
        Get list of fields that should be converted to integers.

        Returns:
            List of integer field names
        """
        transformation = self._config.get("transformation", {})
        return transformation.get("integer_fields", [])

    def get_currency_mapping(self) -> Dict[str, str]:
        """
        Get currency normalization mapping.

        Returns:
            Dict mapping currency symbols/codes to standard codes
        """
        transformation = self._config.get("transformation", {})
        return transformation.get("currency_mapping", {})

    def get_defaults(self) -> Dict[str, Any]:
        """
        Get default values for missing data.

        Returns:
            Dict of default values
        """
        transformation = self._config.get("transformation", {})
        return transformation.get("defaults", {})

    def should_update_on_duplicate(self) -> bool:
        """
        Check if duplicate documents should be updated.

        Returns:
            True if duplicates should update existing records
        """
        storage = self._config.get("storage", {})
        return storage.get("update_on_duplicate", True)

    def should_store_raw_data(self) -> bool:
        """
        Check if raw Reducto JSON should be stored.

        Returns:
            True if raw data should be stored
        """
        storage = self._config.get("storage", {})
        return storage.get("store_raw_data", True)

    def get_transaction_timeout(self) -> int:
        """
        Get transaction timeout in seconds.

        Returns:
            Timeout value in seconds
        """
        storage = self._config.get("storage", {})
        return storage.get("transaction_timeout", 30)

    def get_all_document_types(self) -> List[str]:
        """
        Get list of all configured document types.

        Returns:
            List of document type names (e.g., ['invoice', 'boe', 'packing_list'])
        """
        # Filter out non-document-type keys (extraction_status, confidence_thresholds, etc.)
        excluded_keys = {
            'extraction_status',
            'confidence_thresholds',
            'transformation',
            'storage'
        }
        
        doc_types = [
            key for key in self._config.keys()
            if key not in excluded_keys and isinstance(self._config[key], dict)
        ]
        
        return doc_types

    def get_document_type_config(self, document_type: str) -> Dict[str, Any]:
        """
        Get the complete configuration for a document type.

        Args:
            document_type: Document type

        Returns:
            Complete document type configuration dictionary

        Raises:
            ValueError: If document type not found
        """
        if document_type not in self._config:
            raise ValueError(
                f"Document type '{document_type}' not found in configuration. "
                f"Available types: {', '.join(self.get_all_document_types())}"
            )
        
        return self._config[document_type]


@lru_cache(maxsize=1)
def get_document_config() -> DocumentConfig:
    """
    Get singleton instance of DocumentConfig.

    Returns:
        DocumentConfig instance
    """
    return DocumentConfig()
