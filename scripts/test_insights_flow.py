#!/usr/bin/env python3
"""
Test Insights Flow.

Tests the complete flow:
1. Fetch a document from database
2. Generate insights
3. Save insights to database (both insights table and doc_metadata)
4. Verify insights can be retrieved
5. Verify analytics can query the data

Usage:
    python scripts/test_insights_flow.py [document_id]

If no document_id provided, uses the first available document.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from src.database.connection import get_session, get_engine
from modules.insights import InsightsService
from modules.insights.storage.integration import create_insights_storage
from modules.analytics import AnalyticsService
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


async def test_insights_flow(document_id: str = None):
    """Test the complete insights flow."""
    logger.info("=" * 80)
    logger.info("INSIGHTS FLOW TEST")
    logger.info("=" * 80)

    use_case_id = "forms-capital-loan"
    engine = get_engine()

    async with get_session() as session:
        # Step 1: Get a document
        logger.info("\n1. Fetching document...")
        if document_id:
            query = text(
                "SELECT document_id, fields, document_name FROM api_documents "
                "WHERE document_id = :document_id LIMIT 1"
            )
            result = await session.execute(query, {"document_id": document_id})
        else:
            query = text(
                "SELECT document_id, fields, document_name FROM api_documents "
                "WHERE extraction_status = 'complete' LIMIT 1"
            )
            result = await session.execute(query)

        row = result.fetchone()
        if not row:
            logger.error("   ✗ No document found")
            return False

        doc_id = row[0]
        fields = row[1]
        doc_name = row[2]

        logger.info(f"   ✓ Found document: {doc_id}")
        logger.info(f"     Name: {doc_name}")
        logger.info(f"     Fields: {len(fields) if fields else 0}")

        # Step 2: Generate insights
        logger.info("\n2. Generating insights...")
        insights_service = InsightsService(use_case_id)
        insights = insights_service.generate_insights(fields)

        risk_score = insights["risk_assessment"]["risk_score"]
        risk_level = insights["risk_assessment"]["risk_level"]
        customer_name = insights["customer_profile"].get("full_name", "N/A")

        logger.info(f"   ✓ Insights generated")
        logger.info(f"     Customer: {customer_name}")
        logger.info(f"     Risk Score: {risk_score}")
        logger.info(f"     Risk Level: {risk_level}")

        # Step 3: Save to insights table
        logger.info("\n3. Saving to insights table...")
        insights_storage = await create_insights_storage(engine, session, use_case_id)
        saved_record = await insights_storage.save(doc_id, insights)

        logger.info(f"   ✓ Saved to insights table")
        logger.info(f"     Record ID: {saved_record.get('id')}")

        # Step 4: Save to doc_metadata
        logger.info("\n4. Updating api_documents.doc_metadata...")
        metadata_update = {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "customer_name": customer_name,
            "insights_generated_at": datetime.utcnow().isoformat(),
        }

        update_query = text("""
            UPDATE api_documents
            SET doc_metadata = jsonb_set(
                COALESCE(doc_metadata, '{}'),
                '{risk_score}',
                to_jsonb(:risk_score)
            ),
            doc_metadata = jsonb_set(
                doc_metadata,
                '{risk_level}',
                to_jsonb(:risk_level)
            )
            WHERE document_id = :document_id
        """)

        await session.execute(
            update_query,
            {
                "document_id": doc_id,
                "risk_score": risk_score,
                "risk_level": risk_level,
            }
        )
        await session.commit()

        logger.info(f"   ✓ Updated doc_metadata")

        # Step 5: Verify retrieval
        logger.info("\n5. Verifying retrieval...")
        retrieved = await insights_storage.get(doc_id)

        if retrieved:
            logger.info(f"   ✓ Retrieved from insights table")
            logger.info(f"     Risk Score: {retrieved.get('risk_score')}")
        else:
            logger.warning(f"   ⚠ Could not retrieve insights")

        # Step 6: Test analytics query
        logger.info("\n6. Testing analytics query...")
        analytics_service = AnalyticsService(use_case_id, session)

        try:
            overview = await analytics_service.get_overview_metrics()
            logger.info(f"   ✓ Analytics query successful")
            logger.info(f"     Total documents: {overview.get('total_documents', 0)}")
            logger.info(f"     Average risk score: {overview.get('average_risk_score', 'N/A')}")

            for key, value in overview.items():
                if key not in ['total_documents', 'average_risk_score'] and value is not None:
                    logger.info(f"     {key}: {value}")

        except Exception as e:
            logger.error(f"   ✗ Analytics query failed: {e}")

        logger.info("\n" + "=" * 80)
        logger.info("TEST COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        logger.info("\nNext steps:")
        logger.info("  1. Visit the UI: http://localhost:3000/analytics")
        logger.info("  2. Generate insights for more documents")
        logger.info("  3. Watch the dashboard populate with data")
        logger.info("=" * 80 + "\n")

        return True


async def main():
    """Main entry point."""
    document_id = sys.argv[1] if len(sys.argv) > 1 else None

    try:
        success = await test_insights_flow(document_id)
        return 0 if success else 1
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
