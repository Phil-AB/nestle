"""
Universal Dynamic Schema Manager.

Creates and manages database tables dynamically based on YAML configurations.
100% config-driven - no hardcoded schemas.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import yaml
from sqlalchemy import (
    Table, Column, MetaData, Index, ForeignKeyConstraint,
    CheckConstraint, UniqueConstraint, String, Integer, Float,
    Boolean, Text, DateTime, Numeric, JSON, inspect
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.sql import func
from datetime import datetime
import uuid

from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class SchemaManager:
    """
    Universal schema manager for dynamic table creation.

    Features:
    - Creates tables from YAML config
    - Manages indexes, constraints, foreign keys
    - Validates schema compatibility
    - Supports schema evolution

    Example:
        >>> manager = SchemaManager(engine)
        >>> await manager.create_table_from_config("insights", "forms-capital-loan")
    """

    # Type mapping from config to SQLAlchemy type classes
    TYPE_MAPPING = {
        "uuid": lambda **k: UUID(as_uuid=True),
        "string": lambda length=255, **k: String(length),
        "integer": lambda **k: Integer,
        "decimal": lambda precision=15, scale=2, **k: Numeric(precision, scale),
        "float": lambda **k: Float,
        "boolean": lambda **k: Boolean,
        "text": lambda **k: Text,
        "timestamp": lambda **k: TIMESTAMP(timezone=True),
        "datetime": lambda **k: DateTime,
        "json": lambda **k: JSON,
        "jsonb": lambda **k: JSONB,
    }

    def __init__(self, engine: AsyncEngine, metadata: Optional[MetaData] = None):
        """
        Initialize schema manager.

        Args:
            engine: Async SQLAlchemy engine
            metadata: Optional metadata object (creates new if not provided)
        """
        self.engine = engine
        self.metadata = metadata or MetaData()

    async def create_table_from_config(
        self,
        module: str,
        use_case_id: str,
        config_path: Optional[Path] = None
    ) -> Table:
        """
        Create table from YAML config.

        Args:
            module: Module name ('insights' or 'analytics')
            use_case_id: Use case identifier
            config_path: Optional explicit config path

        Returns:
            Created SQLAlchemy Table object

        Raises:
            FileNotFoundError: If config not found
            ValueError: If config is invalid
        """
        # Load schema config
        if config_path is None:
            config_path = self._get_default_config_path(module, use_case_id)

        logger.info(f"Loading schema config from: {config_path}")
        schema_config = self._load_schema_config(config_path)

        # Validate config
        self._validate_schema_config(schema_config)

        # Build table
        table = self._build_table(schema_config)

        # Create table in database
        await self._create_table(table)

        logger.info(f"Table '{table.name}' created successfully")
        return table

    async def table_exists(self, table_name: str) -> bool:
        """Check if table exists in database."""
        async with self.engine.begin() as conn:
            result = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).has_table(table_name)
            )
            return result

    async def get_table(self, table_name: str) -> Optional[Table]:
        """Get existing table object."""
        if table_name in self.metadata.tables:
            return self.metadata.tables[table_name]

        # Reflect table from database
        if await self.table_exists(table_name):
            async with self.engine.begin() as conn:
                await conn.run_sync(
                    lambda sync_conn: self.metadata.reflect(
                        bind=sync_conn,
                        only=[table_name]
                    )
                )
                return self.metadata.tables.get(table_name)

        return None

    async def drop_table(self, table_name: str):
        """Drop table from database."""
        table = await self.get_table(table_name)
        if table is not None:
            async with self.engine.begin() as conn:
                await conn.run_sync(lambda sync_conn: table.drop(sync_conn))
            logger.info(f"Table '{table_name}' dropped")

    def _get_default_config_path(self, module: str, use_case_id: str) -> Path:
        """Get default config path for module and use case."""
        base_path = Path(__file__).parent.parent.parent / "config"
        return base_path / module / "use_cases" / use_case_id / "schema.yaml"

    def _load_schema_config(self, config_path: Path) -> Dict[str, Any]:
        """Load schema config from YAML file."""
        if not config_path.exists():
            raise FileNotFoundError(f"Schema config not found: {config_path}")

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        return config

    def _validate_schema_config(self, config: Dict[str, Any]):
        """Validate schema configuration."""
        required_keys = ["use_case_id", "table", "schema"]

        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required key in schema config: {key}")

        if "name" not in config["table"]:
            raise ValueError("Table name is required in config")

        if not config["schema"]:
            raise ValueError("Schema definition cannot be empty")

    def _build_table(self, config: Dict[str, Any]) -> Table:
        """Build SQLAlchemy Table object from config."""
        table_config = config["table"]
        table_name = table_config["name"]
        schema_def = config["schema"]

        # Build columns
        columns = []
        for field_name, field_config in schema_def.items():
            column = self._build_column(field_name, field_config)
            columns.append(column)

        # Build constraints
        constraints = self._build_constraints(config.get("constraints", []))

        # Build foreign keys
        foreign_keys = self._build_foreign_keys(config.get("foreign_keys", []))

        # Create table
        table = Table(
            table_name,
            self.metadata,
            *columns,
            *constraints,
            *foreign_keys,
            extend_existing=True
        )

        # Build indexes (added after table creation)
        self._build_indexes(table, table_config.get("indexes", []))

        return table

    def _build_column(self, name: str, config: Dict[str, Any]) -> Column:
        """Build SQLAlchemy Column from config."""
        field_type = config.get("type", "string")

        if field_type not in self.TYPE_MAPPING:
            raise ValueError(f"Unsupported field type: {field_type}")

        # Get the type class with type-specific parameters
        type_func = self.TYPE_MAPPING[field_type]
        column_type = type_func(**config)

        # Build column arguments
        column_args = [column_type]
        column_kwargs = {
            "nullable": config.get("nullable", True),
            "primary_key": config.get("primary_key", False),
            "unique": config.get("unique", False),
            "index": config.get("index", False),
        }

        # Handle defaults
        default = config.get("default")
        if default == "now":
            column_kwargs["server_default"] = func.now()
        elif default is not None:
            column_kwargs["default"] = default

        # Handle special case for UUID primary keys
        if field_type == "uuid" and config.get("primary_key"):
            column_kwargs["default"] = uuid.uuid4

        # Handle on_update
        if config.get("on_update") == "now":
            column_kwargs["onupdate"] = func.now()

        # Add comment/description
        if "description" in config:
            column_kwargs["comment"] = config["description"]

        # Create the column with name
        column = Column(name, *column_args, **column_kwargs)

        return column

    def _build_constraints(self, constraints_config: List[Dict[str, Any]]) -> List:
        """Build SQLAlchemy constraints from config."""
        constraints = []

        for constraint_config in constraints_config:
            constraint_type = constraint_config.get("type")

            if constraint_type == "check":
                constraints.append(
                    CheckConstraint(
                        constraint_config["expression"],
                        name=constraint_config.get("name")
                    )
                )
            elif constraint_type == "unique":
                constraints.append(
                    UniqueConstraint(
                        *constraint_config["columns"],
                        name=constraint_config.get("name")
                    )
                )

        return constraints

    def _build_foreign_keys(self, fk_config: List[Dict[str, Any]]) -> List:
        """Build foreign key constraints from config."""
        if not fk_config:
            return []

        foreign_keys = []

        for fk in fk_config:
            ref = fk["references"]
            foreign_keys.append(
                ForeignKeyConstraint(
                    [fk["column"]],
                    [f"{ref['table']}.{ref['column']}"],
                    name=fk.get("name"),
                    ondelete=fk.get("on_delete", "CASCADE"),
                    onupdate=fk.get("on_update", "CASCADE")
                )
            )

        return foreign_keys

    def _build_indexes(self, table: Table, indexes_config: List[Dict[str, Any]]):
        """Build indexes for table."""
        for idx_config in indexes_config:
            Index(
                idx_config["name"],
                *[table.c[col] for col in idx_config["columns"]],
                unique=idx_config.get("unique", False)
            )

    async def _create_table(self, table: Table):
        """Create table in database if it doesn't exist."""
        async with self.engine.begin() as conn:
            # Check if table exists
            exists = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).has_table(table.name)
            )

            if not exists:
                # Create table
                await conn.run_sync(lambda sync_conn: table.create(sync_conn))
                logger.info(f"Created table: {table.name}")
            else:
                logger.info(f"Table already exists: {table.name}")

    async def ensure_table_exists(
        self,
        module: str,
        use_case_id: str
    ) -> Table:
        """
        Ensure table exists, creating it if necessary.

        Args:
            module: Module name ('insights' or 'analytics')
            use_case_id: Use case identifier

        Returns:
            Table object
        """
        # Get table name from config
        config_path = self._get_default_config_path(module, use_case_id)
        config = self._load_schema_config(config_path)
        table_name = config["table"]["name"]

        # Check if table exists
        table = await self.get_table(table_name)

        if table is None:
            # Create table from config
            table = await self.create_table_from_config(module, use_case_id, config_path)

        return table
