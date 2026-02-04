"""
Template registry implementation.

Manages template storage, retrieval, and metadata.
"""

from typing import Dict, Optional, List, Any
from pathlib import Path
import yaml

from modules.generation.core.interfaces import ITemplateRegistry, TemplateMetadata
from modules.generation.core.exceptions import TemplateNotFoundException
from modules.generation.config import get_generation_config
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class TemplateRegistry(ITemplateRegistry):
    """
    Template registry implementation.
    
    Manages template metadata and file paths.
    Uses YAML files for metadata storage.
    """
    
    def __init__(self, metadata_dir: Optional[Path] = None, project_root: Optional[Path] = None):
        """
        Initialize template registry.
        
        Args:
            metadata_dir: Directory containing template metadata YAML files (optional)
            project_root: Project root path for resolving relative paths (optional)
        """
        # Use provided paths or fallback to config
        config = get_generation_config()
        
        if metadata_dir is None:
            metadata_dir = config.templates_metadata_dir
        
        if project_root is None:
            project_root = config.project_root
        
        self.metadata_dir = Path(metadata_dir)
        self.project_root = Path(project_root)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache for loaded templates
        self._cache: Dict[str, TemplateMetadata] = {}
        
        # Load all templates on init
        self._load_all_templates()
        
        logger.info(f"Initialized TemplateRegistry with {len(self._cache)} templates")
    
    def _load_all_templates(self) -> None:
        """Load all template metadata from YAML files."""
        logger.info(f"Loading templates from: {self.metadata_dir} (exists: {self.metadata_dir.exists()})")

        if not self.metadata_dir.exists():
            logger.warning(f"Metadata directory does not exist: {self.metadata_dir}")
            logger.warning(f"Project root: {self.project_root}")
            return

        yaml_files = list(self.metadata_dir.glob("*.yaml"))
        logger.info(f"Found {len(yaml_files)} YAML files in metadata directory")

        for yaml_file in yaml_files:
            try:
                logger.debug(f"Loading template from: {yaml_file}")
                with open(yaml_file, 'r') as f:
                    data = yaml.safe_load(f)

                if not data:
                    logger.warning(f"Empty YAML file: {yaml_file}")
                    continue

                metadata = self._dict_to_metadata(data)
                self._cache[metadata.template_id] = metadata
                logger.info(f"✅ Loaded template: {metadata.template_id} - {metadata.template_name}")

            except Exception as e:
                logger.error(f"Failed to load template metadata from {yaml_file}: {str(e)}", exc_info=True)
    
    def _dict_to_metadata(self, data: Dict[str, Any]) -> TemplateMetadata:
        """Convert dictionary to TemplateMetadata."""
        return TemplateMetadata(
            template_id=data['template_id'],
            template_name=data['template_name'],
            template_format=data['template_format'],
            version=data['version'],
            template_path=data.get('template_path', ''),
            description=data.get('description', ''),
            required_fields=data.get('required_fields', []),
            optional_fields=data.get('optional_fields', []),
            supports_tables=data.get('supports_tables', False),
            supports_images=data.get('supports_images', False),
            insights_config=data.get('insights_config', {}),
        )
    
    def _metadata_to_dict(self, metadata: TemplateMetadata) -> Dict[str, Any]:
        """Convert TemplateMetadata to dictionary."""
        return metadata.to_dict()
    
    async def register_template(
        self,
        template_id: str,
        template_path: str,
        metadata: TemplateMetadata
    ) -> bool:
        """
        Register a new template.
        
        Args:
            template_id: Unique template identifier
            template_path: Path to template file
            metadata: Template metadata
        
        Returns:
            True if registered successfully
        """
        try:
            # Update template path in metadata
            metadata.template_path = template_path
            metadata.template_id = template_id
            
            # Save metadata to YAML file
            yaml_path = self.metadata_dir / f"{template_id}.yaml"
            with open(yaml_path, 'w') as f:
                yaml.dump(self._metadata_to_dict(metadata), f, default_flow_style=False)
            
            # Add to cache
            self._cache[template_id] = metadata
            
            logger.info(f"✅ Registered template: {template_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register template: {str(e)}")
            return False
    
    async def get_template(self, template_id: str) -> Optional[str]:
        """
        Get template file path by ID.
        
        Args:
            template_id: Template identifier
        
        Returns:
            Template file path or None if not found
        """
        metadata = await self.get_template_metadata(template_id)
        return metadata.template_path if metadata else None
    
    async def get_template_metadata(self, template_id: str) -> Optional[TemplateMetadata]:
        """
        Get template metadata.

        Args:
            template_id: Template identifier

        Returns:
            TemplateMetadata or None if not found
        """
        logger.debug(f"Looking for template '{template_id}' in cache")
        logger.debug(f"Cache keys: {list(self._cache.keys())}")

        # Check cache first
        if template_id in self._cache:
            logger.info(f"Found template '{template_id}' in cache")
            return self._cache[template_id]

        logger.warning(f"Template '{template_id}' not found in cache, trying to load from disk")
        
        # Try to load from disk
        yaml_path = self.metadata_dir / f"{template_id}.yaml"
        if yaml_path.exists():
            try:
                with open(yaml_path, 'r') as f:
                    data = yaml.safe_load(f)
                
                metadata = self._dict_to_metadata(data)
                self._cache[template_id] = metadata
                return metadata
                
            except Exception as e:
                logger.error(f"Failed to load template metadata: {str(e)}")
        
        return None
    
    async def list_templates(
        self,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[TemplateMetadata]:
        """
        List all templates with optional filters.
        
        Args:
            filters: Optional filters
                - format: Filter by template format (docx, pdf, etc.)
                - tags: Filter by tags (if implemented)
        
        Returns:
            List of TemplateMetadata
        """
        templates = list(self._cache.values())
        
        if filters:
            # Filter by format
            if 'format' in filters:
                format_filter = filters['format'].lower()
                templates = [t for t in templates if t.template_format.lower() == format_filter]
            
            # Filter by tags (if tags field is added to metadata)
            if 'tags' in filters:
                # Future implementation
                pass
        
        return templates
    
    async def delete_template(self, template_id: str) -> bool:
        """
        Delete a template.
        
        Args:
            template_id: Template identifier
        
        Returns:
            True if deleted successfully
        """
        try:
            # Remove from cache
            if template_id in self._cache:
                del self._cache[template_id]
            
            # Delete metadata file
            yaml_path = self.metadata_dir / f"{template_id}.yaml"
            if yaml_path.exists():
                yaml_path.unlink()
            
            logger.info(f"✅ Deleted template: {template_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete template: {str(e)}")
            return False
    
    async def template_exists(self, template_id: str) -> bool:
        """
        Check if template exists.
        
        Args:
            template_id: Template identifier
        
        Returns:
            True if template exists
        """
        return template_id in self._cache or \
               (self.metadata_dir / f"{template_id}.yaml").exists()
    
    def reload(self) -> None:
        """Reload all templates from disk."""
        self._cache.clear()
        self._load_all_templates()
        logger.info(f"Reloaded {len(self._cache)} templates")
