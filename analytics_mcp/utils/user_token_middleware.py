# Copyright 2025 Google LLC All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Middleware to extract Google OAuth tokens from Authorization headers.

This middleware follows the pattern used by Google Workspace MCP server,
where Jarvis manages OAuth tokens and forwards them in the Authorization header.
Token validation happens at the Google Analytics API layer, not here.
"""

import json
import logging
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("analytics-mcp.user_token_middleware")


def mask_sensitive(value: str, visible_chars: int = 4) -> str:
    """Mask sensitive values for logging."""
    if not value or len(value) <= visible_chars:
        return "***"
    return f"...{value[-visible_chars:]}"


class UserTokenMiddleware(BaseHTTPMiddleware):
    """Extract Google OAuth tokens from Authorization header.

    Jarvis manages the OAuth flow and automatically injects tokens via:
        Authorization: Bearer ya29.{google_oauth_token}

    This middleware simply extracts the token and stores it in request.state
    for tools to use. Token validation happens when calling Google APIs.
    """

    def __init__(self, app: Any) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        logger.info(
            f"[MIDDLEWARE] {request.method} {request.url.path} | "
            f"Auth: {mask_sensitive(request.headers.get('authorization', 'NONE'), 12)}"
        )

        # Skip auth for health check
        if request.url.path == "/health":
            logger.info("[MIDDLEWARE] Allowing health check without auth")
            return await call_next(request)

        # Only check auth for POST/HEAD/GET requests (GET is for SSE)
        if request.method not in ["POST", "HEAD", "GET"]:
            logger.info(f"[MIDDLEWARE] Skipping auth for {request.method}")
            return await call_next(request)

        # Extract headers
        auth_header = request.headers.get("authorization", "")
        property_id_header = request.headers.get("X-Analytics-Property-Id")

        # GET requests are for SSE streams - allow without body check
        if request.method == "GET":
            logger.info(f"[MIDDLEWARE] GET request for SSE stream - path: {request.url.path}")
            if auth_header:
                token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else ""
                if token:
                    request.state.user_google_token = token
                    logger.info(f"[MIDDLEWARE] SSE stream has auth token: {mask_sensitive(token, 12)}")
            response = await call_next(request)
            logger.info(f"[MIDDLEWARE] SSE response status: {response.status_code}")
            return response

        # Check for MCP protocol methods that don't need auth
        try:
            body = await request.body()
            request._body = body  # Reset body for downstream handlers

            if body:
                try:
                    request_data = json.loads(body.decode())
                    method = request_data.get("method")
                    logger.info(f"[MIDDLEWARE] MCP method: {method}")
                    if method in [
                        "ping",
                        "tools/list",
                        "prompts/list",
                        "resources/list",
                    ]:
                        logger.info(
                            f"[MIDDLEWARE] Allowing MCP protocol method '{method}' without auth"
                        )
                        return await call_next(request)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass
        except Exception as e:
            logger.warning(f"[MIDDLEWARE] Failed to read request body: {e}")

        # Require Authorization header
        if not auth_header:
            logger.warning(f"Missing Authorization header for {request.url.path}")
            return JSONResponse(
                {"error": "Unauthorized: Missing Authorization header"},
                status_code=401,
            )

        # Extract Bearer token
        if not auth_header.startswith("Bearer "):
            logger.warning(
                f"Invalid Authorization type: {auth_header.split(' ', 1)[0]}"
            )
            return JSONResponse(
                {"error": "Unauthorized: Only Bearer tokens supported"},
                status_code=401,
            )

        token = auth_header[7:].strip()  # Remove "Bearer " prefix
        if not token:
            return JSONResponse(
                {"error": "Unauthorized: Empty Bearer token"},
                status_code=401,
            )

        # Basic format check for Google OAuth tokens
        if not token.startswith("ya29."):
            logger.warning(
                f"Token doesn't match Google OAuth format: {mask_sensitive(token)}"
            )
            # Still allow it - might be test token or different format
            logger.info("Allowing non-standard token format")

        # Store token in request state for tools to use
        request.state.user_google_token = token
        request.state.user_email = None  # Will be set by tools after API call

        # Store optional property ID from header
        if property_id_header and property_id_header.strip():
            request.state.user_analytics_property_id = property_id_header.strip()
            logger.debug(f"Property ID from header: {property_id_header.strip()}")
        else:
            request.state.user_analytics_property_id = None

        logger.debug(
            f"Token extracted successfully: {mask_sensitive(token, 8)}"
        )

        response = await call_next(request)
        return response
