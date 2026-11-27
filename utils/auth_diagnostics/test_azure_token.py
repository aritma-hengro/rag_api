"""
Comprehensive test script to diagnose Azure DefaultAzureCredential token issues.

This script will:
1. Test DefaultAzureCredential token acquisition
2. Decode and analyze the JWT token structure
3. Test both standard and URL-safe base64 decoding
4. Validate token content and claims
5. Test the token with langchain-azure-postgresql's parsing logic
"""
import os
import sys
import base64
import json
from datetime import datetime

print("=" * 80)
print("Azure DefaultAzureCredential Token Diagnostic Tool")
print("=" * 80)
print()

# Step 1: Import azure-identity
print("Step 1: Importing azure-identity...")
try:
    from azure.identity import DefaultAzureCredential
    print("[OK] azure-identity imported successfully")
except ImportError as e:
    print(f"[ERROR] Failed to import azure-identity: {e}")
    print("Install with: pip install azure-identity")
    sys.exit(1)

print()

# Step 2: Acquire token
print("Step 2: Acquiring token for Azure PostgreSQL...")
print("Resource: https://ossrdbms-aad.database.windows.net/.default")
print()

try:
    credential = DefaultAzureCredential()
    token_obj = credential.get_token("https://ossrdbms-aad.database.windows.net/.default")
    token = token_obj.token
    print(f"[OK] Token acquired successfully")
    print(f"  Token length: {len(token)} characters")
    print(f"  Token expires: {datetime.fromtimestamp(token_obj.expires_on)}")
    print(f"  Credential type used: {type(credential).__name__}")
    print()
except Exception as e:
    print(f"[ERROR] Failed to acquire token: {e}")
    print("\nTroubleshooting:")
    print("  1. Run 'az login' to authenticate with Azure CLI")
    print("  2. Ensure you have access to Azure PostgreSQL")
    print("  3. Check that you're logged into the correct Azure tenant")
    sys.exit(1)

# Step 3: Analyze token structure
print("=" * 80)
print("Step 3: Analyzing JWT Token Structure")
print("=" * 80)
print()

parts = token.split('.')
print(f"Token parts: {len(parts)} (expected: 3 for JWT)")

if len(parts) != 3:
    print(f"[ERROR] Invalid JWT structure. Expected 3 parts, got {len(parts)}")
    sys.exit(1)

header_b64, body_b64, signature_b64 = parts

print(f"  Header length: {len(header_b64)} characters")
print(f"  Body length: {len(body_b64)} characters")
print(f"  Signature length: {len(signature_b64)} characters")
print()

# Step 4: Decode header
print("Step 4: Decoding JWT Header")
print("-" * 80)

def try_decode(data, method_name, decode_func):
    """Helper to try decoding with different methods."""
    try:
        # Add padding if needed
        padded = data + "=" * (4 - len(data) % 4)
        decoded_bytes = decode_func(padded)
        decoded_str = decoded_bytes.decode("utf-8")
        decoded_json = json.loads(decoded_str)
        print(f"[SUCCESS] {method_name}")
        return decoded_json
    except Exception as e:
        print(f"[FAILED] {method_name}: {type(e).__name__}: {e}")
        return None

# Try header decoding
header_std = try_decode(header_b64, "Standard base64.b64decode", base64.b64decode)
if not header_std:
    header_url = try_decode(header_b64, "URL-safe base64.urlsafe_b64decode", base64.urlsafe_b64decode)
    header = header_url
else:
    header = header_std

if header:
    print(f"\nHeader content:")
    print(json.dumps(header, indent=2))
else:
    print("[ERROR] Could not decode header with any method")

print()

# Step 5: Decode body (the critical part)
print("Step 5: Decoding JWT Body (Claims)")
print("-" * 80)

body_std = try_decode(body_b64, "Standard base64.b64decode", base64.b64decode)
if not body_std:
    body_url = try_decode(body_b64, "URL-safe base64.urlsafe_b64decode", base64.urlsafe_b64decode)
    body = body_url
else:
    body = body_std

print()

if body:
    print("Body decoded successfully!")
    print()
    print("Important claims:")
    print(f"  upn (User Principal Name): {body.get('upn', 'NOT FOUND')}")
    print(f"  unique_name: {body.get('unique_name', 'NOT FOUND')}")
    print(f"  oid (Object ID): {body.get('oid', 'NOT FOUND')}")
    print(f"  email: {body.get('email', 'NOT FOUND')}")
    print(f"  preferred_username: {body.get('preferred_username', 'NOT FOUND')}")
    print()
    print(f"All claims in token ({len(body)} total):")
    for key in sorted(body.keys()):
        value = body[key]
        if isinstance(value, (list, dict)):
            print(f"  {key}: {type(value).__name__} with {len(value)} items")
        else:
            value_str = str(value)
            if len(value_str) > 60:
                value_str = value_str[:60] + "..."
            print(f"  {key}: {value_str}")
