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
        logger.info("ENTRA AUTH: Requesting access token for Azure PostgreSQL")
        logger.debug(f"ENTRA AUTH: Using scope: {self.POSTGRES_SCOPE}")
        try:
            token = self.credential.get_token(self.POSTGRES_SCOPE)
            self._cached_token = token.token
            logger.info(f"ENTRA AUTH: Successfully obtained token (length: {len(token.token)} chars)")
            logger.debug(f"ENTRA AUTH: Token expires at: {token.expires_on}")
            return token.token
        except Exception as e:
            logger.error(f"ENTRA AUTH: Failed to obtain access token: {e}")
            raise

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
        logger.debug(f"ENTRA AUTH: Checking AZURE_PG_USERNAME_OVERRIDE env var: {override_username if override_username else 'NOT SET'}")

        if override_username:
            logger.info(f"ENTRA AUTH: Using overridden username from environment: {override_username}")
            return override_username

        # Try to decode token to get username
        logger.debug("ENTRA AUTH: No username override, attempting to extract from token")
        if self._cached_token:
            try:
                import jwt
                decoded = jwt.decode(
                    self._cached_token,
                    options={"verify_signature": False}
                )
                logger.debug(f"ENTRA AUTH: Token claims: {list(decoded.keys())}")

                # Try different username fields in order of preference
                username = (
                    decoded.get("upn") or
                    decoded.get("unique_name") or
                    decoded.get("email") or
                    decoded.get("preferred_username") or
                    decoded.get("sub")
                )
                if username:
                    logger.info(f"ENTRA AUTH: Extracted username from token: {username}")
                    return username
                else:
                    logger.warning(f"ENTRA AUTH: Could not find username in token claims. Available claims: {list(decoded.keys())}")
            except Exception as e:
                logger.error(f"ENTRA AUTH: Failed to decode token for username: {e}")

        logger.warning("ENTRA AUTH: No cached token available for username extraction")
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
        logger.info(f"ENTRA AUTH: Creating connection string for {host}:{port}/{database}")
        logger.debug(f"ENTRA AUTH: use_psycopg2={use_psycopg2}")

        # Get fresh token
        token = self.get_access_token()
        username = self.get_username_from_token()

        if not username:
            # Fallback to generic username if extraction fails
            username = "entra_user"
            logger.warning(f"ENTRA AUTH: Could not extract username from token, using fallback: {username}")

        logger.info(f"ENTRA AUTH: Building connection string with username: {username}")

        # Encode components for URL
        # Use quote() instead of quote_plus() for URI components (not query params)
        # This encodes spaces as %20 instead of +
        encoded_username = urllib.parse.quote(username, safe='')
        encoded_password = urllib.parse.quote(token, safe='')
        encoded_database = urllib.parse.quote(database, safe='')

        logger.debug(f"ENTRA AUTH: Encoded username: {encoded_username}")
        logger.debug(f"ENTRA AUTH: Token length after encoding: {len(encoded_password)} chars")

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

        logger.info(f"ENTRA AUTH: Successfully created connection string for {host}/{database} with username {username}")
        logger.debug(f"ENTRA AUTH: Connection string pattern: {driver}://{username}:***@{host}:{port}/{database}?sslmode=require")
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
    logger.debug(f"ENTRA AUTH: get_entra_connection_string_if_enabled called")
    logger.debug(f"ENTRA AUTH: Original connection string pattern: {connection_string.split('://')[0]}://***")
    logger.debug(f"ENTRA AUTH: use_psycopg2={use_psycopg2}")

    if not should_use_entra_auth():
        logger.debug("ENTRA AUTH: Entra auth not enabled, returning original connection string")
        return connection_string

    logger.info("ENTRA AUTH: Entra auth is enabled, creating authenticated connection string")

    try:
        # Parse the original connection string to extract host and database
        parsed = urllib.parse.urlparse(connection_string)
        logger.debug(f"ENTRA AUTH: Parsed hostname: {parsed.hostname}, port: {parsed.port}, path: {parsed.path}")

        if not parsed.hostname:
            logger.error("ENTRA AUTH: Could not parse hostname from connection string")
            return connection_string

        # Extract database name (remove leading slash)
        database = parsed.path.lstrip('/').split('?')[0] if parsed.path else 'postgres'

        # Get port or use default
        port = str(parsed.port) if parsed.port else "5432"

        logger.debug(f"ENTRA AUTH: Extracted - host: {parsed.hostname}, port: {port}, database: {database}")

        # Create Entra ID connection string
        logger.info("ENTRA AUTH: Creating EntraIDAuthHelper instance")
        auth_helper = EntraIDAuthHelper()
        new_conn_string = auth_helper.create_entra_connection_string(
            host=parsed.hostname,
            database=database,
            port=port,
            use_psycopg2=use_psycopg2
        )
        logger.info("ENTRA AUTH: Successfully replaced connection string with Entra ID authenticated version")
        return new_conn_string

    except Exception as e:
        logger.error(f"ENTRA AUTH: Failed to create Entra ID connection string: {e}", exc_info=True)
        logger.warning("ENTRA AUTH: Falling back to original connection string")
        return connection_string
