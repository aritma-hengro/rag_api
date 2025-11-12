# FORCE_AZURE_PGVECTOR Environment Variable

## Overview

The `FORCE_AZURE_PGVECTOR` environment variable allows you to force the application to use Azure PostgreSQL vector store exclusively, regardless of what mode is specified in the configuration.

This is particularly useful when:
- You have incompatible dependencies (e.g., `langchain-postgres` not installed)
- You want to ensure Azure PostgreSQL is always used in production
- You're migrating from other vector stores to Azure PostgreSQL

## Usage

### Setting the Environment Variable

Set `FORCE_AZURE_PGVECTOR` to any of these values to enable it:
- `true`
- `1`
- `yes`

Any other value (including empty string) will disable the override.

### Examples

**Linux/Mac:**
```bash
export FORCE_AZURE_PGVECTOR=true
uvicorn app.main:app --reload
```

**Windows (CMD):**
```cmd
set FORCE_AZURE_PGVECTOR=true
uvicorn app.main:app --reload
```

**Windows (PowerShell):**
```powershell
$env:FORCE_AZURE_PGVECTOR="true"
uvicorn app.main:app --reload
```

**Docker:**
```dockerfile
ENV FORCE_AZURE_PGVECTOR=true
```

**Docker Compose:**
```yaml
services:
  api:
    environment:
      - FORCE_AZURE_PGVECTOR=true
```

**.env File:**
```bash
FORCE_AZURE_PGVECTOR=true
```

## How It Works

When `FORCE_AZURE_PGVECTOR` is enabled:

1. The factory function checks for the environment variable **before** processing the `mode` parameter
2. If set to a truthy value, it immediately returns an `AzPgVector` instance
3. All other mode parameters (`sync`, `async`, `atlas-mongo`) are ignored
4. This allows the application to work even when `langchain-postgres` or other dependencies are not installed

## Code Example

```python
from app.services.vector_store.factory import get_vector_store
from langchain_openai import OpenAIEmbeddings

# This will use Azure PostgreSQL even though mode="sync" is specified
# (if FORCE_AZURE_PGVECTOR=true is set)
vector_store = get_vector_store(
    connection_string="postgresql://user:pass@host:5432/db",
    embeddings=OpenAIEmbeddings(),
    collection_name="documents",
    mode="sync",  # This will be ignored
    create_extension=False
)

# vector_store will be an AzPgVector instance
```

## Behavior Matrix

| FORCE_AZURE_PGVECTOR | mode requested | Result | Notes |
|---------------------|----------------|---------|-------|
| `true` | `sync` | Azure PGVector | Override active |
| `true` | `async` | Azure PGVector | Override active |
| `true` | `azurepsql` | Azure PGVector | Would use Azure anyway |
| `true` | `atlas-mongo` | Azure PGVector | Override active |
| `false` / unset | `sync` | ExtendedPgVector | Normal behavior (requires langchain-postgres) |
| `false` / unset | `async` | AsyncPgVector | Normal behavior (requires langchain-postgres) |
| `false` / unset | `azurepsql` | Azure PGVector | Normal behavior |
| `false` / unset | `atlas-mongo` | AtlasMongoVector | Normal behavior (requires pymongo) |

## Error Handling

### When FORCE_AZURE_PGVECTOR is NOT set

If you request a mode that requires missing dependencies, you'll get a helpful error:

```python
# With mode="sync" but langchain-postgres not installed:
ImportError: langchain-postgres is not available.
Install it to use sync mode: pip install langchain-postgres
Or set FORCE_AZURE_PGVECTOR=true to use Azure PostgreSQL.
```

### When FORCE_AZURE_PGVECTOR is set

Azure PostgreSQL will always be used, even if you don't have `langchain-postgres` installed.

## Configuration Files

### Development (.env.development)
```bash
# Use Azure PostgreSQL exclusively in development
FORCE_AZURE_PGVECTOR=true
DB_HOST=localhost
DB_PORT=5432
DB_NAME=rag_dev
```

### Production (.env.production)
```bash
# Force Azure PostgreSQL in production
FORCE_AZURE_PGVECTOR=true
DB_HOST=myserver.postgres.database.azure.com
DB_PORT=5432
DB_NAME=rag_prod
PGVECTOR_CREATE_EXTENSION=false
```

### Testing (.env.test)
```bash
# Can leave unset for testing if you have langchain-postgres
# FORCE_AZURE_PGVECTOR=false
DB_HOST=localhost
DB_PORT=5432
DB_NAME=rag_test
```

## Minimal Dependencies

When using `FORCE_AZURE_PGVECTOR=true`, you only need these core dependencies:

**Required:**
- `langchain-azure-postgresql`
- `langchain-core`
- `psycopg[binary,pool]`
- `pgvector`
- One embedding provider (e.g., `langchain-openai`)

**NOT Required:**
- `langchain-postgres` (standard PGVector)
- `pymongo` (MongoDB)
- `langchain-mongodb` (MongoDB vector store)

Use the minimal requirements file:
```bash
pip install -r requirements-azure-core.txt
```

## Migration Strategy

If you're migrating to Azure-only deployment:

### Step 1: Test with Override
```bash
# Set the override but keep existing dependencies
export FORCE_AZURE_PGVECTOR=true
uvicorn app.main:app --reload
```

### Step 2: Update Configuration
Update all configuration files to explicitly use `mode="azurepsql"` or rely on the environment variable.

### Step 3: Remove Unused Dependencies
Once verified, you can create a minimal requirements file without:
- `langchain-postgres`
- `langchain-mongodb`
- `pymongo`
- Other unused vector stores

### Step 4: Clean Installation
```bash
pip uninstall langchain-postgres pymongo langchain-mongodb -y
pip install -r requirements-azure-core.txt
```

## Troubleshooting

### Issue: Application still trying to use other vector stores

**Solution**: Verify the environment variable is set correctly:
```bash
# Linux/Mac
echo $FORCE_AZURE_PGVECTOR

# Windows CMD
echo %FORCE_AZURE_PGVECTOR%

# Windows PowerShell
echo $env:FORCE_AZURE_PGVECTOR

# Python check
python -c "import os; print(os.getenv('FORCE_AZURE_PGVECTOR'))"
```

### Issue: Import errors even with FORCE_AZURE_PGVECTOR set

**Solution**: The environment variable must be set **before** importing the factory:

```python
# Correct
import os
os.environ['FORCE_AZURE_PGVECTOR'] = 'true'
from app.services.vector_store.factory import get_vector_store

# Incorrect (too late)
from app.services.vector_store.factory import get_vector_store
import os
os.environ['FORCE_AZURE_PGVECTOR'] = 'true'  # Won't work!
```

### Issue: Azure PostgreSQL connection errors

**Solution**: Ensure your Azure PostgreSQL is properly configured:
1. Check the `pgvector` extension is enabled
2. Verify connection string is correct
3. Check firewall rules allow your IP
4. Ensure SSL is properly configured

## Best Practices

1. **Use in Production**: Set this in production to ensure consistency
2. **Document in README**: Make it clear that this variable is available
3. **Include in .env.example**: Add it to your example environment file
4. **CI/CD Integration**: Set it in your deployment pipelines
5. **Docker**: Include it in your Dockerfile or docker-compose.yml

## Related Documentation

- [Azure Installation Success](AZURE_INSTALLATION_SUCCESS.md)
- [Migration Changes Summary](MIGRATION_CHANGES_SUMMARY.md)
- [Factory Pattern Documentation](app/services/vector_store/factory.py)

---

**Added**: 2025-11-12
**Purpose**: Enable Azure PostgreSQL-only deployments without incompatible dependencies
