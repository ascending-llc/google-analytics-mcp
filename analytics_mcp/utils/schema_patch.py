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

"""Patch to fix FastMCP's invalid JSON schema generation.

**Why this patch is needed:**
FastMCP 2.13.0.2 generates invalid JSON schemas where `additionalProperties`
is an object instead of a boolean. This violates the JSON Schema specification
(https://json-schema.org/understanding-json-schema/reference/object.html#additional-properties)
and causes Zod validation errors in MCP SDK clients, preventing tools from appearing.

**What this patch does:**
Monkey-patches FastMCP's `Tool.to_mcp_tool()` method to recursively convert
invalid `additionalProperties` objects to boolean `true` before schemas are
sent to the client.

**Tracking:**
This workaround addresses the issue reported in:
https://github.com/jlowin/fastmcp/issues/2459

This patch can be removed once upgrading to a FastMCP version that generates
valid JSON schemas.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger("analytics-mcp.schema_patch")


def fix_additional_properties(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively fix additionalProperties in a JSON Schema.

    Converts additionalProperties from object format to boolean:
    - {"additionalProperties": {"type": "...", ...}} -> {"additionalProperties": True}
    - Recursively processes nested schemas in objects and arrays

    Args:
        schema: JSON Schema dictionary to fix

    Returns:
        Fixed schema with boolean additionalProperties
    """
    if not isinstance(schema, dict):
        return schema

    # Create a copy to avoid mutating the original
    fixed = schema.copy()

    # Fix additionalProperties if it's an object (should be boolean)
    if "additionalProperties" in fixed:
        additional_props = fixed["additionalProperties"]
        if isinstance(additional_props, dict):
            # Convert object to boolean True (allow any additional properties)
            fixed["additionalProperties"] = True
            logger.debug(
                "Fixed additionalProperties in schema",
                extra={
                    "original_type": "object",
                    "fixed_type": "boolean",
                    "original_value": str(additional_props)[:100],
                },
            )

    # Recursively fix nested schemas in properties
    if "properties" in fixed and isinstance(fixed["properties"], dict):
        fixed["properties"] = {
            key: fix_additional_properties(value)
            for key, value in fixed["properties"].items()
        }

    # Recursively fix array item schemas
    if "items" in fixed:
        if isinstance(fixed["items"], dict):
            fixed["items"] = fix_additional_properties(fixed["items"])
        elif isinstance(fixed["items"], list):
            fixed["items"] = [
                fix_additional_properties(item) for item in fixed["items"]
            ]

    # Recursively fix anyOf, allOf, oneOf
    for key in ["anyOf", "allOf", "oneOf"]:
        if key in fixed and isinstance(fixed[key], list):
            fixed[key] = [
                fix_additional_properties(item) for item in fixed[key]
            ]

    return fixed


def patch_fastmcp_schemas(mcp_instance):
    """Monkey-patch FastMCP Tool.to_mcp_tool to fix output schemas.

    This wraps the Tool.to_mcp_tool method which converts Tool objects to
    MCPTool format with schemas before they're sent to the MCP client.

    Args:
        mcp_instance: The FastMCP instance to patch (unused, but kept for API compatibility)
    """
    # Import the Tool class - try multiple import paths
    Tool = None
    try:
        from fastmcp.tools import Tool as ToolClass
        Tool = ToolClass
        logger.debug("Imported Tool from fastmcp.tools")
    except (ImportError, AttributeError):
        try:
            import fastmcp.tools.tool as tool_module
            Tool = tool_module.Tool
            logger.debug("Imported Tool from fastmcp.tools.tool")
        except (ImportError, AttributeError):
            try:
                from fastmcp import Tool as ToolClass
                Tool = ToolClass
                logger.debug("Imported Tool from fastmcp directly")
            except (ImportError, AttributeError):
                logger.warning(
                    "Could not import Tool class from fastmcp. "
                    "Schema patching skipped."
                )
                return

    if Tool is None:
        logger.warning("Tool class is None. Schema patching skipped.")
        return

    # Check if already patched to avoid double-wrapping
    if getattr(Tool.to_mcp_tool, "__schema_fix_patched__", False):
        logger.debug("Tool.to_mcp_tool already patched, skipping")
        return

    # Store the original to_mcp_tool method
    original_to_mcp_tool = Tool.to_mcp_tool

    def patched_to_mcp_tool(self, **kwargs):
        """Wrapped to_mcp_tool that fixes schemas before conversion."""
        # Fix the schemas on the Tool object before conversion
        if hasattr(self, "parameters") and self.parameters:
            self.parameters = fix_additional_properties(self.parameters)

        if hasattr(self, "output_schema") and self.output_schema:
            self.output_schema = fix_additional_properties(self.output_schema)
            logger.debug(
                "Fixed output_schema for tool",
                extra={"tool_name": self.name},
            )

        # Call the original method
        return original_to_mcp_tool(self, **kwargs)

    # Mark the patched method to prevent double-wrapping
    patched_to_mcp_tool.__schema_fix_patched__ = True

    # Replace the method on the Tool class
    Tool.to_mcp_tool = patched_to_mcp_tool
    logger.info(
        "FastMCP schema patching enabled",
        extra={"patched_method": "Tool.to_mcp_tool"},
    )
