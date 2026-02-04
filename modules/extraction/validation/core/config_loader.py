"""
Validation configuration loader.

Loads and parses validation rules from YAML configuration files.
"""

import os
import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class ValidationConfigLoader:
    """
    Loads validation configuration from YAML files.
    
    Supports:
    - Validator definitions
    - Document type rules
    - Global settings
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize config loader.
        
        Args:
            config_path: Path to validation rules YAML file
                        If None, uses default: config/validation/rules.yaml
        """
        if config_path is None:
            # Default path
            base_dir = Path(__file__).parent.parent.parent.parent.parent
            config_path = base_dir / "config" / "validation" / "rules.yaml"
        
        self.config_path = Path(config_path)
        self._config: Optional[Dict[str, Any]] = None
    
    def load(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file.
        
        Returns:
            Configuration dictionary
        
        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If YAML parsing fails
        """
        if not self.config_path.exists():
            logger.warning(
                f"Validation config file not found: {self.config_path}. "
                "Using empty configuration."
            )
            return self._get_default_config()
        
        try:
            with open(self.config_path, 'r') as f:
                self._config = yaml.safe_load(f)
            
            logger.info(f"Loaded validation config from: {self.config_path}")
            return self._config or {}
        
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse validation config: {e}")
            raise
    
    def get_document_rules(self, document_type: str) -> List[Dict[str, Any]]:
        """
        Get validation rules for a specific document type.
        
        Args:
            document_type: Document type identifier
        
        Returns:
            List of validation rule configurations
        """
        if self._config is None:
            self.load()
        
        document_types = self._config.get('document_types', {})
        doc_config = document_types.get(document_type, {})
        return doc_config.get('validations', [])
    
    def get_global_settings(self) -> Dict[str, Any]:
        """
        Get global validation settings.
        
        Returns:
            Global settings dictionary
        """
        if self._config is None:
            self.load()
        
        return self._config.get('global', {})
    
    def get_validator_definitions(self) -> Dict[str, Any]:
        """
        Get validator definitions.
        
        Returns:
            Dictionary of validator definitions
        """
        if self._config is None:
            self.load()
        
        return self._config.get('validators', {})
    
    def _get_default_config(self) -> Dict[str, Any]:
        """
        Get default configuration when file doesn't exist.
        
        Returns:
            Default configuration dictionary
        """
        return {
            'global': {
                'validation_mode': 'strict',
                'stop_on_first_error': False,
                'confidence_threshold': 0.70
            },
            'validators': {},
            'document_types': {}
        }
    
    def reload(self) -> Dict[str, Any]:
        """
        Reload configuration from file.
        
        Returns:
            Updated configuration dictionary
        """
        self._config = None
        return self.load()


def load_validation_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to load validation configuration.
    
    Args:
        config_path: Optional path to config file
    
    Returns:
        Configuration dictionary
    """
    loader = ValidationConfigLoader(config_path)
    return loader.load()
