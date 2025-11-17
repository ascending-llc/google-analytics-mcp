"""
Authentication Info Middleware for Analytics MCP

This middleware is a stub for future OAuth 2.1 JWT token verification support.
Currently not used - our OAuth 2.0 flow uses file-based credentials.

When we implement OAuth 2.1 (Phase 4), this will:
- Extract JWT tokens from Authorization headers
- Verify token signatures using Google's public keys
- Populate FastMCP context state with authenticated user info
"""

import logging
from fastmcp.server.middleware import Middleware, MiddlewareContext

logger = logging.getLogger(__name__)


class AuthInfoMiddleware(Middleware):
    """
    Middleware to extract authentication information from JWT tokens
    and populate the FastMCP context state.

    CURRENTLY A STUB - Not used in OAuth 2.0 flow.
    Will be implemented when we add OAuth 2.1 support.
    """

    def __init__(self):
        super().__init__()
        logger.debug("AuthInfoMiddleware initialized (stub - not active)")

    async def on_request(self, context: MiddlewareContext):
        """
        Process incoming request to extract auth info.

        Currently does nothing - placeholder for OAuth 2.1.
        """
        # Stub implementation - no-op for now
        pass

    async def on_response(self, context: MiddlewareContext):
        """
        Process outgoing response.

        Currently does nothing - placeholder for OAuth 2.1.
        """
        # Stub implementation - no-op for now
        pass


# TODO: When implementing OAuth 2.1, add:
# 1. JWT token extraction from Authorization header
# 2. Token signature verification using Google's JWKS
# 3. User email extraction from verified claims
# 4. FastMCP context state population
# 5. Integration with OAuth21SessionStore for session binding
