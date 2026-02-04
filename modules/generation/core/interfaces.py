"""
Core interfaces for the generation module.

All components implement these interfaces for perfect modularity.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# ==============================================================================
# RESULT TYPES
# ==============================================================================

class GenerationStatus(str, Enum):
    """Generation job status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class GenerationResult:
    """
    Result from a generation operation.
    
    Universal format returned by all renderers.
    """
    success: bool
    job_id: str
    output_path: Optional[str] = None
    output_bytes: Optional[bytes] = None
    output_format: Optional[str] = None
    
    # Metadata
    template_name: str = ""
    renderer_name: str = ""
    generation_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Error information
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "job_id": self.job_id,
            "output_path": self.output_path,
            "output_format": self.output_format,
            "template_name": self.template_name,
            "renderer_name": self.renderer_name,
            "generation_time_ms": self.generation_time_ms,
            "metadata": self.metadata,
            "error_message": self.error_message,
            "error_details": self.error_details,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


@dataclass
class MappingResult:
    """Result from data mapping operation"""
    success: bool
    mapped_data: Dict[str, Any]
    unmapped_fields: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "mapped_data": self.mapped_data,
            "unmapped_fields": self.unmapped_fields,
            "errors": self.errors,
            "warnings": self.warnings,
        }


@dataclass
class TemplateMetadata:
    """Template metadata"""
    template_id: str
    template_name: str
    template_format: str  # docx, pdf, excel, html, json
    version: str
    template_path: str = ""
    description: str = ""
    required_fields: List[str] = field(default_factory=list)
    optional_fields: List[str] = field(default_factory=list)
    supports_tables: bool = False
    supports_images: bool = False
    insights_config: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "template_id": self.template_id,
            "template_name": self.template_name,
            "template_format": self.template_format,
            "version": self.version,
            "template_path": self.template_path,
            "description": self.description,
            "required_fields": self.required_fields,
            "optional_fields": self.optional_fields,
            "supports_tables": self.supports_tables,
            "supports_images": self.supports_images,
            "insights_config": self.insights_config,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ==============================================================================
# RENDERER INTERFACE
# ==============================================================================

class IRenderer(ABC):
    """
    Abstract interface for template renderers.
    
    Each renderer handles a specific document format (DOCX, PDF, Excel, etc.)
    Renderers self-register with the RendererRegistry.
    
    Example:
        @register_renderer("docx")
        class DocxRenderer(IRenderer):
            async def render(self, template_path, data):
                # Implementation
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize renderer with configuration.
        
        Args:
            config: Renderer configuration from renderers.yaml
        """
        self.config = config
        self.renderer_name = config.get('name', self.__class__.__name__)
    
    @abstractmethod
    async def render(
        self,
        template_path: str,
        data: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None
    ) -> GenerationResult:
        """
        Render template with data.
        
        Args:
            template_path: Path to template file
            data: Data to populate template (already mapped)
            options: Optional rendering options
                - output_path: Where to save output
                - output_format: Output format (if conversion needed)
                - renderer_options: Renderer-specific options
        
        Returns:
            GenerationResult with output bytes or path
        
        Raises:
            RendererException: If rendering fails
        """
        pass
    
    @abstractmethod
    def validate_template(self, template_path: str) -> bool:
        """
        Validate template file.
        
        Args:
            template_path: Path to template file
        
        Returns:
            True if template is valid, False otherwise
        """
        pass
    
    @abstractmethod
    def get_template_fields(self, template_path: str) -> List[str]:
        """
        Extract field placeholders from template.
        
        Useful for validation and mapping.
        
        Args:
            template_path: Path to template file
        
        Returns:
            List of field names found in template
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if renderer is healthy and ready.
        
        Returns:
            True if healthy, False otherwise
        """
        pass
    
    def supports_format(self, format_name: str) -> bool:
        """
        Check if renderer supports a format.
        
        Args:
            format_name: Format to check (docx, pdf, etc.)
        
        Returns:
            True if supported, False otherwise
        """
        supported = self.config.get('supported_formats', [])
        return format_name.lower() in [f.lower() for f in supported]


# ==============================================================================
# DATA PROVIDER INTERFACE
# ==============================================================================

