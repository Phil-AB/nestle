"""
Test Reducto API connectivity and extraction.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio

from modules.extraction.parser import ReductoProvider
from shared.contracts import get_schema
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


async def test_reducto_upload():
    """Test basic file upload to Reducto."""

    # Create a minimal test file
    test_content = b"Test document content"
    test_filename = "test.txt"

    async with ReductoProvider() as parser:
        logger.info(f"Testing upload to Reducto API: {parser.base_url}")

        files = {"file": (test_filename, test_content)}

        try:
            response = await parser.client.post(
                f"{parser.base_url}/upload",
                files=files
            )

            logger.info(f"Upload response status: {response.status_code}")
            logger.info(f"Upload response: {response.text}")

            if response.status_code == 200:
                file_id = response.json()["file_id"]
                logger.info(f"✅ Upload successful! File ID: {file_id}")
                return file_id
            else:
                logger.error(f"❌ Upload failed: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"❌ Upload error: {e}")
            import traceback
            traceback.print_exc()
            return None


async def test_reducto_extract():
    """Test extraction with schema."""

    # First upload a file
    file_id = await test_reducto_upload()

    if not file_id:
        logger.error("Cannot test extraction - upload failed")
        return

    # Get invoice schema
    schema = get_schema("invoice")
    logger.info(f"Using invoice schema with {len(schema)} fields")

    # Test extraction
    async with ReductoProvider() as parser:
        extract_payload = {
            "input": f"reducto://{file_id}",
            "instructions": {
                "schema": schema
            }
        }

        logger.info("Testing extraction...")

        try:
            response = await parser.client.post(
                f"{parser.base_url}/extract",
                json=extract_payload
            )

            logger.info(f"Extract response status: {response.status_code}")
            logger.info(f"Extract response: {response.text[:500]}")

            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Extraction successful!")
                logger.info(f"Result keys: {list(result.keys())}")
                return result
            else:
                logger.error(f"❌ Extraction failed: {response.status_code}")
                logger.error(f"Error details: {response.text}")
                return None

        except Exception as e:
            logger.error(f"❌ Extraction error: {e}")
            import traceback
            traceback.print_exc()
            return None


async def test_reducto_parse():
    """Test basic parse without schema."""

    # Upload file
    file_id = await test_reducto_upload()

    if not file_id:
        return

    # Test parse
    async with ReductoProvider() as parser:
        parse_payload = {
            "input": f"reducto://{file_id}"
        }

        logger.info("Testing parse...")

        try:
            response = await parser.client.post(
                f"{parser.base_url}/parse",
                json=parse_payload
            )

            logger.info(f"Parse response status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Parse successful!")
                logger.info(f"Result keys: {list(result.keys())}")
                return result
            else:
                logger.error(f"❌ Parse failed: {response.status_code}")
                logger.error(f"Error details: {response.text}")
                return None

        except Exception as e:
            logger.error(f"❌ Parse error: {e}")
            import traceback
            traceback.print_exc()
            return None


if __name__ == "__main__":
    print("\n" + "="*60)
    print("REDUCTO API DIAGNOSTIC TEST")
    print("="*60 + "\n")

    print("Test 1: Upload")
    print("-" * 60)
    asyncio.run(test_reducto_upload())

    print("\n\nTest 2: Extract with Schema")
    print("-" * 60)
    asyncio.run(test_reducto_extract())

    print("\n\nTest 3: Parse (no schema)")
    print("-" * 60)
    asyncio.run(test_reducto_parse())

    print("\n" + "="*60)
    print("TESTS COMPLETE")
    print("="*60 + "\n")
