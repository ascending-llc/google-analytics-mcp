#!/usr/bin/env python

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

"""Entry point for the Google Analytics MCP server."""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastmcp import FastMCP
from fastmcp.server.http import StarletteWithLifespan
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from analytics_mcp.config import AnalyticsConfig
from analytics_mcp.context import AppContext
from analytics_mcp.coordinator import mcp
from analytics_mcp.utils.user_token_middleware import UserTokenMiddleware

# The following imports are necessary to register the tools with the `mcp`
# object, even though they are not directly used in this file.
from analytics_mcp.tools.admin import info  # noqa: F401
from analytics_mcp.tools.reporting import realtime  # noqa: F401
from analytics_mcp.tools.reporting import core  # noqa: F401

logger = logging.getLogger("analytics-mcp.server")

# Google OAuth token forwarding from Jarvis
# Jarvis manages OAuth flow and forwards tokens via Authorization header
# No configuration needed here - just extract tokens in middleware


async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for Kubernetes probes."""
    logger.debug("Health check endpoint called.")
    return JSONResponse({"status": "ok"})


@asynccontextmanager
async def analytics_lifespan(
    app: FastMCP[AppContext],
) -> AsyncIterator[dict]:
    """Lifespan context manager for Analytics MCP server.

    Handles server startup and shutdown logic, including loading
    configuration from environment variables.
    """
    logger.info("Analytics MCP server lifespan starting...")

    # Load configuration (if any server-level config exists)
    # For pure user-token mode, this might be minimal
    try:
        analytics_config = AnalyticsConfig.from_env()
        logger.info("Analytics configuration loaded from environment")
    except Exception as e:
        logger.info(
            f"No server-level Analytics config found (expected for user-token mode): {e}"
        )
        analytics_config = None

    read_only = os.getenv("ANALYTICS_READ_ONLY", "false").lower() == "true"

    app_context = AppContext(
        analytics_config=analytics_config,
        read_only=read_only,
    )

    logger.info(f"Read-only mode: {'ENABLED' if read_only else 'DISABLED'}")

    try:
        yield {"app_lifespan_context": app_context}
    except Exception as e:
        logger.error(f"Error during lifespan: {e}", exc_info=True)
        raise
    finally:
        logger.info("Analytics MCP server lifespan shutting down...")
        logger.info("Analytics MCP server lifespan shutdown complete.")


# Configure the MCP server with lifespan
mcp._lifespan = analytics_lifespan


# Override the http_app method to add middleware
_original_http_app = mcp.http_app


def http_app_with_middleware(
    path: str | None = None,
    middleware: list[Middleware] | None = None,
    json_response: bool | None = None,
    transport: Literal["streamable-http", "sse", "http"] = "streamable-http",
) -> StarletteWithLifespan:
    """Create HTTP app with UserTokenMiddleware for token extraction.

    UserTokenMiddleware extracts Google OAuth tokens from Authorization header.
    Jarvis manages the OAuth flow and automatically forwards tokens.
    """
    user_token_mw = Middleware(UserTokenMiddleware)
    final_middleware_list = [user_token_mw]
    if middleware:
        final_middleware_list.extend(middleware)

    return _original_http_app(
        path=path,
        middleware=final_middleware_list,
        json_response=json_response,
        stateless_http=False,  # Enable stateful sessions for persistent SSE
        transport=transport,
    )


mcp.http_app = http_app_with_middleware


@mcp.custom_route("/health", methods=["GET"], include_in_schema=False)
async def _health_check_route(request: Request) -> JSONResponse:
    """Health check route for Kubernetes liveness/readiness probes."""
    return await health_check(request)


logger.info("Added /health endpoint for Kubernetes probes")


def main() -> None:
    """Runs the MCP server using HTTP transport."""
    # Always use HTTP transport for token-based authentication
    transport = os.getenv("MCP_TRANSPORT", "streamable-http")
    host = os.getenv("FASTMCP_HTTP_HOST", "0.0.0.0")
    port = int(os.getenv("FASTMCP_HTTP_PORT", "3334"))
    logger.info(f"Starting Analytics MCP server with transport: {transport} on {host}:{port}")
    mcp.run(transport=transport, host=host, port=port)


def run_server() -> None:
    """Runs the server.

    Serves as the entrypoint for the 'runmcp' command.
    """
    main()


if __name__ == "__main__":
    run_server()
