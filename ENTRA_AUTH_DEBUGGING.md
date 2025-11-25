# Entra ID Authentication Debugging Guide

## Enable Debug Logging

Set in your environment or `.env` file:
```env
DEBUG_RAG_API=true
USE_ENTRA_AUTH=true
AZURE_PG_USERNAME_OVERRIDE=your-username-here
```

## What to Look For in Logs

### 1. **Initialization (from config.py)**
```
INFO: Using Azure Entra ID authentication for asyncpg connection
```

### 2. **Vector Store Connection (from extended_pg_vector.py)**
Look for this sequence:
```
ENTRA AUTH: get_entra_connection_string_if_enabled called
ENTRA AUTH: Entra auth is enabled, creating authenticated connection string
ENTRA AUTH: Creating EntraIDAuthHelper instance
```

### 3. **Token Acquisition**
```
ENTRA AUTH: Requesting access token for Azure PostgreSQL
ENTRA AUTH: Using scope: https://ossrdbms-aad.database.windows.net/.default
ENTRA AUTH: Successfully obtained token (length: XXXX chars)
```

**If this fails**, you'll see:
```
ENTRA AUTH: Failed to obtain access token: [error details]
```

### 4. **Username Resolution**
```
ENTRA AUTH: Checking AZURE_PG_USERNAME_OVERRIDE env var: [value or NOT SET]
ENTRA AUTH: Using overridden username from environment: [username]
```

**If override is NOT SET**, you'll see:
```
ENTRA AUTH: No username override, attempting to extract from token
ENTRA AUTH: Token claims: ['aud', 'iss', 'iat', 'nbf', 'exp', ...]
ENTRA AUTH: Extracted username from token: [username]
```

### 5. **Connection String Creation**
```
ENTRA AUTH: Creating connection string for host:port/database
ENTRA AUTH: Building connection string with username: [username]
ENTRA AUTH: Encoded username: [encoded-username]
ENTRA AUTH: Successfully created connection string for host/database with username [username]
```

## Common Issues and Their Signatures

### Issue 1: Environment Variable Not Set
```
ENTRA AUTH: Checking AZURE_PG_USERNAME_OVERRIDE env var: NOT SET
ENTRA AUTH: No username override, attempting to extract from token
ENTRA AUTH: Could not find username in token claims. Available claims: [...]
ENTRA AUTH: Could not extract username from token, using fallback: entra_user
```
**Fix**: Set `AZURE_PG_USERNAME_OVERRIDE=your-pg-username` in your cloud environment

### Issue 2: Token Acquisition Fails
```
ENTRA AUTH: Failed to obtain access token: [Azure credential error]
```
**Fix**: Check Managed Identity configuration and permissions

### Issue 3: Wrong Username
```
ENTRA AUTH: Building connection string with username: wrong-username
```
Then later:
```
password authentication failed for user "wrong-username"
```
**Fix**: Verify the username in PostgreSQL matches `AZURE_PG_USERNAME_OVERRIDE`

### Issue 4: Token Not Being Used (SQLAlchemy)
If you don't see any "ENTRA AUTH" logs related to SQLAlchemy, it means `get_entra_connection_string_if_enabled()` is not being called.

Check:
1. Is `USE_ENTRA_AUTH=true` set?
2. Is the vector store being initialized correctly?

### Issue 5: Managed Identity Not Authorized
```
ENTRA AUTH: Successfully obtained token (length: XXXX chars)
```
But later:
```
password authentication failed for user "your-username"
```

This means the token is obtained but PostgreSQL rejects it. **Fix**:
1. Ensure the Managed Identity is added as a PostgreSQL user
2. Grant necessary permissions to the Managed Identity in PostgreSQL

## PostgreSQL User Setup for Managed Identity

In Azure PostgreSQL, you need to create a user for your Managed Identity:

```sql
-- Connect as admin
SET aad_validate_oids_in_tenant = off;

-- Create user for Managed Identity or Entra ID group
-- Use the exact name that appears in your override or token claims
CREATE ROLE "your-username-here" WITH LOGIN IN ROLE azure_ad_user;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE "your-database" TO "your-username-here";
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "your-username-here";
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "your-username-here";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO "your-username-here";
```

## Testing Locally vs Cloud

### Local (Azure CLI)
1. Run `az login`
2. Start application
3. Should see: Token obtained via Azure CLI credential

### Cloud (Managed Identity)
1. Ensure Managed Identity is assigned to the resource
2. Ensure `AZURE_PG_USERNAME_OVERRIDE` is set in environment
3. Start application
4. Should see: Token obtained via Managed Identity credential

## Quick Checklist

- [ ] `DEBUG_RAG_API=true` set in environment (enables DEBUG logging)
- [ ] `USE_ENTRA_AUTH=true` set in environment
- [ ] `AZURE_PG_USERNAME_OVERRIDE` set to correct PostgreSQL username
- [ ] Managed Identity has access to PostgreSQL scope
- [ ] PostgreSQL user exists for the Managed Identity/username
- [ ] PostgreSQL user has necessary permissions
- [ ] Application logs show "ENTRA AUTH: Successfully obtained token"
- [ ] Application logs show correct username being used
- [ ] No "Falling back to original connection string" warnings
