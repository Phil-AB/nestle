"""
PostgreSQL Data Provider for Population Module.

Queries extracted document data directly from the database.
Completely independent from the generation module.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text, pool
from sqlalchemy.engine import Engine
import logging
import os

logger = logging.getLogger(__name__)


class PostgresDataProvider:
    """
    Database data provider for population module.

    Queries extracted document data directly from PostgreSQL database.
    Implements merge strategies for combining multi-document data.

    Example:
        >>> provider = PostgresDataProvider(db_config)
        >>> data = await provider.get_documents_data(
        ...     document_ids=["abc123", "def456"],
        ...     merge_strategy="prioritized"
        ... )
        >>> print(f"Fields: {len(data['fields'])}, Items: {len(data['items'])}")
    """

    def __init__(self, db_config: Dict[str, Any]):
        """
        Initialize database connection.

        Args:
            db_config: Database connection configuration:
                - host_env: Environment variable name for host
                - port_env: Environment variable name for port
                - database_env: Environment variable name for database
                - user_env: Environment variable name for user
                - password_env: Environment variable name for password
                - pool_size: Connection pool size (optional)
                - max_overflow: Max connection overflow (optional)
        """
        self.db_config = db_config
        self.engine = self._create_engine()

        logger.info("PostgresDataProvider initialized")

    def _create_engine(self) -> Engine:
        """
        Create SQLAlchemy engine from configuration.

        Returns:
            SQLAlchemy Engine instance

        Raises:
            ValueError: If required environment variables not set
        """
        # Get connection parameters from environment variables
        host = os.getenv(self.db_config["host_env"])
        port = os.getenv(self.db_config["port_env"])
        database = os.getenv(self.db_config["database_env"])
        user = os.getenv(self.db_config["user_env"])
        password = os.getenv(self.db_config["password_env"])

        # Validate required parameters
        if not all([host, port, database, user, password]):
            raise ValueError(
                "Missing required database environment variables. "
                f"Required: {self.db_config['host_env']}, "
                f"{self.db_config['port_env']}, "
                f"{self.db_config['database_env']}, "
                f"{self.db_config['user_env']}, "
                f"{self.db_config['password_env']}"
            )

        # Construct connection string
        connection_string = (
            f"postgresql://{user}:{password}@{host}:{port}/{database}"
        )

        # Create engine with connection pooling
        engine = create_engine(
            connection_string,
            poolclass=pool.QueuePool,
            pool_size=self.db_config.get("pool_size", 5),
            max_overflow=self.db_config.get("max_overflow", 10),
            pool_timeout=self.db_config.get("pool_timeout", 30),
            pool_recycle=self.db_config.get("pool_recycle", 3600),
            echo=False  # Set True for SQL query logging
        )

        logger.info(f"Created database engine: {host}:{port}/{database}")
        return engine

    async def get_documents_data(
        self,
        document_ids: List[str],
        merge_strategy: str = "prioritized"
    ) -> Dict[str, Any]:
        """
        Fetch extracted data for documents from database.

        Args:
            document_ids: List of document IDs (UUIDs)
            merge_strategy: How to merge multi-document data:
                - "prioritized": First document wins
                - "best_available": Most complete value wins
                - "combine": Merge complementary data

        Returns:
            Merged document data dictionary:
                {
                    "fields": {field_name: value, ...},
                    "items": [{item_data}, ...],
                    "metadata": {combined_metadata}
                }

        Raises:
            ValueError: If no data found for documents
        """
        try:
            logger.info(
                f"Fetching data for {len(document_ids)} documents "
                f"with strategy '{merge_strategy}'"
            )

            # Query database for each document
            documents = []
            for doc_id in document_ids:
                doc_data = await self._fetch_document(doc_id)
                if doc_data:
                    documents.append(doc_data)

            if not documents:
                raise ValueError(
                    f"No data found for documents: {document_ids}"
                )

            logger.info(f"Fetched {len(documents)} documents from database")

            # Merge documents according to strategy
            merged = self._merge_documents(documents, merge_strategy)

            logger.info(
                f"Merged data: {len(merged['fields'])} fields, "
                f"{len(merged['items'])} items"
            )

            return merged

        except Exception as e:
            logger.error(f"Data fetch failed: {e}", exc_info=True)
            raise

    async def _fetch_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch single document extraction results from database.

        Args:
            document_id: Document UUID

        Returns:
            Document data dictionary or None if not found
        """
        query = text("""
            SELECT
                id,
                document_id,
                document_type,
                fields,
                items,
                doc_metadata as metadata,
                extraction_status
            FROM api_documents
            WHERE document_id = :id
        """)

        try:
            with self.engine.connect() as conn:
                result = conn.execute(query, {"id": document_id})
                row = result.fetchone()

                if row:
                    # Convert row to dictionary
                    doc_data = {
                        "id": row.id,
                        "document_id": row.document_id,
                        "document_type": row.document_type,
                        "fields": row.fields or {},
                        "items": row.items or [],
                        "metadata": row.metadata or {},
                        "extraction_status": row.extraction_status
                    }

                    logger.debug(
                        f"Fetched document {document_id}: "
                        f"{len(doc_data['fields'])} fields, "
                        f"{len(doc_data['items'])} items"
                    )

                    return doc_data

                logger.warning(f"Document not found: {document_id}")
                return None

        except Exception as e:
            logger.error(f"Error fetching document {document_id}: {e}")
            return None

    def _merge_documents(
        self,
        documents: List[Dict],
        strategy: str
    ) -> Dict[str, Any]:
        """
        Merge multiple documents into single dataset.

        Args:
            documents: List of document data dictionaries
            strategy: Merge strategy name

        Returns:
            Merged data dictionary

        Raises:
            ValueError: If unknown merge strategy
        """
        if strategy == "prioritized":
            return self._merge_prioritized(documents)
        elif strategy == "best_available":
            return self._merge_best_available(documents)
        elif strategy == "combine":
            return self._merge_combine(documents)
        else:
            raise ValueError(f"Unknown merge strategy: {strategy}")

    def _merge_prioritized(self, documents: List[Dict]) -> Dict[str, Any]:
        """
        Merge with prioritized strategy (first document wins).

        Fields: First non-empty value wins
        Items: Combine all items from all documents

        Args:
            documents: List of document data

        Returns:
            Merged data
        """
        merged = {
            "fields": {},
            "items": [],
            "metadata": {}
        }

        # Fields: first non-empty value wins
        for doc in documents:
            for key, value in doc.get("fields", {}).items():
                # Only use if not already set and value is non-empty
                if key not in merged["fields"] and value and value != "":
                    merged["fields"][key] = value

        # Items: combine all items
        for doc in documents:
            merged["items"].extend(doc.get("items", []))

        # Metadata: merge document types
        doc_types = [doc.get("document_type") for doc in documents]
        merged["metadata"]["document_types"] = doc_types
        merged["metadata"]["document_count"] = len(documents)

        logger.debug(
            f"Prioritized merge: {len(merged['fields'])} fields, "
            f"{len(merged['items'])} items"
        )

        return merged

    def _merge_best_available(self, documents: List[Dict]) -> Dict[str, Any]:
        """
        Merge with best_available strategy (most complete value wins).

        Prefers non-empty values, longer strings, higher confidence.

        Args:
            documents: List of document data

        Returns:
            Merged data
        """
        merged = {
            "fields": {},
            "items": [],
            "metadata": {}
        }

        # Fields: most complete value wins
        for doc in documents:
            for key, value in doc.get("fields", {}).items():
                if value and value != "":
                    # If field not set yet, use this value
                    if key not in merged["fields"]:
                        merged["fields"][key] = value
                    else:
                        # Compare with existing value - prefer longer/more complete
                        existing = merged["fields"][key]
                        if len(str(value)) > len(str(existing)):
                            merged["fields"][key] = value

        # Items: combine all items
        for doc in documents:
            merged["items"].extend(doc.get("items", []))

        # Metadata
        doc_types = [doc.get("document_type") for doc in documents]
        merged["metadata"]["document_types"] = doc_types
        merged["metadata"]["document_count"] = len(documents)

        return merged

    def _merge_combine(self, documents: List[Dict]) -> Dict[str, Any]:
        """
        Merge with combine strategy (merge complementary data).

        Combines all non-duplicate fields and items.

        Args:
            documents: List of document data

        Returns:
            Merged data
        """
        merged = {
            "fields": {},
            "items": [],
            "metadata": {}
        }

        # Fields: merge all unique fields
        for doc in documents:
            for key, value in doc.get("fields", {}).items():
                if value and value != "" and key not in merged["fields"]:
                    merged["fields"][key] = value

        # Items: combine with deduplication
        seen_items = set()
        for doc in documents:
            for item in doc.get("items", []):
                # Create hash of item for deduplication
                item_str = str(sorted(item.items()))
                if item_str not in seen_items:
                    merged["items"].append(item)
                    seen_items.add(item_str)

        # Metadata
        doc_types = [doc.get("document_type") for doc in documents]
        merged["metadata"]["document_types"] = doc_types
        merged["metadata"]["document_count"] = len(documents)

        return merged

    async def health_check(self) -> bool:
        """
        Check database connection health.

        Returns:
            True if connection is healthy

        Raises:
            Exception if connection fails
        """
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            logger.info("Database health check passed")
            return True

        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            raise

    def close(self):
        """Close database connection pool."""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connection pool closed")
