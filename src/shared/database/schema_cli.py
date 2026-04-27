#!/usr/bin/env python3
"""
Schema Management CLI.

Command-line tool for managing dynamic database schemas.

Usage:
    python schema_cli.py create insights forms-capital-loan
    python schema_cli.py create analytics forms-capital-loan
    python schema_cli.py list
    python schema_cli.py drop insights_forms_capital_loan
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine
from shared.database.schema_manager import SchemaManager
from src.database.connection import get_database_url
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


async def create_table(module: str, use_case_id: str):
    """Create table for a module and use case."""
    database_url = get_database_url()
    engine = create_async_engine(database_url, echo=False)

    try:
        manager = SchemaManager(engine)

        logger.info(f"Creating table for module={module}, use_case={use_case_id}")
        table = await manager.create_table_from_config(module, use_case_id)

        logger.info(f"✓ Table '{table.name}' created successfully")
        logger.info(f"  Columns: {len(table.columns)}")
        logger.info(f"  Indexes: {len(table.indexes)}")
        logger.info(f"  Constraints: {len(table.constraints)}")

        return True

    except FileNotFoundError as e:
        logger.error(f"✗ Schema config not found: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Error creating table: {e}", exc_info=True)
        return False
    finally:
        await engine.dispose()


async def list_tables():
    """List all tables in the database."""
    database_url = get_database_url()
    engine = create_async_engine(database_url, echo=False)

    try:
        from sqlalchemy import inspect

        async with engine.begin() as conn:
            tables = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )

        logger.info(f"Found {len(tables)} tables:")
        for table in sorted(tables):
            print(f"  - {table}")

        return True

    except Exception as e:
        logger.error(f"Error listing tables: {e}", exc_info=True)
        return False
    finally:
        await engine.dispose()


async def drop_table(table_name: str):
    """Drop a table from the database."""
    database_url = get_database_url()
    engine = create_async_engine(database_url, echo=False)

    try:
        manager = SchemaManager(engine)

        # Confirm
        response = input(f"Are you sure you want to drop table '{table_name}'? (yes/no): ")
        if response.lower() != "yes":
            logger.info("Operation cancelled")
            return False

        await manager.drop_table(table_name)
        logger.info(f"✓ Table '{table_name}' dropped successfully")
        return True

    except Exception as e:
        logger.error(f"Error dropping table: {e}", exc_info=True)
        return False
    finally:
        await engine.dispose()


async def ensure_table(module: str, use_case_id: str):
    """Ensure table exists (create if doesn't exist)."""
    database_url = get_database_url()
    engine = create_async_engine(database_url, echo=False)

    try:
        manager = SchemaManager(engine)

        logger.info(f"Ensuring table exists for module={module}, use_case={use_case_id}")
        table = await manager.ensure_table_exists(module, use_case_id)

        logger.info(f"✓ Table '{table.name}' ready")
        return True

    except Exception as e:
        logger.error(f"Error ensuring table: {e}", exc_info=True)
        return False
    finally:
        await engine.dispose()


def print_usage():
    """Print CLI usage information."""
    print("""
Schema Management CLI

Usage:
    python schema_cli.py <command> [arguments]

Commands:
    create <module> <use_case_id>    Create table for module and use case
                                      Examples: create insights forms-capital-loan
                                               create analytics forms-capital-loan

    ensure <module> <use_case_id>    Ensure table exists (create if needed)

    list                              List all tables in database

    drop <table_name>                 Drop a table (with confirmation)

    help                              Show this help message

Examples:
    python schema_cli.py create insights forms-capital-loan
    python schema_cli.py list
    python schema_cli.py drop insights_forms_capital_loan
    """)


async def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print_usage()
        return 1

    command = sys.argv[1].lower()

    if command == "help":
        print_usage()
        return 0

    elif command == "create":
        if len(sys.argv) < 4:
            print("Error: create requires <module> and <use_case_id>")
            print("Example: python schema_cli.py create insights forms-capital-loan")
            return 1

        module = sys.argv[2]
        use_case_id = sys.argv[3]
        success = await create_table(module, use_case_id)
        return 0 if success else 1

    elif command == "ensure":
        if len(sys.argv) < 4:
            print("Error: ensure requires <module> and <use_case_id>")
            return 1

        module = sys.argv[2]
        use_case_id = sys.argv[3]
        success = await ensure_table(module, use_case_id)
        return 0 if success else 1

    elif command == "list":
        success = await list_tables()
        return 0 if success else 1

    elif command == "drop":
        if len(sys.argv) < 3:
            print("Error: drop requires <table_name>")
            return 1

        table_name = sys.argv[2]
        success = await drop_table(table_name)
        return 0 if success else 1

    else:
        print(f"Unknown command: {command}")
        print_usage()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
