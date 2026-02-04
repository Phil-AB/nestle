"""
Static data provider implementation.

Returns static/hardcoded data for testing and defaults.
Self-registers with DataProviderRegistry.
"""

from typing import Dict, Any, Optional
import time

from modules.generation.core.interfaces import IDataProvider
from modules.generation.core.exceptions import DataProviderException
from modules.generation.core.registry import register_data_provider
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


@register_data_provider("static")  # ← SELF-REGISTERS!
class StaticDataProvider(IDataProvider):
    """
    Static data provider.
    
    Returns predefined static data. Useful for:
    - Testing
    - Default values
    - Mock data
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize static data provider."""
        super().__init__(config)
        
        # Load static data sets from config
        self.data_sets = config.get('data_sets', {})
        
        # Load data provision config
        try:
            from modules.generation.data_providers.config_loader import get_data_provision_config
            provision_config = get_data_provision_config()
            provider_config = provision_config.get_provider_config('static')
            self.data_sets.update(provider_config.get('data_sets', {}))
            logger.info(f"Loaded {len(self.data_sets)} static data sets from config")
        except Exception as e:
            logger.warning(f"Could not load data provision config: {e}")
        
        logger.info("Initialized StaticDataProvider")
    
    async def fetch_data(
        self,
        query: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Fetch static data.
        
        Args:
            query: Query parameters
                - {"data_key": "test_invoice"}  # Returns predefined data set
                - {"data": {...}}                # Returns provided data directly
        
        Returns:
            Dictionary with data in universal format
        """
        start_time = time.time()
        
        try:
            logger.info(f"Fetching static data: {query}")
            
            # Option 1: Return inline data directly
            if "data" in query:
                data = query["data"]
            
            # Option 2: Return predefined data set
            elif "data_key" in query:
                data_key = query["data_key"]
                if data_key not in self.data_sets:
                    raise DataProviderException(f"Data key not found: {data_key}")
                data = self.data_sets[data_key]
            
            else:
                raise DataProviderException("Query must contain 'data' or 'data_key'")
            
            fetch_time = time.time() - start_time
            
            # Ensure standard format
            if not isinstance(data, dict):
                data = {"fields": {}, "items": []}
            
            if "fields" not in data:
                data["fields"] = {}
            
            if "items" not in data:
                data["items"] = []
            
            # Add metadata
            data["metadata"] = {
                "source": "static",
                "fetch_time": fetch_time,
                "provider": self.provider_name
            }
            
            logger.info(f"Successfully fetched static data in {fetch_time:.2f}s")
            return data
            
        except Exception as e:
            logger.error(f"Failed to fetch static data: {str(e)}")
            raise DataProviderException(f"Static data fetch failed: {str(e)}")
    
    async def validate_query(self, query: Dict[str, Any]) -> bool:
        """Validate query parameters."""
        return "data" in query or "data_key" in query
    
    async def health_check(self) -> bool:
        """Check if provider is healthy (always true for static)."""
        return True
