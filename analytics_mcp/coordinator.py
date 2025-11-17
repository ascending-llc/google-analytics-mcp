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

"""Module declaring the singleton MCP instance.

The singleton allows other modules to register their tools with the same MCP
server using `@mcp.tool` annotations, thereby 'coordinating' the bootstrapping
of the server.

Includes OAuth middleware integration for per-user authentication.
"""
import os
import logging
from mcp.server.fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.applications import Starlette

from analytics_mcp.auth.mcp_session_middleware import MCPSessionMiddleware

logger = logging.getLogger(__name__)


def _get_http_host() -> str:
    """Returns the HTTP bind host for FastMCP."""
    return os.getenv("FASTMCP_HTTP_HOST", "127.0.0.1")


def _get_http_port() -> int:
    """Returns the HTTP bind port for FastMCP."""
    # Use port 3334 as default for Analytics MCP
    raw_port = os.getenv("FASTMCP_HTTP_PORT", "3334")
    try:
        return int(raw_port)
    except ValueError:
        return 3334


# Starlette middleware for session extraction
session_middleware = Middleware(MCPSessionMiddleware)


# Custom FastMCP that adds OAuth middleware stack
class SecureFastMCP(FastMCP):
    """
    Extended FastMCP with OAuth session middleware.

    Adds session extraction middleware to the Starlette HTTP app
    to enable per-user authentication.
    """

    def streamable_http_app(self) -> "Starlette":
        """Override to add OAuth session middleware stack."""
        app = super().streamable_http_app()

        # Add middleware in order (first added = outermost layer)
        # Session Management - extracts session info for MCP context
        app.user_middleware.insert(0, session_middleware)

        # Rebuild middleware stack
        app.middleware_stack = app.build_middleware_stack()
        logger.info("Added OAuth session middleware to Analytics MCP server")
        return app


# Creates the singleton with OAuth middleware
mcp = SecureFastMCP(
    "Google Analytics Server",
    host=_get_http_host(),
    port=_get_http_port(),
    streamable_http_path=os.getenv("FASTMCP_HTTP_PATH", "/mcp"),
)
