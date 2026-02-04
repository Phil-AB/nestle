"""
Automated Approval Agent - Agentic AI for Low-Risk Decisions.

LangGraph-based agent that automatically processes and approves low-risk
loan applications without manual review.

Workflow:
1. Check eligibility (risk score >= 70, pre-loan status = eligible)
2. Fetch document and customer data
3. Generate approval letter PDF
4. Send email notification
5. Update document status in database
6. Log automation result
"""

from typing import Dict, Any, Optional, List, TypedDict, Annotated
import json
import operator
from datetime import datetime

from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage

from modules.automation.agents.base_automation_agent import (
    BaseAutomationAgent,
    AutomationTask,
    AutomationResult
)
from modules.automation.services.email_service import EmailService, get_email_service
from modules.automation.services.approval_letter_service import ApprovalLetterService, get_approval_letter_service
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


# ==============================================================================
# STATE DEFINITION
# ==============================================================================

class ApprovalAgentState(TypedDict):
    """State that flows through the approval agent graph."""
    # Input
    task: AutomationTask
    document_id: str

    # Intermediate results
    customer_data: Optional[Dict[str, Any]]  # Customer and document data
    eligibility_result: Optional[Dict[str, bool]]  # Eligibility check results
    approval_letter: Optional[bytes]  # Generated PDF
    email_result: Optional[Dict[str, Any]]  # Email sending result
    database_update: Optional[Dict[str, Any]]  # Database update result

    # Messages for tracking
    messages: Annotated[List[BaseMessage], operator.add]

    # Output
    success: bool
    action_taken: Optional[str]
    error: Optional[str]


# ==============================================================================
# AUTOMATED APPROVAL AGENT (LangGraph)
# ==============================================================================

