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
from starlette.applications import Starlette
from starlette.middleware import Middleware
from fastmcp import FastMCP

from analytics_mcp.context import AppContext
from analytics_mcp.utils.user_token_middleware import UserTokenMiddleware

logger = logging.getLogger("analytics-mcp.coordinator")

# Custom FastMCP that adds UserTokenMiddleware for OAuth token extraction
class AnalyticsFastMCP(FastMCP):
    def streamable_http_app(self) -> Starlette:
        """Override to add UserTokenMiddleware for OAuth token extraction."""
        print("[ANALYTICS-MCP] Creating streamable HTTP app with middleware", flush=True)
        logger.info("Creating streamable HTTP app with middleware")

        app = super().streamable_http_app()

        # Add UserTokenMiddleware using Google Workspace pattern
        user_token_mw = Middleware(UserTokenMiddleware)
        app.user_middleware.insert(0, user_token_mw)

        # Rebuild middleware stack
        app.middleware_stack = app.build_middleware_stack()

        print(f"[ANALYTICS-MCP] Added UserTokenMiddleware - total middleware: {len(app.user_middleware)}", flush=True)
        logger.info(f"Added UserTokenMiddleware - total middleware: {len(app.user_middleware)}")
        return app

# Creates the singleton MCP server instance
# The actual server configuration (middleware, lifespan) happens in server.py
mcp = AnalyticsFastMCP[AppContext]("Google Analytics Server")
