from typing import Optional
from langchain_core.embeddings import Embeddings

# Conditional imports for optional dependencies
try:
    from .azure_pgvector import AzPgVector
    AZURE_PGVECTOR_AVAILABLE = True
except ImportError:
    AZURE_PGVECTOR_AVAILABLE = False
    AzPgVector = None

try:
    from .async_pg_vector import AsyncPgVector
    from .extended_pg_vector import ExtendedPgVector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    AsyncPgVector = None
    ExtendedPgVector = None

try:
    from pymongo import MongoClient
    from .atlas_mongo_vector import AtlasMongoVector
    MONGO_AVAILABLE = True
except ImportError:
    MONGO_AVAILABLE = False
    AtlasMongoVector = None


def get_vector_store(
    connection_string: str,
    embeddings: Embeddings,
    collection_name: str,
    mode: str = "sync",
    search_index: Optional[str] = None,
    create_extension: Optional[bool] = True
):
    """
    Factory function to create vector store instances.

    Note: Uses legacy parameter names (connection_string, embedding_function) for backward
    compatibility. ExtendedPgVector and its subclasses automatically adapt these to the
    new langchain-postgres parameter names (connection, embeddings).
    """
    if mode == "sync":
        if not PGVECTOR_AVAILABLE:
            raise ImportError(
                "langchain-postgres is not available. "
                "Install it to use sync mode: pip install langchain-postgres"
            )
        return ExtendedPgVector(
            connection_string=connection_string,
            embedding_function=embeddings,
            collection_name=collection_name,
            create_extension=create_extension
        )
    elif mode == "async":
        if not PGVECTOR_AVAILABLE:
            raise ImportError(
                "langchain-postgres is not available. "
                "Install it to use async mode: pip install langchain-postgres"
            )
        return AsyncPgVector(
            connection_string=connection_string,
            embedding_function=embeddings,
            collection_name=collection_name,
            create_extension=create_extension
        )
    elif mode == "azurepsql":
        if not AZURE_PGVECTOR_AVAILABLE:
            raise ImportError(
                "Azure PostgreSQL support is not available. "
                "Install langchain-azure-postgresql to use azurepsql mode: "
                "pip install langchain-azure-postgresql"
            )
        return AzPgVector(
            connection_string=connection_string,
            embedding_function=embeddings,
            collection_name=collection_name,
            create_extension=create_extension
        )
    elif mode == "atlas-mongo":
        if not MONGO_AVAILABLE:
            raise ImportError(
                "MongoDB support is not available. "
                "Install pymongo and langchain-mongodb to use atlas-mongo mode: "
                "pip install pymongo langchain-mongodb"
            )
        mongo_db = MongoClient(connection_string).get_database()
        mong_collection = mongo_db[collection_name]
        return AtlasMongoVector(
            collection=mong_collection, embedding=embeddings, index_name=search_index
        )
    else:
        raise ValueError(
            "Invalid mode specified. Choose 'sync', 'async', 'azurepsql', or 'atlas-mongo'."
        )