else:
    print("[ERROR] Could not decode body with any method")
    print()
    print("Detailed analysis of body encoding:")
    print(f"  Body base64 (first 100 chars): {body_b64[:100]}")
    print(f"  Body padding needed: {4 - len(body_b64) % 4}")

    # Check for special characters
    has_hyphen = '-' in body_b64
    has_underscore = '_' in body_b64
    has_plus = '+' in body_b64
    has_slash = '/' in body_b64

    print(f"  Contains '-' (URL-safe): {has_hyphen}")
    print(f"  Contains '_' (URL-safe): {has_underscore}")
    print(f"  Contains '+' (standard): {has_plus}")
    print(f"  Contains '/' (standard): {has_slash}")

    if has_hyphen or has_underscore:
        print("\n  Analysis: Token uses URL-safe base64 encoding")
    elif has_plus or has_slash:
        print("\n  Analysis: Token uses standard base64 encoding")

print()

# Step 6: Test with langchain-azure-postgresql logic
print("=" * 80)
print("Step 6: Testing with langchain-azure-postgresql's parsing logic")
print("=" * 80)
print()

try:
    from langchain_azure_postgresql.common._shared import get_username_password, AccessToken

    print("Importing get_username_password function...")

    # Check the function source
    import inspect
    source = inspect.getsource(get_username_password)

    print("\nFunction uses:")
    if "urlsafe_b64decode" in source:
        print("  - URL-safe base64 decoding (urlsafe_b64decode)")
    elif "b64decode" in source:
        print("  - Standard base64 decoding (b64decode)")
    else:
        print("  - Unknown decoding method")

    print("\nAttempting to parse token with library function...")

    # Create AccessToken object
    access_token = AccessToken(token=token, expires_on=token_obj.expires_on)

    try:
        username, password = get_username_password(access_token)
        print(f"[SUCCESS] Token parsed successfully!")
        print(f"  Username: {username}")
        print(f"  Password (token) length: {len(password)} characters")
    except Exception as e:
        print(f"[FAILED] Library parsing failed: {type(e).__name__}")
        print(f"  Error: {e}")
        print()
        print("Root cause analysis:")

        if "Incorrect padding" in str(e):
            print("  Issue: Base64 padding error")
            print("  Likely cause: Mismatch between URL-safe and standard base64 encoding")
            if body:
                print(f"  Token body CAN be decoded with URL-safe base64")
                print(f"  But library is using standard base64.b64decode()")
                print()
                print("  SOLUTION: Library needs to use base64.urlsafe_b64decode()")
            else:
                print(f"  Token body CANNOT be decoded with either method")
                print("  This suggests a malformed or corrupted token")
        elif "User name not found" in str(e):
            print("  Issue: Username claim missing from token")
            print(f"  Token has 'upn': {body.get('upn') if body else 'unknown'}")
            print(f"  Token has 'unique_name': {body.get('unique_name') if body else 'unknown'}")
        else:
            print(f"  Unexpected error: {e}")

except ImportError as e:
    print(f"[SKIPPED] langchain-azure-postgresql not available: {e}")

print()

# Step 7: Summary and recommendations
print("=" * 80)
print("Summary and Recommendations")
print("=" * 80)
print()

if body:
    username = body.get('upn') or body.get('unique_name')
    if username:
        print("[DIAGNOSIS] Token is valid and contains username")
        print(f"  Username: {username}")
        print()
        print("Issue: langchain-azure-postgresql uses wrong base64 decoder")
        print()
        print("Solutions:")
        print("  1. Patch the library to use base64.urlsafe_b64decode()")
        print("  2. Report issue to langchain-azure-postgresql maintainers")
        print("  3. Use basic auth (username/password) instead of Entra ID")
    else:
        print("[DIAGNOSIS] Token is valid but missing username claims")
        print()
        print("Missing claims:")
        print("  - upn (User Principal Name)")
        print("  - unique_name")
        print()
        print("Solutions:")
        print("  1. Check Azure AD user configuration")
        print("  2. Ensure user has proper claims in the token")
        print("  3. Contact Azure administrator")
else:
    print("[DIAGNOSIS] Token cannot be decoded")
    print()
    print("Possible causes:")
    print("  1. Token is malformed or corrupted")
    print("  2. Token uses non-standard encoding")
    print("  3. Azure CLI or identity service issue")
    print()
    print("Solutions:")
    print("  1. Run 'az logout' then 'az login' to refresh credentials")
    print("  2. Update azure-identity package: pip install --upgrade azure-identity")
    print("  3. Use basic auth (username/password) instead")

print()
print("=" * 80)
print("End of diagnostic")
print("=" * 80)
