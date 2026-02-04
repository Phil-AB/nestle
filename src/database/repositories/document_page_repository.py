"""
Repository for document pages.

Handles CRUD operations for multi-page document pages.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import uuid

from src.database.models.document_page import DocumentPage
from src.database.repositories.base import BaseRepository
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class DocumentPageRepository(BaseRepository[DocumentPage]):
    """Repository for managing document pages."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(DocumentPage, session)
    
    async def create_page(
        self,
        document_id: str,
        page_number: int,
        file_path: str,
        file_name: str,
        file_size: Optional[int] = None,
        mime_type: Optional[str] = None
    ) -> DocumentPage:
        """
        Create a new document page.
        
        Args:
            document_id: Parent document ID
            page_number: Page number (1-indexed)
            file_path: Path to page file
            file_name: Original filename
            file_size: File size in bytes
            mime_type: MIME type
            
        Returns:
            Created DocumentPage instance
        """
        page_id = str(uuid.uuid4())
        
        page = DocumentPage(
            page_id=page_id,
            document_id=document_id,
            page_number=page_number,
            file_path=file_path,
            file_name=file_name,
            file_size=file_size,
            mime_type=mime_type,
            extraction_status="pending"
        )
        
        self.session.add(page)
        await self.session.flush()
        
        logger.info(f"Created page {page_id} for document {document_id}, page number {page_number}")
        return page
    
    async def get_by_id(self, page_id: str) -> Optional[DocumentPage]:
        """Get page by ID."""
        result = await self.session.execute(
            select(DocumentPage).where(DocumentPage.page_id == page_id)
        )
        return result.scalar_one_or_none()
    
    async def get_document_pages(
        self,
        document_id: str,
        order_by_page_number: bool = True
    ) -> List[DocumentPage]:
        """
        Get all pages for a document.
        
        Args:
            document_id: Parent document ID
            order_by_page_number: Sort by page number (default: True)
            
        Returns:
            List of DocumentPage instances
        """
        query = select(DocumentPage).where(DocumentPage.document_id == document_id)
        
        if order_by_page_number:
            query = query.order_by(DocumentPage.page_number)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_page_by_number(
        self,
        document_id: str,
        page_number: int
    ) -> Optional[DocumentPage]:
        """Get specific page by number."""
        result = await self.session.execute(
            select(DocumentPage)
            .where(DocumentPage.document_id == document_id)
            .where(DocumentPage.page_number == page_number)
        )
        return result.scalar_one_or_none()
    
    async def update_page_status(
        self,
        page_id: str,
        status: str,
        extraction_result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update page extraction status and results.
        
        Args:
            page_id: Page ID
            status: New status (pending, processing, completed, failed)
            extraction_result: Extraction data for this page
            error_message: Error message if failed
            
        Returns:
            True if updated successfully
        """
        update_data = {"extraction_status": status}
        
        if extraction_result is not None:
            update_data["extraction_result"] = extraction_result
        
        if error_message is not None:
            update_data["error_message"] = error_message
        
        result = await self.session.execute(
            update(DocumentPage)
            .where(DocumentPage.page_id == page_id)
            .values(**update_data)
        )
        
        await self.session.flush()
        
        success = result.rowcount > 0
        if success:
            logger.info(f"Updated page {page_id} status to {status}")
        
        return success
    
    async def reorder_pages(
        self,
        document_id: str,
        page_order: List[str]
    ) -> bool:
        """
        Reorder pages for a document.
        
        Args:
            document_id: Parent document ID
            page_order: List of page IDs in desired order
            
        Returns:
            True if reordered successfully
        """
        try:
            for new_position, page_id in enumerate(page_order, start=1):
                await self.session.execute(
                    update(DocumentPage)
                    .where(DocumentPage.page_id == page_id)
                    .where(DocumentPage.document_id == document_id)
                    .values(page_number=new_position)
                )
            
            await self.session.flush()
            logger.info(f"Reordered {len(page_order)} pages for document {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reorder pages: {e}")
            return False
    
    async def delete_page(self, page_id: str) -> bool:
        """Delete a page."""
        result = await self.session.execute(
            delete(DocumentPage).where(DocumentPage.page_id == page_id)
        )
        await self.session.flush()
        
        success = result.rowcount > 0
        if success:
            logger.info(f"Deleted page {page_id}")
        
        return success
    
    async def count_pages(self, document_id: str) -> int:
        """Count pages for a document."""
        pages = await self.get_document_pages(document_id)
        return len(pages)
    
    async def get_extraction_summary(self, document_id: str) -> Dict[str, Any]:
        """
        Get extraction status summary for all pages.
        
        Returns:
            Summary dict with counts by status
        """
        pages = await self.get_document_pages(document_id)
        
        summary = {
            "total_pages": len(pages),
            "pending": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
        }
        
        for page in pages:
            status = page.extraction_status
            if status in summary:
                summary[status] += 1
        
        return summary