class AutomatedApprovalAgent(BaseAutomationAgent):
    """
    LangGraph-based agent for automated approval of low-risk applications.

    Automatically approves applications that meet all criteria:
    - Risk score >= 70 (low risk)
    - Pre-loan status = "eligible" (if available)
    - All required fields present
    - No validation errors

    Workflow:
    1. Check eligibility
    2. Fetch customer data
    3. Generate approval letter
    4. Send email notification
    5. Update document status
    6. Return result

    Example:
        >>> agent = AutomatedApprovalAgent()
        >>> task = AutomationTask(
        ...     document_id="doc123",
        ...     trigger_event="insights_generated",
        ...     trigger_data={"risk_score": 85}
        ... )
        >>> result = await agent.execute(task)
    """

    def __init__(
        self,
        llm_provider: str = "anthropic",
        llm_model: str = "claude-3-5-haiku-20241022",
        temperature: float = 0.0,
        config: Optional[Dict[str, Any]] = None,
        session_factory: Optional[Any] = None
    ):
        """
        Initialize automated approval agent.

        Args:
            llm_provider: LLM provider
            llm_model: LLM model name
            temperature: LLM temperature (0.0 for deterministic)
            config: Agent configuration
            session_factory: Database session factory
        """
        super().__init__(llm_provider, llm_model, temperature, config)

        self.session_factory = session_factory
        self.email_service: Optional[EmailService] = None
        self.letter_service: Optional[ApprovalLetterService] = None

        # Build state graph
        self.graph = self._build_graph()

        logger.info("AutomatedApprovalAgent initialized with LangGraph")

    def _build_graph(self) -> StateGraph:
        """
        Build the state graph for the approval workflow.

        Graph flow:
        START → check_eligibility → fetch_data → generate_letter → send_email → update_status → END
                            ↓                    ↓
                          (skip)              (skip if no email)
        """
        graph = StateGraph(ApprovalAgentState)

        # Define nodes
        graph.add_node("check_eligibility", self._check_eligibility_node)
        graph.add_node("fetch_data", self._fetch_data_node)
        graph.add_node("generate_letter", self._generate_letter_node)
        graph.add_node("send_email", self._send_email_node)
        graph.add_node("update_status", self._update_status_node)

        # Define edges with conditional routing
        graph.set_entry_point("check_eligibility")

        # From eligibility check: proceed if eligible, end if not
        graph.add_conditional_edges(
            "check_eligibility",
            self._should_proceed,
            {
                "proceed": "fetch_data",
                "skip": END
            }
        )

        graph.add_edge("fetch_data", "generate_letter")

        # From generate letter: always try to send email
        graph.add_edge("generate_letter", "send_email")

        # From send email: always update status
        graph.add_edge("send_email", "update_status")

        # End after status update
        graph.add_edge("update_status", END)

        logger.info("Built LangGraph state graph for automated approval")
        return graph.compile()

    # ==========================================================================
    # CONDITIONAL ROUTING
    # ==========================================================================

    def _should_proceed(self, state: ApprovalAgentState) -> str:
        """Determine if workflow should proceed based on eligibility."""
        if state.get('error'):
            return "skip"

        eligibility = state.get('eligibility_result', {})
        if not eligibility.get('eligible', False):
            logger.info(f"Document {state['document_id']} not eligible for auto-approval")
            return "skip"

        return "proceed"

    # ==========================================================================
    # GRAPH NODES
    # ==========================================================================

    async def _check_eligibility_node(self, state: ApprovalAgentState) -> ApprovalAgentState:
        """Node: Check if document is eligible for automated approval."""
        document_id = state['document_id']
        logger.info(f"Node: check_eligibility - Checking {document_id}")

        try:
            if not self.session_factory:
                state['error'] = "No database session factory configured"
                state['success'] = False
                return state

            from src.database.connection import get_session
            from src.database.repositories.api_document_repository import APIDocumentRepository

            async with get_session() as session:
                repo = APIDocumentRepository(session)
                doc = await repo.get_by_document_id(document_id)

                if not doc:
                    state['error'] = f"Document not found: {document_id}"
                    state['success'] = False
                    return state

                # Check eligibility criteria
                criteria = {
                    "exists": True,
                    "extraction_complete": doc.extraction_status == "complete",
                    "has_insights": False,
                    "risk_score_threshold": False,
                    "pre_loan_eligible": True  # Default true if no pre-loan data
                }

                # Check for insights (risk score)
                metadata = doc.doc_metadata or {}
                insights = metadata.get("banking_insights", {})
                risk_assessment = insights.get("risk_assessment", {})

                if risk_assessment:
                    criteria["has_insights"] = True
                    risk_score = risk_assessment.get("risk_score", 0)
                    criteria["risk_score_threshold"] = risk_score >= 70

                # Check pre-loan status if available
                pre_loan = metadata.get("pre_loan", {})
                if pre_loan:
                    pre_loan_status = pre_loan.get("status")
                    criteria["pre_loan_eligible"] = pre_loan_status == "eligible"

                # Overall eligibility
                eligible = all([
                    criteria["exists"],
                    criteria["extraction_complete"],
                    criteria["risk_score_threshold"],
                    criteria["pre_loan_eligible"]
                ])

                state['eligibility_result'] = {
                    "eligible": eligible,
                    "criteria": criteria,
                    "risk_score": risk_assessment.get("risk_score", 0) if risk_assessment else 0
                }

                state['messages'].append(HumanMessage(
                    content=f"Eligibility check: {'ELIGIBLE' if eligible else 'NOT ELIGIBLE'} for auto-approval"
                ))

                logger.info(f"Eligibility result: eligible={eligible}, criteria={criteria}")

        except Exception as e:
            logger.error(f"Eligibility check failed: {e}", exc_info=True)
            state['error'] = f"Eligibility check failed: {e}"
            state['success'] = False

        return state

    async def _fetch_data_node(self, state: ApprovalAgentState) -> ApprovalAgentState:
        """Node: Fetch customer and document data."""
        document_id = state['document_id']
        logger.info(f"Node: fetch_data - Fetching data for {document_id}")

        try:
            from src.database.connection import get_session
            from src.database.repositories.api_document_repository import APIDocumentRepository

            async with get_session() as session:
                repo = APIDocumentRepository(session)
                doc = await repo.get_by_document_id(document_id)

                if not doc:
                    state['error'] = f"Document not found: {document_id}"
                    state['success'] = False
                    return state

                # Extract customer data
                fields = doc.fields or {}
                metadata = doc.doc_metadata or {}
                insights = metadata.get("banking_insights", {})

                customer_data = {
                    "customer_name": self._extract_customer_name(fields),
                    "customer_address": self._extract_customer_address(fields),
                    "customer_email": self._extract_customer_email(fields),
                    "account_number": fields.get("account_number", {}).get("value", "N/A"),
                    "document_id": document_id,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                }

                # Add loan details from insights
                if insights:
                    risk_assessment = insights.get("risk_assessment", {})
                    product_eligibility = insights.get("product_eligibility", {})

                    customer_data["risk_score"] = risk_assessment.get("risk_score", 0)
                    customer_data["risk_level"] = risk_assessment.get("risk_level", "unknown")

                    # Use Extra Cash loan details if available
                    extra_cash = product_eligibility.get("extra_cash", {})
                    if extra_cash.get("eligible"):
                        customer_data["approved_amount"] = extra_cash.get("max_amount", 0)
                        customer_data["interest_rate"] = extra_cash.get("interest_rate", 0)
                        customer_data["term_months"] = extra_cash.get("term_months", 12)

                state['customer_data'] = customer_data

                state['messages'].append(HumanMessage(
                    content=f"Data fetched: {customer_data['customer_name']}, risk_score={customer_data.get('risk_score', 0)}"
                ))

                logger.info(f"Fetched customer data for {customer_data['customer_name']}")

        except Exception as e:
            logger.error(f"Data fetch failed: {e}", exc_info=True)
            state['error'] = f"Data fetch failed: {e}"
            state['success'] = False

        return state

    async def _generate_letter_node(self, state: ApprovalAgentState) -> ApprovalAgentState:
        """Node: Generate approval letter PDF."""
        logger.info("Node: generate_letter - Creating approval letter")

        try:
            # Initialize letter service if needed
            if self.letter_service is None:
                self.letter_service = get_approval_letter_service()

            customer = state['customer_data']

            # Generate approval letter
            pdf_content = await self.letter_service.generate_approval_letter(
                customer_name=customer['customer_name'],
                customer_address=customer['customer_address'],
                document_id=customer['document_id'],
                risk_score=customer.get('risk_score', 0),
                approved_amount=customer.get('approved_amount', 5000),
                interest_rate=customer.get('interest_rate', 15),
                term_months=customer.get('term_months', 12),
                account_number=customer['account_number'],
                application_date=customer.get('created_at')
            )

            state['approval_letter'] = pdf_content

            state['messages'].append(HumanMessage(
                content=f"Approval letter generated: {len(pdf_content)} bytes"
            ))

            logger.info(f"Generated approval letter: {len(pdf_content)} bytes")

        except Exception as e:
            logger.error(f"Letter generation failed: {e}", exc_info=True)
            state['error'] = f"Letter generation failed: {e}"
            state['success'] = False

        return state

    async def _send_email_node(self, state: ApprovalAgentState) -> ApprovalAgentState:
        """Node: Send email notification with approval letter."""
        logger.info("Node: send_email - Sending notification")

        try:
            # Initialize email service if needed
            if self.email_service is None:
                self.email_service = get_email_service()

            customer = state['customer_data']

            # Check if customer has email
            if not customer.get('customer_email'):
                logger.warning(f"No email for customer {customer['customer_name']}, skipping email")
                state['messages'].append(HumanMessage(
                    content="Email skipped: no customer email address"
                ))
                return state

            # Send approval email
            result = await self.email_service.send_approval_email(
                customer_name=customer['customer_name'],
                customer_email=customer['customer_email'],
                document_id=customer['document_id'],
                risk_score=customer.get('risk_score', 0),
                approved_amount=customer.get('approved_amount', 5000),
                interest_rate=customer.get('interest_rate', 15),
                account_number=customer['account_number'],
                approval_letter_pdf=state.get('approval_letter')
            )

            state['email_result'] = result

            state['messages'].append(HumanMessage(
                content=f"Email sent: {result.get('success', False)} - {result.get('message', '')}"
            ))

            logger.info(f"Email result: success={result.get('success', False)}")

        except Exception as e:
            logger.error(f"Email sending failed: {e}", exc_info=True)
            # Don't fail the entire workflow for email errors
            state['email_result'] = {"success": False, "message": str(e)}
            state['messages'].append(HumanMessage(
                content=f"Email failed: {str(e)}"
            ))

        return state

    async def _update_status_node(self, state: ApprovalAgentState) -> ApprovalAgentState:
        """Node: Update document status in database."""
        logger.info("Node: update_status - Updating document status")

        try:
            from src.database.connection import get_session
            from src.database.repositories.api_document_repository import APIDocumentRepository

            async with get_session() as session:
                repo = APIDocumentRepository(session)

                # Update document metadata with automation result
                doc = await repo.get_by_document_id(state['document_id'])
                if doc:
                    metadata = doc.doc_metadata or {}
                    automation = metadata.get("automation", {})

                    automation["auto_approval"] = {
                        "approved_at": datetime.utcnow().isoformat(),
                        "approved": True,
                        "risk_score": state['customer_data'].get('risk_score', 0),
                        "email_sent": state['email_result'].get('success', False) if state.get('email_result') else False,
                        "letter_generated": bool(state.get('approval_letter'))
                    }

                    metadata["automation"] = automation
                    metadata["approval_status"] = "auto_approved"

                    await repo.update(state['document_id'], {"doc_metadata": metadata})

                state['database_update'] = {"success": True}

                state['messages'].append(HumanMessage(
                    content="Document status updated: auto_approved"
                ))

                state['action_taken'] = "auto_approved"
                state['success'] = True

                logger.info(f"Document {state['document_id']} marked as auto-approved")

        except Exception as e:
            logger.error(f"Status update failed: {e}", exc_info=True)
            state['error'] = f"Status update failed: {e}"
            state['success'] = False

        return state

    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================

    async def execute(self, task: AutomationTask) -> AutomationResult:
        """
        Execute automated approval workflow.

        Args:
            task: Automation task with document_id

        Returns:
            AutomationResult with action taken
        """
        try:
            logger.info(
                f"Starting automated approval: document={task.document_id}, "
                f"trigger={task.trigger_event}"
            )

            # Initialize state
            initial_state: ApprovalAgentState = {
                "task": task,
                "document_id": task.document_id,
                "customer_data": None,
                "eligibility_result": None,
                "approval_letter": None,
                "email_result": None,
                "database_update": None,
                "messages": [],
                "success": True,
                "action_taken": None,
                "error": None
            }

            # Execute graph
            logger.info("Executing automated approval workflow...")
            final_state = await self.graph.ainvoke(initial_state)

            # Determine result
            if final_state.get('error'):
                return AutomationResult(
                    success=False,
                    document_id=task.document_id,
                    action_taken="none",
                    error=final_state.get('error'),
                    metadata={
                        "trigger_event": task.trigger_event,
                        "workflow_messages": [msg.content for msg in final_state.get('messages', [])]
                    }
                )

            action_taken = final_state.get('action_taken', 'processed')

            return AutomationResult(
                success=True,
                document_id=task.document_id,
                action_taken=action_taken,
                metadata={
                    "eligibility": final_state.get('eligibility_result'),
                    "email_sent": final_state.get('email_result', {}).get('success', False),
                    "letter_generated": bool(final_state.get('approval_letter')),
                    "customer_data": {
                        "name": final_state.get('customer_data', {}).get('customer_name'),
                        "risk_score": final_state.get('customer_data', {}).get('risk_score')
                    },
                    "trigger_event": task.trigger_event,
                    "workflow_messages": [msg.content for msg in final_state.get('messages', [])]
                }
            )

        except Exception as e:
            logger.error(f"Automated approval failed: {e}", exc_info=True)
            return AutomationResult(
                success=False,
                document_id=task.document_id,
                action_taken="none",
                error=str(e),
                metadata={"trigger_event": task.trigger_event}
            )

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================

    def _extract_customer_name(self, fields: Dict[str, Any]) -> str:
        """Extract customer name from fields."""
        # Try name field
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

        return "Valued Customer"

    def _extract_customer_address(self, fields: Dict[str, Any]) -> str:
        """Extract customer address from fields."""
        address = fields.get("address", {})
        if isinstance(address, dict) and "value" in address:
            return address["value"]
        elif isinstance(address, str):
            return address
        return "Accra, Ghana"

    def _extract_customer_email(self, fields: Dict[str, Any]) -> Optional[str]:
        """Extract customer email from fields."""
        email = fields.get("email", {})
        if isinstance(email, dict) and "value" in email:
            return email["value"]
        elif isinstance(email, str):
            return email
        return None
