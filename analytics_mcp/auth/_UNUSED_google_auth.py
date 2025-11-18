"""
Google OAuth Authentication for Analytics MCP

Handles OAuth 2.0 flow for Google Analytics API access.
Adapted from Google Workspace MCP.
"""

import os
import logging
import secrets
from typing import Optional, Dict, Any, Tuple
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from analytics_mcp.auth.oauth_config import get_oauth_config
from analytics_mcp.auth.credential_store import get_credential_store
from analytics_mcp.auth.oauth21_session_store import (
    get_oauth21_session_store,
    get_session_context,
)
from analytics_mcp.auth.scopes import DEFAULT_SCOPES

logger = logging.getLogger(__name__)


class GoogleAuthenticationError(Exception):
    """Exception raised when OAuth authentication is required."""

    def __init__(self, message: str, auth_url: Optional[str] = None):
        super().__init__(message)
        self.auth_url = auth_url


def load_client_secrets_from_env() -> Optional[Dict[str, Any]]:
    """
    Load OAuth client secrets from environment variables.

    Returns:
        Client configuration dictionary or None
    """
    config = get_oauth_config()

    if not config.client_id or not config.client_secret:
        logger.warning(
            "OAuth client credentials not found in environment variables"
        )
        return None

    # Build client configuration in the format expected by google-auth-oauthlib
    client_config = {
        "installed": {
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "redirect_uris": config.get_redirect_uris(),
        }
    }

    logger.debug("Loaded OAuth client configuration from environment")
    return client_config


def check_client_secrets() -> Optional[str]:
    """
    Verify that OAuth client secrets are available.

    Returns:
        Error message if secrets are missing, None otherwise
    """
    client_config = load_client_secrets_from_env()
    if not client_config:
        return (
            "OAuth credentials not configured. Please set "
            "GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET "
            "environment variables."
        )
    return None


def create_oauth_flow(
    scopes: list,
    redirect_uri: str,
    state: Optional[str] = None,
) -> Flow:
    """
    Create an OAuth flow instance.

    Args:
        scopes: List of OAuth scopes to request
        redirect_uri: OAuth redirect URI
        state: Optional OAuth state parameter for CSRF protection

    Returns:
        Configured Flow instance

    Raises:
        ValueError: If client configuration cannot be loaded
    """
    client_config = load_client_secrets_from_env()
    if not client_config:
        raise ValueError("OAuth client configuration not available")

    flow = Flow.from_client_config(
        client_config=client_config,
        scopes=scopes,
        redirect_uri=redirect_uri,
        state=state,
    )

    logger.debug(f"Created OAuth flow with {len(scopes)} scopes")
    return flow


async def start_auth_flow(
    user_google_email: str,
    service_name: str = "Google Analytics",
    redirect_uri: Optional[str] = None,
    scopes: Optional[list] = None,
) -> str:
    """
    Start the OAuth authentication flow.

    Args:
        user_google_email: User's Google email for login hint
        service_name: Name of the service being authenticated
        redirect_uri: OAuth redirect URI (uses config default if not provided)
        scopes: OAuth scopes to request (uses DEFAULT_SCOPES if not provided)

    Returns:
        Formatted message with authorization URL for the user

    Raises:
        GoogleAuthenticationError: If OAuth configuration is invalid
    """
    config = get_oauth_config()

    # Use provided values or defaults
    if redirect_uri is None:
        redirect_uri = config.redirect_uri
    if scopes is None:
        scopes = DEFAULT_SCOPES

    # Generate random state for CSRF protection
    state = secrets.token_urlsafe(32)

    # Get session context if available
    session_ctx = get_session_context()
    session_id = session_ctx.session_id if session_ctx else None

    # Store state in session store for validation
    store = get_oauth21_session_store()
    store.store_oauth_state(state, session_id=session_id, expires_in_seconds=600)

    # Create OAuth flow
    try:
        flow = create_oauth_flow(scopes, redirect_uri, state)
    except ValueError as e:
        error_msg = f"Failed to create OAuth flow: {e}"
        logger.error(error_msg)
        raise GoogleAuthenticationError(error_msg)

    # Generate authorization URL
    authorization_url, _ = flow.authorization_url(
        access_type="offline",  # Request refresh token
        include_granted_scopes="true",  # Incremental authorization
        login_hint=user_google_email,
        prompt="consent",  # Force consent screen to get refresh token
    )

    logger.info(
        f"Generated OAuth URL for {user_google_email} (service: {service_name})"
    )

    # Format response message
    message = f"""
**{service_name} Authentication Required**

Please authorize access to your {service_name} account by visiting this URL:

{authorization_url}

After authorizing, your credentials will be saved and you can retry your command.
"""

    return message


