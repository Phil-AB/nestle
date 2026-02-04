"""
Generic document repository with dynamic model selection.

This repository works for ANY document type defined in config without code changes.
Uses model registry pattern for dynamic model selection.
"""

from typing import Optional, List, Dict, Any, Type, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.database.schema import (
    Invoice, InvoiceItem,
    BillOfEntry, BOEItem,
    PackingList, PackingListItem,
    CertificateOfOrigin, COOItem,
    FreightDocument
)
from shared.utils.document_config import get_document_config
from shared.utils.logger import setup_logger
from .base import BaseRepository

logger = setup_logger(__name__)


# Model Registry: Maps model_name string to SQLAlchemy model class
MODEL_REGISTRY: Dict[str, Type] = {
    # Document models
    'Invoice': Invoice,
    'BillOfEntry': BillOfEntry,
    'PackingList': PackingList,
    'CertificateOfOrigin': CertificateOfOrigin,
    'FreightDocument': FreightDocument,
    
    # Item models
    'InvoiceItem': InvoiceItem,
    'BOEItem': BOEItem,
    'PackingListItem': PackingListItem,
    'COOItem': COOItem,
}


class GenericDocumentRepository:
    """
    Generic repository that works for ANY document type.
    
    Dynamically selects models based on config and performs CRUD operations.
    This eliminates the need for separate repository classes for each document type.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize generic repository.

        Args:
            session: Async database session
        """
        self.session = session
        self.config = get_document_config()

    def _get_model_class(self, model_name: str) -> Type:
        """
        Get SQLAlchemy model class from registry.

        Args:
            model_name: Model class name (e.g., 'Invoice', 'BillOfEntry')

        Returns:
            Model class

        Raises:
            ValueError: If model not found in registry
        """
        if model_name not in MODEL_REGISTRY:
            raise ValueError(
                f"Model '{model_name}' not found in registry. "
                f"Available models: {', '.join(MODEL_REGISTRY.keys())}"
            )
        
        return MODEL_REGISTRY[model_name]

    def _get_models_for_document_type(
        self, 
        document_type: str
    ) -> Tuple[Type, Optional[Type]]:
        """
        Get document and items model classes for a document type.

        Args:
            document_type: Document type (invoice, boe, etc.)

        Returns:
            Tuple of (DocumentModel, ItemsModel or None)

        Raises:
            ValueError: If document type not configured or models not found
        """
        # Get model names from config
        model_name = self.config.get_model_name(document_type)
        items_model_name = self.config.get_items_model_name(document_type)

        if not model_name:
            raise ValueError(
                f"No model_name configured for document type '{document_type}'"
            )

        # Get model classes from registry
        doc_model = self._get_model_class(model_name)
        items_model = None
        
        if items_model_name:
            items_model = self._get_model_class(items_model_name)

        return doc_model, items_model

    async def get_by_unique_field(
        self,
        document_type: str,
        unique_value: str,
        load_items: bool = True
    ) -> Optional[Any]:
        """
        Get document by its unique identifier field.

        Args:
            document_type: Document type (invoice, boe, etc.)
            unique_value: Value of unique field
            load_items: Whether to eagerly load items

        Returns:
            Document instance or None
        """
        doc_model, items_model = self._get_models_for_document_type(document_type)
        unique_field = self.config.get_unique_field(document_type)

        if not unique_field:
            raise ValueError(f"No unique_field configured for {document_type}")

        # Build query
        query = select(doc_model).where(
            getattr(doc_model, unique_field) == unique_value
        )

        # Eagerly load items if requested and document has items
        if load_items and self.config.has_items(document_type):
            # Get the relationship name (e.g., 'items')
            query = query.options(selectinload(doc_model.items))

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create_or_update_by_unique_field(
        self,
        document_type: str,
        unique_value: str,
        header_data: Dict[str, Any],
        items_data: Optional[List[Dict[str, Any]]] = None,
        raw_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[Any, bool]:
        """
        Create new document or update existing one by unique field.

        This is the main method for saving documents - works for ALL document types.

        Args:
            document_type: Document type (invoice, boe, packing_list, etc.)
            unique_value: Value of the unique field
            header_data: Document header data
            items_data: Optional list of item data
            raw_data: Optional raw extraction data

        Returns:
            Tuple of (Document instance, was_updated: bool)

        Raises:
            ValueError: If document type not configured
        """
        logger.info(
            f"Creating or updating {document_type} with unique value: {unique_value}"
        )

        # Get models
        doc_model, items_model = self._get_models_for_document_type(document_type)
        unique_field = self.config.get_unique_field(document_type)
        has_items = self.config.has_items(document_type)

        # Check if document exists
        existing = await self.get_by_unique_field(
            document_type, 
            unique_value,
            load_items=has_items
        )

        if existing:
            # UPDATE existing document
            logger.info(f"Updating existing {document_type}: {unique_value}")

            # Update header fields
            for key, value in header_data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)

            # Update metadata
            existing.parsed_at = datetime.utcnow()
            if raw_data and hasattr(existing, 'raw_data'):
                existing.raw_data = raw_data

            # Handle items if document has them
            if has_items and items_data is not None and items_model:
                # Delete old items
                for item in existing.items:
                    await self.session.delete(item)

                await self.session.flush()

                # Create new items
                parent_fk_field = self.config.get_parent_fk_field(document_type)
                if not parent_fk_field:
                    raise ValueError(
                        f"No parent_fk_field configured for {document_type}"
                    )

                for item_data in items_data:
                    item = items_model(
                        **{parent_fk_field: existing.id},
                        **item_data
                    )
                    self.session.add(item)

            await self.session.flush()
            await self.session.refresh(existing)

            logger.info(
                f"Updated {document_type} {unique_value} with "
                f"{len(items_data) if items_data else 0} items"
            )
            return existing, True

        else:
            # CREATE new document
            logger.info(f"Creating new {document_type}: {unique_value}")

            # Add raw_data if provided
            if raw_data and 'raw_data' not in header_data:
                header_data['raw_data'] = raw_data

            # Create document
            document = doc_model(
                parsed_at=datetime.utcnow(),
                **header_data
            )
            self.session.add(document)
            await self.session.flush()

            # Create items if document has them
            if has_items and items_data is not None and items_model:
                parent_fk_field = self.config.get_parent_fk_field(document_type)
                if not parent_fk_field:
                    raise ValueError(
                        f"No parent_fk_field configured for {document_type}"
                    )

                for item_data in items_data:
                    item = items_model(
                        **{parent_fk_field: document.id},
                        **item_data
                    )
                    self.session.add(item)

            await self.session.flush()
            await self.session.refresh(document)

            logger.info(
                f"Created {document_type} {unique_value} with "
                f"{len(items_data) if items_data else 0} items"
            )
            return document, False

    async def get_by_id(self, document_type: str, document_id: str) -> Optional[Any]:
        """
        Get document by ID.

        Args:
            document_type: Document type
            document_id: Document UUID

        Returns:
            Document instance or None
        """
        doc_model, _ = self._get_models_for_document_type(document_type)
        
        query = select(doc_model).where(doc_model.id == document_id)
        
        if self.config.has_items(document_type):
            query = query.options(selectinload(doc_model.items))

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def delete_by_unique_field(
        self, 
        document_type: str, 
        unique_value: str
    ) -> bool:
        """
        Delete document by unique field.

        Args:
            document_type: Document type
            unique_value: Value of unique field

        Returns:
            True if deleted, False if not found
        """
        document = await self.get_by_unique_field(
            document_type, 
            unique_value,
            load_items=False
        )

        if not document:
            return False

        await self.session.delete(document)
        await self.session.flush()

        logger.info(f"Deleted {document_type}: {unique_value}")
        return True


def get_generic_repository(session: AsyncSession) -> GenericDocumentRepository:
    """
    Get generic repository instance.

    Args:
        session: Async database session

    Returns:
        GenericDocumentRepository instance
    """
    return GenericDocumentRepository(session)
