# main.py
import os
import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

from starlette.responses import JSONResponse

from app.config import (
    VectorDBType,
    debug_mode,
    RAG_HOST,
    RAG_PORT,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    PDF_EXTRACT_IMAGES,
    VECTOR_DB_TYPE,
    LogMiddleware,
    logger,
)
from app.middleware import security_middleware
from app.routes import document_routes, pgvector_routes
from app.services.database import PSQLDatabase, ensure_vector_indexes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic goes here
    # Create bounded thread pool executor based on CPU cores
    max_workers = min(
        int(os.getenv("RAG_THREAD_POOL_SIZE", str(os.cpu_count()))), 8
    )  # Cap at 8
    app.state.thread_pool = ThreadPoolExecutor(
        max_workers=max_workers, thread_name_prefix="rag-worker"
    )
    logger.info(
        f"Initialized thread pool with {max_workers} workers (CPU cores: {os.cpu_count()})"
    )

    if VECTOR_DB_TYPE == VectorDBType.PGVECTOR:
        await PSQLDatabase.get_pool()  # Initialize the pool

        try:
            await ensure_vector_indexes()
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to ensure vector indexes: {error_msg}")

            if "InsufficientPrivilegeError" in str(type(e).__name__) or "must be owner" in error_msg.lower():
                logger.error("=" * 80)
                logger.error("DATABASE PERMISSIONS ERROR")
                logger.error("=" * 80)
                logger.error("")
                logger.error("The database user does not have sufficient privileges to create indexes.")
                logger.error("")
                logger.error("SOLUTIONS:")
                logger.error("")
                logger.error("Option 1: Grant ownership of the table to your database user")
                logger.error("  Connect as a database admin and run:")
                logger.error(f"  ALTER TABLE langchain_pg_embedding OWNER TO \"your-username\";")
                logger.error("")
                logger.error("Option 2: Grant specific privileges")
                logger.error("  GRANT ALL PRIVILEGES ON TABLE langchain_pg_embedding TO \"your-username\";")
                logger.error("")
                logger.error("Option 3: Create the indexes manually as a superuser")
                logger.error("  CREATE INDEX IF NOT EXISTS idx_langchain_pg_embedding_custom_id")
                logger.error("    ON langchain_pg_embedding (custom_id);")
                logger.error("  CREATE INDEX IF NOT EXISTS idx_langchain_pg_embedding_file_id")
                logger.error("    ON langchain_pg_embedding ((cmetadata->>'file_id'));")
                logger.error("")
                logger.error("After fixing permissions, restart the application.")
                logger.error("=" * 80)

            # Exit the application - don't start with insufficient permissions
            import sys
            sys.exit(1)

    yield

    # Cleanup logic
    logger.info("Shutting down thread pool")
    app.state.thread_pool.shutdown(wait=True)
    logger.info("Thread pool shutdown complete")


app = FastAPI(lifespan=lifespan, debug=debug_mode)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(LogMiddleware)

app.middleware("http")(security_middleware)

# Set state variables for use in routes
app.state.CHUNK_SIZE = CHUNK_SIZE
app.state.CHUNK_OVERLAP = CHUNK_OVERLAP
app.state.PDF_EXTRACT_IMAGES = PDF_EXTRACT_IMAGES

# Include routers
app.include_router(document_routes.router)
if debug_mode:
    app.include_router(router=pgvector_routes.router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    body = await request.body()
    logger.debug(f"Validation error occurred")
    logger.debug(f"Raw request body: {body.decode()}")
    logger.debug(f"Validation errors: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "body": body.decode(),
            "message": "Request validation failed",
        },
    )


if __name__ == "__main__":
    uvicorn.run(app, host=RAG_HOST, port=RAG_PORT, log_config=None)
