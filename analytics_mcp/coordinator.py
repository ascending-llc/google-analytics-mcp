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
"""

import logging

from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware

from analytics_mcp.context import AppContext
from analytics_mcp.utils.user_token_middleware import UserTokenMiddleware

logger = logging.getLogger("analytics-mcp.coordinator")

# Middleware for token extraction
token_middleware = Middleware(UserTokenMiddleware)


# Custom FastMCP class that overrides streamable_http_app to add middleware
class AnalyticsFastMCP(FastMCP[AppContext]):
    """FastMCP subclass that adds UserTokenMiddleware to streamable-http transport."""

    def streamable_http_app(self) -> "Starlette":
        """Override to add UserTokenMiddleware for token extraction."""
        app = super().streamable_http_app()

        # Add token middleware (first added = outermost layer)
        app.user_middleware.insert(0, token_middleware)

        # Rebuild middleware stack
        app.middleware_stack = app.build_middleware_stack()
        logger.info("Added UserTokenMiddleware to streamable-http app")
        return app


# Creates the singleton MCP server instance
# The middleware is configured in streamable_http_app() override above
mcp = AnalyticsFastMCP("Google Analytics Server")
