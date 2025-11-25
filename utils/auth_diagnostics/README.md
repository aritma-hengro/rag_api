# Authentication Diagnostic Tools

This directory contains utilities for testing and diagnosing authentication mechanisms.

## Scripts

### generate_test_token.py
Generates JWT tokens for testing API authentication with shared secrets.

**Usage:**
```bash
# Use JWT_SECRET from .env
python utils/auth_diagnostics/generate_test_token.py

# Custom username
python utils/auth_diagnostics/generate_test_token.py testuser@example.com

# Custom username and secret
python utils/auth_diagnostics/generate_test_token.py testuser@example.com my-secret-key
```

**Features:**
- Generates HS256 signed JWT tokens
- Supports custom claims and expiration
- Provides curl and Python usage examples
- Validates generated tokens

### test_azure_token.py
Comprehensive diagnostic tool for Azure Entra ID token issues.

**Usage:**
```bash
python utils/auth_diagnostics/test_azure_token.py
```

**Features:**
- Tests DefaultAzureCredential token acquisition
- Decodes and analyzes JWT structure
- Tests both standard and URL-safe base64 decoding
- Validates token claims and username extraction
- Provides troubleshooting recommendations

**Prerequisites:**
- `azure-identity` package installed
- Azure CLI authenticated (`az login`) or other credential source configured

## When to Use

- **generate_test_token.py**: Testing API endpoints that require JWT authentication
- **test_azure_token.py**: Diagnosing Azure Entra ID authentication issues with PostgreSQL

## Notes

These scripts are for development and testing purposes only. Do not use in production environments.
