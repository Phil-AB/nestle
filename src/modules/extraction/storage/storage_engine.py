"""
StorageEngine - Main orchestrator for document storage.

This is the primary entry point for storing documents.
It routes documents to configured backends and handles multi-backend storage.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

from modules.extraction.storage.core.backend import StorageBackend, StorageResult
from modules.extraction.storage.core.registry import STORAGE_BACKENDS, get_backend
from modules.extraction.storage.core.config_loader import StorageConfigLoader
from shared.utils.logger import setup_logger

# Import backends to trigger registration
from modules.extraction.storage import backends  # noqa: F401

logger = setup_logger(__name__)


@dataclass
class MultiBackendStorageResult:
    """Result from storing across multiple backends"""
    success: bool
    document_id: Optional[str]
    backends_results: Dict[str, StorageResult]
    timestamp: datetime
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'success': self.success,
            'document_id': self.document_id,
            'backends': {
                name: result.to_dict()
                for name, result in self.backends_results.items()
            },
            'timestamp': self.timestamp.isoformat()
        }


class StorageEngine:
    """
    Universal storage orchestrator.
    
    Routes documents to appropriate storage backends based on configuration.
    Supports:
    - Single backend storage
    - Multi-backend storage (primary + backup)
    - Document type-based routing
    
    This engine is completely independent and can store ANY data.
    
    Usage:
        engine = StorageEngine()
        result = await engine.store("invoice", data)
        
        if result.success:
            print(f"Stored with ID: {result.document_id}")
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize storage engine.
        
        Args:
            config_path: Path to storage config YAML file
                        If None, uses default location
        """
        self.config_loader = StorageConfigLoader(config_path)
        self.config = self.config_loader.load()
        self.backends: Dict[str, StorageBackend] = {}
        
        # Initialize configured backends
        self._initialize_backends()
        
        logger.info(
            f"StorageEngine initialized with {len(self.backends)} backends"
        )
    
    def _initialize_backends(self) -> None:
        """Initialize all configured storage backends"""
        backend_configs = self.config.get('storage', {}).get('backends', {})
        
        for backend_name, backend_config in backend_configs.items():
            backend_type = backend_config.get('type', backend_name)
            backend_class = get_backend(backend_type)
            
            if not backend_class:
                logger.warning(f"Backend type '{backend_type}' not found in registry")
                continue
            
            try:
                # Add backend name to config
                backend_config['name'] = backend_name
                backend_instance = backend_class(backend_config)
                self.backends[backend_name] = backend_instance
                logger.info(f"Initialized backend: {backend_name} ({backend_type})")
            except Exception as e:
                logger.error(f"Failed to initialize backend '{backend_name}': {e}")
    
    async def store(
        self,
        document_type: str,
        data: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None
    ) -> MultiBackendStorageResult:
        """
        Store document data.
        
        Args:
            document_type: Type of document
            data: Document data to store
            options: Optional storage options
                - backend: Override backend selection
                - document_id: For updates
                - unique_field: Field name for deduplication
        
        Returns:
            MultiBackendStorageResult
        
        Example:
            result = await engine.store(
                "invoice",
                {"invoice_number": "INV-001", "amount": 1000},
                {"unique_field": "invoice_number"}
            )
        """
        logger.info(f"Storing document type: {document_type}")
        
        options = options or {}
        
        # Determine which backend(s) to use
        target_backends = self._get_target_backends(document_type, options)
        
        if not target_backends:
            logger.error("No storage backends configured")
            return MultiBackendStorageResult(
                success=False,
                document_id=None,
                backends_results={},
                timestamp=datetime.utcnow()
            )
        
        # Store in each backend
        results = {}
        primary_id = None
        
        for backend_name in target_backends:
            backend = self.backends.get(backend_name)
            
            if not backend:
                logger.warning(f"Backend '{backend_name}' not initialized")
                continue
            
            try:
                result = await backend.store(document_type, data, options)
                results[backend_name] = result
                
                # Capture ID from first successful storage
                if result.success and not primary_id:
                    primary_id = result.document_id
                
                logger.info(
                    f"Stored in {backend_name}: "
                    f"{'success' if result.success else 'failed'}"
                )
                
            except Exception as e:
                logger.error(f"Storage failed in {backend_name}: {e}", exc_info=True)
                results[backend_name] = StorageResult(
                    success=False,
                    backend_name=backend_name,
                    message=f"Storage error: {str(e)}"
                )
        
        # Overall success if at least one backend succeeded
        overall_success = any(r.success for r in results.values())
        
        return MultiBackendStorageResult(
            success=overall_success,
            document_id=primary_id,
            backends_results=results,
            timestamp=datetime.utcnow()
        )
    
    def _get_target_backends(
        self,
        document_type: str,
        options: Dict[str, Any]
    ) -> List[str]:
        """
        Determine which backend(s) to use for storage.
        
        Priority:
        1. Explicit backend in options
        2. Document type routing override
        3. Multi-store configuration
        4. Default backend
        
        Args:
            document_type: Document type
            options: Storage options
        
        Returns:
            List of backend names
        """
        # 1. Check explicit override in options
        if 'backend' in options:
            return [options['backend']]
        
        # 2. Check multi-store configuration
        multi_store_config = self.config_loader.get_multi_store_config()
        if multi_store_config.get('enabled', False):
            return multi_store_config.get('backends', [])
        
        # 3. Check document type routing
        routing_config = self.config_loader.get_routing_config()
        overrides = routing_config.get('overrides', {})
        if document_type in overrides:
            return [overrides[document_type]]
        
        # 4. Use default backend
        default = routing_config.get('default') or self.config_loader.get_default_backend()
        return [default]
    
    async def retrieve(
        self,
        document_type: str,
        document_id: str,
        backend: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieve document by ID.
        
        Args:
            document_type: Document type
            document_id: Document ID
            backend: Optional backend name (uses default if not specified)
        
        Returns:
            Document data
        """
        if not backend:
            backend = self.config_loader.get_default_backend()
        
        backend_instance = self.backends.get(backend)
        if not backend_instance:
            raise ValueError(f"Backend '{backend}' not available")
        
        return await backend_instance.retrieve(document_type, document_id)
    
    async def update(
        self,
        document_type: str,
        document_id: str,
        data: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None
    ) -> MultiBackendStorageResult:
        """
        Update existing document.
        
        Args:
            document_type: Document type
            document_id: Document ID
            data: Updated data
            options: Optional update options
        
        Returns:
            MultiBackendStorageResult
        """
        options = options or {}
        options['document_id'] = document_id
        
        return await self.store(document_type, data, options)
    
    async def delete(
        self,
        document_type: str,
        document_id: str,
        backend: Optional[str] = None
    ) -> bool:
        """
        Delete document.
        
        Args:
            document_type: Document type
            document_id: Document ID
            backend: Optional backend name
        
        Returns:
            True if deleted
        """
        if not backend:
            backend = self.config_loader.get_default_backend()
        
        backend_instance = self.backends.get(backend)
        if not backend_instance:
            raise ValueError(f"Backend '{backend}' not available")
        
        return await backend_instance.delete(document_type, document_id)
    
    async def query(
        self,
        document_type: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0,
        backend: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query documents.
        
        Args:
            document_type: Document type
            filters: Query filters
            limit: Maximum results
            offset: Offset for pagination
            backend: Optional backend name
        
        Returns:
            List of documents
        """
        if not backend:
            backend = self.config_loader.get_default_backend()
        
        backend_instance = self.backends.get(backend)
        if not backend_instance:
            raise ValueError(f"Backend '{backend}' not available")
        
        return await backend_instance.query(
            document_type,
            filters,
            limit,
            offset
        )
    
    def get_available_backends(self) -> List[str]:
        """
        Get list of initialized backends.
        
        Returns:
            List of backend names
        """
        return list(self.backends.keys())
    
    def reload_config(self) -> None:
        """Reload storage configuration and reinitialize backends"""
        logger.info("Reloading storage configuration")
        self.config = self.config_loader.reload()
        self.backends.clear()
        self._initialize_backends()
