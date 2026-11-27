#!/usr/bin/env python3
"""
JWT Token Generator for API Testing

This script generates JWT tokens signed with a shared secret for testing
your RAG API authentication.

Usage:
    python generate_test_token.py [username] [secret]

Examples:
    python generate_test_token.py                           # Uses defaults (JWT_SECRET from .env if available)
    python generate_test_token.py testuser                  # Custom username, JWT_SECRET from .env
    python generate_test_token.py testuser my-secret-key    # Custom username and secret
"""

import sys
import os
import json
from datetime import datetime, timedelta

try:
    import jwt
except ImportError:
    print("Error: PyJWT library not found.")
    print("Install it with: pip install PyJWT")
    sys.exit(1)

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not available, will use system environment variables only


def generate_token(username="testuser@example.com", secret="your-secret-key-here"):
    """
    Generate a JWT token for testing.

    Args:
        username: The username/email to include in the token
        secret: The secret key to sign the token with

    Returns:
        A signed JWT token string
    """
    # Current time
    now = datetime.utcnow()

    # Token payload - customize as needed for your API
    payload = {
        # Standard JWT claims
        "sub": username,           # Subject (user identifier)
        "iss": "test-jwt-generator",  # Issuer
        "iat": now,                # Issued at
        "exp": now + timedelta(hours=24),  # Expires in 24 hours

        # Custom claims - add any claims your API expects
        "id": username,            # ID claim (same as username)
        "username": username,
        "email": username,
        "roles": ["user", "admin"],

        # Optional: Add more claims as needed by your API
        # "aud": "rag-api",      # Audience (not required by this API)
        # "scope": "read write",
        # "tenant_id": "test-tenant",
    }

    # Sign the token
    token = jwt.encode(payload, secret, algorithm="HS256")

    return token, payload


def main():
    # Parse command line arguments
    args = sys.argv[1:]
    username = args[0] if len(args) > 0 else "testuser@example.com"

    # Use JWT_SECRET from environment if available, otherwise use command line arg or default
    if len(args) > 1:
        # Explicit secret provided via command line
        secret = args[1]
        secret_source = "command line"
    elif os.getenv("JWT_SECRET"):
        # Use JWT_SECRET from .env or environment
        secret = os.getenv("JWT_SECRET")
        secret_source = "JWT_SECRET environment variable"
    else:
        # Fall back to default
        secret = "your-secret-key-here"
        secret_source = "default"

    try:
        # Generate the token
        token, payload = generate_token(username, secret)

        # Display results
        print("\n" + "=" * 80)
        print("JWT Token Generated Successfully")
        print("=" * 80)
        print("\nToken Details:")
        print(f"  Username:  {username}")
        print(f"  Secret:    {secret}")
        print(f"  Source:    {secret_source}")
        print(f"  Algorithm: HS256")
        print(f"  Issued:    {payload['iat'].isoformat()}Z")
        print(f"  Expires:   {payload['exp'].isoformat()}Z")
        print("\nToken:")
        print(token)
        print("\nDecoded Payload:")
        # Convert datetime objects to ISO format for JSON serialization
        payload_json = payload.copy()
        payload_json['iat'] = payload['iat'].isoformat() + 'Z'
        payload_json['exp'] = payload['exp'].isoformat() + 'Z'
        print(json.dumps(payload_json, indent=2))
        print("\nTo use this token, add it to your request headers:")
        print(f"  Authorization: Bearer {token}")
        print("\nCurl Example:")
        print(f'  curl -H "Authorization: Bearer {token}" http://localhost:8000/health')
        print("\nPython Example:")
        print(f'''  import requests
  headers = {{"Authorization": "Bearer {token}"}}
  response = requests.get("http://localhost:8000/health", headers=headers)
  print(response.json())''')
        print("\n" + "=" * 80 + "\n")

        # Verify the token (sanity check)
        decoded = jwt.decode(token, secret, algorithms=["HS256"])
        print("[OK] Token verified successfully\n")

    except Exception as e:
        print(f"\n[ERROR] Error generating token: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
