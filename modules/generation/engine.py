"""
Generation Engine - Main orchestrator.

Coordinates data providers, mappers, and renderers to generate documents.
"""

from typing import Dict, Any, Optional
import uuid
import time
import asyncio

from modules.generation.core.interfaces import GenerationResult, GenerationStatus
from modules.generation.core.exceptions import (
    GenerationException,
    TemplateNotFoundException,
    ConfigurationException
)
from modules.generation.core.registry import (
    RendererRegistry,
    DataProviderRegistry,
    MapperRegistry
)
from modules.generation.templates.registry import TemplateRegistry
from modules.generation.templates.loader import TemplateLoader
from modules.generation.storage.job_storage import IJobStorage, InMemoryJobStorage, JobData
from modules.generation.config import get_generation_config, GenerationConfig
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class GenerationEngine:
    """
    Main generation engine.
    
    Orchestrates the entire generation pipeline:
    1. Load template metadata
    2. Fetch data from provider
    3. Map data to template format
    4. Render template
    """
    
    def __init__(
        self,
        config: Optional[GenerationConfig] = None,
        job_storage: Optional[IJobStorage] = None
    ):
        """
        Initialize generation engine.
        
        Args:
            config: Generation configuration (optional)
            job_storage: Job storage implementation (optional, defaults to in-memory)
        """
        # Use provided config or global config
        self.config = config or get_generation_config()
        
        # Initialize components with config
        self.template_registry = TemplateRegistry(
            metadata_dir=self.config.templates_metadata_dir,
            project_root=self.config.project_root
        )
        self.template_loader = TemplateLoader(
            mappings_dir=self.config.mappings_dir
        )
        
        # Job storage (default to in-memory)
        self.job_storage = job_storage or InMemoryJobStorage()
        
        logger.info("✅ Initialized GenerationEngine")
    
    async def generate(self, request: Dict[str, Any]) -> GenerationResult:
        """
        Generate document from template and data.
        
        Args:
            request: Generation request
                {
                    "template_id": "invoice_standard_v1",
                    "data_source": {
                        "provider": "postgres",
                        "query": {"document_id": "123"}
                    },
                    "mapping_id": "invoice_extraction_to_template",  # Optional
                    "options": {
                        "output_format": "pdf",
                        "output_path": "./output/doc.docx"
                    }
                }
        
        Returns:
            GenerationResult
        """
        job_id = str(uuid.uuid4())
        start_time = time.time()
        
        try:
            logger.info(f"Starting generation job: {job_id}")
            
            # Track job
            job_data = JobData(
                job_id=job_id,
                status=GenerationStatus.IN_PROGRESS,
                created_at=time.time(),
                request=request
            )
            await self.job_storage.save_job(job_id, job_data)
            
            # 1. Load template metadata
            template_id = request.get('template_id')
            if not template_id:
                raise ConfigurationException("template_id is required")
            
            template_metadata = await self.template_registry.get_template_metadata(template_id)
            if not template_metadata:
                raise TemplateNotFoundException(f"Template not found: {template_id}")
            
            template_path = template_metadata.template_path
            logger.info(f"Loaded template: {template_id} ({template_metadata.template_format})")
            
            # 2. Fetch data
            data_source = request.get('data_source', {})
            provider_name = data_source.get('provider', 'postgres')
            provider_config = {"name": provider_name}

            data_provider = DataProviderRegistry.get(provider_name, provider_config)

            # Detect multi-source vs single-source
            query = data_source.get('query', {})

            # Check if template requires insights generation
            mapping_id = request.get('mapping_id', template_id)
            template_insights_config = template_metadata.insights_config or {}

            # Build options with mapping_id for insights detection
            fetch_options = data_source.get('options') or {}

            # Determine if insights should be included (explicit option or template config)
            include_insights = fetch_options.get('include_insights', 'auto')
            if include_insights == 'auto':
                # Auto-detect from template metadata
                include_insights = template_insights_config.get('enabled', False) if template_insights_config else False

            if include_insights:
                fetch_options['mapping_id'] = mapping_id
                fetch_options['include_insights'] = True

            if 'document_ids' in query and isinstance(query['document_ids'], list):
                # Multi-source mode - fetch and merge multiple documents
                document_ids = query['document_ids']
                merge_strategy = data_source.get('merge_strategy', 'prioritized')

                source_data = await data_provider.fetch_multi_source_data(
                    document_ids=document_ids,
                    merge_strategy=merge_strategy,
                    options=fetch_options
                )
                logger.info(f"Fetched multi-source data: {len(document_ids)} documents, strategy={merge_strategy}")
            else:
                # Single-source mode - use enhanced fetch if insights needed
                if include_insights and hasattr(data_provider, 'fetch_data_with_insights'):
                    source_data = await data_provider.fetch_data_with_insights(
                        query=query,
                        options=fetch_options
                    )
                    logger.info(f"Fetched data with insights from provider: {provider_name}")
                else:
                    source_data = await data_provider.fetch_data(
                        query=query,
                        options=fetch_options
                    )
                    logger.info(f"Fetched data from provider: {provider_name}")
            
            # 3. Map data (if mapping config provided)
            mapping_id = request.get('mapping_id')

            # If no mapping_id provided, try using template_id as mapping_id (common pattern)
            if not mapping_id:
                mapping_id = template_id
                logger.info(f"No mapping_id provided. Trying template_id as mapping: {mapping_id}")

            # Try to load and apply mapping
            try:
                mapping_config = self.template_loader.load_mapping_config(mapping_id)
                logger.debug(f"Loaded mapping config: {list(mapping_config.keys())}")

                mapper_name = mapping_config.get('mapper', 'field')
                mapper_config = {"name": mapper_name}

                mapper = MapperRegistry.get(mapper_name, mapper_config)
                mapping_result = await mapper.map_data(source_data, mapping_config)

                if not mapping_result.success:
                    logger.warning(f"Mapping completed with errors: {mapping_result.errors}")

                mapped_data = mapping_result.mapped_data
                logger.info(f"Mapped data using: {mapping_id}")
                logger.debug(f"Mapped fields: {list(mapped_data.keys())[:10]}")
                logger.debug(f"Sample mapped data: {dict(list(mapped_data.items())[:3])}")
            except Exception as e:
                # If mapping fails or doesn't exist, use source data directly
                logger.warning(f"Mapping failed or not found ({mapping_id}): {e}. Using source data directly.")
                mapped_data = source_data
            
            # 4. Render document
            renderer_name = template_metadata.template_format
            renderer_config = {"name": renderer_name, "supported_formats": [renderer_name]}

            # Pass project_root to renderer for correct template path resolution
            renderer = RendererRegistry.get(renderer_name, renderer_config, project_root=self.config.project_root)
            
            options = request.get('options', {})
            options['job_id'] = job_id
            
            logger.info(f"🎯 Passing data to renderer:")
            logger.info(f"   - Data type: {type(mapped_data)}")
            logger.info(f"   - Data keys: {list(mapped_data.keys())[:15] if isinstance(mapped_data, dict) else 'N/A'}")
            logger.info(f"   - Sample: {dict(list(mapped_data.items())[:2]) if isinstance(mapped_data, dict) else str(mapped_data)[:100]}")
            
            result = await renderer.render(
                template_path=template_path,
                data=mapped_data,
                options=options
            )
            
            generation_time = (time.time() - start_time) * 1000
            
            # Update job status
            job_data = await self.job_storage.get_job(job_id)
            if job_data:
                job_data.status = GenerationStatus.COMPLETED if result.success else GenerationStatus.FAILED
                job_data.completed_at = time.time()
                job_data.result = result
                await self.job_storage.save_job(job_id, job_data)
            
            logger.info(f"✅ Generation completed in {generation_time:.2f}ms")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Generation failed: {str(e)}")
            
            # Update job status
            await self.job_storage.update_job_status(job_id, GenerationStatus.FAILED, str(e))
            
            return GenerationResult(
                success=False,
                job_id=job_id,
                error_message=str(e),
                error_details={"request": request}
            )
    
    async def generate_batch(self, request: Dict[str, Any]) -> list:
        """
        Generate multiple documents in batch.
        
        Args:
            request: Batch generation request
                {
                    "template_id": "invoice_standard_v1",
                    "data_sources": [
                        {"provider": "postgres", "query": {"document_id": "123"}},
                        {"provider": "postgres", "query": {"document_id": "456"}}
                    ],
                    "mapping_id": "invoice_extraction_to_template",
                    "options": {}
                }
        
        Returns:
            List of GenerationResult
        """
        data_sources = request.get('data_sources', [])
        template_id = request.get('template_id')
        mapping_id = request.get('mapping_id')
        options = request.get('options', {})
        
        logger.info(f"Starting batch generation: {len(data_sources)} documents")
        
        # Create individual requests
        tasks = []
        for data_source in data_sources:
            individual_request = {
                "template_id": template_id,
                "data_source": data_source,
                "mapping_id": mapping_id,
                "options": options.copy()
            }
            tasks.append(self.generate(individual_request))
        
        # Execute in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to failed results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(GenerationResult(
                    success=False,
                    job_id=f"batch_{i}",
                    error_message=str(result)
                ))
            else:
                final_results.append(result)
        
        successful = sum(1 for r in final_results if r.success)
        logger.info(f"✅ Batch generation completed: {successful}/{len(data_sources)} successful")
        
        return final_results
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status by ID."""
        job_data = await self.job_storage.get_job(job_id)
        if not job_data:
            return None
        
        return job_data.to_dict()
    
    async def get_output_path(self, job_id: str) -> Optional[str]:
        """Get output file path for completed job."""
        job_data = await self.job_storage.get_job(job_id)
        if not job_data or not job_data.result:
            return None
        
        if job_data.result.success:
            return job_data.result.output_path
        
        return None
    
    async def list_templates(self, format: Optional[str] = None) -> list:
        """List available templates."""
        filters = {}
        if format:
            filters['format'] = format
        
        templates = await self.template_registry.list_templates(filters)
        return [t.to_dict() for t in templates]
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of generation system."""
        health = {
            "status": "healthy",
            "renderers": {},
            "data_providers": {},
            "templates_loaded": len(self.template_registry._cache),
            "job_storage_type": type(self.job_storage).__name__
        }
        
        # Check registered renderers
        for renderer_name in RendererRegistry.list_renderers():
            try:
                renderer = RendererRegistry.get(
                    renderer_name,
                    {"name": renderer_name},
                    project_root=self.config.project_root
                )
                is_healthy = await renderer.health_check()
                health["renderers"][renderer_name] = is_healthy
            except Exception as e:
                health["renderers"][renderer_name] = False
                logger.warning(f"Renderer {renderer_name} health check failed: {e}")
        
        # Check registered data providers
        for provider_name in DataProviderRegistry.list_providers():
            try:
                provider = DataProviderRegistry.get(provider_name, {"name": provider_name})
                is_healthy = await provider.health_check()
                health["data_providers"][provider_name] = is_healthy
            except Exception as e:
                health["data_providers"][provider_name] = False
                logger.warning(f"Provider {provider_name} health check failed: {e}")
        
        return health
