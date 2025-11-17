"""
Service decorator for Analytics MCP tools.

Provides @require_analytics_service decorator that handles authentication
and API client creation, following the same pattern as Google Workspace MCP.
"""

import inspect
import logging
from functools import wraps
from typing import Callable, Any

from analytics_mcp.auth.google_auth import GoogleAuthenticationError
from analytics_mcp.tools.utils import (
    create_admin_api_client,
    create_data_api_client,
    create_admin_alpha_api_client,
)

logger = logging.getLogger(__name__)


# API client type mapping
CLIENT_FACTORIES = {
    "admin": create_admin_api_client,
    "data": create_data_api_client,
    "admin_alpha": create_admin_alpha_api_client,
}


def require_analytics_service(api_type: str):
    """
    Decorator that automatically handles Analytics API authentication and client injection.

    This follows the same pattern as Google Workspace MCP's @require_google_service decorator.
    The decorated function must have 'client' as its first parameter and 'user_email: str'
    as a required parameter.

    Args:
        api_type: Type of Analytics API client ("admin", "data", or "admin_alpha")

    Usage:
        @require_analytics_service("admin")
        async def get_account_summaries(client, user_email: str):
            # client parameter is automatically injected
            # user_email is required and will be used for authentication
            # If authentication fails, GoogleAuthenticationError is raised

    Note:
        - The 'client' parameter is removed from the tool's visible signature
        - The 'user_email: str' parameter remains visible and required
        - Authentication errors are raised (not returned), triggering OAuth flow in Jarvis
    """

    def decorator(func: Callable) -> Callable:
        original_sig = inspect.signature(func)
        params = list(original_sig.parameters.values())

        # The decorated function must have 'client' as its first parameter
        if not params or params[0].name != "client":
            raise TypeError(
                f"Function '{func.__name__}' decorated with @require_analytics_service "
                "must have 'client' as its first parameter."
            )

        # Create a new signature for the wrapper that excludes the 'client' parameter
        # but keeps 'user_email' as required (following workspace pattern)
        wrapper_sig = original_sig.replace(parameters=params[1:])

        @wraps(func)
        async def wrapper(*args, **kwargs):
            tool_name = func.__name__

            # Extract user_email from arguments (required parameter)
            bound_args = wrapper_sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            user_email = bound_args.arguments.get("user_email")
            if not user_email:
                raise ValueError(
                    f"[{tool_name}] 'user_email' parameter is required but was not provided."
                )

            logger.debug(
                f"[{tool_name}] Creating {api_type} API client for user: {user_email}"
            )

            # Get the appropriate client factory
            if api_type not in CLIENT_FACTORIES:
                raise ValueError(f"Unknown API type: {api_type}")

            client_factory = CLIENT_FACTORIES[api_type]

            try:
                # Create authenticated API client
                # This will raise GoogleAuthenticationError if auth is needed
                client = await client_factory(user_email)
                logger.debug(f"[{tool_name}] Successfully created {api_type} client")

            except GoogleAuthenticationError as e:
                # Re-raise authentication errors so Jarvis can trigger OAuth flow
                logger.error(
                    f"[{tool_name}] GoogleAuthenticationError for user {user_email}: {e}"
                )
                raise

            # Call the original function with the client injected
            try:
                return await func(client, *args, **kwargs)
            except Exception as e:
                logger.error(f"[{tool_name}] Error executing tool: {e}", exc_info=True)
                raise

        # Set the wrapper's signature to exclude 'client' parameter
        wrapper.__signature__ = wrapper_sig

        return wrapper

    return decorator