class IDataProvider(ABC):
    """
    Abstract interface for data providers.
    
    Data providers fetch data from various sources:
    - PostgreSQL database
    - External APIs
    - JSON files
    - Static data
    
    Providers self-register with the DataProviderRegistry.
    
    Example:
        @register_data_provider("postgres")
        class PostgresDataProvider(IDataProvider):
            async def fetch_data(self, query_params):
                # Implementation
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize data provider with configuration.
        
        Args:
            config: Provider configuration from data_sources.yaml
        """
        self.config = config
        self.provider_name = config.get('name', self.__class__.__name__)
    
    @abstractmethod
    async def fetch_data(
        self,
        query: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Fetch data from source.
        
        Args:
            query: Query parameters
                Examples:
                - {"document_id": "123", "document_type": "invoice"}
                - {"api_endpoint": "/orders/123", "method": "GET"}
                - {"file_path": "/data/customer.json"}
            options: Optional fetch options
        
        Returns:
            Dictionary with fetched data in standard format:
            {
                "fields": {"field1": "value1", ...},
                "items": [{"item_field1": "value1", ...}, ...],
                "metadata": {"source": "postgres", "fetch_time": 0.5}
            }
        
        Raises:
            DataProviderException: If fetch fails
        """
        pass
    
    @abstractmethod
    async def validate_query(self, query: Dict[str, Any]) -> bool:
        """
        Validate query parameters.
        
        Args:
            query: Query parameters to validate
        
        Returns:
            True if valid, False otherwise
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if data provider is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        pass
    
    def supports_query_type(self, query_type: str) -> bool:
        """
        Check if provider supports a query type.
        
        Args:
            query_type: Type of query (document_id, api_call, file_path, etc.)
        
        Returns:
            True if supported, False otherwise
        """
        supported = self.config.get('query_types', [])
        return query_type in supported


# ==============================================================================
# MAPPER INTERFACE
# ==============================================================================

class IMapper(ABC):
    """
    Abstract interface for data mappers.
    
    Mappers transform data from source format to template format.
    They apply field mappings, transformations, and calculations.
    
    Example:
        @register_mapper("field")
        class FieldMapper(IMapper):
            async def map_data(self, source_data, mapping_config):
                # Implementation
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize mapper with configuration.
        
        Args:
            config: Mapper configuration
        """
        self.config = config
        self.mapper_name = config.get('name', self.__class__.__name__)
    
    @abstractmethod
    async def map_data(
        self,
        source_data: Dict[str, Any],
        mapping_config: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> MappingResult:
        """
        Map source data to target format.
        
        Args:
            source_data: Data from data provider
            mapping_config: Mapping configuration from mappings YAML
            context: Optional context for complex mappings
        
        Returns:
            MappingResult with mapped data
        
        Raises:
            MappingException: If mapping fails
        """
        pass
    
    @abstractmethod
    def validate_mapping_config(self, mapping_config: Dict[str, Any]) -> bool:
        """
        Validate mapping configuration.
        
        Args:
            mapping_config: Mapping config to validate
        
        Returns:
            True if valid, False otherwise
        """
        pass


# ==============================================================================
# TEMPLATE REGISTRY INTERFACE
# ==============================================================================

class ITemplateRegistry(ABC):
    """
    Abstract interface for template registry.
    
    Manages template storage, retrieval, and metadata.
    """
    
    @abstractmethod
    async def register_template(
        self,
        template_id: str,
        template_path: str,
        metadata: TemplateMetadata
    ) -> bool:
        """
        Register a template.
        
        Args:
            template_id: Unique template identifier
            template_path: Path to template file
            metadata: Template metadata
        
        Returns:
            True if registered successfully
        """
        pass
    
    @abstractmethod
    async def get_template(self, template_id: str) -> Optional[str]:
        """
        Get template path by ID.
        
        Args:
            template_id: Template identifier
        
        Returns:
            Template file path or None if not found
        """
        pass
    
    @abstractmethod
    async def get_template_metadata(self, template_id: str) -> Optional[TemplateMetadata]:
        """
        Get template metadata.
        
        Args:
            template_id: Template identifier
        
        Returns:
            TemplateMetadata or None if not found
        """
        pass
    
    @abstractmethod
    async def list_templates(
        self,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[TemplateMetadata]:
        """
        List all templates with optional filters.
        
        Args:
            filters: Optional filters (format, tags, etc.)
        
        Returns:
            List of TemplateMetadata
        """
        pass
    
    @abstractmethod
    async def delete_template(self, template_id: str) -> bool:
        """
        Delete a template.
        
        Args:
            template_id: Template identifier
        
        Returns:
            True if deleted successfully
        """
        pass
    
    @abstractmethod
    async def template_exists(self, template_id: str) -> bool:
        """
        Check if template exists.
        
        Args:
            template_id: Template identifier
        
        Returns:
            True if template exists
        """
        pass
