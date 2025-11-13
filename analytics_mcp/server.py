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

import os

from analytics_mcp.coordinator import mcp

# The following imports are necessary to register the tools with the `mcp`
# object, even though they are not directly used in this file.
# The `# noqa: F401` comment tells the linter to ignore the "unused import"
# warning.
from analytics_mcp.tools.admin import info  # noqa: F401
from analytics_mcp.tools.reporting import realtime  # noqa: F401
from analytics_mcp.tools.reporting import core  # noqa: F401


def main() -> None:
    """Runs the MCP server using the FastMCP transports."""
    transport = os.getenv("MCP_TRANSPORT", "streamable-http")

    if transport == "streamable-http":
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


def run_server() -> None:
    """Runs the server.

    Serves as the entrypoint for the 'runmcp' command.
    """
    main()


if __name__ == "__main__":
    run_server()
