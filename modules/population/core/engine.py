"""
PDF Form Population Engine.

Main orchestrator for the population module. Coordinates data fetching,
field mapping, and PDF form filling operations.

IMPORTANT: Agent-based population is MANDATORY.
All population requests use the LangGraph-based intelligent agent for
maximum accuracy in field mapping. Traditional static mapping is deprecated.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
import logging
import yaml

from modules.population.core.types import PopulationResult, FormConfig

logger = logging.getLogger(__name__)


class PopulationEngine:
    """
    PDF Form Population Engine.

    Orchestrates the complete form population workflow:
    1. Load fillable PDF template
    2. Query database for extracted data
    3. Map database fields to PDF form fields
    4. Fill form fields programmatically
    5. Return populated PDF

    Completely standalone - no dependency on generation module.

    Example:
        >>> engine = PopulationEngine()
        >>> result = await engine.populate(
        ...     form_id="boe_gra_v1",
        ...     document_ids=["invoice_123", "bol_456"],
        ...     options={"flatten_form": True}
        ... )
        >>> print(f"Generated: {result.output_path}")
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize population engine.

        Args:
            config_path: Path to population config.yaml.
                        Defaults to config/population/config.yaml
        """
        # Find project root by looking for marker files
        current = Path(__file__).resolve()
        while current != current.parent:
            if (current / "config").exists() and (current / "modules").exists():
                self.project_root = current
                break
            current = current.parent
        else:
            # Fallback to cwd if markers not found
            self.project_root = Path.cwd()

        self.config_path = config_path or (
            self.project_root / "config/population/config.yaml"
        )

        logger.info(f"Initializing PopulationEngine with config: {self.config_path}")

        # Load configuration
        self.config = self._load_config()

        # Initialize components (lazy loading)
        self._data_provider = None
        self._field_mapper = None
        self._form_filler = None
        self._population_agent = None
        self._overlay_renderer = None

        logger.info("PopulationEngine initialized successfully")

    async def populate(
        self,
        form_id: str,
        document_ids: List[str],
        options: Optional[Dict[str, Any]] = None
    ) -> PopulationResult:
        """
        Populate PDF form with data from database using intelligent agent.

        Args:
            form_id: Form template identifier (e.g., "boe_gra_v1")
            document_ids: List of document IDs to extract data from
            options: Optional parameters:
                - flatten_form (bool): Make PDF read-only (default: True)
                - merge_strategy (str): How to merge multi-doc data
                - validate_required (bool): Check required fields

        Returns:
            PopulationResult with output_path, metadata, and success status

        Note:
            Agent-based population is MANDATORY. The system always uses
            LangGraph-based intelligent field mapping for maximum accuracy.

        Example:
            >>> result = await engine.populate(
            ...     form_id="boe_gra_v1",
            ...     document_ids=["abc123", "def456", "ghi789"],
            ...     options={"flatten_form": True, "merge_strategy": "prioritized"}
            ... )
        """
        options = options or {}

        # Agent mode is mandatory - always use intelligent population
        agent_mandatory = self.config.get("agent", {}).get("mandatory", True)

        if not agent_mandatory:
            logger.warning(
                "Agent mode is not set as mandatory in config. "
                "This is not recommended. Setting mandatory=true for this request."
            )

        # Warn if traditional mode was explicitly requested (deprecated)
        if options.get("use_agent") is False:
            logger.warning(
                "Traditional mode (use_agent=False) is deprecated and disabled. "
                "Using agent-based population for accuracy. "
                "Please remove 'use_agent' parameter from requests."
            )

        # Always use agent-based population
        logger.info("Using AGENT-BASED population (mandatory mode)")
        return await self._populate_with_agent(form_id, document_ids, options)

    async def _populate_with_agent(
        self,
        form_id: str,
        document_ids: List[str],
        options: Dict[str, Any]
    ) -> PopulationResult:
        """
        Populate PDF using LangChain agent (intelligent mapping).

        Args:
            form_id: Form template identifier
            document_ids: List of document IDs
            options: Population options

        Returns:
            PopulationResult
        """
        try:
            logger.info(
                f"Starting AGENT-BASED population: form={form_id}, "
                f"docs={len(document_ids)}"
            )

            # Load form configuration
            form_config = self._load_form_config(form_id)
            template_path = form_config["template_path"]

            # Create population task
            from modules.population.agents.base_population_agent import PopulationTask

            task = PopulationTask(
                form_id=form_id,
                document_ids=document_ids,
                template_path=template_path,
                options=options
            )

            # Run agent
            logger.info("Running population agent...")
            agent_result = await self.population_agent.populate(task)

            if not agent_result.success:
                return PopulationResult(
                    success=False,
                    error=agent_result.error,
                    form_id=form_id,
                    metadata=agent_result.metadata
                )

            # Fill PDF form with agent-detected mappings
            logger.info("Filling PDF form with agent mappings...")
            output_path = await self.form_filler.fill_form(
                template_path=template_path,
                field_data=agent_result.field_mappings,
                options={
                    "flatten_form": options.get("flatten_form", True),
                    "validate_required": options.get("validate_required", True)
                }
            )

            logger.info(f"Agent-based population complete: {output_path}")

            return PopulationResult(
                success=True,
                output_path=str(output_path),  # Convert Path to string for Pydantic
                form_id=form_id,
                metadata={
                    "document_ids": document_ids,
                    "mode": "agent",
                    "confidence": agent_result.confidence,
                    "field_count": len(agent_result.field_mappings or {}),
                    "agent_metadata": agent_result.metadata
                }
            )

        except Exception as e:
            logger.error(f"Agent-based population failed: {e}", exc_info=True)
            return PopulationResult(
                success=False,
                error=str(e),
                form_id=form_id,
                metadata={"document_ids": document_ids, "mode": "agent"}
            )

    async def _populate_traditional(
        self,
        form_id: str,
        document_ids: List[str],
        options: Dict[str, Any]
    ) -> PopulationResult:
        """
        [DEPRECATED] Populate PDF using traditional approach (static mapping + field filling).

        ⚠️ WARNING: This method is DEPRECATED and should NOT be called.
        Agent-based population is now mandatory for all requests.
        This method is kept for backward compatibility only.

        Args:
            form_id: Form template identifier
            document_ids: List of document IDs
            options: Population options

        Returns:
            PopulationResult

        Raises:
            DeprecationWarning: Always logs deprecation warning
        """
        logger.warning(
            "⚠️ DEPRECATED: _populate_traditional() was called. "
            "This method is deprecated. Agent-based population is now mandatory. "
            "Please update your code to remove any calls to this method."
        )
        try:
            logger.info(
                f"Starting TRADITIONAL population: form={form_id}, "
                f"docs={len(document_ids)}, options={options}"
            )

            # 1. Load form configuration
            logger.info("Loading form configuration...")
            form_config = self._load_form_config(form_id)

            # 2. Fetch data from database
            logger.info("Fetching data from database...")
            merge_strategy = options.get(
                "merge_strategy",
                form_config.get("merge_strategy", "prioritized")
            )

            data = await self.data_provider.get_documents_data(
                document_ids=document_ids,
                merge_strategy=merge_strategy
            )

            logger.info(
                f"Fetched data: {len(data.get('fields', {}))} fields, "
                f"{len(data.get('items', []))} items"
            )

            # 3. Map database fields to PDF form fields
            logger.info("Mapping fields...")
            mapped_data = await self.field_mapper.map(
                data=data,
                mapping_config=form_config["mapping_config"]
            )

            logger.info(f"Mapped {len(mapped_data)} fields")

            # 4. Fill PDF form fields
            logger.info("Filling PDF form...")
            output_path = await self.form_filler.fill_form(
                template_path=form_config["template_path"],
                field_data=mapped_data,
                options={
                    "flatten_form": options.get("flatten_form", True),
                    "validate_required": options.get("validate_required", True)
                }
            )

            logger.info(f"Population complete: {output_path}")

            # Return success result
            return PopulationResult(
                success=True,
                output_path=str(output_path),
                form_id=form_id,
                metadata={
                    "document_ids": document_ids,
                    "field_count": len(mapped_data),
                    "merge_strategy": merge_strategy,
                    "options": options
                }
            )

        except Exception as e:
            logger.error(f"Population failed: {e}", exc_info=True)
            return PopulationResult(
                success=False,
                error=str(e),
                form_id=form_id,
                metadata={"document_ids": document_ids}
            )

    def _load_config(self) -> Dict[str, Any]:
        """
        Load population module configuration from YAML.

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If config file not found
            yaml.YAMLError: If config file is invalid
        """
        try:
            if not self.config_path.exists():
                raise FileNotFoundError(
                    f"Configuration file not found: {self.config_path}"
                )

            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)

            logger.info(f"Loaded configuration from {self.config_path}")
            return config

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise

    def _load_form_config(self, form_id: str) -> Dict[str, Any]:
        """
        Load form-specific configuration from YAML.

        Args:
            form_id: Form template identifier

        Returns:
            Form configuration dictionary with keys:
                - template_path: Path to PDF template
                - mapping_config: Path to field mapping config
                - merge_strategy: Data merge strategy

        Raises:
            FileNotFoundError: If form config not found
        """
        mappings_dir = self.project_root / self.config["forms"]["mappings_dir"]
        config_path = mappings_dir / f"{form_id}.yaml"

        if not config_path.exists():
            raise FileNotFoundError(
                f"Form configuration not found: {config_path}"
            )

        with open(config_path, 'r') as f:
            form_config = yaml.safe_load(f)

        # Resolve paths relative to project root
        form_config["template_path"] = str(
            self.project_root / form_config["template_path"]
        )
        form_config["mapping_config"] = str(config_path)

        logger.info(f"Loaded form config for {form_id}")
        return form_config

    @property
    def data_provider(self):
        """
        Lazy-load database data provider.

        Returns:
            PostgresDataProvider instance
        """
        if self._data_provider is None:
            from modules.population.data_providers.postgres_provider import (
                PostgresDataProvider
            )

            self._data_provider = PostgresDataProvider(
                db_config=self.config["database"]
            )
            logger.info("Initialized PostgresDataProvider")

        return self._data_provider

    @property
    def field_mapper(self):
        """
        Lazy-load field mapper.

        Returns:
            FieldMapper instance
        """
        if self._field_mapper is None:
            from modules.population.mappers.field_mapper import FieldMapper

            self._field_mapper = FieldMapper(
                transformations=self.config["field_mapping"]["transformations"]
            )
            logger.info("Initialized FieldMapper")

        return self._field_mapper

    @property
    def form_filler(self):
        """
        Lazy-load PDF form filler.

        Returns:
            PDFFormFiller instance
        """
        if self._form_filler is None:
            from modules.population.form_filler.pdf_form_filler import PDFFormFiller

            self._form_filler = PDFFormFiller(
                output_dir=self.config["forms"]["output_dir"]
            )
            logger.info("Initialized PDFFormFiller")

        return self._form_filler

    @property
    def population_agent(self):
        """
        Lazy-load population agent.

        Returns:
            PopulationAgent instance
        """
        if self._population_agent is None:
            from modules.population.agents import PopulationAgent

            # Get agent config
            agent_config = self.config.get("agent", {})

            self._population_agent = PopulationAgent(
                llm_provider=agent_config.get("llm", {}).get("provider", "anthropic"),
                llm_model=agent_config.get("llm", {}).get("model", "claude-3-5-sonnet-20241022"),
                temperature=agent_config.get("llm", {}).get("temperature", 0.0),
                config=agent_config,
                data_provider=self.data_provider
            )
            logger.info("Initialized PopulationAgent")

        return self._population_agent

    @property
    def overlay_renderer(self):
        """
        Lazy-load overlay renderer.

        Returns:
            OverlayRenderer instance
        """
        if self._overlay_renderer is None:
            from modules.population.renderers import OverlayRenderer

            self._overlay_renderer = OverlayRenderer(
                output_dir=self.config["forms"]["output_dir"]
            )
            logger.info("Initialized OverlayRenderer")

        return self._overlay_renderer

    def list_forms(self) -> List[Dict[str, Any]]:
        """
        List available PDF form templates.

        Returns:
            List of form metadata dictionaries with:
                - form_id: Form identifier
                - form_name: Human-readable name
                - description: Form description
                - template_path: Path to fillable PDF
                - field_count: Number of form fields
                - required_document_types: List of required document types
                - created_at: Creation timestamp
                - updated_at: Last update timestamp
        """
        mappings_dir = self.project_root / self.config["forms"]["mappings_dir"]

        forms = []
        for config_file in mappings_dir.glob("*.yaml"):
            try:
                with open(config_file, 'r') as f:
                    form_config = yaml.safe_load(f)

                # Get actual field count from PDF (not from manual mappings)
                field_count = self._get_pdf_field_count(form_config.get("template_path"))

                forms.append({
                    "form_id": form_config.get("form_id"),
                    "form_name": form_config.get("form_name"),
                    "description": form_config.get("description", ""),
                    "template_path": form_config.get("template_path"),
                    "field_count": field_count,
                    "required_document_types": form_config.get("required_document_types", []),
                    "created_at": form_config.get("created_at", ""),
                    "updated_at": form_config.get("updated_at", "")
                })
            except Exception as e:
                logger.warning(f"Error loading form config {config_file}: {e}")

        return forms

    def _get_pdf_field_count(self, template_path: str) -> int:
        """
        Get the actual number of fields in a PDF form.

        Args:
            template_path: Path to PDF template (relative to project root)

        Returns:
            Number of form fields in the PDF
        """
        try:
            from PyPDF2 import PdfReader

            pdf_path = self.project_root / template_path
            if not pdf_path.exists():
                logger.warning(f"PDF not found: {pdf_path}")
                return 0

            reader = PdfReader(str(pdf_path))

            # Check if PDF has form fields
            if '/AcroForm' not in reader.trailer['/Root']:
                return 0

            fields = reader.trailer['/Root']['/AcroForm'].get('/Fields', [])
            return len(fields)

        except Exception as e:
            logger.warning(f"Error reading PDF field count from {template_path}: {e}")
            return 0

    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of population module components.

        Returns:
            Health status dictionary
        """
        status = {
            "status": "healthy",
            "components": {}
        }

        try:
            # Check database connection
            await self.data_provider.health_check()
            status["components"]["database"] = "healthy"
        except Exception as e:
            status["components"]["database"] = f"unhealthy: {e}"
            status["status"] = "degraded"

        try:
            # Check forms directory
            forms_dir = self.project_root / self.config["forms"]["templates_dir"]
            if not forms_dir.exists():
                raise FileNotFoundError(f"Forms directory not found: {forms_dir}")

            status["components"]["forms_directory"] = "healthy"
        except Exception as e:
            status["components"]["forms_directory"] = f"unhealthy: {e}"
            status["status"] = "degraded"

        return status
