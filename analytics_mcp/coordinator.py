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
import os
from mcp.server.fastmcp import FastMCP


def _get_http_host() -> str:
    """Returns the HTTP bind host for FastMCP."""
    return os.getenv("FASTMCP_HTTP_HOST", "127.0.0.1")


def _get_http_port() -> int:
    """Returns the HTTP bind port for FastMCP."""
    raw_port = os.getenv("FASTMCP_HTTP_PORT", "8000")
    try:
        return int(raw_port)
    except ValueError:
        return 8000


# Creates the singleton.
mcp = FastMCP(
    "Google Analytics Server",
    host=_get_http_host(),
    port=_get_http_port(),
    streamable_http_path=os.getenv("FASTMCP_HTTP_PATH", "/mcp"),
)