def handle_auth_callback(
    scopes: list,
    authorization_response: str,
    redirect_uri: str,
    session_id: Optional[str] = None,
) -> Tuple[str, Credentials]:
    """
    Handle the OAuth callback and exchange authorization code for tokens.

    Args:
        scopes: OAuth scopes that were requested
        authorization_response: Full callback URL with code and state
        redirect_uri: OAuth redirect URI used in the flow
        session_id: Optional session ID for state validation

    Returns:
        Tuple of (user_email, credentials)

    Raises:
        ValueError: If state validation fails or token exchange fails
    """
    # Extract state from authorization response
    from urllib.parse import urlparse, parse_qs

    parsed_url = urlparse(authorization_response)
    query_params = parse_qs(parsed_url.query)
    state = query_params.get("state", [None])[0]

    if not state:
        raise ValueError("Missing state parameter in OAuth callback")

    # Validate and consume OAuth state
    store = get_oauth21_session_store()
    try:
        store.validate_and_consume_oauth_state(state, session_id)
    except ValueError as e:
        logger.error(f"OAuth state validation failed: {e}")
        raise

    # Create flow with the state
    flow = create_oauth_flow(scopes, redirect_uri, state)

    # Exchange authorization code for tokens
    try:
        flow.fetch_token(authorization_response=authorization_response)
        credentials = flow.credentials
    except Exception as e:
        logger.error(f"Failed to fetch OAuth token: {e}")
        raise ValueError(f"Token exchange failed: {e}")

    # Get user info to verify email
    user_info = get_user_info(credentials)
    if not user_info or not user_info.get("email"):
        raise ValueError("Failed to retrieve user email from Google")

    user_email = user_info["email"]
    logger.info(f"Successfully exchanged OAuth code for tokens (user: {user_email})")

    # Store credentials in file-based store
    credential_store = get_credential_store()
    credential_store.store_credential(user_email, credentials)

    return user_email, credentials


def get_credentials(
    user_email: str,
    session_id: Optional[str] = None,
    scopes: Optional[list] = None,
) -> Optional[Credentials]:
    """
    Get credentials for a user, checking both session store and file store.

    Args:
        user_email: User's email address
        session_id: Optional session ID for validation
        scopes: Optional scopes to validate

    Returns:
        Credentials if found and valid, None otherwise
    """
    if scopes is None:
        scopes = DEFAULT_SCOPES

    # Priority 1: Check OAuth21SessionStore (in-memory, session-bound)
    store = get_oauth21_session_store()
    credentials = store.get_credentials_with_validation(
        requested_user_email=user_email,
        session_id=session_id,
    )

    if credentials and credentials.valid:
        logger.debug(f"Found valid credentials in session store for {user_email}")
        return credentials

    # Priority 2: Check file-based CredentialStore (persistent)
    credential_store = get_credential_store()
    credentials = credential_store.get_credential(user_email)

    if credentials:
        # Refresh if expired
        if credentials.expired and credentials.refresh_token:
            try:
                from google.auth.transport.requests import Request
                credentials.refresh(Request())
                logger.info(f"Refreshed expired credentials for {user_email}")

                # Update both stores
                credential_store.store_credential(user_email, credentials)

                # Also update session store if we have session context
                config = get_oauth_config()
                store.store_session(
                    user_email=user_email,
                    access_token=credentials.token,
                    refresh_token=credentials.refresh_token,
                    token_uri=credentials.token_uri,
                    client_id=credentials.client_id,
                    client_secret=credentials.client_secret,
                    scopes=credentials.scopes,
                    expiry=credentials.expiry,
                    session_id=f"refreshed_{user_email}",
                    mcp_session_id=session_id,
                )

                return credentials
            except Exception as e:
                logger.error(f"Failed to refresh credentials for {user_email}: {e}")
                return None

        if credentials.valid:
            logger.debug(f"Found valid credentials in file store for {user_email}")
            return credentials

    logger.debug(f"No valid credentials found for {user_email}")
    return None


def get_user_info(credentials: Credentials) -> Optional[Dict[str, Any]]:
    """
    Retrieve user information from Google using OAuth credentials.

    Args:
        credentials: Google OAuth credentials

    Returns:
        Dictionary with user info (including 'email') or None on failure
    """
    try:
        # Use Google OAuth2 API to get user info
        service = build("oauth2", "v2", credentials=credentials)
        user_info = service.userinfo().get().execute()

        logger.debug(f"Retrieved user info for {user_info.get('email')}")
        return user_info

    except HttpError as e:
        logger.error(f"HTTP error retrieving user info: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error retrieving user info: {e}")
        return None


async def get_authenticated_credentials(
    user_email: str,
    service_name: str = "Google Analytics",
    scopes: Optional[list] = None,
) -> Credentials:
    """
    Get authenticated credentials for a user, initiating OAuth if needed.

    This is the main entry point for tools to get credentials.

    Args:
        user_email: User's Google email address
        service_name: Name of the service (for auth messages)
        scopes: OAuth scopes to request

    Returns:
        Valid Google Credentials object

    Raises:
        GoogleAuthenticationError: If authentication is required
    """
    if scopes is None:
        scopes = DEFAULT_SCOPES

    # Get session context
    session_ctx = get_session_context()
    session_id = session_ctx.session_id if session_ctx else None

    # Try to get existing credentials
    credentials = get_credentials(user_email, session_id, scopes)

    if credentials and credentials.valid:
        return credentials

    # No valid credentials - initiate OAuth flow
    config = get_oauth_config()
    auth_message = await start_auth_flow(
        user_google_email=user_email,
        service_name=service_name,
        redirect_uri=config.redirect_uri,
        scopes=scopes,
    )

    # Extract authorization URL from message
    lines = auth_message.split("\n")
    auth_url = None
    for line in lines:
        if line.strip().startswith("http"):
            auth_url = line.strip()
            break

    raise GoogleAuthenticationError(auth_message, auth_url=auth_url)
