"""
Analytics MCP Authentication Module

This module provides OAuth 2.0 authentication for Google Analytics APIs,
supporting per-user credential management and session-based authentication.
"""

from analytics_mcp.auth.credential_store import (
    get_credential_store,
    CredentialStore,
)
from analytics_mcp.auth.oauth_config import (
    get_oauth_config,
    OAuthConfig,
)
from analytics_mcp.auth.google_auth import (
    start_auth_flow,
    handle_auth_callback,
    get_credentials,
    get_user_info,
    GoogleAuthenticationError,
)
from analytics_mcp.auth.scopes import (
    ANALYTICS_READONLY_SCOPE,
    ANALYTICS_SCOPE,
    USERINFO_EMAIL_SCOPE,
    DEFAULT_SCOPES,
)
from analytics_mcp.auth.oauth21_session_store import (
    SessionContext,
    SessionContextManager,
    get_session_context,
    set_session_context,
    clear_session_context,
    extract_session_from_headers,
    get_oauth21_session_store,
)

__all__ = [
    "get_credential_store",
    "CredentialStore",
    "get_oauth_config",
    "OAuthConfig",
    "start_auth_flow",
    "handle_auth_callback",
    "get_credentials",
    "get_user_info",
    "GoogleAuthenticationError",
    "ANALYTICS_READONLY_SCOPE",
    "ANALYTICS_SCOPE",
    "USERINFO_EMAIL_SCOPE",
    "DEFAULT_SCOPES",
    "SessionContext",
    "SessionContextManager",
    "get_session_context",
    "set_session_context",
    "clear_session_context",
    "extract_session_from_headers",
    "get_oauth21_session_store",
]
