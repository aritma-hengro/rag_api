"""
Azure Entra ID Authentication Helper for PostgreSQL

This module provides utilities for authenticating to Azure PostgreSQL Flexible Server
using Azure Entra ID (formerly Azure AD) instead of traditional username/password.

Usage:
    Set USE_ENTRA_AUTH=true in your .env file to enable Entra ID authentication.
    The module will automatically use DefaultAzureCredential to obtain access tokens.
"""

import os
import urllib.parse
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Conditional import for Azure Identity
try:
    from azure.identity import DefaultAzureCredential
    AZURE_IDENTITY_AVAILABLE = True
except ImportError:
    DefaultAzureCredential = None
    AZURE_IDENTITY_AVAILABLE = False
    logger.warning("azure-identity not available. Entra ID authentication will not work.")


class EntraIDAuthHelper:
    """Helper class for Azure Entra ID authentication with PostgreSQL."""

    # Azure PostgreSQL resource scope for token requests
    POSTGRES_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"

    def __init__(self):
        """Initialize the auth helper with Azure credentials."""
        if not AZURE_IDENTITY_AVAILABLE:
            raise ImportError(
                "azure-identity package is required for Entra ID authentication. "
                "Install it with: pip install azure-identity"
            )
        self.credential = DefaultAzureCredential()
        self._cached_token = None
        self._token_username = None

    def get_access_token(self) -> str:
        """
        Get an access token for Azure PostgreSQL.

        Returns:
            Access token string
        """
        logger.debug("Requesting access token for Azure PostgreSQL")
        token = self.credential.get_token(self.POSTGRES_SCOPE)
        self._cached_token = token.token
        return token.token

    def get_username_from_token(self) -> Optional[str]:
        """
        Extract username from the access token.

        Uses environment variable AZURE_PG_USERNAME_OVERRIDE if set,
        otherwise attempts to extract from token claims.

        Returns:
            Username string or None
        """
        # Check for explicit username override
        override_username = os.getenv("AZURE_PG_USERNAME_OVERRIDE")
        if override_username:
            logger.debug(f"Using overridden username: {override_username}")
            return override_username

        # Try to decode token to get username
        if self._cached_token:
            try:
                import jwt
                decoded = jwt.decode(
                    self._cached_token,
                    options={"verify_signature": False}
                )
                # Try different username fields in order of preference
                username = (
                    decoded.get("upn") or
                    decoded.get("unique_name") or
                    decoded.get("email") or
                    decoded.get("preferred_username")
                )
                if username:
                    logger.debug(f"Extracted username from token: {username}")
                    return username
            except Exception as e:
                logger.warning(f"Failed to decode token for username: {e}")

        return None

    def create_entra_connection_string(
        self,
        host: str,
        database: str,
        port: str = "5432",
        use_psycopg2: bool = True
    ) -> str:
        """
        Create a PostgreSQL connection string using Entra ID authentication.

        Args:
            host: PostgreSQL server hostname
            database: Database name
            port: Port number (default: 5432)
            use_psycopg2: Whether to use psycopg2 driver (default: True)

        Returns:
            Connection string with token-based authentication
        """
        # Get fresh token
        token = self.get_access_token()
        username = self.get_username_from_token()

        if not username:
            # Fallback to generic username if extraction fails
            username = "entra_user"
            logger.warning(f"Could not extract username from token, using: {username}")

        # Encode components for URL
        # Use quote() instead of quote_plus() for URI components (not query params)
        # This encodes spaces as %20 instead of +
        encoded_username = urllib.parse.quote(username, safe='')
        encoded_password = urllib.parse.quote(token, safe='')
        encoded_database = urllib.parse.quote(database, safe='')

        # Build connection string
        if use_psycopg2:
            driver = "postgresql+psycopg2"
        else:
            driver = "postgresql"

        conn_string = (
            f"{driver}://{encoded_username}:{encoded_password}"
            f"@{host}:{port}/{encoded_database}"
            f"?sslmode=require"
        )

        logger.info(f"Created Entra ID connection string for {host}/{database}")
        return conn_string


def should_use_entra_auth() -> bool:
    """
    Check if Entra ID authentication should be used.

    Returns:
        True if USE_ENTRA_AUTH environment variable is set to true
    """
    return os.getenv("USE_ENTRA_AUTH", "").lower() in ("true", "1", "yes")


def get_entra_connection_string_if_enabled(
    connection_string: str,
    use_psycopg2: bool = True
) -> str:
    """
    Return an Entra ID connection string if enabled, otherwise return the original.

    Args:
        connection_string: Original connection string
        use_psycopg2: Whether to use psycopg2 driver

    Returns:
        Modified connection string if Entra ID is enabled, otherwise original
    """
    if not should_use_entra_auth():
        return connection_string

    try:
        # Parse the original connection string to extract host and database
        parsed = urllib.parse.urlparse(connection_string)

        if not parsed.hostname:
            logger.error("Could not parse hostname from connection string")
            return connection_string

        # Extract database name (remove leading slash)
        database = parsed.path.lstrip('/').split('?')[0] if parsed.path else 'postgres'

        # Get port or use default
        port = str(parsed.port) if parsed.port else "5432"

        # Create Entra ID connection string
        auth_helper = EntraIDAuthHelper()
        return auth_helper.create_entra_connection_string(
            host=parsed.hostname,
            database=database,
            port=port,
            use_psycopg2=use_psycopg2
        )

    except Exception as e:
        logger.error(f"Failed to create Entra ID connection string: {e}")
        logger.warning("Falling back to original connection string")
        return connection_string
