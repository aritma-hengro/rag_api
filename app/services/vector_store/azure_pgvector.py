from typing import Optional, List, Tuple, Dict, Any

from langchain_core.documents import Document
from langchain_core.runnables.config import run_in_executor
from langchain_azure_postgresql.common import (
    BasicAuth,
    AzurePGConnectionPool,
    ConnectionInfo,
)
from langchain_azure_postgresql.langchain import AzurePGVectorStore


class AzPgVector(AzurePGVectorStore):
    """
    Azure PostgreSQL Vector Store wrapper.

    This class extends AzurePGVectorStore to provide compatibility with the
    factory pattern and existing codebase conventions.

    Note: This uses the Azure-specific langchain-azure-postgresql package,
    which is separate from langchain-postgres and has its own authentication
    and connection pooling mechanisms.
    """

    def __init__(self, *args, **kwargs):
        # Adapt parameter names for compatibility
        # The factory might pass old-style parameters
        if 'connection_string' in kwargs:
            # AzurePGVectorStore might expect different connection setup
            # This needs to be tested with actual Azure PostgreSQL
            kwargs['connection'] = kwargs.pop('connection_string')

        if 'embedding_function' in kwargs:
            kwargs['embeddings'] = kwargs.pop('embedding_function')

        if 'create_extension' in kwargs:
            # Remove unsupported parameter
            kwargs.pop('create_extension')

        super().__init__(*args, **kwargs)

    def add_documents(
        self,
        documents: List[Document],
        ids: Optional[List[str]] = None,
        **kwargs
    ) -> List[str]:
        """
        Add documents to the vector store.

        Args:
            documents: List of documents to add
            ids: Optional list of IDs for the documents
            **kwargs: Additional arguments

        Returns:
            List of document IDs that were added
        """
        # Delegate to parent class implementation
        return super().add_documents(documents=documents, ids=ids, **kwargs)

    async def aadd_documents(
        self,
        documents: List[Document],
        ids: Optional[List[str]] = None,
        **kwargs
    ) -> List[str]:
        """
        Async version of add_documents.

        Args:
            documents: List of documents to add
            ids: Optional list of IDs for the documents
            **kwargs: Additional arguments

        Returns:
            List of document IDs that were added
        """
        # Check if parent has native async support
        if hasattr(super(), 'aadd_documents'):
            return await super().aadd_documents(documents=documents, ids=ids, **kwargs)
        else:
            # Fallback to executor-based async
            executor = kwargs.pop('executor', None)
            return await run_in_executor(
                executor,
                self.add_documents,
                documents,
                ids=ids,
                **kwargs
            )