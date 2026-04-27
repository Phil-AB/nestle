"""
PostgreSQL storage backend.

Implements StorageBackend interface for PostgreSQL with JSONB storage.
Provides flexible, schema-less document storage using PostgreSQL's JSONB capabilities.
"""

from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4
from datetime import datetime

from modules.extraction.storage.core.backend import (
    StorageBackend,
    StorageResult,
    NotFoundError,
    DuplicateError
)
from modules.extraction.storage.core.registry import register_backend
from src.database.connection import get_session
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


@register_backend("postgresql")
class PostgreSQLBackend(StorageBackend):
    """
    PostgreSQL backend using JSONB for flexible document storage.
    
    Stores documents in a generic 'documents' table with JSONB fields.
    This allows ANY document type without schema changes.
    
    Table structure:
        - id: UUID primary key
        - document_type: VARCHAR
        - data: JSONB (all document fields)
        - metadata: JSONB (confidence scores, etc.)
        - created_at: TIMESTAMP
        - updated_at: TIMESTAMP
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize PostgreSQL backend.
        
        Args:
            config: Backend configuration
        """
        super().__init__(config)
        self.table_name = config.get('table_name', 'documents')
    
    async def store(
        self,
        document_type: str,
        data: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None
    ) -> StorageResult:
        """
        Store document in PostgreSQL.
        
        Args:
            document_type: Document type
            data: Document data
            options: Optional options (may contain document_id for updates)
        
        Returns:
            StorageResult
        """
        try:
            options = options or {}
            document_id = options.get('document_id')
            
            # Separate metadata from data
            metadata = data.pop('_metadata', {})
            
            if document_id:
                # Update existing document
                return await self.update(document_type, document_id, data, options)
            
            # Create new document
            async with get_session() as session:
                # Check for duplicates if unique field specified
                unique_field = options.get('unique_field')
                if unique_field and unique_field in data:
                    unique_value = data[unique_field]
                    existing = await self._find_by_unique_field(
                        session,
                        document_type,
                        unique_field,
                        unique_value
                    )
                    if existing:
                        # Update existing
                        return await self.update(
                            document_type,
                            str(existing['id']),
                            data,
                            options
                        )
                
                # Insert new document
                new_id = str(uuid4())
                query = f"""
                    INSERT INTO {self.table_name} 
                    (id, document_type, data, metadata, created_at, updated_at)
                    VALUES 
                    ($1, $2, $3, $4, $5, $6)
                """
                
                now = datetime.utcnow()
                await session.execute(
                    query,
                    new_id,
                    document_type,
                    data,  # PostgreSQL will convert dict to JSONB
                    metadata,
                    now,
                    now
                )
                
                logger.info(f"Stored {document_type} document: {new_id}")
                
                return StorageResult(
                    success=True,
                    document_id=new_id,
                    backend_name="postgresql",
                    message=f"Document created successfully"
                )
        
        except Exception as e:
            logger.error(f"Failed to store document: {e}", exc_info=True)
            return StorageResult(
                success=False,
                backend_name="postgresql",
                message=f"Storage failed: {str(e)}"
            )
    
    async def retrieve(
        self,
        document_type: str,
        document_id: str
    ) -> Dict[str, Any]:
        """
        Retrieve document by ID.
        
        Args:
            document_type: Document type
            document_id: Document ID
        
        Returns:
            Document data dictionary
        
        Raises:
            NotFoundError: If document doesn't exist
        """
        async with get_session() as session:
            query = f"""
                SELECT id, document_type, data, metadata, created_at, updated_at
                FROM {self.table_name}
                WHERE id = $1 AND document_type = $2
            """
            
            row = await session.fetchrow(query, document_id, document_type)
            
            if not row:
                raise NotFoundError(
                    f"Document not found: {document_type}/{document_id}"
                )
            
            return {
                'id': str(row['id']),
                'document_type': row['document_type'],
                'data': row['data'],
                '_metadata': row['metadata'],
                'created_at': row['created_at'].isoformat(),
                'updated_at': row['updated_at'].isoformat()
            }
    
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
            document_type: Document type
            document_id: Document ID
            data: Updated data
            options: Optional update options
        
        Returns:
            StorageResult
        """
        try:
            # Separate metadata
            metadata = data.pop('_metadata', {})
            
            async with get_session() as session:
                query = f"""
                    UPDATE {self.table_name}
                    SET data = $1, metadata = $2, updated_at = $3
                    WHERE id = $4 AND document_type = $5
                """
                
                now = datetime.utcnow()
                result = await session.execute(
                    query,
                    data,
                    metadata,
                    now,
                    document_id,
                    document_type
                )
                
                if result == "UPDATE 0":
                    raise NotFoundError(
                        f"Document not found: {document_type}/{document_id}"
                    )
                
                logger.info(f"Updated {document_type} document: {document_id}")
                
                return StorageResult(
                    success=True,
                    document_id=document_id,
                    backend_name="postgresql",
                    message="Document updated successfully"
                )
        
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to update document: {e}", exc_info=True)
            return StorageResult(
                success=False,
                backend_name="postgresql",
                message=f"Update failed: {str(e)}"
            )
    
    async def delete(
        self,
        document_type: str,
        document_id: str
    ) -> bool:
        """
        Delete document.
        
        Args:
            document_type: Document type
            document_id: Document ID
        
        Returns:
            True if deleted, False if not found
        """
        async with get_session() as session:
            query = f"""
                DELETE FROM {self.table_name}
                WHERE id = $1 AND document_type = $2
            """
            
            result = await session.execute(query, document_id, document_type)
            
            deleted = result == "DELETE 1"
            
            if deleted:
                logger.info(f"Deleted {document_type} document: {document_id}")
            
            return deleted
    
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
            document_type: Document type
            filters: JSONB query filters (e.g., {"data->>\'field\': \'value\'"})
            limit: Maximum results
            offset: Offset for pagination
        
        Returns:
            List of documents
        """
        async with get_session() as session:
            # Base query
            query = f"""
                SELECT id, document_type, data, metadata, created_at, updated_at
                FROM {self.table_name}
                WHERE document_type = $1
            """
            params = [document_type]
            
            # Add filters if provided
            if filters:
                for i, (key, value) in enumerate(filters.items(), start=2):
                    query += f" AND data->>'{key}' = ${i}"
                    params.append(str(value))
            
            # Add pagination
            query += f" ORDER BY created_at DESC LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}"
            params.extend([limit, offset])
            
            rows = await session.fetch(query, *params)
            
            return [
                {
                    'id': str(row['id']),
                    'document_type': row['document_type'],
                    'data': row['data'],
                    '_metadata': row['metadata'],
                    'created_at': row['created_at'].isoformat(),
                    'updated_at': row['updated_at'].isoformat()
                }
                for row in rows
            ]
    
    async def _find_by_unique_field(
        self,
        session,
        document_type: str,
        field_name: str,
        field_value: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Find document by unique field.
        
        Args:
            session: Database session
            document_type: Document type
            field_name: Field name
            field_value: Field value
        
        Returns:
            Document dict or None
        """
        query = f"""
            SELECT id, document_type, data, metadata
            FROM {self.table_name}
            WHERE document_type = $1 AND data->>$2 = $3
            LIMIT 1
        """
        
        row = await session.fetchrow(query, document_type, field_name, str(field_value))
        
        if row:
            return {
                'id': row['id'],
                'document_type': row['document_type'],
                'data': row['data'],
                '_metadata': row['metadata']
            }
        
        return None
