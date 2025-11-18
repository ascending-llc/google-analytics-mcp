"""
MCP Session Middleware for Analytics MCP

This middleware intercepts MCP requests and sets the session context
for use by tool functions.

Adapted from Google Workspace MCP, with security improvements:
- Removed JWT decoding without verification (security vulnerability)
- Simplified for Analytics-only use case
"""

import logging
from typing import Callable, Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from analytics_mcp.auth.oauth21_session_store import (
    SessionContext,
    SessionContextManager,
    extract_session_from_headers,
)

logger = logging.getLogger(__name__)


class MCPSessionMiddleware(BaseHTTPMiddleware):
    """
    Middleware that extracts session information from requests and makes it
    available to MCP tool functions via context variables.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Any:
        """Process request and set session context."""

        logger.debug(f"MCPSessionMiddleware processing request: {request.method} {request.url.path}")

        # Skip non-MCP paths
        if not request.url.path.startswith("/mcp"):
            logger.debug(f"Skipping non-MCP path: {request.url.path}")
            return await call_next(request)

        session_context = None

        try:
            # Extract session information
            headers = dict(request.headers)
            session_id = extract_session_from_headers(headers)

            # Try to get auth context from FastMCP (if using OAuth 2.1)
            auth_context = None
            user_email = None
            mcp_session_id = None

            # Check for FastMCP auth context
            if hasattr(request.state, "auth"):
                auth_context = request.state.auth
                # Extract user email from auth claims if available
                if hasattr(auth_context, 'claims') and auth_context.claims:
                    user_email = auth_context.claims.get('email')
                    logger.debug(f"Found user email from FastMCP auth: {user_email}")

            # Check for FastMCP session ID (from streamable HTTP transport)
            if hasattr(request.state, "session_id"):
                mcp_session_id = request.state.session_id
                logger.debug(f"Found FastMCP session ID: {mcp_session_id}")

            # Build session context
            if session_id or auth_context or user_email or mcp_session_id:
                # Create session ID hierarchy: explicit session_id > Google user session > FastMCP session
                effective_session_id = session_id
                if not effective_session_id and user_email:
                    effective_session_id = f"google_{user_email}"
                elif not effective_session_id and mcp_session_id:
                    effective_session_id = mcp_session_id

                session_context = SessionContext(
                    session_id=effective_session_id,
                    user_id=user_email or (auth_context.user_id if auth_context and hasattr(auth_context, 'user_id') else None),
                    auth_context=auth_context,
                    request=request,
                    metadata={
                        "path": request.url.path,
                        "method": request.method,
                        "user_email": user_email,
                        "mcp_session_id": mcp_session_id,
                    }
                )

                logger.debug(
                    f"MCP request with session: session_id={session_context.session_id}, "
                    f"user_id={session_context.user_id}, path={request.url.path}"
                )

            # Process request with session context
            with SessionContextManager(session_context):
                response = await call_next(request)
                return response

        except Exception as e:
            logger.error(f"Error in MCP session middleware: {e}", exc_info=True)
            # Continue without session context
            return await call_next(request)
