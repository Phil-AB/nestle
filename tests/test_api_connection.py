"""
End-to-End API Connection Test Script

Tests the FastAPI backend endpoints to verify:
- API connectivity and health
- Document upload
- Document retrieval
- Document listing
- Error handling

Usage:
    python tests/test_api_connection.py
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import httpx
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class APIConnectionTest:
    """Test suite for API connectivity and endpoints"""

    def __init__(self, base_url: str = "http://localhost:8000", api_key: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key or "dev-key-12345"  # Default dev key
        self.headers = {
            "X-API-Key": self.api_key
        }
        self.test_results: Dict[str, Any] = {}

    def print_header(self, text: str):
        """Print formatted test header"""
        print(f"\n{'=' * 80}")
        print(f"  {text}")
        print(f"{'=' * 80}\n")

    def print_result(self, test_name: str, success: bool, details: str = ""):
        """Print test result"""
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status} | {test_name}")
        if details:
            print(f"       {details}")
        self.test_results[test_name] = {"success": success, "details": details}

    async def test_health_check(self, client: httpx.AsyncClient) -> bool:
        """Test API health endpoint"""
        try:
            response = await client.get(f"{self.base_url}/health")
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                details += f" | {data}"
            self.print_result("Health Check", success, details)
            return success
        except Exception as e:
            self.print_result("Health Check", False, f"Error: {str(e)}")
            return False

    async def test_api_info(self, client: httpx.AsyncClient) -> bool:
        """Test API info endpoint"""
        try:
            response = await client.get(f"{self.base_url}/api/v1")
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                details += f" | Version: {data.get('version', 'N/A')}"
            self.print_result("API Info", success, details)
            return success
        except Exception as e:
            self.print_result("API Info", False, f"Error: {str(e)}")
            return False

    async def test_list_documents_empty(self, client: httpx.AsyncClient) -> bool:
        """Test listing documents (should be empty or return existing)"""
        try:
            response = await client.get(
                f"{self.base_url}/api/v1/documents/",
                headers=self.headers
            )
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                count = len(data.get('data', []))
                details += f" | Documents found: {count}"
            self.print_result("List Documents", success, details)
            return success
        except Exception as e:
            self.print_result("List Documents", False, f"Error: {str(e)}")
            return False

    async def test_upload_document(self, client: httpx.AsyncClient) -> Optional[str]:
        """Test document upload"""
        try:
            # Create a test PDF file
            test_file_path = project_root / "tests" / "test_document.pdf"

            if not test_file_path.exists():
                # Create a minimal PDF for testing
                test_content = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
                test_file_path.parent.mkdir(exist_ok=True)
                test_file_path.write_bytes(test_content)

            with open(test_file_path, "rb") as f:
                files = {"file": ("test_invoice.pdf", f, "application/pdf")}
                data = {"document_type": "commercial_invoice"}

                response = await client.post(
                    f"{self.base_url}/api/v1/documents/upload",
                    headers=self.headers,
                    files=files,
                    data=data
                )

            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            document_id = None

            if success:
                result = response.json()
                document_id = result.get('document_id')
                details += f" | Document ID: {document_id}"
            else:
                details += f" | Error: {response.text}"

            self.print_result("Upload Document", success, details)
            return document_id if success else None

        except Exception as e:
            self.print_result("Upload Document", False, f"Error: {str(e)}")
            return None

    async def test_get_document(self, client: httpx.AsyncClient, document_id: str) -> bool:
        """Test retrieving a specific document"""
        try:
            response = await client.get(
                f"{self.base_url}/api/v1/documents/{document_id}",
                headers=self.headers
            )
            success = response.status_code == 200
            details = f"Status: {response.status_code}"

            if success:
                data = response.json()
                doc_type = data.get('document_type', 'N/A')
                status = data.get('extraction_status', 'N/A')
                details += f" | Type: {doc_type} | Status: {status}"
            else:
                details += f" | Error: {response.text}"

            self.print_result("Get Document", success, details)
            return success

        except Exception as e:
            self.print_result("Get Document", False, f"Error: {str(e)}")
            return False

    async def test_authentication_required(self, client: httpx.AsyncClient) -> bool:
        """Test that authentication is required (request without API key should fail)"""
        try:
            response = await client.get(f"{self.base_url}/api/v1/documents/")
            # Should fail with 401 or 403
            success = response.status_code in [401, 403]
            details = f"Status: {response.status_code} (expected 401/403)"
            self.print_result("Authentication Required", success, details)
            return success
        except Exception as e:
            self.print_result("Authentication Required", False, f"Error: {str(e)}")
            return False

    async def test_invalid_api_key(self, client: httpx.AsyncClient) -> bool:
        """Test that invalid API key is rejected"""
        try:
            invalid_headers = {"X-API-Key": "invalid-key-12345"}
            response = await client.get(
                f"{self.base_url}/api/v1/documents/",
                headers=invalid_headers
            )
            # Should fail with 403
            success = response.status_code == 403
            details = f"Status: {response.status_code} (expected 403)"
            self.print_result("Invalid API Key Rejected", success, details)
            return success
        except Exception as e:
            self.print_result("Invalid API Key Rejected", False, f"Error: {str(e)}")
            return False

    async def run_all_tests(self):
        """Run all API tests"""
        self.print_header("API Connection Test Suite")
        print(f"Base URL: {self.base_url}")
        print(f"API Key: {self.api_key[:10]}..." if len(self.api_key) > 10 else self.api_key)
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Basic connectivity
            self.print_header("Basic Connectivity Tests")
            await self.test_health_check(client)
            await self.test_api_info(client)

            # Authentication tests
            self.print_header("Authentication Tests")
            await self.test_authentication_required(client)
            await self.test_invalid_api_key(client)

            # Document operations
            self.print_header("Document Operations Tests")
            await self.test_list_documents_empty(client)

            # Upload and retrieve
            document_id = await self.test_upload_document(client)
            if document_id:
                await self.test_get_document(client, document_id)

        # Summary
        self.print_summary()

    def print_summary(self):
        """Print test summary"""
        self.print_header("Test Summary")

        total = len(self.test_results)
        passed = sum(1 for r in self.test_results.values() if r['success'])
        failed = total - passed

        print(f"Total Tests: {total}")
        print(f"Passed: {passed} ✓")
        print(f"Failed: {failed} ✗")
        print(f"Success Rate: {(passed/total*100):.1f}%")

        if failed > 0:
            print(f"\nFailed Tests:")
            for name, result in self.test_results.items():
                if not result['success']:
                    print(f"  - {name}: {result['details']}")

        print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'=' * 80}\n")

        # Exit code
        sys.exit(0 if failed == 0 else 1)


async def main():
    """Main test runner"""
    import argparse

    parser = argparse.ArgumentParser(description='Test API connectivity')
    parser.add_argument('--url', default='http://localhost:8000', help='API base URL')
    parser.add_argument('--api-key', default='dev-key-12345', help='API key for authentication')

    args = parser.parse_args()

    tester = APIConnectionTest(base_url=args.url, api_key=args.api_key)
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
