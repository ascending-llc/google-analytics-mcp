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
from typing import Literal

from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware

from analytics_mcp.context import AppContext
from analytics_mcp.utils.user_token_middleware import UserTokenMiddleware

logger = logging.getLogger("analytics-mcp.coordinator")

# Middleware for token extraction
token_middleware = Middleware(UserTokenMiddleware)


# Custom FastMCP class that overrides http_app to add middleware correctly
class AnalyticsFastMCP(FastMCP[AppContext]):
    """FastMCP subclass that injects UserTokenMiddleware via http_app override."""

    def http_app(
        self,
        path: str | None = None,
        middleware: list[Middleware] | None = None,
        json_response: bool | None = None,
        stateless_http: bool | None = None,
        transport: Literal["http", "streamable-http", "sse"] = "http",
    ) -> "Starlette":
        """Override to inject UserTokenMiddleware using FastMCP's supported pattern."""
        final_middleware: list[Middleware] = [token_middleware]
        if middleware:
            final_middleware.extend(middleware)

        logger.info(
            "AnalyticsFastMCP.http_app configuring transport",
            extra={
                "path": path or "(default)",
                "transport": transport,
                "stateless": stateless_http,
                "json_response": json_response,
                "middleware_count": len(final_middleware),
            },
        )

        app = super().http_app(
            path=path,
            middleware=final_middleware,
            json_response=json_response,
            stateless_http=stateless_http,
            transport=transport,
        )
        logger.info("Configured http_app with UserTokenMiddleware")
        return app


# Creates the singleton MCP server instance
mcp = AnalyticsFastMCP("Google Analytics Server")

# Apply schema patch to work around FastMCP 2.13.0.2 bug where additionalProperties
# is generated as an object instead of a boolean
# See: https://github.com/jlowin/fastmcp/issues/2459
from analytics_mcp.utils.schema_patch import patch_fastmcp_schemas

patch_fastmcp_schemas(mcp)
logger.info("Applied FastMCP schema patch for additionalProperties")
