"""
PostgreSQL data provider implementation.

Fetches data from PostgreSQL database for document generation.
Self-registers with DataProviderRegistry - NO factory changes needed.
"""

from typing import Dict, Any, Optional, List
import time
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.generation.core.interfaces import IDataProvider
from modules.generation.core.exceptions import DataProviderException
from modules.generation.core.registry import register_data_provider
from modules.generation.data_providers.data_transformer import DataTransformer
from modules.generation.data_providers.db_interface import IDatabaseConnection, DefaultDatabaseConnection
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


@register_data_provider("postgres")  # ← SELF-REGISTERS! Zero factory changes.
class PostgresDataProvider(IDataProvider):
    """
    PostgreSQL data provider.
    
    Fetches document data from PostgreSQL database.
    """
    
    def __init__(self, config: Dict[str, Any], db_connection: Optional[IDatabaseConnection] = None):
        """
        Initialize PostgreSQL data provider.

        Args:
            config: Provider configuration
            db_connection: Database connection implementation (optional)
                          If not provided, uses DefaultDatabaseConnection
        """
        super().__init__(config)

        # Use provided connection or default to project's connection
        self.db_connection = db_connection or DefaultDatabaseConnection()

        # Load provider options
        self.pool_size = config.get('options', {}).get('pool_size', 20)
        self.timeout = config.get('options', {}).get('timeout', 30)
        self.queries = config.get('queries', {})

        # Load data provision config
        try:
            from modules.generation.data_providers.config_loader import get_data_provision_config
            self.provision_config = get_data_provision_config()
            provider_config = self.provision_config.get_provider_config('postgres')
            self.queries.update(provider_config.get('queries', {}))
            logger.info(f"Loaded {len(self.queries)} predefined queries from config")
        except Exception as e:
            logger.warning(f"Could not load data provision config: {e}")
            self.provision_config = None

        # Initialize template loader for checking mapping configs
        try:
            from modules.generation.templates.loader import TemplateLoader
            from modules.generation.config import get_generation_config
            gen_config = get_generation_config()
            self.template_loader = TemplateLoader(mappings_dir=gen_config.mappings_dir)
        except Exception as e:
            logger.warning(f"Could not initialize template loader: {e}")
            self.template_loader = None

        logger.info(f"Initialized PostgresDataProvider")
    
    async def fetch_data(
        self,
        query: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Fetch data from PostgreSQL.
        
        Args:
            query: Query parameters
                Examples:
                - {"document_id": "123"}
                - {"query_name": "get_invoice", "invoice_id": "456"}
                - {"custom_sql": "SELECT * FROM invoices WHERE id = :id", "id": "789"}
        
        Returns:
            Dictionary with data in universal format:
            {
                "fields": {"invoice_number": "INV-001", ...},
                "items": [{"description": "Item 1", ...}, ...],
                "metadata": {"source": "postgres", "fetch_time": 0.5}
            }
        """
        start_time = time.time()
        
        try:
            logger.info(f"Fetching data from PostgreSQL: {query}")
            
            async with self.db_connection.get_session() as session:
                # Determine query type
                if "document_id" in query:
                    data = await self._fetch_by_document_id(session, query["document_id"])
                elif "query_name" in query:
                    data = await self._fetch_by_query_name(session, query)
                elif "custom_sql" in query:
                    data = await self._fetch_by_custom_sql(session, query)
                else:
                    raise DataProviderException("Invalid query format. Provide 'document_id', 'query_name', or 'custom_sql'")
                
                fetch_time = time.time() - start_time
                
                # Add metadata
                data["metadata"] = {
                    "source": "postgres",
                    "fetch_time": fetch_time,
                    "provider": self.provider_name,
                    "query_type": list(query.keys())[0] if query else "unknown"
                }
                
                logger.info(f"Successfully fetched data in {fetch_time:.2f}s")
                return data
                
        except Exception as e:
            logger.error(f"Failed to fetch data: {str(e)}")
            raise DataProviderException(f"PostgreSQL fetch failed: {str(e)}")
    
    async def _fetch_by_document_id(
        self, 
        session: AsyncSession, 
        document_id: str
    ) -> Dict[str, Any]:
        """Fetch document by ID from api_documents table."""
        
        # Query main document
        result = await session.execute(
            text("SELECT * FROM api_documents WHERE document_id = :document_id"),
            {"document_id": document_id}
        )
        row = result.fetchone()
        
        if not row:
            raise DataProviderException(f"Document not found: {document_id}")
        
        # Convert to dict
        row_dict = dict(row._mapping)
        
        # Transform nested structure to flat structure
        transformed = DataTransformer.transform_document(row_dict)
        
        return transformed
    
    async def _fetch_by_query_name(
        self,
        session: AsyncSession,
        query: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute predefined query from config."""
        query_name = query.get('query_name')
        
        if query_name not in self.queries:
            raise DataProviderException(f"Query not found in config: {query_name}")
        
        query_config = self.queries[query_name]
        
        # Get SQL from config (supports both old and new format)
        if 'sql' in query_config:
            # New format from data_provision.yaml
            sql = query_config['sql'].strip()
        else:
            # Old format (backward compatible)
            sql = f"SELECT {query_config['fields']} FROM {query_config['table']}"
            if 'where' in query_config:
                sql += f" WHERE {query_config['where']}"
        
        # Execute
        params = {k: v for k, v in query.items() if k != 'query_name'}
        result = await session.execute(text(sql), params)
        
        # Handle single vs multiple results
        returns = query_config.get('returns', 'single')
        if returns == 'multiple':
            rows = result.fetchall()
            if not rows:
                return {"fields": {}, "items": [], "raw_data": []}
            
            # Transform each row
            transformed_rows = []
            for row in rows:
                row_dict = dict(row._mapping)
                if 'fields' in row_dict or 'items' in row_dict:
                    transformed_rows.append(DataTransformer.transform_document(row_dict))
                else:
                    transformed_rows.append(row_dict)
            
            return {
                "fields": {},
                "items": transformed_rows,
                "raw_data": [dict(row._mapping) for row in rows]
            }
        else:
            row = result.fetchone()
            if not row:
                raise DataProviderException(f"No data found for query: {query_name}")
            
            row_dict = dict(row._mapping)
            
            # Transform if it has the database structure
            if 'fields' in row_dict or 'items' in row_dict:
                return DataTransformer.transform_document(row_dict)
            else:
                # Already flat or different structure
                return {
                    "fields": row_dict,
                    "items": [],
                    "raw_data": row_dict
                }
    
    async def _fetch_by_custom_sql(
        self,
        session: AsyncSession,
        query: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute custom SQL query."""
        sql = query.pop('custom_sql')
        
        result = await session.execute(text(sql), query)
        row = result.fetchone()
        
        if not row:
            raise DataProviderException("No data found for custom query")
        
        return {
            "fields": dict(row._mapping),
            "items": [],
            "raw_data": dict(row._mapping)
        }
    
    async def validate_query(self, query: Dict[str, Any]) -> bool:
        """Validate query parameters."""
        required_keys = ["document_id", "query_name", "custom_sql"]
        return any(key in query for key in required_keys)
    
    async def fetch_multi_source_data(
        self,
        document_ids: List[str],
        merge_strategy: str = "prioritized",
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Fetch and merge data from multiple documents.

        Args:
            document_ids: List of document IDs to merge (in priority order)
            merge_strategy: How to merge conflicts
                - 'prioritized': First document wins (respects document_ids order)
                - 'best_available': Most complete value wins
                - 'all_required': All documents must have field or return None
            options: Additional options

        Returns:
            Merged data dictionary with source tracking
        """
        start_time = time.time()

        if not document_ids:
            raise DataProviderException("At least one document_id required for multi-source fetch")

        logger.info(f"Fetching multi-source data: {len(document_ids)} documents, strategy={merge_strategy}")

        try:
            async with self.db_connection.get_session() as session:
                # Fetch all documents
                all_doc_data = []
                for doc_id in document_ids:
                    try:
                        doc_data = await self._fetch_by_document_id(session, doc_id)
                        doc_data['_source_document_id'] = doc_id
                        all_doc_data.append(doc_data)
                        logger.debug(f"Fetched document {doc_id}: {len(doc_data.get('fields', {}))} fields, {len(doc_data.get('items', []))} items")
                    except Exception as e:
                        logger.warning(f"Failed to fetch document {doc_id}: {e}")
                        continue

                if not all_doc_data:
                    raise DataProviderException("No documents could be fetched")

                # Merge based on strategy
                if merge_strategy == "prioritized":
                    merged = self._merge_prioritized(all_doc_data)
                elif merge_strategy == "best_available":
                    merged = self._merge_best_available(all_doc_data)
                elif merge_strategy == "all_required":
                    merged = self._merge_all_required(all_doc_data)
                else:
                    raise DataProviderException(f"Unknown merge strategy: {merge_strategy}")

                fetch_time = time.time() - start_time

                # Add metadata
                merged["metadata"] = {
                    "source": "postgres_multi",
                    "fetch_time": fetch_time,
                    "provider": self.provider_name,
                    "document_count": len(all_doc_data),
                    "merge_strategy": merge_strategy,
                    "source_documents": document_ids
                }

                logger.info(f"Successfully merged {len(all_doc_data)} documents in {fetch_time:.2f}s")
                logger.info(f"Result: {len(merged.get('fields', {}))} fields, {len(merged.get('items', []))} items")

                return merged

        except Exception as e:
            logger.error(f"Failed to fetch multi-source data: {str(e)}")
            raise DataProviderException(f"Multi-source fetch failed: {str(e)}")

    def _merge_prioritized(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge with priority order - first document wins for conflicts.

        Args:
            documents: List of document data (in priority order)

        Returns:
            Merged dictionary
        """
        merged_fields = {}
        merged_items = []
        field_sources = {}  # Track which document each field came from

        for doc in documents:
            source_id = doc.get('_source_document_id', 'unknown')

            # Merge fields (first value wins)
            for field, value in doc.get('fields', {}).items():
                if field not in merged_fields and value is not None:
                    merged_fields[field] = value
                    field_sources[field] = source_id

            # Concatenate items
            items = doc.get('items', [])
            if items:
                # Add source tracking to each item
                for item in items:
                    item['_source_document'] = source_id
                merged_items.extend(items)

        return {
            "fields": merged_fields,
            "items": merged_items,
            "_field_sources": field_sources  # Track origins for audit
        }

    def _merge_best_available(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge choosing most complete value for each field.

        Args:
            documents: List of document data

        Returns:
            Merged dictionary with best values
        """
        merged_fields = {}
        merged_items = []
        field_sources = {}
        field_scores = {}  # Track completeness scores

        for doc in documents:
            source_id = doc.get('_source_document_id', 'unknown')

            # Merge fields (best value wins)
            for field, value in doc.get('fields', {}).items():
                current_score = field_scores.get(field, 0)
                new_score = self._score_value(value)

                if new_score > current_score:
                    merged_fields[field] = value
                    field_sources[field] = source_id
                    field_scores[field] = new_score

            # Concatenate items
            items = doc.get('items', [])
            if items:
                for item in items:
                    item['_source_document'] = source_id
                merged_items.extend(items)

        return {
            "fields": merged_fields,
            "items": merged_items,
            "_field_sources": field_sources,
            "_field_scores": field_scores
        }

    def _merge_all_required(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Only include fields present in ALL documents (intersection).

        Args:
            documents: List of document data

        Returns:
            Merged dictionary with only common fields
        """
        if not documents:
            return {"fields": {}, "items": []}

        # Find common fields
        field_sets = [set(doc.get('fields', {}).keys()) for doc in documents]
        common_fields = set.intersection(*field_sets) if field_sets else set()

        merged_fields = {}
        field_sources = {}

        # Use first document's value for common fields
        first_doc = documents[0]
        source_id = first_doc.get('_source_document_id', 'unknown')

        for field in common_fields:
            merged_fields[field] = first_doc['fields'][field]
            field_sources[field] = source_id

        # Concatenate all items
        merged_items = []
        for doc in documents:
            items = doc.get('items', [])
            if items:
                source_id = doc.get('_source_document_id', 'unknown')
                for item in items:
                    item['_source_document'] = source_id
                merged_items.extend(items)

        return {
            "fields": merged_fields,
            "items": merged_items,
            "_field_sources": field_sources,
            "_excluded_fields": len(field_sets[0]) - len(common_fields) if field_sets else 0
        }

    def _score_value(self, value: Any) -> int:
        """
        Score value completeness (0-100).

        Higher score = more complete/reliable value.
        """
        if value is None or value == "":
            return 0

        score = 50  # Base score for having a value

        value_str = str(value).strip()

        # Empty or placeholder patterns
        if not value_str or value_str.upper() in ['N/A', 'TBD', 'NULL', 'NONE', '[', ']']:
            return 5

        # Length bonus (more detail = better)
        if len(value_str) > 10:
            score += 15
        if len(value_str) > 50:
            score += 10

        # Specific valid patterns
        import re

        # Valid date format
        if re.match(r'\d{4}-\d{2}-\d{2}', value_str):
            score += 15

        # Valid number (not just "0" or "0.00")
        if re.match(r'^\d+\.?\d*$', value_str) and float(value_str) > 0:
            score += 10

        # No placeholder indicators
        if '[' not in value_str and 'TBD' not in value_str.upper() and 'TODO' not in value_str.upper():
            score += 10

        return min(score, 100)

    async def health_check(self) -> bool:
        """Check if PostgreSQL is accessible."""
        try:
            return await self.db_connection.health_check()
        except Exception as e:
            logger.error(f"PostgreSQL health check failed: {str(e)}")
            return False

    async def fetch_data_with_insights(
        self,
        query: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Fetch data and generate AI-powered insights.

        This extends fetch_data to optionally include calculated insights
        when the mapping configuration specifies them.

        Args:
            query: Query parameters (same as fetch_data)
            options: Optional dictionary containing:
                - 'mapping_id': Field mapping configuration ID
                - 'include_insights': Whether to generate insights (default: auto-detect)

        Returns:
            Dictionary with data and optionally generated insights:
            {
                "fields": {...},
                "items": [...],
                "insights": {...}  # If enabled and configured
                "metadata": {...}
            }
        """
        start_time = time.time()

        # Fetch base data
        data = await self.fetch_data(query, options)

        # Check if insights should be generated
        include_insights = options.get('include_insights', 'auto') if options else 'auto'

        if include_insights == 'auto':
            # Auto-detect from mapping configuration
            mapping_id = options.get('mapping_id') if options else None
            if mapping_id:
                include_insights = await self._mapping_requires_insights(mapping_id)

        if include_insights in ['auto', True, 'yes']:
            # Generate insights
            try:
                insights = await self._generate_insights(
                    data,
                    query.get('document_id') or query.get('document_ids', [''])[0] if 'document_ids' in query else None
                )
                data['insights'] = insights
                logger.info(f"Generated insights for document")
            except Exception as e:
                logger.warning(f"Could not generate insights: {e}")
                data['insights'] = None

        return data

    async def _mapping_requires_insights(self, mapping_id: str) -> bool:
        """Check if mapping configuration requires insights generation."""
        try:
            # Use the template_loader to check if the mapping requires insights
            mapping_config = self.template_loader.load_mapping_config(mapping_id)
            if mapping_config:
                # Check if any field mappings use insights.* as source
                field_mappings = mapping_config.get('field_mappings', {})
                for field_def in field_mappings.values():
                    if isinstance(field_def, dict):
                        source = field_def.get('source', '')
                        if source.startswith('insights.'):
                            return True
        except Exception as e:
            logger.debug(f"Could not check mapping for insights: {e}")
        return False

    async def _generate_insights(
        self,
        data: Dict[str, Any],
        document_id: str
    ) -> Dict[str, Any]:
        """
        Generate insights from customer data.

        Uses the BankingInsightsService to analyze the customer data
        and generate risk assessment, product eligibility, recommendations, etc.
        """
        from modules.generation.services.banking_insights_service import BankingInsightsService

        async with self.db_connection.get_session() as session:
            service = BankingInsightsService(session)

            # Get customer data from fields
            customer_data = data.get('fields', {})

            # Generate comprehensive insights
            insights = await service.generate_customer_insights(
                customer_data=customer_data,
                document_id=document_id or 'unknown'
            )

            return insights
