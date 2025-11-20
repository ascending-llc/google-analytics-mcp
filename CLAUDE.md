# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Model Context Protocol (MCP) server for Google Analytics that provides tools for LLMs to interact with Google Analytics Admin API and Data API. The server is built using Python 3.10+ and the FastMCP framework.

## Development Commands

### Setup
```bash
# Install development dependencies
pip install -e .[dev]
```

### Testing
```bash
# Run tests for all supported Python versions (3.10, 3.11, 3.12, 3.13)
nox -s tests*

# Run tests for a specific Python version
nox -s tests-3.12
```

### Code Formatting
```bash
# Format code with black (80 character line width, PEP 8 compliant)
nox -s format

# Check formatting without applying changes
nox -s lint
```

### Local Testing with Gemini
To test changes locally, update `~/.gemini/settings.json`:
```json
{
  "mcpServers": {
    "analytics-mcp": {
      "command": "/path/to/repo/.venv/bin/analytics-mcp",
      "env": {
        "GOOGLE_APPLICATION_CREDENTIALS": "PATH_TO_CREDENTIALS_JSON",
        "GOOGLE_PROJECT_ID": "YOUR_PROJECT_ID"
      }
    }
  }
}
```

Run Gemini CLI with debug mode:
```bash
gemini --debug
```

## Architecture

### MCP Server Pattern
The codebase uses a **singleton coordinator pattern** for tool registration:

1. **Coordinator** (`analytics_mcp/coordinator.py`): Creates a singleton `FastMCP` instance named "Google Analytics Server"
2. **Server Entry Point** (`analytics_mcp/server.py`): Imports tool modules to trigger registration via `@mcp.tool()` decorators, then calls `mcp.run()`
3. **Tool Modules**: Register tools with the singleton by importing `from analytics_mcp.coordinator import mcp` and using `@mcp.tool()` decorators

### Tool Organization
Tools are organized by API type:
- **Admin Tools** (`analytics_mcp/tools/admin/info.py`): Account summaries, property details, Google Ads links, property annotations
- **Reporting Tools** (`analytics_mcp/tools/reporting/`):
  - `core.py`: Core reporting via Data API (`run_report`)
  - `realtime.py`: Realtime reports
  - `metadata.py`: Custom dimensions/metrics retrieval and filter hints

### API Client Creation
All API clients are created via utilities in `analytics_mcp/tools/utils.py`:
- `create_admin_api_client()`: Returns `admin_v1beta.AnalyticsAdminServiceAsyncClient`
- `create_admin_alpha_api_client()`: Returns `admin_v1alpha.AnalyticsAdminServiceAsyncClient`
- `create_data_api_client()`: Returns `data_v1beta.BetaAnalyticsDataAsyncClient`

All clients use Application Default Credentials with `analytics.readonly` scope and custom user agent tracking.

### Key Utilities
- `construct_property_rn(property_id)`: Normalizes property IDs to `properties/{number}` format
- `proto_to_dict(obj)`: Converts protobuf messages to dictionaries with snake_case field names
- `proto_to_json(obj)`: Converts protobuf messages to JSON strings

## Important Conventions

### Adding New Tools
1. Create tool function in appropriate module under `analytics_mcp/tools/`
2. Import `from analytics_mcp.coordinator import mcp`
3. Decorate with `@mcp.tool()` or use `mcp.add_tool()` for complex descriptions
4. Import the module in `analytics_mcp/server.py` (with `# noqa: F401` to suppress unused import warnings)
5. Use async functions and async API clients throughout

### API Field Names
- REST API docs use camelCase, but this server uses **snake_case** (protobuf format)
- All date ranges, filters, and order_bys should use snake_case field names
- Reference protobuf definitions at https://github.com/googleapis/googleapis/tree/master/google/analytics/data/v1beta

### Code Style
- PEP 8 compliant with **80 character line width**
- Use `black` formatter (enforced via `nox -s lint`)
- All contributions require CLA signature (https://cla.developers.google.com/)

### Testing
- Tests live in `tests/` directory with `*_test.py` naming
- Use `pyfakefs` for filesystem mocking
- Coverage tracking via `coverage` module
- Tests must pass for Python 3.10, 3.11, 3.12, and 3.13
