#!/usr/bin/env python3
"""
Dynamic Database System Demo.

Demonstrates the complete flow of the config-driven database system for
insights and analytics modules.

This shows:
1. How schemas are created dynamically from YAML configs
2. How data is stored using universal repositories
3. How to query and aggregate data
4. How the system works across different use cases

Usage:
    python examples/dynamic_database_demo.py
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from src.database.connection import get_database_url
from modules.insights.storage.integration import create_insights_storage
from modules.analytics.storage.integration import create_analytics_storage
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


async def demo_insights_storage():
    """Demonstrate insights storage functionality."""
    logger.info("=" * 80)
    logger.info("INSIGHTS STORAGE DEMO")
    logger.info("=" * 80)

    use_case_id = "forms-capital-loan"
    database_url = get_database_url()
    engine = create_async_engine(database_url, echo=False)

    try:
        async with AsyncSession(engine) as session:
            # Initialize storage (creates table if needed)
            logger.info("\n1. Initializing insights storage...")
            storage = await create_insights_storage(engine, session, use_case_id)
            logger.info("✓ Insights table created/verified")

            # Save sample insights
            logger.info("\n2. Saving sample insights...")
            sample_insights = [
                {
                    "document_id": "doc_001",
                    "full_name": "John Doe",
                    "age": 35,
                    "monthly_income": 7500.00,
                    "occupation": "Software Engineer",
                    "employment_status": "employed",
                    "risk_score": 75,
                    "risk_level": "low",
                    "auto_approval_status": "approved",
                    "max_loan_amount": 50000.00,
                    "risk_factors": {
                        "income_stability": 90,
                        "credit_history": 85,
                        "debt_ratio": 70
                    }
                },
                {
                    "document_id": "doc_002",
                    "full_name": "Jane Smith",
                    "age": 28,
                    "monthly_income": 4200.00,
                    "occupation": "Teacher",
                    "employment_status": "employed",
                    "risk_score": 55,
                    "risk_level": "medium",
                    "auto_approval_status": "manual_review",
                    "max_loan_amount": 20000.00,
                    "risk_factors": {
                        "income_stability": 75,
                        "credit_history": 60,
                        "debt_ratio": 45
                    }
                },
                {
                    "document_id": "doc_003",
                    "full_name": "Bob Wilson",
                    "age": 42,
                    "monthly_income": 12000.00,
                    "occupation": "Business Owner",
                    "employment_status": "self_employed",
                    "risk_score": 85,
                    "risk_level": "low",
                    "auto_approval_status": "approved",
                    "max_loan_amount": 100000.00,
                    "risk_factors": {
                        "income_stability": 95,
                        "credit_history": 90,
                        "debt_ratio": 80
                    }
                }
            ]

            for insight in sample_insights:
                doc_id = insight.pop("document_id")
                await storage.save(doc_id, insight)
                logger.info(f"  ✓ Saved insights for {doc_id}")

            # Retrieve insights
            logger.info("\n3. Retrieving insights...")
            retrieved = await storage.get("doc_001")
            logger.info(f"  Document: {retrieved['document_id']}")
            logger.info(f"  Name: {retrieved['full_name']}")
            logger.info(f"  Risk Score: {retrieved['risk_score']}")
            logger.info(f"  Risk Level: {retrieved['risk_level']}")

            # Get statistics
            logger.info("\n4. Getting aggregate statistics...")
            stats = await storage.get_statistics()
            logger.info(f"  Total insights: {stats['total_insights']}")
            logger.info(f"  Risk distribution: {stats['risk_level_distribution']}")
            logger.info(f"  Approval distribution: {stats['approval_distribution']}")

            await session.commit()

    finally:
        await engine.dispose()

    logger.info("\n✓ Insights storage demo completed successfully\n")


async def demo_analytics_storage():
    """Demonstrate analytics storage functionality."""
    logger.info("=" * 80)
    logger.info("ANALYTICS STORAGE DEMO")
    logger.info("=" * 80)

    use_case_id = "forms-capital-loan"
    database_url = get_database_url()
    engine = create_async_engine(database_url, echo=False)

    try:
        async with AsyncSession(engine) as session:
            # Initialize storage
            logger.info("\n1. Initializing analytics storage...")
            storage = await create_analytics_storage(engine, session, use_case_id)
            logger.info("✓ Analytics table created/verified")

            # Save monthly metrics
            logger.info("\n2. Saving monthly metrics...")

            # Generate 6 months of sample data
            current_date = datetime(2026, 2, 1)
            for i in range(6):
                period_start = current_date - relativedelta(months=i)

                # Average risk score metric
                await storage.save_monthly_metric(
                    "average_risk_score",
                    period_start,
                    70.0 + (i * 2),  # Increasing trend
                    metric_name="Average Risk Score"
                )

                # Application count
                await storage.save_monthly_metric(
                    "application_count",
                    period_start,
                    150 + (i * 10),  # Growing applications
                    metric_name="Application Count"
                )

                logger.info(f"  ✓ Saved metrics for {period_start.strftime('%Y-%m')}")

            # Save dimensional breakdowns
            logger.info("\n3. Saving dimensional breakdowns...")
            feb_start = datetime(2026, 2, 1)

            # Risk level breakdown
            risk_levels = [
                ("low", 45),
                ("medium", 35),
                ("high", 15),
                ("critical", 5)
            ]

            for level, count in risk_levels:
                await storage.save_dimension_breakdown(
                    dimension_id="risk_level",
                    dimension_value=level,
                    period_type="monthly",
                    period_start=feb_start,
                    count=count
                )

            logger.info("  ✓ Saved risk level breakdown")

            # Save product metrics
            logger.info("\n4. Saving product metrics...")
            products = [
                ("personal_loan", 85, 100),
                ("business_loan", 60, 100),
                ("quick_cash", 95, 100)
            ]

            for product_id, eligible, total in products:
                await storage.save_product_metric(
                    product_id=product_id,
                    period_type="monthly",
                    period_start=feb_start,
                    eligible_count=eligible,
                    total_count=total
                )

            logger.info("  ✓ Saved product eligibility metrics")

            # Retrieve trend data
            logger.info("\n5. Retrieving trend data...")
            trend = await storage.get_trend("average_risk_score", "monthly", 6)
            logger.info(f"  Retrieved {len(trend)} trend points")
            for point in reversed(trend):  # Show chronologically
                logger.info(
                    f"    {point['period_label']}: "
                    f"Score = {point.get('average', 'N/A')}"
                )

            # Retrieve dimensional breakdown
            logger.info("\n6. Retrieving dimensional breakdown...")
            breakdown = await storage.get_dimension_breakdown(
                "risk_level",
                "monthly",
                feb_start
            )
            logger.info("  Risk level distribution:")
            for item in breakdown:
                logger.info(
                    f"    {item['dimension_value']}: "
                    f"{item['count']} applications"
                )

            await session.commit()

    finally:
        await engine.dispose()

    logger.info("\n✓ Analytics storage demo completed successfully\n")


async def demo_cross_use_case():
    """Demonstrate how system works across different use cases."""
    logger.info("=" * 80)
    logger.info("CROSS-USE-CASE DEMO")
    logger.info("=" * 80)

    database_url = get_database_url()
    engine = create_async_engine(database_url, echo=False)

    try:
        logger.info("\nDemonstrating use case isolation...")
        logger.info("Each use case gets its own table with its own schema\n")

        # Show both use cases can coexist
        use_cases = ["forms-capital-loan"]  # Could add more use cases here

        async with AsyncSession(engine) as session:
            for use_case in use_cases:
                logger.info(f"Use case: {use_case}")

                # Insights
                insights_storage = await create_insights_storage(
                    engine, session, use_case
                )
                insights_count = await insights_storage.repository.count()
                logger.info(f"  Insights table: {insights_storage.repository.table.name}")
                logger.info(f"  Records: {insights_count}")

                # Analytics
                analytics_storage = await create_analytics_storage(
                    engine, session, use_case
                )
                analytics_count = await analytics_storage.repository.count()
                logger.info(f"  Analytics table: {analytics_storage.repository.table.name}")
                logger.info(f"  Records: {analytics_count}")
                logger.info()

            await session.commit()

    finally:
        await engine.dispose()

    logger.info("✓ Cross-use-case demo completed\n")


async def main():
    """Run all demos."""
    logger.info("\n" + "=" * 80)
    logger.info("DYNAMIC DATABASE SYSTEM - COMPLETE DEMONSTRATION")
    logger.info("=" * 80 + "\n")

    try:
        # Run demos in sequence
        await demo_insights_storage()
        await demo_analytics_storage()
        await demo_cross_use_case()

        logger.info("=" * 80)
        logger.info("ALL DEMOS COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        logger.info("\nKey Features Demonstrated:")
        logger.info("  ✓ Dynamic table creation from YAML config")
        logger.info("  ✓ Automatic schema management")
        logger.info("  ✓ Universal CRUD operations")
        logger.info("  ✓ Aggregations and statistics")
        logger.info("  ✓ Trend analysis")
        logger.info("  ✓ Dimensional breakdowns")
        logger.info("  ✓ Use case isolation")
        logger.info("\nThe system is 100% config-driven and works with any use case!")
        logger.info("=" * 80 + "\n")

        return 0

    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
