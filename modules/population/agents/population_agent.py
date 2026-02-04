"""
Population Agent - Intelligent PDF Form Population with LangGraph.

Modern LangGraph-based agent that intelligently populates fillable PDF forms using:
- PDF field inspection to extract actual field names from AcroForm
- Database queries to fetch document data
- Intelligent field mapping with fuzzy matching
- Validation before form filling

The agent uses a state graph to orchestrate the workflow, providing better
control and observability than traditional ReAct agents.
"""

from typing import Dict, Any, Optional, List, TypedDict, Annotated
import json
import operator

from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage

from modules.population.agents.base_population_agent import (
    BasePopulationAgent,
    PopulationTask,
    PopulationResult
)
from modules.population.agents.tools import (
    PDFFieldInspectionTool,
    DatabaseQueryTool,
    ValidationTool
)
# Import enhanced semantic field mapping tool
from modules.population.agents.enhanced_tools import SemanticFieldMappingTool
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


# ==============================================================================
# STATE DEFINITION
# ==============================================================================

class AgentState(TypedDict):
    """State that flows through the agent graph."""
    # Input
    task: PopulationTask
    template_path: str
    document_ids: List[str]

    # Intermediate results
    pdf_fields: Optional[str]  # JSON string of PDF field names
    database_data: Optional[str]  # JSON string of document data
    field_mappings: Optional[Dict[str, Any]]  # Final mappings
    validation_result: Optional[Dict[str, Any]]  # Validation results

    # Messages for tool calls
    messages: Annotated[List[BaseMessage], operator.add]

    # Output
    success: bool
    error: Optional[str]
    confidence: float


# ==============================================================================
# POPULATION AGENT (LangGraph)
# ==============================================================================

