"""
Abstract base interface for document parsers.
This allows swapping between different parser providers (Reducto, Azure, Tesseract, etc.)
without affecting other modules.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List, Optional


@dataclass
class ParsedDocument:
    """
    Common structure for parsed documents across all providers.
    """
    document_id: str
    document_type: str
    raw_text: str
    structured_data: Dict[str, Any]
    tables: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    language: Optional[str] = None
    page_count: Optional[int] = None


class IParserProvider(ABC):
    """
    Abstract interface for document parsing providers.

    Any parser implementation (Reducto, Google Document AI, AWS Textract, etc.)
    must implement this interface.

    The provider is responsible for:
    1. Translating universal config schema to provider-specific format
    2. Extracting fields from documents using provider's API
    3. Normalizing provider response back to universal format
    """

    @abstractmethod
    async def parse_document(
        self,
        file_bytes: bytes,
        file_name: str,
        document_type: str,
        **options
    ) -> ParsedDocument:
        """
        Parse a document and return structured data.

        Args:
            file_bytes: Document content as bytes
            file_name: Original file name (for extension detection)
            document_type: Type of document (invoice, boe, packing_list, coo, freight)
            **options: Additional provider-specific options

        Returns:
            ParsedDocument with extracted content

        Raises:
            ParserException: If parsing fails
        """
        pass

    @abstractmethod
    async def extract_fields(
        self,
        file_bytes: bytes,
        schema: Dict[str, Any],
        **options
    ) -> Dict[str, Any]:
        """
        Extract specific fields from document using a schema.

        Args:
            file_bytes: Document content as bytes
            schema: Universal field extraction schema (provider-agnostic)
            **options: Additional provider-specific options

        Returns:
            Dictionary with extracted fields in universal format

        Raises:
            ParserException: If extraction fails
        """
        pass

    @abstractmethod
    def translate_schema(
        self,
        universal_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Translate universal schema to provider-specific format.

        Universal schema format (from config):
        {
            "fields": {
                "invoice_number": {"type": "string", "required": true},
                "invoice_date": {"type": "date", "required": false},
                "total": {"type": "decimal", "required": true}
            },
            "items": {
                "field_name": "items",
                "fields": {
                    "description": {"type": "string"},
                    "quantity": {"type": "decimal"}
                }
            }
        }

        Provider translates this to their specific format:
        - Reducto: JSON Schema format
        - Google Document AI: Processor schema format
        - AWS Textract: Feature types and queries

        Args:
            universal_schema: Provider-agnostic schema from config

        Returns:
            Provider-specific schema format
        """
        pass

    @abstractmethod
    def normalize_response(
        self,
        provider_response: Dict[str, Any],
        document_type: str
    ) -> Dict[str, Any]:
        """
        Normalize provider-specific response to universal format.

        Universal format:
        {
            "fields": {
                "invoice_number": "INV-001",
                "invoice_date": "2024-01-15",
                "total": 1000.00
            },
            "items": [
                {"description": "Product A", "quantity": 10},
                {"description": "Product B", "quantity": 5}
            ],
            "metadata": {
                "confidence": 0.95,
                "provider": "reducto",
                "extraction_time": 2.5
            }
        }

        Args:
            provider_response: Raw response from provider API
            document_type: Type of document being processed

        Returns:
            Normalized dictionary in universal format
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the parser provider is accessible and working.

        Returns:
            True if provider is healthy, False otherwise
        """
        pass


class ParserException(Exception):
    """Base exception for parser errors."""
    pass


class ParserConnectionError(ParserException):
    """Raised when cannot connect to parser service."""
    pass


class ParserValidationError(ParserException):
    """Raised when document validation fails."""
    pass


class ParserTimeoutError(ParserException):
    """Raised when parsing times out."""
    pass
