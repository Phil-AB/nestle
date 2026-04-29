"""
Registry mapping document types to their specialised extractor classes.

Every document type MUST have a registered specialist.  If the registry does
not contain an entry for a document type, extraction will raise
MissingExtractorError — this is intentional.  The error surfaces clearly in
logs and API responses so a developer knows exactly which extractor to create.

The old generic 4-step pipeline (section-parse → table-parse → block-parse →
resolve) is no longer used anywhere.

────────────────────────────────────────────────────────────────────────────
HOW TO ADD A NEW DOCUMENT TYPE
────────────────────────────────────────────────────────────────────────────
Option A — register in code:
  1. Create modules/extraction/parser/extractors/my_doc_extractor.py
  2. Subclass BaseDocumentExtractor, implement extract()
  3. Add an entry to _BUILT_IN_REGISTRY below

Option B — register via config (no code change for registration):
  In config/document_config.yaml, under the document-type key add:
      extractor_class: "modules.extraction.parser.extractors.my_doc_extractor.MyDocExtractor"
────────────────────────────────────────────────────────────────────────────
"""

import logging
from typing import Dict, Optional, Type

from .base import BaseDocumentExtractor

logger = logging.getLogger(__name__)


class MissingExtractorError(Exception):
    """
    Raised when no specialised extractor is registered for a document type.

    Resolution: create a new extractor in
    modules/extraction/parser/extractors/ and register it here or in
    config/document_config.yaml.
    """


# Built-in registry: normalised document_type → dotted class path
_BUILT_IN_REGISTRY: Dict[str, str] = {
    "invoice":
        "modules.extraction.parser.extractors.invoice_extractor.InvoiceExtractor",
    "packing_list":
        "modules.extraction.parser.extractors.packing_list_extractor.PackingListExtractor",
    "bill_of_lading":
        "modules.extraction.parser.extractors.bol_extractor.BOLExtractor",
    "airway_bill":
        "modules.extraction.parser.extractors.airway_bill_extractor.AirwayBillExtractor",
    "freight_manifest":
        "modules.extraction.parser.extractors.freight_manifest_extractor.FreightManifestExtractor",
    "bill_of_entry":
        "modules.extraction.parser.extractors.boe_extractor.BOEExtractor",
    "boe":
        "modules.extraction.parser.extractors.boe_extractor.BOEExtractor",
    "certificate_of_origin":
        "modules.extraction.parser.extractors.certificate_of_origin_extractor.CertificateOfOriginExtractor",
    "coo":
        "modules.extraction.parser.extractors.certificate_of_origin_extractor.CertificateOfOriginExtractor",
    "sanitary_certificate":
        "modules.extraction.parser.extractors.sanitary_cert_extractor.SanitaryCertExtractor",
    "certificate_of_analysis":
        "modules.extraction.parser.extractors.coa_extractor.COAExtractor",
    "coa":
        "modules.extraction.parser.extractors.coa_extractor.COAExtractor",
}


class DocumentExtractorRegistry:
    """
    Resolves document type → specialised extractor instance.

    Raises MissingExtractorError if no specialist is registered.
    """

    def __init__(self, llm_extraction, llm_resolution):
        self._llm_extraction = llm_extraction
        self._llm_resolution = llm_resolution
        self._instances: Dict[str, BaseDocumentExtractor] = {}
        self._registry: Dict[str, str] = dict(_BUILT_IN_REGISTRY)

        # Load overrides / additions from document_config.yaml
        self._load_config_overrides()

    def _load_config_overrides(self) -> None:
        """
        Merge extractor_class entries from document_config.yaml into the
        registry.  Allows new extractors to be wired in without touching this
        file.
        """
        try:
            from shared.utils.config import get_config
            doc_config = get_config("document_config")
            if not doc_config:
                return
            for doc_type, type_config in doc_config.items():
                if isinstance(type_config, dict) and "extractor_class" in type_config:
                    normalised = self._normalise(doc_type)
                    self._registry[normalised] = type_config["extractor_class"]
                    logger.debug(
                        f"Registry: {normalised} → {type_config['extractor_class']} (config)"
                    )
        except Exception as e:
            logger.debug(f"Could not load extractor overrides from config: {e}")

    def get(self, document_type: str) -> BaseDocumentExtractor:
        """
        Return the specialist extractor for document_type.

        Raises:
            MissingExtractorError — if no specialist is registered, with a
                clear message indicating which extractor needs to be created.
        """
        doc_type = self._normalise(document_type)

        if doc_type in self._instances:
            return self._instances[doc_type]

        class_path = self._registry.get(doc_type)
        if not class_path:
            raise MissingExtractorError(
                f"No specialised extractor registered for document type '{doc_type}'. "
                f"Create one at modules/extraction/parser/extractors/{doc_type}_extractor.py "
                f"(subclass BaseDocumentExtractor, implement extract()) and register it in "
                f"_BUILT_IN_REGISTRY or in config/document_config.yaml under "
                f"'{doc_type}.extractor_class'."
            )

        try:
            extractor_class = self._import_class(class_path)
            instance = extractor_class(self._llm_extraction, self._llm_resolution)
            self._instances[doc_type] = instance
            logger.info(f"Registry: loaded {class_path} for '{doc_type}'")
            return instance
        except MissingExtractorError:
            raise
        except Exception as e:
            raise MissingExtractorError(
                f"Failed to load extractor '{class_path}' for '{doc_type}': {e}"
            ) from e

    @staticmethod
    def _normalise(document_type: str) -> str:
        return document_type.lower().replace("-", "_").replace(" ", "_")

    @staticmethod
    def _import_class(class_path: str) -> Type[BaseDocumentExtractor]:
        """Dynamically import a class from a dotted module path."""
        module_path, class_name = class_path.rsplit(".", 1)
        import importlib
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
