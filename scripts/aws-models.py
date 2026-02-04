#!/usr/bin/env python3
"""
AWS Bedrock Model Listing Script.

Lists all available models in AWS Bedrock using credentials from .env file.
"""

import boto3
import requests
import json
import os
import sys
from pathlib import Path
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# --- CONFIGURATION FROM .env ---
REGION = os.getenv("AWS_REGION", "us-east-1")
ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN")  # Required if using temporary credentials
BEARER_TOKEN = os.getenv("AWS_BEARER_TOKEN_BEDROCK")  # The 'ABSK...' token from Bedrock console

# Validate required credentials
if not ACCESS_KEY or not SECRET_KEY:
    print("❌ Error: AWS credentials not found in .env file!")
    print("Required environment variables:")
    print("  - AWS_ACCESS_KEY_ID")
    print("  - AWS_SECRET_ACCESS_KEY")
    print("  - AWS_SESSION_TOKEN (if using temporary credentials)")
    print("  - AWS_REGION (optional, defaults to us-east-1)")
    sys.exit(1)

def list_all_models():
    """List all available foundation models in AWS Bedrock."""
    print("=" * 80)
    print(f"AWS Bedrock Models - Region: {REGION}")
    print("=" * 80)

    try:
        session = boto3.Session(
            aws_access_key_id=ACCESS_KEY,
            aws_secret_access_key=SECRET_KEY,
            aws_session_token=SESSION_TOKEN,
            region_name=REGION
        )
        bedrock = session.client(service_name='bedrock')

        # List all foundation models
        response = bedrock.list_foundation_models()
        models = response.get('modelSummaries', [])

        print(f"\n✅ Successfully connected! Found {len(models)} models.\n")

        # Group models by provider
        models_by_provider = {}
        for model in models:
            provider = model.get('providerName', 'Unknown')
            if provider not in models_by_provider:
                models_by_provider[provider] = []
            models_by_provider[provider].append(model)

        # Display models grouped by provider
        for provider in sorted(models_by_provider.keys()):
            print(f"\n{'─' * 80}")
            print(f"📦 {provider}")
            print(f"{'─' * 80}")

            for model in sorted(models_by_provider[provider], key=lambda x: x.get('modelName', '')):
                model_id = model.get('modelId', 'N/A')
                model_name = model.get('modelName', 'N/A')
                input_modalities = ', '.join(model.get('inputModalities', []))
                output_modalities = ', '.join(model.get('outputModalities', []))

                print(f"  • {model_name}")
                print(f"    ID: {model_id}")
                print(f"    Input:  {input_modalities}")
                print(f"    Output: {output_modalities}")
                print()

        # Show Claude models specifically
        print(f"\n{'=' * 80}")
        print("🎯 ANTHROPIC CLAUDE MODELS (Recommended)")
        print(f"{'=' * 80}\n")

        claude_models = [m for m in models if 'anthropic' in m.get('providerName', '').lower()]
        for model in sorted(claude_models, key=lambda x: x.get('modelId', '')):
            model_id = model.get('modelId')
            model_name = model.get('modelName')
            print(f"  ✓ {model_name}")
            print(f"    {model_id}")
            print()

        return models

    except ClientError as e:
        print(f"❌ AWS Error: {e}")
        return []
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        return []

def test_model_access(model_id: str = None):
    """Test if you have access to invoke a specific model."""
    if not model_id:
        # Try the model from .env or default to Claude
        model_id = os.getenv("AWS_BEDROCK_MODEL", "anthropic.claude-3-sonnet-20240229-v1:0")

    print(f"\n{'=' * 80}")
    print(f"🧪 Testing Model Access: {model_id}")
    print(f"{'=' * 80}\n")

    try:
        session = boto3.Session(
            aws_access_key_id=ACCESS_KEY,
            aws_secret_access_key=SECRET_KEY,
            aws_session_token=SESSION_TOKEN,
            region_name=REGION
        )
        runtime = session.client(service_name='bedrock-runtime')

        # Test invoke
        test_payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "Hi"}]
        }

        response = runtime.invoke_model(
            modelId=model_id,
            body=json.dumps(test_payload)
        )

        print(f"✅ SUCCESS! You have access to: {model_id}")
        print(f"   Response received successfully.")
        return True

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if "AccessDeniedException" in str(e):
            print(f"❌ ACCESS DENIED for {model_id}")
            print(f"   You need to enable this model in the AWS Bedrock Console.")
            print(f"   Go to: https://console.aws.amazon.com/bedrock/home?region={REGION}#/modelaccess")
        elif "ValidationException" in str(e):
            print(f"⚠️  Model exists but validation failed (likely wrong payload format)")
            print(f"   This still confirms the model is accessible.")
        else:
            print(f"❌ Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        return False


def check_access_via_bearer():
    """Checks model access using Bearer Token / API Key method."""
    if not BEARER_TOKEN:
        return

    print(f"\n{'=' * 80}")
    print("🔑 Testing Bearer Token Access")
    print(f"{'=' * 80}\n")

    model_id = os.getenv("AWS_BEDROCK_MODEL", "anthropic.claude-3-sonnet-20240229-v1:0")
    url = f"https://bedrock-runtime.{REGION}.amazonaws.com/model/{model_id}/invoke"

    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 10,
        "messages": [{"role": "user", "content": "Hi"}]
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            print(f"✅ Bearer Token is VALID and has active model access.")
        elif response.status_code == 403:
            print(f"❌ Bearer Token REJECTED (403). Check if expired or lacks permissions.")
        else:
            print(f"⚠️  Status {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"❌ HTTP Request Failed: {e}")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("AWS BEDROCK MODEL CHECKER")
    print("=" * 80)
    print(f"Loaded credentials from: {env_path}")
    print(f"Region: {REGION}")
    print("=" * 80 + "\n")

    # List all available models
    models = list_all_models()

    # Test access to your configured model
    if models:
        test_model_access()

    # Test bearer token if available
    if BEARER_TOKEN:
        check_access_via_bearer()

    print("\n" + "=" * 80)
    print("✅ Done!")
    print("=" * 80 + "\n")