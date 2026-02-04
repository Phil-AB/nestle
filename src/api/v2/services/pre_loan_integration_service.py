"""
Pre-Loan Integration Service.

Handles integration between the pre-loan qualification app
and the main document processing system.

All data is real - no hardcoded values.
"""

from typing import Optional, Dict, Any, List
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import logging

from src.database.models.api_document import APIDocument
from src.database.repositories.api_document_repository import APIDocumentRepository
from src.database.connection import get_session

logger = logging.getLogger(__name__)


class PreLoanIntegrationService:
    """
    Service for managing pre-loan qualification integration.

    Handles the workflow where users complete a pre-loan qualification check
    and then proceed to a full loan application.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize the integration service.

        Args:
            session: Async SQLAlchemy session
        """
        self.session = session
        self.document_repo = APIDocumentRepository(session)

    async def store_pre_loan_data(
        self,
        document_id: str,
        pre_loan_data: Dict[str, Any]
    ) -> Optional[APIDocument]:
        """
        Store pre-loan qualification data for a document.

        Args:
            document_id: Document ID to link pre-loan data to
            pre_loan_data: Pre-loan qualification results

        Returns:
            Updated document or None if not found

        Pre-loan data structure:
        {
            "session_id": "unique session identifier",
            "pre_loan_status": "eligible" | "discuss_with_officer" | "not_eligible",
            "pre_loan_date": "2026-01-30T10:30:00Z",
            "answers": {
                "employment_status": "employed",
                "monthly_income_range": "3,001 - 4,000",
                "age_range": "25-35",
                "existing_customer": false,
                ...
            },
            "risk_assessment": {
                "pre_score": 75,
                "factors": [...]
            }
        }
        """
        doc = await self.document_repo.get_by_document_id(document_id)
        if not doc:
            logger.warning(f"Document not found for pre-loan data: {document_id}")
            return None

        # Store pre-loan data in doc_metadata
        metadata = doc.doc_metadata or {}
        metadata["pre_loan"] = {
            "status": pre_loan_data.get("pre_loan_status"),
            "date": pre_loan_data.get("pre_loan_date"),
            "session_id": pre_loan_data.get("session_id"),
            "answers": pre_loan_data.get("answers"),
            "risk_assessment": pre_loan_data.get("risk_assessment"),
            "integrated_at": datetime.utcnow().isoformat(),
        }

        return await self.document_repo.update(
            document_id,
            {"doc_metadata": metadata}
        )

    async def get_pre_loan_status(
        self,
        document_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve pre-loan qualification data for a document.

        Args:
            document_id: Document ID

        Returns:
            Pre-loan data or None if not found
        """
        doc = await self.document_repo.get_by_document_id(document_id)
        if not doc:
            return None

        metadata = doc.doc_metadata or {}
        return metadata.get("pre_loan")

    async def list_pre_qualified_documents(
        self,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List documents that have pre-loan qualification data.

        Args:
            limit: Maximum results to return

        Returns:
            List of documents with pre-loan data
        """
        # Query documents with pre_loan metadata
        query = select(APIDocument).where(
            and_(
                APIDocument.extraction_status == "complete",
                APIDocument.doc_metadata["pre_loan"].astext != None
            )
        ).order_by(
            APIDocument.created_at.desc()
        ).limit(limit)

        result = await self.session.execute(query)
        documents = result.scalars().all()

        result_list = []
        for doc in documents:
            metadata = doc.doc_metadata or {}
            pre_loan = metadata.get("pre_loan", {})
            fields = doc.fields or {}

            # Extract customer name
            name = self._extract_customer_name(fields)

            result_list.append({
                "document_id": doc.document_id,
                "customer_name": name,
                "pre_loan_status": pre_loan.get("status"),
                "pre_loan_date": pre_loan.get("date"),
                "session_id": pre_loan.get("session_id"),
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
            })

        return result_list

    async def link_pre_loan_to_document(
        self,
        session_id: str,
        document_id: str
    ) -> Optional[APIDocument]:
        """
        Link an existing pre-loan session to a document after upload.

        This is called when a user uploads a full application after passing pre-loan check.

        Args:
            session_id: Pre-loan session identifier
            document_id: Document ID from full application upload

        Returns:
            Updated document or None if not found
        """
        doc = await self.document_repo.get_by_document_id(document_id)
        if not doc:
            logger.warning(f"Document not found for pre-loan linking: {document_id}")
            return None

        # TODO: In production, fetch the actual pre-loan data from external API
        # For now, store the session link
        metadata = doc.doc_metadata or {}
        metadata["pre_loan"] = {
            "status": "linked",
            "session_id": session_id,
            "linked_at": datetime.utcnow().isoformat(),
        }

        return await self.document_repo.update(
            document_id,
            {"doc_metadata": metadata}
        )

    async def get_combined_assessment(
        self,
        document_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get combined assessment from pre-loan check and full document insights.

        Args:
            document_id: Document ID

        Returns:
            Combined assessment data or None if not found
        """
        doc = await self.document_repo.get_by_document_id(document_id)
        if not doc:
            return None

        metadata = doc.doc_metadata or {}
        pre_loan = metadata.get("pre_loan", {})

        # Extract risk scores from both sources
        insights_risk_score = metadata.get("risk_score")
        pre_loan_risk_score = pre_loan.get("risk_assessment", {}).get("pre_score")

        return {
            "document_id": document_id,
            "pre_loan_status": pre_loan.get("status"),
            "pre_loan_risk_score": pre_loan_risk_score,
            "insights_risk_score": insights_risk_score,
            "combined_status": self._calculate_combined_status(
                pre_loan.get("status"),
                insights_risk_score
            ),
            "pre_loan_date": pre_loan.get("date"),
            "session_id": pre_loan.get("session_id"),
        }

    def _calculate_combined_status(
        self,
        pre_loan_status: Optional[str],
        insights_risk_score: Optional[int]
    ) -> str:
        """
        Calculate combined status from both assessments.

        Args:
            pre_loan_status: Status from pre-loan check
            insights_risk_score: Risk score from full insights

        Returns:
            Combined status string
        """
        if pre_loan_status == "not_eligible":
            return "not_eligible"
        elif pre_loan_status == "discuss_with_officer":
            return "requires_review"
        elif pre_loan_status == "eligible":
            if insights_risk_score and insights_risk_score >= 50:
                return "approved"
            return "pending_full_assessment"
        return "unknown"

    def _extract_customer_name(self, fields: Dict[str, Any]) -> str:
        """Extract customer name from document fields."""
        # Try different name field patterns
        name_field = fields.get("name", {})
        if isinstance(name_field, dict) and "value" in name_field:
            return name_field["value"]
        elif isinstance(name_field, str):
            return name_field

        # Try first_name + surname
        first = fields.get("first_name", {})
        surname = fields.get("surname", {})
        if isinstance(first, dict):
            first = first.get("value", "")
        else:
            first = first
        if isinstance(surname, dict):
            surname = surname.get("value", "")
        else:
            surname = surname

        if first or surname:
            return f"{first} {surname}".strip()

        return "Unknown"


# Session management for pre-loan to document linking
class PreLoanSessionManager:
    """
    Manages temporary sessions for pre-loan to document linking.
    """

    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def create_session(self, pre_loan_data: Dict[str, Any]) -> str:
        """
        Create a new session and return its ID.

        Args:
            pre_loan_data: Pre-loan qualification results

        Returns:
            Session ID
        """
        import uuid
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "data": pre_loan_data,
            "created_at": datetime.utcnow(),
            "document_id": None,  # Will be set when document is uploaded
            "expires_at": datetime.utcnow() + timedelta(hours=24),  # Session expires in 24 hours
        }
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session data or None if not found/expired
        """
        session = self.sessions.get(session_id)
        if not session:
            return None

        # Check if expired
        if datetime.utcnow() > session["expires_at"]:
            del self.sessions[session_id]
            return None

        return session

    def link_document(self, session_id: str, document_id: str) -> bool:
        """
        Link a document to a session.

        Args:
            session_id: Session ID
            document_id: Document ID

        Returns:
            True if linked successfully, False otherwise
        """
        session = self.get_session(session_id)
        if not session:
            return False

        session["document_id"] = document_id
        return True

    def cleanup_expired_sessions(self):
        """Clean up expired sessions."""
        now = datetime.utcnow()
        expired = [
            sid for sid, s in self.sessions.items()
            if now > s["expires_at"]
        ]
        for sid in expired:
            del self.sessions[sid]

        logger.info(f"Cleaned up {len(expired)} expired pre-loan sessions")


from datetime import timedelta
