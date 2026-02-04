"""
Data provision configuration loader.

Loads data provision config from YAML file.
"""

from typing import Dict, Any, Optional
from pathlib import Path
import yaml
import os

from modules.generation.config import get_generation_config
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class DataProvisionConfig:
    """
    Data provision configuration loader.
    
    Loads configuration from config/generation/data_provision.yaml
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize data provision config.
        
        Args:
            config_path: Path to config file (optional)
        """
        if config_path is None:
            gen_config = get_generation_config()
            config_path = gen_config.data_provision_config_path
        
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        try:
            if not self.config_path.exists():
                logger.warning(f"Config file not found: {self.config_path}")
                self._config = {}
                return
            
            with open(self.config_path, 'r') as f:
                self._config = yaml.safe_load(f) or {}
            
            logger.info(f"Loaded data provision config from {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load data provision config: {e}")
            self._config = {}
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration."""
        db_config = self._config.get('database', {})
        
        # Build connection string from environment variables
        if db_config.get('use_env', True):
            # Check if DATABASE_URL is set
            database_url = os.getenv('DATABASE_URL')
            if database_url:
                return {
                    'connection_string': database_url,
                    'pool_size': db_config.get('pool_size', 5),
                    'max_overflow': db_config.get('max_overflow', 10),
                    'timeout': db_config.get('pool_timeout', 30)
                }
            
            # Build from individual env vars
            host = os.getenv(db_config.get('host_env', 'DB_HOST'), 'localhost')
            port = os.getenv(db_config.get('port_env', 'DB_PORT'), '5432')
            user = os.getenv(db_config.get('user_env', 'DB_USER'), 'postgres')
            password = os.getenv(db_config.get('password_env', 'DB_PASSWORD'), '')
            database = os.getenv(db_config.get('database_env', 'DB_NAME'), 'nestle')
            
            connection_string = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
            
            return {
                'connection_string': connection_string,
                'pool_size': int(os.getenv('DATABASE_POOL_SIZE', db_config.get('pool_size', 5))),
                'max_overflow': int(os.getenv('DATABASE_MAX_OVERFLOW', db_config.get('max_overflow', 10))),
                'timeout': db_config.get('pool_timeout', 30)
            }
        
        return db_config
    
    def get_provider_config(self, provider_name: str) -> Dict[str, Any]:
        """Get configuration for a specific provider."""
        providers = self._config.get('providers', {})
        return providers.get(provider_name, {})
    
    def get_query_config(self, provider_name: str, query_name: str) -> Optional[Dict[str, Any]]:
        """Get a predefined query configuration."""
        provider_config = self.get_provider_config(provider_name)
        queries = provider_config.get('queries', {})
        return queries.get(query_name)
    
    def get_static_data(self, data_key: str) -> Optional[Dict[str, Any]]:
        """Get static test data by key."""
        static_provider = self.get_provider_config('static')
        data_sets = static_provider.get('data_sets', {})
        return data_sets.get(data_key)
    
    def get_transformation_config(self) -> Dict[str, Any]:
        """Get data transformation configuration."""
        return self._config.get('transformation', {})
    
    def get_caching_config(self) -> Dict[str, Any]:
        """Get caching configuration."""
        return self._config.get('caching', {})
    
    def get_error_handling_config(self) -> Dict[str, Any]:
        """Get error handling configuration."""
        return self._config.get('error_handling', {})
    
    def get_security_config(self) -> Dict[str, Any]:
        """Get security configuration."""
        return self._config.get('security', {})


# Global instance
_config_instance: Optional[DataProvisionConfig] = None


def get_data_provision_config() -> DataProvisionConfig:
    """
    Get global data provision config instance.
    
    Returns:
        DataProvisionConfig instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = DataProvisionConfig()
    return _config_instance
