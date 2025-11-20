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

"""Test cases for the schema_fix utility module."""

import unittest
from unittest.mock import Mock, patch

from analytics_mcp.utils.schema_fix import (
    fix_additional_properties,
    patch_fastmcp_schemas,
)


class TestFixAdditionalProperties(unittest.TestCase):
    """Test cases for the fix_additional_properties function."""

    def test_fix_object_to_boolean(self):
        """Tests that additionalProperties object is converted to boolean."""
        schema = {
            "type": "object",
            "additionalProperties": {"type": "string"},
        }
        fixed = fix_additional_properties(schema)
        self.assertEqual(
            fixed["additionalProperties"],
            True,
            "Object additionalProperties should be converted to True",
        )

    def test_preserve_boolean_additional_properties(self):
        """Tests that boolean additionalProperties is preserved."""
        schema = {
            "type": "object",
            "additionalProperties": False,
        }
        fixed = fix_additional_properties(schema)
        self.assertEqual(
            fixed["additionalProperties"],
            False,
            "Boolean additionalProperties should be preserved",
        )

    def test_fix_nested_properties(self):
        """Tests that nested schemas in properties are fixed."""
        schema = {
            "type": "object",
            "properties": {
                "nested": {
                    "type": "object",
                    "additionalProperties": {"type": "number"},
                }
            },
        }
        fixed = fix_additional_properties(schema)
        self.assertEqual(
            fixed["properties"]["nested"]["additionalProperties"],
            True,
            "Nested additionalProperties should be fixed",
        )

    def test_fix_array_items_schema(self):
        """Tests that array items schemas are fixed."""
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": {"type": "string"},
            },
        }
        fixed = fix_additional_properties(schema)
        self.assertEqual(
            fixed["items"]["additionalProperties"],
            True,
            "Array items additionalProperties should be fixed",
        )

    def test_fix_array_items_list(self):
        """Tests that array items list schemas are fixed."""
        schema = {
            "type": "array",
            "items": [
                {"type": "object", "additionalProperties": {"type": "string"}},
                {"type": "object", "additionalProperties": {"type": "number"}},
            ],
        }
        fixed = fix_additional_properties(schema)
        self.assertEqual(
            fixed["items"][0]["additionalProperties"],
            True,
            "First array item additionalProperties should be fixed",
        )
        self.assertEqual(
            fixed["items"][1]["additionalProperties"],
            True,
            "Second array item additionalProperties should be fixed",
        )

    def test_fix_anyof_schemas(self):
        """Tests that anyOf schemas are fixed."""
        schema = {
            "anyOf": [
                {"type": "object", "additionalProperties": {"type": "string"}},
                {"type": "null"},
            ]
        }
        fixed = fix_additional_properties(schema)
        self.assertEqual(
            fixed["anyOf"][0]["additionalProperties"],
            True,
            "anyOf schema additionalProperties should be fixed",
        )

    def test_fix_allof_schemas(self):
        """Tests that allOf schemas are fixed."""
        schema = {
            "allOf": [
                {"type": "object", "additionalProperties": {"type": "string"}},
                {"required": ["foo"]},
            ]
        }
        fixed = fix_additional_properties(schema)
        self.assertEqual(
            fixed["allOf"][0]["additionalProperties"],
            True,
            "allOf schema additionalProperties should be fixed",
        )

    def test_fix_oneof_schemas(self):
        """Tests that oneOf schemas are fixed."""
        schema = {
            "oneOf": [
                {"type": "object", "additionalProperties": {"type": "string"}},
                {"type": "array"},
            ]
        }
        fixed = fix_additional_properties(schema)
        self.assertEqual(
            fixed["oneOf"][0]["additionalProperties"],
            True,
            "oneOf schema additionalProperties should be fixed",
        )

    def test_schema_without_additional_properties(self):
        """Tests that schemas without additionalProperties are unchanged."""
        schema = {"type": "object", "properties": {"foo": {"type": "string"}}}
        fixed = fix_additional_properties(schema)
        self.assertNotIn(
            "additionalProperties",
            fixed,
            "Schema without additionalProperties should remain unchanged",
        )

    def test_non_dict_schema(self):
        """Tests that non-dict values are returned unchanged."""
        schema = "not a dict"
        fixed = fix_additional_properties(schema)
        self.assertEqual(
            fixed, schema, "Non-dict schemas should be returned unchanged"
        )

    def test_complex_nested_structure(self):
        """Tests fixing a complex nested schema structure."""
        schema = {
            "type": "object",
            "properties": {
                "data": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": {"type": "string"},
                        },
                    },
                }
            },
        }
        fixed = fix_additional_properties(schema)
        self.assertEqual(
            fixed["properties"]["data"]["additionalProperties"],
            True,
            "Top-level nested additionalProperties should be fixed",
        )


