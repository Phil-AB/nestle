"""
Ground Truth Service - Core service for managing ground truth data.

Provides CRUD operations for storing and retrieving human-verified data
used for accuracy validation.
"""

from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime

from src.database.connection import get_session
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class GroundTruthService:
    """
    Service for managing ground truth (human-verified) data.
    
    Ground truth is used to measure extraction accuracy by comparing
    extracted values against manually verified correct values.
    
    Usage:
        service = GroundTruthService()
        
        # Store ground truth
        await service.store(
            document_id="uuid-123",
            document_type="invoice",
            verified_data={"invoice_number": "INV-001", "amount": 15000},
            verified_by="jane.doe"
        )
        
        # Retrieve ground truth
        gt = await service.get(document_id="uuid-123")
    """
    
    async def store(
        self,
        document_type: str,
        verified_data: Dict[str, Any],
        document_id: Optional[str] = None,
        verified_by: Optional[str] = None,
        verification_method: str = "manual",
        confidence_level: str = "high",
        notes: Optional[str] = None
    ) -> str:
        """
        Store ground truth data for a document.
        
        Args:
            document_type: Type of document (invoice, packing_list, etc.)
            verified_data: Dictionary of correct field values
            document_id: Optional UUID of the extracted document
            verified_by: Email/username of who verified
            verification_method: How it was verified (manual, automated, reference_system)
            confidence_level: Confidence in ground truth (high, medium, low)
            notes: Optional notes about verification
        
        Returns:
            UUID of the ground truth record
        
        Example:
            ground_truth_id = await service.store(
                document_type="invoice",
                verified_data={
                    "invoice_number": "INV-12345",
                    "total_amount": 15000.00,
                    "supplier_name": "ACME Corp"
                },
                document_id="abc-123",
                verified_by="john.doe@company.com",
                notes="Verified against original paper document"
            )
        """
        async with get_session() as session:
            query = """
                INSERT INTO ground_truth 
                (document_id, document_type, verified_data, verified_by, 
                 verification_method, confidence_level, notes)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
            """
            
            result = await session.fetchrow(
                query,
                document_id,
                document_type,
                verified_data,
                verified_by,
                verification_method,
                confidence_level,
                notes
            )
            
            ground_truth_id = str(result['id'])
            logger.info(f"Stored ground truth for {document_type}: {ground_truth_id}")
            
            return ground_truth_id
    
    async def get(
        self,
        document_id: Optional[str] = None,
        ground_truth_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve ground truth data.
        
        Args:
            document_id: UUID of the document
            ground_truth_id: UUID of the ground truth record
        
        Returns:
            Dictionary with verified_data, or None if not found
        
        Example:
            gt = await service.get(document_id="abc-123")
            if gt:
                print(gt['verified_data'])  # {"invoice_number": "INV-001", ...}
        """
        if not document_id and not ground_truth_id:
            raise ValueError("Either document_id or ground_truth_id must be provided")
        
        async with get_session() as session:
            if ground_truth_id:
                query = """
                    SELECT id, document_id, document_type, verified_data, 
                           verified_by, verified_at, verification_method,
                           confidence_level, notes
                    FROM ground_truth
                    WHERE id = $1
                """
                row = await session.fetchrow(query, ground_truth_id)
            else:
                query = """
                    SELECT id, document_id, document_type, verified_data,
                           verified_by, verified_at, verification_method,
                           confidence_level, notes
                    FROM ground_truth
                    WHERE document_id = $1
                    ORDER BY created_at DESC
                    LIMIT 1
                """
                row = await session.fetchrow(query, document_id)
            
            if not row:
                return None
            
            return {
                'id': str(row['id']),
                'document_id': str(row['document_id']) if row['document_id'] else None,
                'document_type': row['document_type'],
                'verified_data': row['verified_data'],
                'verified_by': row['verified_by'],
                'verified_at': row['verified_at'].isoformat() if row['verified_at'] else None,
                'verification_method': row['verification_method'],
                'confidence_level': row['confidence_level'],
                'notes': row['notes']
            }
    
    async def update(
        self,
        ground_truth_id: str,
        verified_data: Optional[Dict[str, Any]] = None,
        verified_by: Optional[str] = None,
        confidence_level: Optional[str] = None,
        notes: Optional[str] = None
    ) -> bool:
        """
        Update existing ground truth record.
        
        Args:
            ground_truth_id: UUID of ground truth record
            verified_data: Updated verified data
            verified_by: Updated verifier
            confidence_level: Updated confidence
            notes: Updated notes
        
        Returns:
            True if updated, False if not found
        """
        async with get_session() as session:
            updates = []
            params = []
            param_num = 1
            
            if verified_data is not None:
                updates.append(f"verified_data = ${param_num}")
                params.append(verified_data)
                param_num += 1
            
            if verified_by is not None:
                updates.append(f"verified_by = ${param_num}")
                params.append(verified_by)
                param_num += 1
            
            if confidence_level is not None:
                updates.append(f"confidence_level = ${param_num}")
                params.append(confidence_level)
                param_num += 1
            
            if notes is not None:
                updates.append(f"notes = ${param_num}")
                params.append(notes)
                param_num += 1
            
            if not updates:
                return False
            
            updates.append("updated_at = NOW()")
            params.append(ground_truth_id)
            
            query = f"""
                UPDATE ground_truth
                SET {', '.join(updates)}
                WHERE id = ${param_num}
            """
            
            result = await session.execute(query, *params)
            return result == "UPDATE 1"
    
    async def delete(self, ground_truth_id: str) -> bool:
        """
        Delete ground truth record.
        
        Args:
            ground_truth_id: UUID of ground truth record
        
        Returns:
            True if deleted, False if not found
        """
        async with get_session() as session:
            query = "DELETE FROM ground_truth WHERE id = $1"
            result = await session.execute(query, ground_truth_id)
            return result == "DELETE 1"
    
    async def list_by_document_type(
        self,
        document_type: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List all ground truth records for a document type.
        
        Args:
            document_type: Type of document
            limit: Maximum records to return
            offset: Offset for pagination
        
        Returns:
            List of ground truth records
        """
        async with get_session() as session:
            query = """
                SELECT id, document_id, document_type, verified_data,
                       verified_by, verified_at, verification_method,
                       confidence_level, notes, created_at
                FROM ground_truth
                WHERE document_type = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
            """
            
            rows = await session.fetch(query, document_type, limit, offset)
            
            return [
                {
                    'id': str(row['id']),
                    'document_id': str(row['document_id']) if row['document_id'] else None,
                    'document_type': row['document_type'],
                    'verified_data': row['verified_data'],
                    'verified_by': row['verified_by'],
                    'verified_at': row['verified_at'].isoformat() if row['verified_at'] else None,
                    'verification_method': row['verification_method'],
                    'confidence_level': row['confidence_level'],
                    'notes': row['notes'],
                    'created_at': row['created_at'].isoformat()
                }
                for row in rows
            ]
