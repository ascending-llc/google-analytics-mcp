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

"""Middleware to extract and verify Google OAuth tokens from Authorization headers."""

import json
import logging
from typing import Any

from fastmcp.server.auth.providers.jwt import JWTVerifier
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("analytics-mcp.user_token_middleware")


def mask_sensitive(value: str, visible_chars: int = 4) -> str:
    """Mask sensitive values for logging."""
    if not value or len(value) <= visible_chars:
        return "***"
    return f"...{value[-visible_chars:]}"


class UserTokenMiddleware(BaseHTTPMiddleware):
    """Middleware to extract Google OAuth user tokens from Authorization headers and verify JWT."""

    def __init__(
        self,
        app: Any,
        *,
        jwks_uri: str,
        issuer: str,
        audience: str,
        algorithm: str = "RS256",
    ) -> None:
        super().__init__(app)
        self.token_verifier = JWTVerifier(
            jwks_uri=jwks_uri,
            issuer=issuer,
            audience=audience,
            algorithm=algorithm,
        )

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> JSONResponse:
        logger.debug(
            f"UserTokenMiddleware.dispatch: ENTERED for request path='{request.url.path}', method='{request.method}'"
        )
        request_path = request.url.path
        logger.info(f"JWT Auth Middleware processing path: {request_path}")

        # Skip auth for health check
        if request.url.path == "/health":
            return await call_next(request)

        if request.method == "POST" or request.method == "HEAD":
            auth_header = request.headers.get("authorization")
            property_id_header = request.headers.get("X-Analytics-Property-Id")

            logger.debug(
                f"UserTokenMiddleware: Full request - Method: {request.method}, URL: {request.url}"
            )
            logger.debug(
                f"UserTokenMiddleware: Request headers: {dict(request.headers)}"
            )

            try:
                body = await request.body()
                logger.debug(f"UserTokenMiddleware: Request body: {body!r}")
                request._body = body  # Reset body for downstream handlers

                # Check if this is an MCP protocol method that doesn't need auth
                if body:
                    try:
                        request_data = json.loads(body.decode())
                        method = request_data.get("method")
                        if method in [
                            "ping",
                            "tools/list",
                            "prompts/list",
                            "resources/list",
                        ]:
                            logger.debug(
                                f"UserTokenMiddleware: Allowing MCP protocol method '{method}' without auth"
                            )
                            response = await call_next(request)
                            logger.debug(
                                f"UserTokenMiddleware.dispatch: EXITED for MCP method '{method}'"
                            )
                            return response
                    except (json.JSONDecodeError, UnicodeDecodeError) as e:
                        logger.debug(
                            f"UserTokenMiddleware: Could not parse request body as JSON: {e}"
                        )

            except Exception as e:
                logger.warning(f"UserTokenMiddleware: Failed to read request body: {e}")

            if not auth_header:
                logger.debug(
                    f"UserTokenMiddleware: Path='{request.url.path}', no auth header provided"
                )
                return JSONResponse(
                    content={
                        "error": "Unauthorized: Empty Authorization Header",
                        "code": 401,
                    },
                    status_code=401,
                )

            token_for_log = mask_sensitive(
                auth_header.split(" ", 1)[1].strip()
                if auth_header and " " in auth_header
                else auth_header
            )
            logger.debug(
                f"UserTokenMiddleware: Path='{request.url.path}', AuthHeader='{mask_sensitive(auth_header)}', ParsedToken(masked)='{token_for_log}', PropertyId='{property_id_header}'"
            )

            # Extract and save property ID if provided
            if property_id_header and property_id_header.strip():
                request.state.user_analytics_property_id = property_id_header.strip()
                logger.debug(
                    f"UserTokenMiddleware: Extracted property ID from header: {property_id_header.strip()}"
                )
            else:
                request.state.user_analytics_property_id = None
                logger.debug(
                    "UserTokenMiddleware: No property ID header provided"
                )

            # Check for mcp-session-id header for debugging
            mcp_session_id = request.headers.get("mcp-session-id")
            if mcp_session_id:
                logger.debug(
                    f"UserTokenMiddleware: MCP-Session-ID header found: {mcp_session_id}"
                )

            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ", 1)[1].strip()
                if not token:
                    return JSONResponse(
                        {"error": "Unauthorized: Empty Bearer token"},
                        status_code=401,
                    )
                logger.debug(
                    f"UserTokenMiddleware.dispatch: Bearer token extracted (masked): ...{mask_sensitive(token, 8)}"
                )
                # JWT verification
                try:
                    access_token = await self.token_verifier.verify_token(token)

                    # Check if token verification failed (returns None for expired/invalid tokens)
                    if access_token is None:
                        logger.warning(
                            "Token verification failed: token is invalid or expired"
                        )
                        return JSONResponse(
                            {"error": "Unauthorized: Invalid or expired token"},
                            status_code=401,
                        )

                    request.state.user_google_token = token
                    request.state.user_google_auth_type = "oauth"
                    request.state.user_email = (
                        access_token.claims.get("email") if access_token else None
                    )
                    logger.debug(
                        f"UserTokenMiddleware.dispatch: JWT verified, email={getattr(request.state, 'user_email', None)}"
                    )
                except Exception as e:
                    logger.warning(f"JWT verification failed: {e}")
                    return JSONResponse(
                        {"error": "Unauthorized: Invalid JWT token"},
                        status_code=401,
                    )
            elif auth_header:
                logger.warning(
                    f"Unsupported Authorization type for {request_path}: {auth_header.split(' ', 1)[0] if ' ' in auth_header else 'UnknownType'}"
                )
                return JSONResponse(
                    {
                        "error": "Unauthorized: Only 'Bearer <OAuthToken>' type is supported."
                    },
                    status_code=401,
                )
            else:
                logger.debug(
                    f"No Authorization header provided for {request_path}. Request will be rejected."
                )

        response = await call_next(request)
        logger.debug(
            f"UserTokenMiddleware.dispatch: EXITED for request path='{request_path}'"
        )
        return response
