"""
Storage configuration loader.

Loads and parses storage configuration from YAML files.
"""

import os
import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class StorageConfigLoader:
    """
    Loads storage configuration from YAML files.
    
    Supports:
    - Backend definitions
    - Routing rules
    - Global settings
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize config loader.
        
        Args:
            config_path: Path to storage config YAML file
                        If None, uses default: config/storage/backends.yaml
        """
        if config_path is None:
            base_dir = Path(__file__).parent.parent.parent.parent.parent
            config_path = base_dir / "config" / "storage" / "backends.yaml"
        
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
                f"Storage config file not found: {self.config_path}. "
                "Using default configuration."
            )
            return self._get_default_config()
        
        try:
            with open(self.config_path, 'r') as f:
                self._config = yaml.safe_load(f)
            
            logger.info(f"Loaded storage config from: {self.config_path}")
            return self._config or {}
        
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse storage config: {e}")
            raise
    
    def get_backend_config(self, backend_name: str) -> Dict[str, Any]:
        """
        Get configuration for a specific backend.
        
        Args:
            backend_name: Backend name
        
        Returns:
            Backend configuration dictionary
        """
        if self._config is None:
            self.load()
        
        backends = self._config.get('storage', {}).get('backends', {})
        return backends.get(backend_name, {})
    
    def get_default_backend(self) -> str:
        """
        Get default backend name.
        
        Returns:
            Default backend name
        """
        if self._config is None:
            self.load()
        
        return self._config.get('storage', {}).get('default_backend', 'postgresql')
    
    def get_routing_config(self) -> Dict[str, Any]:
        """
        Get routing configuration.
        
        Returns:
            Routing configuration dictionary
        """
        if self._config is None:
            self.load()
        
        return self._config.get('storage', {}).get('routing', {})
    
    def get_multi_store_config(self) -> Dict[str, Any]:
        """
        Get multi-store configuration.
        
        Returns:
            Multi-store configuration dictionary
        """
        if self._config is None:
            self.load()
        
        return self._config.get('storage', {}).get('multi_store', {})
    
    def _get_default_config(self) -> Dict[str, Any]:
        """
        Get default configuration when file doesn't exist.
        
        Returns:
            Default configuration dictionary
        """
        return {
            'storage': {
                'default_backend': 'postgresql',
                'backends': {},
                'routing': {
                    'default': 'postgresql',
                    'overrides': {}
                },
                'multi_store': {
                    'enabled': False,
                    'strategy': 'async',
                    'backends': ['postgresql']
                }
            }
        }
    
    def reload(self) -> Dict[str, Any]:
        """
        Reload configuration from file.
        
        Returns:
            Updated configuration dictionary
        """
        self._config = None
        return self.load()


def load_storage_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to load storage configuration.
    
    Args:
        config_path: Optional path to config file
    
    Returns:
        Configuration dictionary
    """
    loader = StorageConfigLoader(config_path)
    return loader.load()
