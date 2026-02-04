"""
Template loader implementation.

Loads templates and mapping configurations from YAML files.
"""

from typing import Dict, Any, Optional
from pathlib import Path
import yaml

from modules.generation.core.exceptions import ConfigurationException
from modules.generation.config import get_generation_config
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class TemplateLoader:
    """
    Template loader.
    
    Loads mapping configurations from YAML files.
    """
    
    def __init__(self, mappings_dir: Optional[Path] = None):
        """
        Initialize template loader.
        
        Args:
            mappings_dir: Directory containing mapping YAML files (optional)
        """
        # Use provided path or fallback to config
        config = get_generation_config()
        
        if mappings_dir is None:
            mappings_dir = config.mappings_dir
        
        self.mappings_dir = Path(mappings_dir)
        self.mappings_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache for loaded mappings
        self._cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"Initialized TemplateLoader")
    
    def load_mapping_config(self, mapping_id: str) -> Dict[str, Any]:
        """
        Load mapping configuration.

        Args:
            mapping_id: Mapping identifier (e.g., "invoice_extraction_to_template")

        Returns:
            Mapping configuration dictionary

        Raises:
            ConfigurationException: If mapping not found or invalid
        """
        # Check cache first
        if mapping_id in self._cache:
            logger.debug(f"Loading mapping '{mapping_id}' from cache")
            return self._cache[mapping_id]

        # Load from file
        yaml_path = self.mappings_dir / f"{mapping_id}.yaml"
        logger.info(f"Looking for mapping '{mapping_id}' at: {yaml_path} (exists: {yaml_path.exists()}, is_dir: {yaml_path.is_dir() if yaml_path.exists() else 'N/A'})")

        if not yaml_path.exists():
            # Try without .yaml extension (in case it's already included)
            yaml_path = self.mappings_dir / f"{mapping_id}"
            logger.info(f"Trying without extension at: {yaml_path} (exists: {yaml_path.exists()})")
            if not yaml_path.exists():
                logger.error(f"Mapping not found. Searched: {self.mappings_dir} (type: {type(self.mappings_dir)})")
                raise ConfigurationException(f"Mapping configuration not found: {mapping_id}")
        
        try:
            with open(yaml_path, 'r') as f:
                config = yaml.safe_load(f)
            
            if not config:
                raise ConfigurationException(f"Empty mapping configuration: {mapping_id}")
            
            # Cache the config
            self._cache[mapping_id] = config
            
            logger.debug(f"Loaded mapping '{mapping_id}' from {yaml_path}")
            return config
            
        except yaml.YAMLError as e:
            raise ConfigurationException(f"Invalid YAML in mapping '{mapping_id}': {str(e)}")
        except Exception as e:
            raise ConfigurationException(f"Failed to load mapping '{mapping_id}': {str(e)}")
    
    def save_mapping_config(self, mapping_id: str, config: Dict[str, Any]) -> bool:
        """
        Save mapping configuration.
        
        Args:
            mapping_id: Mapping identifier
            config: Mapping configuration dictionary
        
        Returns:
            True if saved successfully
        """
        try:
            yaml_path = self.mappings_dir / f"{mapping_id}.yaml"
            
            with open(yaml_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            
            # Update cache
            self._cache[mapping_id] = config
            
            logger.info(f"✅ Saved mapping configuration: {mapping_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save mapping configuration: {str(e)}")
            return False
    
    def list_mappings(self) -> list:
        """
        List all available mapping IDs.
        
        Returns:
            List of mapping identifiers
        """
        if not self.mappings_dir.exists():
            return []
        
        mappings = []
        for yaml_file in self.mappings_dir.glob("*.yaml"):
            mapping_id = yaml_file.stem
            mappings.append(mapping_id)
        
        return mappings
    
    def reload(self) -> None:
        """Reload all mappings from disk."""
        self._cache.clear()
        logger.info("Cleared mapping cache")
