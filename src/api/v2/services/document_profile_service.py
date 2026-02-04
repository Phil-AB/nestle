"""
Document Profile Management Service.

Production-grade service for managing document profiles and metadata.
Works with real documents only - no hardcoded data.
"""

from typing import Optional, List, Dict, Any, Literal
from sqlalchemy import select, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import logging

from src.database.repositories.api_document_repository import APIDocumentRepository
from src.database.models.api_document import APIDocument

logger = logging.getLogger(__name__)


# Type definitions for production use
FormType = Literal["handwritten", "digital", "unknown"]
RiskLevel = Literal["high", "medium", "low", "unknown"]


class DocumentProfileService:
    """
    Service for managing document profiles.

    Extends existing document metadata to support profile management
    without requiring schema changes. Uses doc_metadata JSONB field.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize service with database session.

        Args:
            session: Async SQLAlchemy session
        """
        self.session = session
        self.document_repo = APIDocumentRepository(session)

    async def set_form_type(
        self,
        document_id: str,
        form_type: FormType
    ) -> Optional[APIDocument]:
        """
        Tag a document with its form type (handwritten/digital).

        Args:
            document_id: Document ID
            form_type: Form type classification

        Returns:
            Updated document or None if not found
        """
        doc = await self.document_repo.get_by_document_id(document_id)
        if not doc:
            logger.warning(f"Document not found: {document_id}")
            return None

        # Update metadata
        metadata = doc.doc_metadata or {}
        metadata["form_type"] = form_type
        metadata["form_type_updated_at"] = datetime.utcnow().isoformat()

        return await self.document_repo.update(
            document_id,
            {"doc_metadata": metadata}
        )

    async def set_risk_level(
        self,
        document_id: str,
        risk_level: RiskLevel,
        risk_score: Optional[int] = None
    ) -> Optional[APIDocument]:
        """
        Tag a document with its risk level.

        Args:
            document_id: Document ID
            risk_level: Risk classification
            risk_score: Optional numeric risk score

        Returns:
            Updated document or None if not found
        """
        doc = await self.document_repo.get_by_document_id(document_id)
        if not doc:
            logger.warning(f"Document not found: {document_id}")
            return None

        # Update metadata
        metadata = doc.doc_metadata or {}
        metadata["risk_level"] = risk_level
        if risk_score is not None:
            metadata["risk_score"] = risk_score
        metadata["risk_updated_at"] = datetime.utcnow().isoformat()

        return await self.document_repo.update(
            document_id,
            {"doc_metadata": metadata}
        )

    async def set_display_order(
        self,
        document_id: str,
        order: int
    ) -> Optional[APIDocument]:
        """
        Set display order for a document in profile selector.

        Args:
            document_id: Document ID
            order: Display order position

        Returns:
            Updated document or None if not found
        """
        doc = await self.document_repo.get_by_document_id(document_id)
        if not doc:
            return None

        metadata = doc.doc_metadata or {}
        metadata["display_order"] = order

        return await self.document_repo.update(
            document_id,
            {"doc_metadata": metadata}
        )

    async def set_profile_tags(
        self,
        document_id: str,
        tags: List[str]
    ) -> Optional[APIDocument]:
        """
        Set custom profile tags for a document.

        Args:
            document_id: Document ID
            tags: List of tags to apply

        Returns:
            Updated document or None if not found
        """
        doc = await self.document_repo.get_by_document_id(document_id)
        if not doc:
            return None

        metadata = doc.doc_metadata or {}
        metadata["profile_tags"] = tags

        return await self.document_repo.update(
            document_id,
            {"doc_metadata": metadata}
        )

    async def list_profiles(
        self,
        form_type: Optional[FormType] = None,
        risk_level: Optional[RiskLevel] = None,
        tag: Optional[str] = None,
        has_insights: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        List documents with profile metadata.

        Args:
            form_type: Filter by form type
            risk_level: Filter by risk level
            tag: Filter by tag
            has_insights: Filter by whether insights exist
            limit: Maximum results
            offset: Results to skip

        Returns:
            Tuple of (profiles list, total count)
        """
        # Build base query with JSONB metadata filtering
        query = select(APIDocument).where(
            APIDocument.extraction_status == "complete"
        )

        # Apply filters using JSONB operators
        if form_type:
            query = query.where(
                text("doc_metadata->>'form_type' = :form_type")
            ).params(form_type=form_type)

        if risk_level:
            query = query.where(
                text("doc_metadata->>'risk_level' = :risk_level")
            ).params(risk_level=risk_level)

        if tag:
            query = query.where(
                text(":tag = ANY(doc_metadata->'profile_tags')")
            ).params(tag=tag)

        # Order by display_order if set, otherwise by created_at
        query = query.order_by(
            text("COALESCE((doc_metadata->>'display_order')::int, 999999) ASC"),
            APIDocument.created_at.desc()
        )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.session.scalar(count_query)

        # Apply pagination
        query = query.limit(limit).offset(offset)

        # Execute
        result = await self.session.execute(query)
        documents = result.scalars().all()

        # Format as profile objects
        profiles = []
        for doc in documents:
            metadata = doc.doc_metadata or {}
            fields = doc.fields or {}

            # Extract customer name
            name = self._extract_customer_name(fields)

            profiles.append({
                "document_id": doc.document_id,
                "name": name,
                "document_type": doc.document_type,
                "form_type": metadata.get("form_type", "unknown"),
                "risk_level": metadata.get("risk_level"),
                "risk_score": metadata.get("risk_score"),
                "display_order": metadata.get("display_order"),
                "tags": metadata.get("profile_tags", []),
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
            })

        return profiles, total or 0

    def _extract_customer_name(self, fields: Dict[str, Any]) -> str:
        """
        Extract customer name from document fields.

        Args:
            fields: Extracted fields dictionary

        Returns:
            Customer name or "Unknown"
        """
        # Try different name field patterns
        name_field = fields.get("name", {})

        if isinstance(name_field, dict):
            if "value" in name_field:
                return name_field["value"]
        elif isinstance(name_field, str):
            return name_field

        # Try first_name + surname
        first = fields.get("first_name", {})
        surname = fields.get("surname", {})

        if isinstance(first, dict):
            first = first.get("value", "")
        if isinstance(surname, dict):
            surname = surname.get("value", "")

        if first or surname:
            return f"{first} {surname}".strip()

        return "Unknown"

    async def get_profile_stats(self) -> Dict[str, Any]:
        """
        Get statistics about document profiles.

        Returns:
            Dictionary with profile statistics
        """
        # Total documents with profile metadata
        total_with_metadata = await self.session.scalar(
            select(text("COUNT(*)")).where(
                and_(
                    APIDocument.extraction_status == "complete",
                    text("doc_metadata IS NOT NULL"),
                    text("doc_metadata != '{}'::jsonb")
                )
            )
        )

        # Count by form type
        form_type_counts = await self.session.execute(
            select(
                text("doc_metadata->>'form_type'"),
                text("COUNT(*)")
            ).where(
                and_(
                    APIDocument.extraction_status == "complete",
                    text("doc_metadata ? 'form_type'")
                )
            ).group_by(text("doc_metadata->>'form_type'"))
        )
        by_form_type = dict(form_type_counts.all())

        # Count by risk level
        risk_level_counts = await self.session.execute(
            select(
                text("doc_metadata->>'risk_level'"),
                text("COUNT(*)")
            ).where(
                and_(
                    APIDocument.extraction_status == "complete",
                    text("doc_metadata ? 'risk_level'")
                )
            ).group_by(text("doc_metadata->>'risk_level'"))
        )
        by_risk_level = dict(risk_level_counts.all())

        return {
            "total_with_profiles": total_with_metadata or 0,
            "by_form_type": by_form_type,
            "by_risk_level": by_risk_level,
        }

    async def bulk_update_form_types(
        self,
        document_ids: List[str],
        form_type: FormType
    ) -> int:
        """
        Bulk update form type for multiple documents.

        Args:
            document_ids: List of document IDs
            form_type: Form type to set

        Returns:
            Number of documents updated
        """
        updated_count = 0

        for doc_id in document_ids:
            result = await self.set_form_type(doc_id, form_type)
            if result:
                updated_count += 1

        logger.info(f"Bulk updated {updated_count}/{len(document_ids)} documents to form_type={form_type}")
        return updated_count


# Import func for COUNT queries
from sqlalchemy import func
