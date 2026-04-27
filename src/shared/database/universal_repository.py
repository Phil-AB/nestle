"""
Universal Repository for Dynamic Tables.

Provides CRUD operations for any dynamically created table.
100% config-driven - works with any schema.
"""

from typing import Dict, Any, List, Optional, Union
from uuid import uuid4
from datetime import datetime

from sqlalchemy import Table, select, insert, update, delete, and_, or_, desc, asc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class UniversalRepository:
    """
    Universal repository for dynamic table operations.

    Provides standard CRUD operations that work with any table structure.
    No hardcoded field names or queries.

    Features:
    - Dynamic CRUD operations
    - Flexible filtering
    - Pagination
    - Aggregations
    - Transactions

    Example:
        >>> repo = UniversalRepository(session, insights_table)
        >>> record = await repo.create({"document_id": "123", "risk_score": 75})
        >>> records = await repo.find_many({"risk_level": "high"})
    """

    def __init__(self, session: AsyncSession, table: Table):
        """
        Initialize repository.

        Args:
            session: Async SQLAlchemy session
            table: SQLAlchemy Table object
        """
        self.session = session
        self.table = table

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new record.

        Args:
            data: Field values for new record

        Returns:
            Created record as dictionary

        Example:
            >>> record = await repo.create({
            ...     "document_id": "doc_123",
            ...     "risk_score": 75,
            ...     "risk_level": "medium"
            ... })
        """
        # Generate ID if not provided and table has UUID primary key
        if "id" not in data:
            pk_cols = [col for col in self.table.columns if col.primary_key]
            if pk_cols and str(pk_cols[0].type) == "UUID":
                data["id"] = uuid4()

        # Set timestamps if columns exist
        if "created_at" in self.table.columns and "created_at" not in data:
            data["created_at"] = datetime.utcnow()
        if "updated_at" in self.table.columns and "updated_at" not in data:
            data["updated_at"] = datetime.utcnow()

        # Insert record
        stmt = insert(self.table).values(**data).returning(self.table)
        result = await self.session.execute(stmt)
        await self.session.commit()

        record = result.fetchone()
        return self._row_to_dict(record) if record else None

    async def bulk_create(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Create multiple records in bulk.

        Args:
            records: List of record data dictionaries

        Returns:
            List of created records
        """
        if not records:
            return []

        # Prepare records
        for record in records:
            if "id" not in record:
                pk_cols = [col for col in self.table.columns if col.primary_key]
                if pk_cols and str(pk_cols[0].type) == "UUID":
                    record["id"] = uuid4()

            if "created_at" in self.table.columns and "created_at" not in record:
                record["created_at"] = datetime.utcnow()
            if "updated_at" in self.table.columns and "updated_at" not in record:
                record["updated_at"] = datetime.utcnow()

        # Bulk insert
        stmt = insert(self.table).values(records).returning(self.table)
        result = await self.session.execute(stmt)
        await self.session.commit()

        return [self._row_to_dict(row) for row in result.fetchall()]

    async def find_one(
        self,
        filters: Dict[str, Any],
        order_by: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find single record matching filters.

        Args:
            filters: Field-value pairs to filter by
            order_by: Optional column to order by (prefix with '-' for DESC)

        Returns:
            Record as dictionary or None
        """
        query = self._build_select_query(filters, order_by=order_by)
        result = await self.session.execute(query)
        row = result.fetchone()

        return self._row_to_dict(row) if row else None

    async def find_many(
        self,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[Union[str, List[str]]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Find multiple records matching filters.

        Args:
            filters: Optional field-value pairs to filter by
            order_by: Column(s) to order by (prefix with '-' for DESC)
            limit: Maximum number of records
            offset: Number of records to skip

        Returns:
            List of records as dictionaries
        """
        query = self._build_select_query(
            filters,
            order_by=order_by,
            limit=limit,
            offset=offset
        )
        result = await self.session.execute(query)
        rows = result.fetchall()

        return [self._row_to_dict(row) for row in rows]

    async def find_by_id(self, record_id: Any) -> Optional[Dict[str, Any]]:
        """
        Find record by primary key.

        Args:
            record_id: Primary key value

        Returns:
            Record as dictionary or None
        """
        pk_col = self._get_primary_key_column()
        return await self.find_one({pk_col.name: record_id})

    async def update_one(
        self,
        filters: Dict[str, Any],
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update single record matching filters.

        Args:
            filters: Field-value pairs to identify record
            updates: Field-value pairs to update

        Returns:
            Updated record or None
        """
        # Set updated_at if column exists
        if "updated_at" in self.table.columns:
            updates["updated_at"] = datetime.utcnow()

        where_clause = self._build_where_clause(filters)
        stmt = (
            update(self.table)
            .where(where_clause)
            .values(**updates)
            .returning(self.table)
        )

        result = await self.session.execute(stmt)
        await self.session.commit()

        row = result.fetchone()
        return self._row_to_dict(row) if row else None

    async def update_by_id(
        self,
        record_id: Any,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update record by primary key."""
        pk_col = self._get_primary_key_column()
        return await self.update_one({pk_col.name: record_id}, updates)

    async def update_many(
        self,
        filters: Dict[str, Any],
        updates: Dict[str, Any]
    ) -> int:
        """
        Update multiple records matching filters.

        Args:
            filters: Field-value pairs to identify records
            updates: Field-value pairs to update

        Returns:
            Number of records updated
        """
        if "updated_at" in self.table.columns:
            updates["updated_at"] = datetime.utcnow()

        where_clause = self._build_where_clause(filters)
        stmt = update(self.table).where(where_clause).values(**updates)

        result = await self.session.execute(stmt)
        await self.session.commit()

        return result.rowcount

    async def delete_one(self, filters: Dict[str, Any]) -> bool:
        """
        Delete single record matching filters.

        Args:
            filters: Field-value pairs to identify record

        Returns:
            True if record was deleted
        """
        where_clause = self._build_where_clause(filters)
        stmt = delete(self.table).where(where_clause)

        result = await self.session.execute(stmt)
        await self.session.commit()

        return result.rowcount > 0

    async def delete_by_id(self, record_id: Any) -> bool:
        """Delete record by primary key."""
        pk_col = self._get_primary_key_column()
        return await self.delete_one({pk_col.name: record_id})

    async def delete_many(self, filters: Dict[str, Any]) -> int:
        """
        Delete multiple records matching filters.

        Returns:
            Number of records deleted
        """
        where_clause = self._build_where_clause(filters)
        stmt = delete(self.table).where(where_clause)

        result = await self.session.execute(stmt)
        await self.session.commit()

        return result.rowcount

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count records matching filters.

        Args:
            filters: Optional field-value pairs to filter by

        Returns:
            Count of matching records
        """
        query = select(func.count()).select_from(self.table)

        if filters:
            where_clause = self._build_where_clause(filters)
            query = query.where(where_clause)

        result = await self.session.execute(query)
        return result.scalar() or 0

    async def exists(self, filters: Dict[str, Any]) -> bool:
        """Check if any record matches filters."""
        count = await self.count(filters)
        return count > 0

    async def aggregate(
        self,
        aggregations: Dict[str, str],
        filters: Optional[Dict[str, Any]] = None,
        group_by: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform aggregations.

        Args:
            aggregations: Dict of {alias: "func(column)"} (e.g., {"avg_score": "avg(risk_score)"})
            filters: Optional filters
            group_by: Optional columns to group by

        Returns:
            List of aggregation results

        Example:
            >>> results = await repo.aggregate(
            ...     {"avg_score": "avg(risk_score)", "count": "count(*)"},
            ...     group_by=["risk_level"]
            ... )
        """
        # Build select expressions
        select_cols = []

        if group_by:
            for col_name in group_by:
                select_cols.append(self.table.c[col_name])

        for alias, agg_expr in aggregations.items():
            # Parse aggregation expression
            if "(" in agg_expr:
                func_name, col_part = agg_expr.split("(")
                col_name = col_part.rstrip(")")

                if col_name == "*":
                    agg_col = func.count()
                else:
                    col = self.table.c[col_name]
                    if func_name == "avg":
                        agg_col = func.avg(col)
                    elif func_name == "sum":
                        agg_col = func.sum(col)
                    elif func_name == "min":
                        agg_col = func.min(col)
                    elif func_name == "max":
                        agg_col = func.max(col)
                    elif func_name == "count":
                        agg_col = func.count(col)
                    else:
                        raise ValueError(f"Unsupported aggregation function: {func_name}")

                select_cols.append(agg_col.label(alias))

        query = select(*select_cols)

        if filters:
            where_clause = self._build_where_clause(filters)
            query = query.where(where_clause)

        if group_by:
            query = query.group_by(*[self.table.c[col] for col in group_by])

        result = await self.session.execute(query)
        rows = result.fetchall()

        return [dict(row._mapping) for row in rows]

    def _build_select_query(
        self,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[Union[str, List[str]]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> Select:
        """Build SELECT query with filters and options."""
        query = select(self.table)

        # Apply filters
        if filters:
            where_clause = self._build_where_clause(filters)
            query = query.where(where_clause)

        # Apply ordering
        if order_by:
            order_list = [order_by] if isinstance(order_by, str) else order_by
            for order_col in order_list:
                if order_col.startswith("-"):
                    col_name = order_col[1:]
                    query = query.order_by(desc(self.table.c[col_name]))
                else:
                    query = query.order_by(asc(self.table.c[order_col]))

        # Apply pagination
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)

        return query

    def _build_where_clause(self, filters: Dict[str, Any]):
        """Build WHERE clause from filters dictionary."""
        conditions = []

        for key, value in filters.items():
            col = self.table.c[key]

            if isinstance(value, (list, tuple)):
                # IN operator
                conditions.append(col.in_(value))
            elif isinstance(value, dict):
                # Support for operators: {"gte": 50, "lte": 100}
                for op, val in value.items():
                    if op == "gte":
                        conditions.append(col >= val)
                    elif op == "gt":
                        conditions.append(col > val)
                    elif op == "lte":
                        conditions.append(col <= val)
                    elif op == "lt":
                        conditions.append(col < val)
                    elif op == "ne":
                        conditions.append(col != val)
            elif value is None:
                conditions.append(col.is_(None))
            else:
                # Equality
                conditions.append(col == value)

        return and_(*conditions) if conditions else True

    def _get_primary_key_column(self):
        """Get primary key column."""
        pk_cols = [col for col in self.table.columns if col.primary_key]
        if not pk_cols:
            raise ValueError(f"Table {self.table.name} has no primary key")
        return pk_cols[0]

    def _row_to_dict(self, row) -> Dict[str, Any]:
        """Convert SQLAlchemy row to dictionary."""
        if row is None:
            return None

        result = dict(row._mapping)

        # Convert UUID to string
        for key, value in result.items():
            if hasattr(value, 'hex'):  # UUID object
                result[key] = str(value)
            elif isinstance(value, datetime):
                result[key] = value.isoformat()

        return result
