# Changelog

All notable changes to the Google Analytics MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

### Added
- **Schema Fix Utility** (2025-11-20)
  - Added `analytics_mcp/utils/schema_fix.py` to fix FastMCP 2.13.0.2 invalid JSON schema generation
  - Monkey-patches `Tool.to_mcp_tool()` to convert invalid `additionalProperties` objects to boolean
  - Fixes Zod validation errors in MCP SDK clients
  - Comprehensive test coverage in `tests/schema_fix_test.py` (15 test cases)
  - Structured logging with extra context for debugging
  - Related commit: `40d55ec`

- **Test Coverage** (2025-11-20)
  - Added comprehensive unit tests for schema fix utility
  - Tests cover nested schemas, arrays, anyOf/allOf/oneOf, and edge cases
  - All 15 tests passing

### Changed
- **Middleware Refactoring** (2025-11-18 - 2025-11-19)
  - Refactored to use custom `AnalyticsFastMCP` 
  - Overrides `http_app()` method to inject `UserTokenMiddleware` cleanly
  - Fixed SSE streaming issues by removing body reading from middleware
  - Simplified token extraction to use Jarvis authorization headers
  - Enhanced logging with structured context throughout middleware
  - Related commits: `2a4929d`, `3441577`, `1539a0d`, `920c001`, `39f384a`, `a90aa2d`

- **Authentication Architecture** (2025-11-17 - 2025-11-18)
  - Implemented JWT token middleware authentication pattern
  - Migrated from OAuth decorator pattern to middleware-based per-user authentication
  - Refactored API client creation to use dependency injection via FastMCP context
  - All tools now receive user-specific clients via `get_analytics_data_client(ctx)` and `get_analytics_admin_client(ctx)`
  - Removed service decorator pattern in favor of middleware approach
  - Related commits: `2adcefc`, `2671df5`, `1c6b5a1`

### Fixed
- **Kubernetes Configuration** (2025-11-17)
  - Fixed K8s port parsing issues
  - Related commit: `6043d7f`

- **Docker Build** (2025-11-19)
  - Added Python bytecode cleanup in Dockerfile to reduce image size
  - Related commit: `337bf29`

### Infrastructure
- **Docker Support** (2025-11-13)
  - Initial Dockerfile creation for containerized deployment
  - Support for `streamable-http` transport mode
  - Health check endpoint for Kubernetes probes
  - Related commit: `d438ec4`

- **CI/CD** (2025-11-17)
  - Added GitHub Actions workflow
  - Related commit: `4b2a8d9`

- **OAuth Integration** (2025-11-17)
  - Configured OAuth for Google Workspace with GA4
  - Simplified OAuth flow focused on Analytics scopes
  - Related commit: `6b2d2e8`

## [0.26.0] - 2025-10-27

### Changed
- Updated `google-analytics-admin` dependency to v0.26.0
- Updated `google-analytics-data` dependency to v0.19.0
