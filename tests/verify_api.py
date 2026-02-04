"""
Quick API Verification Script

Simple script to verify the API is running and accessible.

Usage:
    python tests/verify_api.py
    python tests/verify_api.py --url http://localhost:8000 --api-key your-key
"""

import requests
import sys


def test_api(base_url: str = "http://localhost:8000", api_key: str = "dev-key-12345") -> bool:
    """Quick check if API is running and accessible"""

    print("=" * 60)
    print("  API Quick Verification")
    print("=" * 60)
    print(f"\nBase URL: {base_url}")
    print(f"API Key: {api_key}\n")

    # Test 1: Health check
    print("1. Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("   ✓ Health check passed")
            print(f"   Response: {response.json()}")
        else:
            print(f"   ✗ Health check failed (Status: {response.status_code})")
            return False
    except requests.exceptions.ConnectionError:
        print(f"   ✗ Cannot connect to API at {base_url}")
        print("   Make sure the API server is running:")
        print("   > cd src/api && uvicorn main:app --reload")
        return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

    # Test 2: API info
    print("\n2. Testing API info endpoint...")
    try:
        response = requests.get(f"{base_url}/api/v1", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("   ✓ API info endpoint accessible")
            print(f"   Title: {data.get('title')}")
            print(f"   Version: {data.get('version')}")
        else:
            print(f"   ✗ API info failed (Status: {response.status_code})")
            return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

    # Test 3: Authentication
    print("\n3. Testing authentication...")
    try:
        headers = {"X-API-Key": api_key}
        response = requests.get(
            f"{base_url}/api/v1/documents/",
            headers=headers,
            timeout=5
        )
        if response.status_code == 200:
            print("   ✓ Authentication successful")
            data = response.json()
            doc_count = len(data.get('data', []))
            print(f"   Documents in system: {doc_count}")
        elif response.status_code in [401, 403]:
            print(f"   ✗ Authentication failed (Status: {response.status_code})")
            print(f"   Check your API key in config/api_config.yaml")
            return False
        else:
            print(f"   ⚠ Unexpected status: {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

    # Success
    print("\n" + "=" * 60)
    print("  ✓ All checks passed! API is ready.")
    print("=" * 60)
    print("\nNext steps:")
    print("  - Start the Next.js UI: cd src/ui && npm run dev")
    print("  - Access UI at: http://localhost:3000")
    print("  - Run full tests: python tests/test_api_connection.py")
    print()

    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Quick API verification')
    parser.add_argument('--url', default='http://localhost:8000', help='API base URL')
    parser.add_argument('--api-key', default='dev-key-12345', help='API key')

    args = parser.parse_args()

    success = test_api(base_url=args.url, api_key=args.api_key)
    sys.exit(0 if success else 1)
