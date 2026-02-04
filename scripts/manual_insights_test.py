#!/usr/bin/env python3
"""
Manual Insights Generation Test.

Manually generates insights for a document and saves to database.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from src.database.connection import get_session, get_engine
from modules.insights import InsightsService
from modules.insights.storage.integration import create_insights_storage
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


async def test_manual_generation():
    """Test manual insights generation and save."""
    use_case_id = "forms-capital-loan"
    engine = get_engine()

    async with get_session() as session:
        # Get first document
        result = await session.execute(
            text("SELECT document_id, fields FROM api_documents WHERE extraction_status = 'complete' LIMIT 1")
        )
        row = result.fetchone()

        if not row:
            print("No documents found")
            return

        doc_id = row[0]
        fields = row[1]

        print(f"Testing with document: {doc_id}")
        print(f"Fields count: {len(fields) if fields else 0}")

        # Generate insights WITHOUT LLM (rule-based only for testing)
        print("\nGenerating rule-based insights...")
        service = InsightsService(use_case_id)

        # Patch the LLM methods to skip them
        service.llm_reasoning.generate_risk_reasoning = lambda **kwargs: kwargs['risk_assessment']
        service.llm_reasoning.generate_recommendations = lambda **kwargs: "Test recommendations"

        insights = service.generate_insights(fields)

        print(f"✓ Generated insights:")
        print(f"  Risk Score: {insights['risk_assessment']['risk_score']}")
        print(f"  Risk Level: {insights['risk_assessment']['risk_level']}")

        # Save to database
        print("\nSaving to database...")
        storage = await create_insights_storage(engine, session, use_case_id)
        saved = await storage.save(doc_id, insights)

        print(f"✓ Saved to database:")
        print(f"  Record ID: {saved.get('id')}")

        # Verify
        print("\nVerifying...")
        retrieved = await storage.get(doc_id)
        if retrieved:
            print(f"✓ Successfully retrieved from database")
            print(f"  Risk Score: {retrieved.get('risk_score')}")
        else:
            print("✗ Failed to retrieve")

        # Count total
        count = await storage.repository.count()
        print(f"\nTotal insights records: {count}")


if __name__ == "__main__":
    asyncio.run(test_manual_generation())
