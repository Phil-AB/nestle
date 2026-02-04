"""
Repository for API Document CRUD operations.

Provides database persistence for document metadata,
replacing in-memory storage for production scalability.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from src.database.models.api_document import APIDocument
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class APIDocumentRepository:
    """
    Repository for APIDocument model operations.

    Provides CRUD operations and specialized queries for document management.
    Thread-safe and works with async SQLAlchemy sessions.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: Async SQLAlchemy session
        """
        self.session = session

    async def create(self, document_data: Dict[str, Any]) -> APIDocument:
        """
        Create a new API document record.

        Args:
            document_data: Dictionary with document fields

        Returns:
            Created APIDocument instance
        """
        document = APIDocument(**document_data)
        self.session.add(document)
        await self.session.commit()
        await self.session.refresh(document)
        logger.info(f"Created document: {document.document_id}")
        return document

    async def get_by_document_id(self, document_id: str) -> Optional[APIDocument]:
        """
        Get document by document_id.

        Args:
            document_id: Document ID (UUID string)

        Returns:
            APIDocument if found, None otherwise
        """
        query = select(APIDocument).where(APIDocument.document_id == document_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id(self, id: str) -> Optional[APIDocument]:
        """
        Get document by primary key id.

        Args:
            id: Primary key UUID

        Returns:
            APIDocument if found, None otherwise
        """
        return await self.session.get(APIDocument, id)

    async def update(
        self,
        document_id: str,
        update_data: Dict[str, Any]
    ) -> Optional[APIDocument]:
        """
        Update document fields.

        Args:
            document_id: Document ID to update
            update_data: Dictionary of fields to update

        Returns:
            Updated APIDocument if found, None otherwise
        """
        # Add updated_at timestamp
        update_data['updated_at'] = datetime.utcnow()

        query = (
            update(APIDocument)
            .where(APIDocument.document_id == document_id)
            .values(**update_data)
            .returning(APIDocument)
        )

        result = await self.session.execute(query)
        await self.session.commit()

        updated = result.scalar_one_or_none()
        if updated:
            logger.info(f"Updated document: {document_id}")
        return updated

    async def delete(self, document_id: str) -> bool:
        """
        Delete document by document_id.

        Args:
            document_id: Document ID to delete

        Returns:
            True if deleted, False if not found
        """
        query = delete(APIDocument).where(APIDocument.document_id == document_id)
        result = await self.session.execute(query)
        await self.session.commit()

        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"Deleted document: {document_id}")
        return deleted

    async def list_documents(
        self,
        document_type: Optional[str] = None,
        extraction_status: Optional[str] = None,
        shipment_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[List[APIDocument], int]:
        """
        List documents with optional filtering and pagination.

        Args:
            document_type: Filter by document type
            extraction_status: Filter by extraction status
            shipment_id: Filter by shipment ID
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            Tuple of (documents list, total count)
        """
        # Build base query
        query = select(APIDocument)

        # Apply filters
        if document_type:
            query = query.where(APIDocument.document_type == document_type)
        if extraction_status:
            query = query.where(APIDocument.extraction_status == extraction_status)
        if shipment_id:
            query = query.where(APIDocument.shipment_id == shipment_id)

        # Count total (before pagination)
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.session.scalar(count_query)

        # Apply pagination and ordering
        query = (
            query
            .order_by(APIDocument.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        # Execute
        result = await self.session.execute(query)
        documents = result.scalars().all()

        logger.debug(f"Listed {len(documents)} documents (total: {total})")
        return list(documents), total or 0

    async def exists(self, document_id: str) -> bool:
        """
        Check if document exists.

        Args:
            document_id: Document ID to check

        Returns:
            True if exists, False otherwise
        """
        query = select(func.count()).select_from(
            select(APIDocument).where(APIDocument.document_id == document_id).subquery()
        )
        count = await self.session.scalar(query)
        return count > 0

    async def update_extraction_result(
        self,
        document_id: str,
        fields: Dict[str, Any],
        items: List[Dict[str, Any]],
        blocks: List[Dict[str, Any]],
        metadata: Dict[str, Any],
        extraction_status: str,
        raw_provider_response: Optional[Dict[str, Any]] = None
    ) -> Optional[APIDocument]:
        """
        Update document with extraction results.

        Specialized method for updating after background parsing.

        Args:
            document_id: Document ID
            fields: Extracted fields
            items: Extracted line items
            blocks: Content blocks
            metadata: Provider metadata
            extraction_status: Extraction status
            raw_provider_response: Original raw response from provider (optional)

        Returns:
            Updated APIDocument if found, None otherwise
        """
        update_data = {
            'fields': fields,
            'items': items,
            'blocks': blocks,
            'doc_metadata': metadata,
            'extraction_status': extraction_status,
            'items_count': len(items),
            'fields_count': len(fields),
            'parsed_at': datetime.utcnow(),
        }

        # Include raw provider response if provided
        if raw_provider_response:
            update_data['raw_provider_response'] = raw_provider_response

        return await self.update(document_id, update_data)

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get document statistics.

        Returns:
            Dictionary with statistics
        """
        total_query = select(func.count()).select_from(APIDocument)
        total = await self.session.scalar(total_query)

        by_status_query = (
            select(
                APIDocument.extraction_status,
                func.count(APIDocument.id)
            )
            .group_by(APIDocument.extraction_status)
        )
        status_result = await self.session.execute(by_status_query)
        by_status = dict(status_result.all())

        by_type_query = (
            select(
                APIDocument.document_type,
                func.count(APIDocument.id)
            )
            .group_by(APIDocument.document_type)
        )
        type_result = await self.session.execute(by_type_query)
        by_type = dict(type_result.all())

        return {
            "total": total or 0,
            "by_status": by_status,
            "by_type": by_type,
        }
