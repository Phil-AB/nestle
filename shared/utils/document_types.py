"""
Document types configuration loader.

Loads document types from config/document_types.yaml.
"""

import yaml
from functools import lru_cache
from typing import Dict, Any, List
from pathlib import Path

from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class DocumentTypesConfig:
    """Document types configuration loader and accessor."""

    def __init__(self, config_path: str = None):
        """
        Initialize document types configuration.

        Args:
            config_path: Path to document_types.yaml (defaults to config/document_types.yaml)
        """
        if config_path is None:
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "document_types.yaml"

        self.config_path = Path(config_path)
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """
        Load document types configuration from YAML file.

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If YAML is invalid
        """
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Document types configuration not found: {self.config_path}"
            )

        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)

            logger.info(f"Loaded document types configuration from: {self.config_path}")
            return config

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse document types YAML: {e}")
            raise

    def get_all_document_types(self) -> List[str]:
        """
        Get list of all configured document type IDs.

        Returns:
            List of document type IDs (e.g., ['invoice', 'boe', 'packing_list'])
        """
        document_types = self._config.get('document_types', {})
        return list(document_types.keys())

    def get_document_type_info(self, doc_type: str) -> Dict[str, Any]:
        """
        Get information about a document type.

        Args:
            doc_type: Document type ID

        Returns:
            Document type configuration dict

        Raises:
            ValueError: If document type not found
        """
        document_types = self._config.get('document_types', {})

        if doc_type not in document_types:
            raise ValueError(
                f"Document type '{doc_type}' not found in config. "
                f"Available types: {', '.join(document_types.keys())}"
            )

        return document_types[doc_type]

    def get_display_name(self, doc_type: str) -> str:
        """
        Get display name for a document type.

        Args:
            doc_type: Document type ID

        Returns:
            Display name (e.g., "Commercial Invoice")
        """
        info = self.get_document_type_info(doc_type)
        return info.get('display_name', doc_type.replace('_', ' ').title())

    def get_description(self, doc_type: str) -> str:
        """
        Get description for a document type.

        Args:
            doc_type: Document type ID

        Returns:
            Description text
        """
        info = self.get_document_type_info(doc_type)
        return info.get('description', '')

    def get_category(self, doc_type: str) -> str:
        """
        Get category for a document type.

        Args:
            doc_type: Document type ID

        Returns:
            Category ID (e.g., 'financial', 'shipping')
        """
        info = self.get_document_type_info(doc_type)
        return info.get('category', 'other')

    def get_categories(self) -> Dict[str, str]:
        """
        Get all categories.

        Returns:
            Dictionary mapping category ID to display name
        """
        return self._config.get('categories', {})

    def get_types_by_category(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Get document types grouped by category.

        Returns:
            Dictionary mapping category to list of document type info
        """
        grouped = {}
        categories = self.get_categories()

        # Initialize all categories
        for cat_id, cat_name in categories.items():
            grouped[cat_name] = []

        # Group document types
        for doc_type in self.get_all_document_types():
            info = self.get_document_type_info(doc_type)
            category_id = info.get('category', 'other')
            category_name = categories.get(category_id, 'Other')

            if category_name not in grouped:
                grouped[category_name] = []

            grouped[category_name].append({
                'id': doc_type,
                'display_name': info.get('display_name', doc_type),
                'description': info.get('description', '')
            })

        return grouped

    def document_type_exists(self, doc_type: str) -> bool:
        """
        Check if a document type exists in configuration.

        Args:
            doc_type: Document type ID

        Returns:
            True if exists, False otherwise
        """
        document_types = self._config.get('document_types', {})
        return doc_type in document_types


@lru_cache()
def get_document_types_config() -> DocumentTypesConfig:
    """
    Get cached document types configuration instance.

    Returns:
        DocumentTypesConfig singleton
    """
    return DocumentTypesConfig()
