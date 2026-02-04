#!/usr/bin/env python3
"""
Setup Insights Storage.

Creates the database tables needed for insights and analytics storage.
Run this before using the insights API.

Usage:
    python scripts/setup_insights_storage.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine
from src.database.connection import get_database_url
from shared.database.schema_manager import SchemaManager
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


async def setup_storage():
    """Setup insights and analytics storage tables."""
    logger.info("=" * 80)
    logger.info("INSIGHTS & ANALYTICS STORAGE SETUP")
    logger.info("=" * 80)

    use_case_id = "forms-capital-loan"
    database_url = get_database_url()
    engine = create_async_engine(database_url, echo=False)

    try:
        manager = SchemaManager(engine)

        # Create insights table
        logger.info("\n1. Creating insights table...")
        try:
            insights_table = await manager.ensure_table_exists("insights", use_case_id)
            logger.info(f"   ✓ Insights table ready: {insights_table.name}")
            logger.info(f"     - Columns: {len(insights_table.columns)}")
            logger.info(f"     - Indexes: {len(insights_table.indexes)}")
        except Exception as e:
            logger.error(f"   ✗ Failed to create insights table: {e}")
            return False

        # Create analytics table
        logger.info("\n2. Creating analytics table...")
        try:
            analytics_table = await manager.ensure_table_exists("analytics", use_case_id)
            logger.info(f"   ✓ Analytics table ready: {analytics_table.name}")
            logger.info(f"     - Columns: {len(analytics_table.columns)}")
            logger.info(f"     - Indexes: {len(analytics_table.indexes)}")
        except Exception as e:
            logger.error(f"   ✗ Failed to create analytics table: {e}")
            return False

        logger.info("\n" + "=" * 80)
        logger.info("SETUP COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        logger.info("\nYou can now:")
        logger.info("  1. Generate insights via POST /api/v2/insights/generate")
        logger.info("  2. View analytics via GET /api/v2/analytics/dashboard")
        logger.info("  3. Run the demo: python examples/dynamic_database_demo.py")
        logger.info("=" * 80 + "\n")

        return True

    except Exception as e:
        logger.error(f"\nSetup failed: {e}", exc_info=True)
        return False

    finally:
        await engine.dispose()


async def main():
    """Main entry point."""
    success = await setup_storage()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
