"""
Base storage backend interface.

Defines the interface that all storage backends must implement.
This allows for pluggable storage backends (PostgreSQL, MongoDB, S3, etc.)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class StorageResult:
    """Result from a storage operation"""
    success: bool
    document_id: Optional[str] = None
    backend_name: Optional[str] = None
    message: str = ""
    metadata: Dict[str, Any] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class StorageBackend(ABC):
    """
    Abstract base class for storage backends.
    
    All storage backends must implement these methods.
    This allows the system to support multiple storage backends
    (PostgreSQL, MongoDB, S3, local filesystem, etc.)
    
    Example:
        @register_backend("my_storage")
        class MyStorageBackend(StorageBackend):
            async def store(self, document_type, data):
                # Implementation here
                ...
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize backend with configuration.
        
        Args:
            config: Backend configuration dictionary
        """
        self.config = config
        self.backend_name = config.get('name', self.__class__.__name__)
    
    @abstractmethod
    async def store(
        self,
        document_type: str,
        data: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None
    ) -> StorageResult:
        """
        Store document data.
        
        Args:
            document_type: Type of document
            data: Document data to store
            options: Optional storage options (metadata, etc.)
        
        Returns:
            StorageResult
        """
        pass
    
    @abstractmethod
    async def retrieve(
        self,
        document_type: str,
        document_id: str
    ) -> Dict[str, Any]:
        """
        Retrieve document by ID.
        
        Args:
            document_type: Type of document
            document_id: Document ID
        
        Returns:
            Document data dictionary
        
        Raises:
            NotFoundError: If document doesn't exist
        """
        pass
    
    @abstractmethod
    async def update(
        self,
        document_type: str,
        document_id: str,
        data: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None
    ) -> StorageResult:
        """
        Update existing document.
        
        Args:
            document_type: Type of document
            document_id: Document ID
            data: Updated data
            options: Optional update options
        
        Returns:
            StorageResult
        """
        pass
    
    @abstractmethod
    async def delete(
        self,
        document_type: str,
        document_id: str
    ) -> bool:
        """
        Delete document.
        
        Args:
            document_type: Type of document
            document_id: Document ID
        
        Returns:
            True if deleted, False if not found
        """
        pass
    
    @abstractmethod
    async def query(
        self,
        document_type: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Query documents.
        
        Args:
            document_type: Type of document
            filters: Query filters
            limit: Maximum results
            offset: Offset for pagination
        
        Returns:
            List of document data dictionaries
        """
        pass
    
    async def health_check(self) -> bool:
        """
        Check if backend is healthy/available.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            # Default implementation - can be overridden
            return True
        except Exception:
            return False


class StorageError(Exception):
    """Base exception for storage errors"""
    pass


class NotFoundError(StorageError):
    """Exception raised when document is not found"""
    pass


class DuplicateError(StorageError):
    """Exception raised when trying to create duplicate document"""
    pass