class TestPatchFastMCPSchemas(unittest.TestCase):
    """Test cases for the patch_fastmcp_schemas function."""

    @patch("analytics_mcp.utils.schema_fix.fix_additional_properties")
    def test_patch_applies_to_tool_class(self, mock_fix):
        """Tests that the patch is applied to the Tool class."""
        # Create a mock Tool class with to_mcp_tool method
        mock_tool_class = Mock()
        original_to_mcp_tool = Mock(return_value={"name": "test_tool"})
        mock_tool_class.to_mcp_tool = original_to_mcp_tool

        # Create a mock tool instance
        mock_tool_instance = Mock()
        mock_tool_instance.name = "test_tool"
        mock_tool_instance.parameters = {"type": "object"}
        mock_tool_instance.output_schema = {"type": "object"}

        # Mock the import to return our mock Tool class
        with patch.dict(
            "sys.modules",
            {"fastmcp.tools": Mock(Tool=mock_tool_class)},
        ):
            # Apply the patch
            mock_mcp = Mock()
            patch_fastmcp_schemas(mock_mcp)

            # Verify the method was replaced
            self.assertNotEqual(
                mock_tool_class.to_mcp_tool,
                original_to_mcp_tool,
                "to_mcp_tool should be replaced",
            )

    def test_patch_handles_import_failure_gracefully(self):
        """Tests that patch handles import failures gracefully."""
        # Mock all import paths to fail
        with patch.dict("sys.modules", {"fastmcp": None, "fastmcp.tools": None}):
            mock_mcp = Mock()
            # Should not raise an exception
            patch_fastmcp_schemas(mock_mcp)

    @patch("analytics_mcp.utils.schema_fix.fix_additional_properties")
    def test_patched_method_fixes_parameters(self, mock_fix):
        """Tests that the patched method fixes parameters schema."""
        mock_fix.side_effect = lambda x: x  # Return input unchanged

        # Create a mock Tool class
        mock_tool_class = Mock()
        original_to_mcp_tool = Mock(return_value={"name": "test_tool"})
        mock_tool_class.to_mcp_tool = original_to_mcp_tool

        # Mock the import
        with patch.dict(
            "sys.modules",
            {"fastmcp.tools": Mock(Tool=mock_tool_class)},
        ):
            mock_mcp = Mock()
            patch_fastmcp_schemas(mock_mcp)

            # Create a tool instance and call the patched method
            mock_tool = Mock()
            mock_tool.name = "test_tool"
            mock_tool.parameters = {"type": "object", "properties": {}}
            mock_tool.output_schema = None

            # Call the patched method
            mock_tool_class.to_mcp_tool(mock_tool)

            # Verify fix_additional_properties was called with parameters
            self.assertTrue(
                mock_fix.called,
                "fix_additional_properties should be called",
            )

    @patch("analytics_mcp.utils.schema_fix.fix_additional_properties")
    def test_patched_method_fixes_output_schema(self, mock_fix):
        """Tests that the patched method fixes output_schema."""
        mock_fix.side_effect = lambda x: x  # Return input unchanged

        # Create a mock Tool class
        mock_tool_class = Mock()
        original_to_mcp_tool = Mock(return_value={"name": "test_tool"})
        mock_tool_class.to_mcp_tool = original_to_mcp_tool

        # Mock the import
        with patch.dict(
            "sys.modules",
            {"fastmcp.tools": Mock(Tool=mock_tool_class)},
        ):
            mock_mcp = Mock()
            patch_fastmcp_schemas(mock_mcp)

            # Create a tool instance and call the patched method
            mock_tool = Mock()
            mock_tool.name = "test_tool"
            mock_tool.parameters = None
            mock_tool.output_schema = {
                "type": "object",
                "additionalProperties": {"type": "string"},
            }

            # Call the patched method
            mock_tool_class.to_mcp_tool(mock_tool)

            # Verify fix_additional_properties was called
            self.assertTrue(
                mock_fix.called,
                "fix_additional_properties should be called",
            )

    def test_patch_is_idempotent(self):
        """Tests that calling patch_fastmcp_schemas multiple times is safe."""
        # Create a mock Tool class
        mock_tool_class = Mock()
        original_to_mcp_tool = Mock(return_value={"name": "test_tool"})
        mock_tool_class.to_mcp_tool = original_to_mcp_tool

        # Mock the import
        with patch.dict(
            "sys.modules",
            {"fastmcp.tools": Mock(Tool=mock_tool_class)},
        ):
            mock_mcp = Mock()

            # Apply patch first time
            patch_fastmcp_schemas(mock_mcp)
            first_patched_method = mock_tool_class.to_mcp_tool

            # Verify it was patched
            self.assertNotEqual(
                first_patched_method,
                original_to_mcp_tool,
                "Method should be patched",
            )
            self.assertTrue(
                getattr(first_patched_method, "__schema_fix_patched__", False),
                "Patched method should have marker attribute",
            )

            # Apply patch second time
            patch_fastmcp_schemas(mock_mcp)
            second_patched_method = mock_tool_class.to_mcp_tool

            # Verify it's still the same patched method (not double-wrapped)
            self.assertEqual(
                first_patched_method,
                second_patched_method,
                "Method should not be double-wrapped",
            )
