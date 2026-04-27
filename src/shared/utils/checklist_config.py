"""
Checklist configuration loader.

Loads import checklist from config/checklist.yaml and provides
field lookups per document type for focused extraction mode.
"""

import yaml
from functools import lru_cache
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


# Maps internal document_type names to the keys used in checklist.yaml
_DOC_TYPE_ALIASES: Dict[str, str] = {
    "bill_of_entry": "boe",
    "airway_bill": "bill_of_lading",
}


class ChecklistConfig:
    """Load and query the import checklist configuration."""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "checklist.yaml"

        self.config_path = Path(config_path)
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Checklist configuration not found: {self.config_path}"
            )

        with open(self.config_path, "r") as f:
            config = yaml.safe_load(f)

        logger.info(f"Loaded checklist config from: {self.config_path}")
        return config

    def get_checklist_fields(
        self, document_type: str
    ) -> Tuple[List[str], List[str]]:
        """
        Get header fields and item-level fields from the checklist
        for a given document type.

        Args:
            document_type: e.g. "invoice", "packing_list", "boe", "bill_of_lading"

        Returns:
            Tuple of (header_fields, item_fields) — each a flat list of field names.
        """
        doc_type = document_type.lower().strip().replace("-", "_").replace(" ", "_")
        doc_type = _DOC_TYPE_ALIASES.get(doc_type, doc_type)
        header_fields: List[str] = []
        item_fields: List[str] = []

        for item in self._config.get("checklist", []):
            fields_by_doc = item.get("fields", {})
            doc_fields = fields_by_doc.get(doc_type, [])
            if not doc_fields:
                continue

            if item.get("item_level", False):
                for f in doc_fields:
                    if f not in item_fields:
                        item_fields.append(f)
            else:
                for f in doc_fields:
                    if f not in header_fields:
                        header_fields.append(f)

        logger.debug(
            f"Checklist fields for '{doc_type}': "
            f"{len(header_fields)} header, {len(item_fields)} item"
        )
        return header_fields, item_fields

    def get_extraction_hints(self, document_type: str) -> Dict[str, str]:
        """
        Return per-field extraction hints for a document type.

        Reads ``extraction_hints`` blocks from checklist items and maps each
        field name for the given document type to its hint string.

        Args:
            document_type: e.g. "invoice", "packing_list", "bill_of_lading"

        Returns:
            Dict mapping field_name → hint string.
        """
        doc_type = document_type.lower().strip().replace("-", "_").replace(" ", "_")
        doc_type = _DOC_TYPE_ALIASES.get(doc_type, doc_type)
        hints: Dict[str, str] = {}

        for item in self._config.get("checklist", []):
            item_hints = item.get("extraction_hints", {})
            hint_text = item_hints.get(doc_type, "")
            if not hint_text:
                continue
            fields_by_doc = item.get("fields", {})
            doc_fields = fields_by_doc.get(doc_type, [])
            for field_name in doc_fields:
                if field_name not in hints:
                    hints[field_name] = hint_text

        return hints

    def get_all_checklist_items(self) -> List[Dict[str, Any]]:
        """Return the raw checklist items list."""
        return self._config.get("checklist", [])

    def get_metadata(self) -> Dict[str, str]:
        """Return checklist metadata (name, version, description)."""
        return {
            "name": self._config.get("name", ""),
            "version": self._config.get("version", ""),
            "description": self._config.get("description", ""),
        }


@lru_cache()
def get_checklist_config(config_path: Optional[str] = None) -> ChecklistConfig:
    """Get cached checklist configuration instance."""
    return ChecklistConfig(config_path)
