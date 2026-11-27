# Claude Code Knowledge Base

This document contains architectural knowledge, implementation details, and important context about the RAG API codebase.

## Project Overview

**ID-based RAG FastAPI** is a scalable, asynchronous document indexing and retrieval system built with:
- **FastAPI** for async API endpoints
- **PostgreSQL + pgvector** for vector storage
- **Langchain** for document processing and embeddings
- **Azure Entra ID** for passwordless authentication (optional)

The primary use case is integration with [LibreChat](https://librechat.ai), organizing embeddings by `file_id` for targeted queries.

## Architecture

### Core Components

1. **Vector Stores** (`app/services/vector_store/`)
   - `ExtendedPgVector` - Base class extending Langchain's PGVector with custom features
   - `AsyncPgVector` - Async wrapper with thread pool execution
   - `azure_entra_auth.py` - Azure Entra ID authentication helper
   - `factory.py` - Factory pattern for vector store instantiation

2. **Database Layer** (`app/services/database.py`)
   - `PSQLDatabase` - Connection pool management using asyncpg
   - Automatic SSL configuration for Azure PostgreSQL
   - Health check functionality

3. **Configuration** (`app/config.py`)
   - Environment-based configuration
   - Multiple connection string builders (Unix socket, Entra ID, standard)
   - Embeddings provider initialization (OpenAI, Azure, Hugging Face, Ollama, etc.)

4. **Routes** (`app/routes/`)
   - `document_routes.py` - Document upload, retrieval, deletion
   - `pgvector_routes.py` - Database diagnostics and management

## Authentication Mechanisms

### 1. API Authentication (Optional)
- JWT token verification using shared secret (`JWT_SECRET`)
- Middleware: `app/middleware.py` → `security_middleware`
- No token generation - expects externally signed tokens

### 2. Database Authentication

#### Traditional (Username/Password)
```env
POSTGRES_USER=myuser
POSTGRES_PASSWORD=mypassword
DB_HOST=db
DB_PORT=5432
POSTGRES_DB=mydatabase
```

#### Azure Entra ID (Passwordless)
```env
USE_ENTRA_AUTH=true
AZURE_PG_USERNAME_OVERRIDE="your-entra-user"
```

**How it works:**
1. `DefaultAzureCredential` acquires access token from Azure
2. Token extracted and decoded to get username (or uses override)
3. Token used as password for PostgreSQL connections
4. Separate implementations for:
   - **SQLAlchemy/psycopg2** (vector store) - via `azure_entra_auth.py`
   - **asyncpg** (connection pool) - via `config.py` DSN construction

**Key Implementation Details:**
- SSL must be passed as parameter to `asyncpg.create_pool()`, not in DSN
- Token refresh handled by DefaultAzureCredential automatically
- Username extraction from JWT claims: `upn`, `unique_name`, `email`, or `preferred_username`

## Database Schema

### Main Table: `langchain_pg_embedding`

Created by Langchain's PGVector, stores:
- `id` - Primary key
- `custom_id` - File ID for grouping embeddings
- `embedding` - Vector representation (pgvector type)
- `document` - Original text content
- `cmetadata` - JSONB metadata including `file_id`

### Indexes

Created by `ensure_vector_indexes()` in startup:
```sql
CREATE INDEX idx_langchain_pg_embedding_custom_id ON langchain_pg_embedding (custom_id);
CREATE INDEX idx_langchain_pg_embedding_file_id ON langchain_pg_embedding ((cmetadata->>'file_id'));
```

**Note:** Azure Entra ID users may need explicit permissions:
```sql
ALTER TABLE langchain_pg_embedding OWNER TO "your-entra-user";
-- OR --
GRANT ALL PRIVILEGES ON TABLE langchain_pg_embedding TO "your-entra-user";
```

## Configuration Deep Dive

### Critical Environment Variables

#### Database Connection
- `USE_ENTRA_AUTH` - Enable Azure Entra ID authentication (true/false)
- `AZURE_PG_USERNAME_OVERRIDE` - Override username from token
- `DB_HOST` - PostgreSQL hostname
- `DB_PORT` - PostgreSQL port (default: 5432)
- `POSTGRES_DB` - Database name
- `POSTGRES_USER` - Username (ignored when USE_ENTRA_AUTH=true)
- `POSTGRES_PASSWORD` - Password (ignored when USE_ENTRA_AUTH=true)

#### Vector Store
- `VECTOR_DB_TYPE` - "pgvector" or "atlas-mongo"
- `COLLECTION_NAME` - Vector store collection name
- `PGVECTOR_CREATE_EXTENSION` - Auto-create pgvector extension (set false for Azure)

#### Embeddings
- `EMBEDDINGS_PROVIDER` - openai, azure, huggingface, ollama, bedrock, google_genai, vertexai
- `EMBEDDINGS_MODEL` - Model name (provider-specific)
- `EMBEDDINGS_CHUNK_SIZE` - Batch size for embedding requests

#### Application
- `RAG_HOST` - API bind address (default: 0.0.0.0)
- `RAG_PORT` - API port (default: 8000)
- `DEBUG_RAG_API` - Enable debug logging
- `DEBUG_PGVECTOR_QUERIES` - Log detailed pgvector query info

### Connection String Construction

The application builds TWO connection strings:

1. **CONNECTION_STRING** - For SQLAlchemy/psycopg2 (vector store)
   ```python
   # Format: postgresql+psycopg2://user:pass@host:port/db
   # Modified by azure_entra_auth.get_entra_connection_string_if_enabled()
   ```

2. **DSN** - For asyncpg (connection pool)
   ```python
   # Format: postgresql://user:pass@host:port/db
   # Built with token in config.py when USE_ENTRA_AUTH=true
   ```

## Key Features

### 1. Query Logging (`ExtendedPgVector`)
Enable with `DEBUG_PGVECTOR_QUERIES=true`:
- Logs all pgvector queries
- Sanitizes embedding vectors in logs (shows length instead of full array)
- Tracks query execution time

### 2. Async Thread Pool
- Bounded thread pool for blocking operations
- Size: `min(RAG_THREAD_POOL_SIZE || cpu_count(), 8)`
- Used by `AsyncPgVector` for non-async Langchain operations

### 3. Document Processing
Supports multiple file types via `app/utils/document_loader.py`:
- PDF (with optional image extraction)
- Microsoft Office (Word, Excel, PowerPoint)
- CSV, JSON, Markdown, HTML
- Source code files (50+ extensions)

### 4. Error Handling

#### Permissions Error (Index Creation)
Location: `main.py` → `lifespan()` → `ensure_vector_indexes()`

Catches `InsufficientPrivilegeError` and provides three solutions:
1. Grant table ownership
2. Grant specific privileges
3. Create indexes manually as superuser

Exits application with code 1 on failure.

## Common Issues & Solutions

### Issue: "must be owner of table langchain_pg_embedding"
**Cause:** Entra ID user lacks permissions to create indexes

**Solution:** See error message output or grant permissions:
```sql
ALTER TABLE langchain_pg_embedding OWNER TO "your-entra-user";
```

### Issue: "parameter 'ssl' cannot be changed now"
**Cause:** SSL parameter in asyncpg DSN query string (not supported)

**Solution:** Pass SSL as parameter to `create_pool()`:
```python
await asyncpg.create_pool(dsn=DSN, ssl='require')
```

### Issue: SSL cleanup errors on Windows
**Cause:** Known Windows + asyncpg + ProactorEventLoop issue

**Impact:** Warnings during shutdown, doesn't affect functionality

**Solution:** Ignore warnings or upgrade asyncpg when fix available

### Issue: "User name not found in token"
**Cause:** Token missing `upn`, `unique_name`, `email`, `preferred_username` claims

**Solution:** Set `AZURE_PG_USERNAME_OVERRIDE` in environment

## Development Workflows

### Local Development
```bash
# Setup
pip install -r requirements.txt
cp .env.example .env  # Configure environment

# Run locally
uvicorn main:app --reload

# With Entra ID
az login
export USE_ENTRA_AUTH=true
uvicorn main:app
```

### Testing Authentication

#### JWT Token Generation
```bash
python utils/auth_diagnostics/generate_test_token.py
```

#### Azure Token Diagnostics
```bash
python utils/auth_diagnostics/test_azure_token.py
```

### Code Formatting
```bash
pip install pre-commit
pre-commit install
# Auto-formats with black on commit
```

## Deployment Considerations

### Azure PostgreSQL Flexible Server
1. Enable pgvector extension in server parameters
2. Create extension: `CREATE EXTENSION vector;`
3. Configure Entra ID admin
4. Create Entra ID user/service principal
5. Grant permissions on database and tables
6. Set `USE_ENTRA_AUTH=true`

### Managed Identity (Azure Container Apps, AKS, VMs)
```env
USE_ENTRA_AUTH=true
# No credentials needed - uses managed identity automatically
```

### Service Principal
```env
USE_ENTRA_AUTH=true
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
AZURE_TENANT_ID=your-tenant-id
```

## File Structure

```
rag_api/
├── app/
│   ├── config.py                    # Configuration & initialization
│   ├── middleware.py                # JWT authentication
│   ├── routes/                      # API endpoints
│   ├── services/
│   │   ├── database.py             # asyncpg pool management
│   │   └── vector_store/
│   │       ├── azure_entra_auth.py # Entra ID helper
│   │       ├── extended_pg_vector.py
│   │       ├── async_pg_vector.py
│   │       └── factory.py
│   └── utils/
│       └── document_loader.py      # File parsing
├── utils/
│   └── auth_diagnostics/           # Testing tools
├── main.py                         # FastAPI app & lifecycle
├── requirements.txt                # Python dependencies
└── .env                           # Configuration
```

## Version History

### Recent Changes (2025-11-18)

**Azure Entra ID Authentication** (commits 647d4ec, c406ba7, d80d647)
- Passwordless authentication for PostgreSQL
- Support for DefaultAzureCredential (CLI, Managed Identity, Service Principal)
- Automatic token acquisition and refresh
- Username extraction from JWT claims
- SSL configuration for Azure PostgreSQL
- Comprehensive error handling with actionable messages
- Diagnostic tools for troubleshooting

**Dependencies Added:**
- `azure-identity==1.19.0` - Azure authentication

## Best Practices

1. **Never commit secrets** - Use `.env` files (gitignored)
2. **Use Entra ID in production** - Avoid password management
3. **Enable query logging** - Set `DEBUG_PGVECTOR_QUERIES=true` for performance tuning
4. **Create indexes manually** - For production, create indexes as superuser before deployment
5. **Monitor token expiration** - DefaultAzureCredential handles refresh, but monitor for auth issues
6. **Use connection pooling** - asyncpg pool already configured
7. **SSL in production** - Always use SSL for Azure PostgreSQL

## Additional Resources

- [README.md](README.md) - Setup and usage instructions
- [utils/auth_diagnostics/README.md](utils/auth_diagnostics/README.md) - Testing tools documentation
- [Langchain Documentation](https://python.langchain.com/)
- [Azure Entra ID for PostgreSQL](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/how-to-configure-sign-in-azure-ad-authentication)

---

**Last Updated:** 2025-11-18
**Maintained By:** Development team with assistance from Claude Code