class PopulationAgent(BasePopulationAgent):
    """
    LangGraph-based agent for intelligent PDF form population.

    Uses state graph workflow:
    1. Extract PDF field names from fillable form (PDF inspection)
    2. Fetch document data from database (shows all available fields)
    3. Map database fields to PDF fields (fuzzy matching)
    4. Validate mappings
    5. Return field mappings for PDFFormFiller

    Example:
        >>> agent = PopulationAgent(
        ...     llm_provider="google",
        ...     llm_model="gemini-2.5-pro",
        ...     data_provider=postgres_provider
        ... )
        >>> task = PopulationTask(
        ...     form_id="boe_gra_v1",
        ...     document_ids=["doc1", "doc2"],
        ...     template_path="form.pdf"
        ... )
        >>> result = await agent.populate(task)
    """

    def __init__(
        self,
        llm_provider: str = "google",
        llm_model: str = "gemini-2.5-pro",
        temperature: float = 0.0,
        config: Optional[Dict[str, Any]] = None,
        data_provider: Optional[Any] = None
    ):
        """
        Initialize population agent.

        Args:
            llm_provider: LLM provider (anthropic, openai, google)
            llm_model: LLM model name
            temperature: LLM temperature (0.0 for deterministic)
            config: Agent configuration dict
            data_provider: PostgreSQL data provider instance
        """
        super().__init__(llm_provider, llm_model, temperature, config)

        self.data_provider = data_provider

        # Initialize tools
        self.tools = self._initialize_tools()

        # Build state graph
        self.graph = self._build_graph()

        logger.info("PopulationAgent initialized with LangGraph")

    def _initialize_tools(self) -> List:
        """Initialize tools for the agent."""
        tools = [
            PDFFieldInspectionTool(),
            SemanticFieldMappingTool(llm=self.llm),  # ⭐ NEW: Enhanced semantic mapping
            ValidationTool()
        ]

        if self.data_provider:
            tools.append(DatabaseQueryTool(data_provider=self.data_provider))

        logger.info(f"✅ Initialized {len(tools)} tools with SEMANTIC mapping: {[t.name for t in tools]}")
        return tools

    def _build_graph(self) -> StateGraph:
        """
        Build the state graph for the agent workflow.

        Graph flow:
        START → inspect_pdf → query_database → map_fields → validate → END
        """
        graph = StateGraph(AgentState)

        # Define nodes
        graph.add_node("inspect_pdf", self._inspect_pdf_node)
        graph.add_node("query_database", self._query_database_node)
        graph.add_node("map_fields", self._map_fields_node)
        graph.add_node("validate", self._validate_node)

        # Define edges
        graph.set_entry_point("inspect_pdf")
        graph.add_edge("inspect_pdf", "query_database")
        graph.add_edge("query_database", "map_fields")
        graph.add_edge("map_fields", "validate")
        graph.add_edge("validate", END)

        logger.info("Built LangGraph state graph")
        return graph.compile()

    # ==========================================================================
    # GRAPH NODES
    # ==========================================================================

    async def _inspect_pdf_node(self, state: AgentState) -> AgentState:
        """Node: Extract PDF field names from fillable form."""
        logger.info(f"Node: inspect_pdf - Analyzing {state['template_path']}")

        try:
            pdf_tool = PDFFieldInspectionTool()
            result = await pdf_tool._arun(pdf_path=state['template_path'])

            state['pdf_fields'] = result
            state['messages'].append(HumanMessage(content=f"PDF inspection complete: {len(json.loads(result))} fields found"))

            logger.info(f"Extracted {len(json.loads(result))} PDF fields")
        except Exception as e:
            logger.error(f"PDF inspection failed: {e}")
            state['error'] = f"PDF inspection failed: {e}"
            state['success'] = False

        return state

    async def _query_database_node(self, state: AgentState) -> AgentState:
        """Node: Fetch document data from database."""
        logger.info(f"Node: query_database - Fetching {len(state['document_ids'])} documents")

        try:
            db_tool = DatabaseQueryTool(data_provider=self.data_provider)
            merge_strategy = state['task'].options.get('merge_strategy', 'best_available')

            result = await db_tool._arun(
                document_ids=state['document_ids'],
                merge_strategy=merge_strategy
            )

            state['database_data'] = result
            data = json.loads(result)
            state['messages'].append(HumanMessage(
                content=f"Database query complete: {len(data.get('fields', {}))} fields retrieved"
            ))

            logger.info(f"Retrieved {len(data.get('fields', {}))} database fields")
        except Exception as e:
            logger.error(f"Database query failed: {e}")
            state['error'] = f"Database query failed: {e}"
            state['success'] = False

        return state

    async def _map_fields_node(self, state: AgentState) -> AgentState:
        """Node: Intelligently map database fields to PDF fields using semantic understanding."""
        logger.info("🧠 Node: map_fields - SEMANTIC matching with LLM validation")

        try:
            # Use enhanced semantic mapping tool
            mapping_tool = SemanticFieldMappingTool(llm=self.llm)
            fuzzy_threshold = self.config.get('agent', {}).get('tools', {}).get('field_mapping', {}).get('fuzzy_threshold', 0.60)

            logger.info(f"Using semantic threshold: {fuzzy_threshold}")

            result = await mapping_tool._arun(
                detected_fields=state['pdf_fields'],
                database_fields=state['database_data'],
                fuzzy_threshold=fuzzy_threshold
            )

            mappings = json.loads(result)
            state['field_mappings'] = mappings
            state['messages'].append(HumanMessage(
                content=f"Field mapping complete: {len(mappings)} mappings created"
            ))

            logger.info(f"Created {len(mappings)} field mappings")
        except Exception as e:
            logger.error(f"Field mapping failed: {e}", exc_info=True)
            state['error'] = f"Field mapping failed: {e}"
            state['field_mappings'] = {}  # Empty dict instead of None to prevent validation errors
            state['success'] = False

        return state

    async def _validate_node(self, state: AgentState) -> AgentState:
        """Node: Validate field mappings."""
        logger.info("Node: validate - Checking mapping quality")

        try:
            validation_tool = ValidationTool()
            strict_mode = self.config.get('tools', {}).get('validation', {}).get('strict_mode', False)

            result = await validation_tool._arun(
                field_mappings=json.dumps(state['field_mappings']),
                strict_mode=strict_mode
            )

            validation = json.loads(result)
            state['validation_result'] = validation

            # Calculate confidence
            state['confidence'] = self._calculate_confidence(state['field_mappings'])

            # Set success
            state['success'] = validation.get('valid', False)

            state['messages'].append(HumanMessage(
                content=f"Validation complete: {'✓ Valid' if validation['valid'] else '✗ Invalid'} "
                       f"(confidence: {state['confidence']:.2f})"
            ))

            logger.info(f"Validation: {validation['validated_count']} fields validated, "
                       f"confidence: {state['confidence']:.2f}")
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            state['error'] = f"Validation failed: {e}"
            state['success'] = False

        return state

    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================

    async def populate(self, task: PopulationTask) -> PopulationResult:
        """
        Populate PDF form with intelligent field mapping using LangGraph.

        Args:
            task: Population task specification

        Returns:
            PopulationResult with field mappings and metadata
        """
        try:
            logger.info(
                f"Starting LangGraph population: form={task.form_id}, "
                f"docs={len(task.document_ids)}"
            )

            # Initialize state
            initial_state: AgentState = {
                "task": task,
                "template_path": task.template_path,
                "document_ids": task.document_ids,
                "pdf_fields": None,
                "database_data": None,
                "field_mappings": None,
                "validation_result": None,
                "messages": [],
                "success": True,
                "error": None,
                "confidence": 0.0
            }

            # Execute graph
            logger.info("Executing LangGraph workflow...")
            final_state = await self.graph.ainvoke(initial_state)

            # Extract results
            if not final_state['success']:
                return PopulationResult(
                    success=False,
                    error=final_state.get('error', 'Unknown error'),
                    metadata={"form_id": task.form_id}
                )

            # Convert field_mappings to simple dict format for PDFFormFiller
            # Format: {pdf_field_name: value}
            simple_mappings = {}
            for pdf_field, mapping in final_state['field_mappings'].items():
                if isinstance(mapping, dict):
                    simple_mappings[pdf_field] = mapping.get('value', '')
                else:
                    simple_mappings[pdf_field] = mapping

            logger.info(f"LangGraph workflow complete: {len(simple_mappings)} mappings")

            return PopulationResult(
                success=True,
                field_mappings=simple_mappings,
                confidence=final_state['confidence'],
                metadata={
                    "form_id": task.form_id,
                    "document_ids": task.document_ids,
                    "validation": final_state['validation_result'],
                    "workflow_messages": [msg.content for msg in final_state['messages']],
                    "agent_type": "langgraph"
                }
            )

        except Exception as e:
            logger.error(f"LangGraph population failed: {e}", exc_info=True)
            return PopulationResult(
                success=False,
                error=str(e),
                metadata={"form_id": task.form_id, "agent_type": "langgraph"}
            )

    def _calculate_confidence(self, field_mappings: Dict[str, Any]) -> float:
        """Calculate overall confidence score for mappings."""
        if not field_mappings:
            return 0.0

        confidences = []
        for mapping in field_mappings.values():
            if isinstance(mapping, dict):
                confidences.append(mapping.get("confidence", 0.0))
            else:
                # Simple string value, assume high confidence
                confidences.append(1.0)

        return sum(confidences) / len(confidences) if confidences else 0.0
