# Multi-Account Google Analytics MCP Server - Implementation Plan

## Executive Summary

This document outlines the detailed implementation plan to transform the single-account Google Analytics MCP server into a multi-account system supporting multiple GA4 dealer accounts for regional benchmarking and vehicle interest analysis.

**Goal**: Enable querying multiple GA4 accounts simultaneously for dealer benchmarking and comparative analytics, deployed on client infrastructure using Docker containers.

**Reference Architecture**: Based on aws-mcp-cloudwatch multi-account patterns, adapted for Google OAuth2 authentication.

---

## Business Use Cases

### Use Case 1: Dealer Benchmarking
**Question**: "How is my website performing relative to the region?"

**Requirements**:
- Query multiple dealer GA4 accounts simultaneously
- Compare: sessions, qualified sessions, form_submit events, traffic sources, landing pages
- Calculate regional averages and performance indices
- Identify over/under-performing metrics vs. peer set

**Example Outputs**:
- Trend comparison: Dealer A traffic vs. regional average
- Source/medium breakdown: Dealer A vs. region
- Landing page performance: Which pages over/under-perform

### Use Case 2: Vehicle Interest Analysis
**Question**: "Which models are consumers most engaged with across dealer websites?"

**Requirements**:
- Aggregate data across all dealer GA4 properties
- Track: sessions, duration, bounce rates by vehicle model
- Analyze: form submissions by model, VDP engagement
- Identify trends: week-over-week model interest shifts

**Example Outputs**:
- Top models by region and engagement
- Category breakdown (SUV/Truck/Sedan/EV) interest share
- Lead conversion by model (high traffic vs. low conversion signals)

---

## Technical Architecture Overview

### Current State
```
┌─────────────────────────────────────┐
│   User (Gemini CLI/Code Assist)    │
└──────────────┬──────────────────────┘
               │ stdio (single process)
               ↓
┌─────────────────────────────────────┐
│   Google Analytics MCP Server       │
│   - Single account ADC auth         │
│   - Stdio transport                 │
└──────────────┬──────────────────────┘
               │ ADC (single account)
               ↓
┌─────────────────────────────────────┐
│   Google Analytics API              │
│   - Single GA4 property             │
└─────────────────────────────────────┘
```

### Target State
```
┌─────────────────────────────────────┐
│   Jarvis (LibreChat Client)        │
│   http://analytics-mcp:3334/mcp    │
└──────────────┬──────────────────────┘
               │ streamable-http
               │ OAuth Bearer Token
               ↓
┌─────────────────────────────────────┐
│   Google Analytics MCP Server       │
│   - Multi-account credential broker │
│   - OAuth2 token management         │
│   - HTTP transport                  │
└──────────────┬──────────────────────┘
               │ Multiple OAuth2 tokens
               ├──────┬──────┬─────────┐
               ↓      ↓      ↓         ↓
        Dealer 1  Dealer 2  Dealer 3  ...
        GA4 API   GA4 API   GA4 API
```

---

## Implementation Phases
## Phase 1: Containerization & Base Infrastructure

### 1.1 Create Dockerfile
**File**: `/Dockerfile`

**Purpose**: Multi-stage Docker build for efficient image size and security

**Key Features**:
- Python 3.10 alpine base (minimal size)
- Multi-stage build (builder + runtime)
- uv package manager for fast dependency installation
- Non-root user (security best practice)
- Expose port 3334 for HTTP transport

**Testing**:
```bash
# Build image
docker build -t analytics-mcp:latest .

# Run locally
docker run -p 3334:3334 \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/creds.json \
  analytics-mcp:latest
```

---

### 1.2 Update pyproject.toml
**File**: `/pyproject.toml`

**Changes Required**:
1. Add HTTP transport dependencies:
   ```toml
   dependencies = [
       "google-analytics-data==0.19.0",
       "google-analytics-admin==0.26.0",
       "google-auth~=2.40",
       "mcp[cli]>=1.2.0",
       "httpx>=0.28.1",
       "uvicorn>=0.30.0",        # NEW: HTTP server
       "starlette>=0.37.0",      # NEW: ASGI middleware
       "loguru>=0.7.0",          # NEW: Logging
   ]
   ```

2. Add OAuth2 dependencies:
   ```toml
   "google-auth-oauthlib>=1.2.0",  # OAuth2 flow
   "google-auth-httplib2>=0.2.0",  # HTTP support
   ```

3. Update entry point for Docker:
   ```toml
   [project.scripts]
   analytics-mcp = "analytics_mcp.server:main"
   ```

**Testing**:
```bash
pip install -e .
python -m analytics_mcp.server
```

---

### 1.3 Create GitHub Actions CI/CD Workflows

#### File 1: `.github/workflows/ci-analytics.yml`
**Purpose**: Build and push Docker image to registry

**Workflow**:
1. Checkout code
2. Set up Docker Buildx (multi-arch)
3. Configure AWS credentials (OIDC)
4. Login to ECR
5. Build amd64 + arm64 images
6. Push with tags: `latest`, `{commit-sha}`, `{version}` (optional)

**Triggers**:
- Push to main branch
- Manual workflow_dispatch with version tag

**Example Configuration**:
```yaml
name: Build and Push Analytics MCP to ECR
on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      release_version:
        description: 'Optional version tag (e.g., 0.2.0)'
        type: string
        required: false

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}
      - uses: aws-actions/amazon-ecr-login@v2
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          platforms: linux/amd64,linux/arm64
          push: true
          tags: |
            {registry}/analytics-mcp:latest
            {registry}/analytics-mcp:${{ github.sha }}
```

#### File 2: `.github/workflows/deploy-analytics.yml` (Optional)
**Purpose**: Deploy to client infrastructure

**Note**: Deployment strategy depends on client infrastructure. This is a placeholder for future integration.

---

## Phase 2: Multi-Account Authentication Architecture

### 2.1 Create Credential Broker
**File**: `/analytics_mcp/auth/credential_broker.py`

**Purpose**: Manage multiple OAuth2 credential sets and handle token refresh

**Core Responsibilities**:
1. Store multiple account credentials (keyed by account_id/dealer_id)
2. Automatically refresh tokens before expiry
3. Thread-safe credential access
4. Load credentials from config file or environment

**Key Classes**:

```python
@dataclass
class GACredentials:
    """Single account credentials"""
    account_id: str
    dealer_id: str
    access_token: str
    refresh_token: str
    token_expiry: datetime
    client_id: str
    client_secret: str

    def is_expired(self) -> bool:
        """Check if token needs refresh"""
        return datetime.now() >= self.token_expiry - timedelta(minutes=5)

class CredentialBroker:
    """Manages multiple GA4 account credentials"""

    def __init__(self, config_path: str = None):
        self._credentials: Dict[str, GACredentials] = {}
        self._lock = threading.Lock()
        self._load_credentials(config_path)

    def get_credentials(self, account_id: str) -> GACredentials:
        """Get credentials for account, refresh if needed"""
        with self._lock:
            creds = self._credentials.get(account_id)
            if creds and creds.is_expired():
                creds = self._refresh_token(creds)
            return creds

    def _refresh_token(self, creds: GACredentials) -> GACredentials:
        """Use Google OAuth2 to refresh access token"""
        # Use google-auth-oauthlib to refresh
        # Update creds.access_token and creds.token_expiry
        pass
```

**Configuration Format** (`config/dealers.json`):
```json
{
  "dealers": [
    {
      "account_id": "12345678",
      "dealer_id": "dealer_123",
      "name": "Acme Auto - Downtown",
      "region": "northeast",
      "oauth": {
        "client_id": "xxx.apps.googleusercontent.com",
        "client_secret": "GOCSPX-xxx",
        "refresh_token": "1//xxx",
        "token_uri": "https://oauth2.googleapis.com/token"
      }
    },
    {
      "account_id": "87654321",
      "dealer_id": "dealer_456",
      "name": "Acme Auto - Westside",
      "region": "northeast",
      "oauth": {
        "client_id": "yyy.apps.googleusercontent.com",
        "client_secret": "GOCSPX-yyy",
        "refresh_token": "1//yyy",
        "token_uri": "https://oauth2.googleapis.com/token"
      }
    }
  ]
}
```

**Testing**:
```python
broker = CredentialBroker("config/dealers.json")
creds = broker.get_credentials("dealer_123")
assert creds.access_token is not None
```

---

### 2.2 Create Authentication Middleware
**File**: `/analytics_mcp/auth/middleware.py`

**Purpose**: ASGI middleware to validate OAuth Bearer tokens and attach credentials to requests

**Based on**: aws-mcp-cloudwatch `BrowserCredentialsMiddleware` pattern

**Flow**:
1. Extract `Authorization: Bearer {token}` header
2. Decode base64-encoded JSON token
3. Extract account_id and validate
4. Attach credentials to `request.state.ga_credentials`
5. Pass to next handler

**Token Format** (base64-encoded JSON):
```json
{
  "account_id": "dealer_123",
  "access_token": "ya29.xxx",
  "refresh_token": "1//xxx",
  "expires_at": 1234567890,
  "dealer_name": "Acme Auto - Downtown"
}
```

**Key Classes**:
```python
class GAAuthMiddleware:
    """ASGI middleware for GA OAuth authentication"""

    def __init__(self, app, credential_broker: CredentialBroker, enable_auth: bool = True):
        self.app = app
        self.broker = credential_broker
        self.enable_auth = enable_auth

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)

        # Skip auth for health checks
        if request.url.path in ['/health', '/']:
            await self.app(scope, receive, send)
            return

        # Extract Bearer token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            response = JSONResponse(status_code=401, content={'error': 'Missing credentials'})
            await response(scope, receive, send)
            return

        # Decode and validate
        token = auth_header.replace('Bearer ', '')
        try:
            creds_json = base64.b64decode(token).decode('utf-8')
            creds_data = json.loads(creds_json)

            # Get fresh credentials from broker
            account_id = creds_data['account_id']
            creds = self.broker.get_credentials(account_id)

            # Attach to request state
            if 'state' not in scope:
                scope['state'] = {}
            scope['state']['ga_credentials'] = creds
            scope['state']['account_id'] = account_id

            await self.app(scope, receive, send)

        except Exception as e:
            logger.error(f"Auth error: {e}")
            response = JSONResponse(status_code=401, content={'error': 'Invalid credentials'})
            await response(scope, receive, send)
```

**Environment Variables**:
- `ENABLE_AUTH=true` - Enable authentication (default: true)
- `GA_CREDENTIALS_PATH=/path/to/dealers.json` - Credential config file
- `FASTMCP_LOG_LEVEL=INFO` - Logging level

---

### 2.3 Update Utils Module for Multi-Account
**File**: `/analytics_mcp/tools/utils.py`

**Changes Required**:

**1. Update `_create_credentials()` function**:
```python
def _create_credentials(request_state=None) -> google.auth.credentials.Credentials:
    """Returns credentials with read-only scope.

    Args:
        request_state: Optional request state with GA credentials from middleware

    Returns:
        Google auth credentials
    """
    # If request has authenticated credentials, use them
    if request_state and hasattr(request_state, 'ga_credentials'):
        creds = request_state.ga_credentials

        # Create credentials object from middleware-provided tokens
        credentials = google.oauth2.credentials.Credentials(
            token=creds.access_token,
            refresh_token=creds.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=creds.client_id,
            client_secret=creds.client_secret,
            scopes=[_READ_ONLY_ANALYTICS_SCOPE]
        )

        logger.info(f"Using authenticated credentials for account: {creds.account_id}")
        return credentials

    # Fall back to ADC for local development
    logger.info("Using ADC credentials (local development)")
    (credentials, _) = google.auth.default(scopes=[_READ_ONLY_ANALYTICS_SCOPE])
    return credentials
```

**2. Update API client creation functions**:
```python
def create_admin_api_client(request_state=None) -> admin_v1beta.AnalyticsAdminServiceAsyncClient:
    """Returns a properly configured Google Analytics Admin API async client.

    Args:
        request_state: Optional request state with credentials
    """
    return admin_v1beta.AnalyticsAdminServiceAsyncClient(
        client_info=_CLIENT_INFO,
        credentials=_create_credentials(request_state)
    )

def create_data_api_client(request_state=None) -> data_v1beta.BetaAnalyticsDataAsyncClient:
    """Returns a properly configured Google Analytics Data API async client.

    Args:
        request_state: Optional request state with credentials
    """
    return data_v1beta.BetaAnalyticsDataAsyncClient(
        client_info=_CLIENT_INFO,
        credentials=_create_credentials(request_state)
    )

def create_admin_alpha_api_client(request_state=None) -> admin_v1alpha.AnalyticsAdminServiceAsyncClient:
    """Returns a properly configured Google Analytics Admin API (alpha) async client.

    Args:
        request_state: Optional request state with credentials
    """
    return admin_v1alpha.AnalyticsAdminServiceAsyncClient(
        client_info=_CLIENT_INFO,
        credentials=_create_credentials(request_state)
    )
```

**Backward Compatibility**: Functions still work without `request_state` (ADC fallback)

---

## Phase 3: Update MCP Server Architecture

### 3.1 Modify Server Entry Point
**File**: `/analytics_mcp/server.py`

**Changes Required**:

```python
#!/usr/bin/env python

from analytics_mcp.coordinator import mcp
from analytics_mcp.auth.credential_broker import CredentialBroker
from analytics_mcp.auth.middleware import GAAuthMiddleware
from loguru import logger
import os

# Import tools to register them
from analytics_mcp.tools.admin import info  # noqa: F401
from analytics_mcp.tools.reporting import realtime  # noqa: F401
from analytics_mcp.tools.reporting import core  # noqa: F401


def main() -> None:
    """Runs the server with HTTP transport and authentication."""

    # Configure logging
    logger.info('Initializing Google Analytics MCP server...')

    # Load credentials
    creds_path = os.getenv('GA_CREDENTIALS_PATH', 'config/dealers.json')
    broker = CredentialBroker(creds_path)
    logger.info(f'Loaded credentials for {len(broker.accounts)} accounts')

    # Configure server
    host = os.getenv('ANALYTICS_MCP_HOST', '0.0.0.0')
    port = int(os.getenv('ANALYTICS_MCP_PORT', '3334'))
    enable_auth = os.getenv('ENABLE_AUTH', 'true').lower() == 'true'

    # Wrap with authentication middleware
    app = mcp.get_asgi_app()
    wrapped_app = GAAuthMiddleware(app, broker, enable_auth=enable_auth)

    # Run server
    logger.info(f'Starting server on {host}:{port} (auth={enable_auth})')
    mcp.run(
        transport='streamable-http',
        host=host,
        port=port,
        app=wrapped_app  # Use wrapped app with middleware
    )


if __name__ == "__main__":
    main()
```

**Environment Variables**:
- `ANALYTICS_MCP_HOST=0.0.0.0` - Bind address
- `ANALYTICS_MCP_PORT=3334` - Port number
- `GA_CREDENTIALS_PATH=/app/config/dealers.json` - Credentials file
- `ENABLE_AUTH=true` - Enable/disable authentication
- `FASTMCP_LOG_LEVEL=INFO` - Logging level

---

### 3.2 Coordinator Module
**File**: `/analytics_mcp/coordinator.py`

**Changes**: Minimal - just update server instructions

```python
from mcp.server.fastmcp import FastMCP

# Creates the singleton with updated instructions
mcp = FastMCP(
    "Google Analytics Server (Multi-Account)",
    instructions=(
        "Use this server to query multiple Google Analytics 4 properties "
        "for dealer benchmarking and vehicle interest analysis. "
        "Supports multi-account queries, regional comparisons, and aggregate reporting."
    )
)
```

---

## Phase 4: Update Tool Implementations

### 4.1 Admin Tools Pattern
**File**: `/analytics_mcp/tools/admin/info.py`

**Pattern**: Add `Context` parameter to extract request state

**Example - Before**:
```python
@mcp.tool()
async def get_account_summaries() -> List[Dict[str, Any]]:
    """Retrieves information about the user's Google Analytics accounts and properties."""
    summary_pager = await create_admin_api_client().list_account_summaries()
    all_pages = [proto_to_dict(summary_page) async for summary_page in summary_pager]
    return all_pages
```

**Example - After**:
```python
from mcp.server.fastmcp import Context

@mcp.tool()
async def get_account_summaries(ctx: Context) -> List[Dict[str, Any]]:
    """Retrieves information about the user's Google Analytics accounts and properties."""
    # Extract request state from context
    request_state = getattr(ctx, 'request_state', None)

    # Pass to API client
    summary_pager = await create_admin_api_client(request_state).list_account_summaries()
    all_pages = [proto_to_dict(summary_page) async for summary_page in summary_pager]
    return all_pages
```

**All functions to update**:
- `get_account_summaries(ctx: Context)`
- `get_property_details(property_id, ctx: Context)`
- `list_google_ads_links(property_id, ctx: Context)`
- `list_property_annotations(property_id, ctx: Context)`

---

### 4.2 Reporting Tools Pattern
**Files**:
- `/analytics_mcp/tools/reporting/core.py`
- `/analytics_mcp/tools/reporting/realtime.py`
- `/analytics_mcp/tools/reporting/metadata.py`

**Same pattern** - add `ctx: Context` and pass `request_state`

**Example - `run_report()`**:
```python
async def run_report(
    property_id: int | str,
    date_ranges: List[Dict[str, str]],
    dimensions: List[str],
    metrics: List[str],
    ctx: Context,  # NEW
    dimension_filter: Dict[str, Any] = None,
    metric_filter: Dict[str, Any] = None,
    order_bys: List[Dict[str, Any]] = None,
    limit: int = None,
    offset: int = None,
    currency_code: str = None,
    return_property_quota: bool = False,
) -> Dict[str, Any]:
    """Runs a Google Analytics Data API report."""
    request_state = getattr(ctx, 'request_state', None)

    # ... build request ...

    response = await create_data_api_client(request_state).run_report(request)
    return proto_to_dict(response)
```

---

### 4.3 Optional Enhancement: Explicit Account Selection

**Consider adding** explicit `account_id` parameter to tools:

```python
@mcp.tool()
async def run_report(
    account_id: str,  # NEW: Explicit account selection
    property_id: int | str,
    date_ranges: List[Dict[str, str]],
    dimensions: List[str],
    metrics: List[str],
    ctx: Context,
    ...
) -> Dict[str, Any]:
    """Runs a report for a specific dealer account."""
    # Override request state if account_id provided
    if account_id:
        # Look up credentials from broker
        creds = credential_broker.get_credentials(account_id)
        # Create temporary request state
        request_state = create_temp_state(creds)
    else:
        request_state = getattr(ctx, 'request_state', None)

    # ... rest of function
```

**Pros**:
- LLM can explicitly select accounts
- Enables multi-account queries in single call

**Cons**:
- More complex
- Requires access to global credential broker

**Recommendation**: Phase 2 enhancement (not initial implementation)

---

## Phase 5: Configuration & Credential Management

### 5.1 Create Example Configuration Files

**File 1**: `/config/dealers.example.json`
```json
{
  "dealers": [
    {
      "account_id": "12345678",
      "dealer_id": "dealer_001",
      "name": "Sample Dealer - Downtown",
      "region": "northeast",
      "city": "Boston",
      "state": "MA",
      "oauth": {
        "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
        "client_secret": "GOCSPX-YOUR_CLIENT_SECRET",
        "refresh_token": "1//YOUR_REFRESH_TOKEN",
        "token_uri": "https://oauth2.googleapis.com/token"
      },
      "properties": [
        {
          "property_id": "123456789",
          "name": "Main Website",
          "type": "web"
        }
      ]
    },
    {
      "account_id": "87654321",
      "dealer_id": "dealer_002",
      "name": "Sample Dealer - Westside",
      "region": "northeast",
      "city": "Cambridge",
      "state": "MA",
      "oauth": {
        "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
        "client_secret": "GOCSPX-YOUR_CLIENT_SECRET",
        "refresh_token": "1//YOUR_REFRESH_TOKEN",
        "token_uri": "https://oauth2.googleapis.com/token"
      },
      "properties": [
        {
          "property_id": "987654321",
          "name": "Main Website",
          "type": "web"
        }
      ]
    }
  ]
}
```

**File 2**: `/.env.example`
```bash
# Server Configuration
ANALYTICS_MCP_HOST=0.0.0.0
ANALYTICS_MCP_PORT=3334
FASTMCP_LOG_LEVEL=INFO

# Authentication
ENABLE_AUTH=true
GA_CREDENTIALS_PATH=/app/config/dealers.json

# Google Cloud (for local dev with ADC)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/adc.json
GOOGLE_CLOUD_PROJECT=your-project-id
```

**File 3**: `/docker-compose.yml`
```yaml
version: '3.8'

services:
  analytics-mcp:
    build: .
    ports:
      - "3334:3334"
    environment:
      - ANALYTICS_MCP_HOST=0.0.0.0
      - ANALYTICS_MCP_PORT=3334
      - ENABLE_AUTH=false  # Disable for local dev
      - FASTMCP_LOG_LEVEL=DEBUG
    volumes:
      - ./config/dealers.json:/app/config/dealers.json:ro
      - ./analytics_mcp:/app/analytics_mcp:ro  # Hot reload
```

---

### 5.2 Security Considerations

**Credential File Security**:
1. Add to `.gitignore`:
   ```
   config/dealers.json
   config/*-creds.json
   *.credentials
   ```

2. Never commit real credentials

3. Use environment variable for credentials path in production

4. Consider encryption at rest for credential file

**OAuth Token Security**:
1. Store refresh tokens, not long-lived tokens
2. Implement token rotation
3. Use short-lived access tokens (1 hour)
4. Log token usage for audit

---

## Phase 6: Testing & Validation

### 6.1 Unit Tests

**New test files to create**:

1. `/tests/auth/test_credential_broker.py`
   - Test credential loading
   - Test token refresh logic
   - Test thread safety
   - Test expired token detection

2. `/tests/auth/test_middleware.py`
   - Test Bearer token extraction
   - Test base64 decoding
   - Test credential attachment to request state
   - Test authentication failures

3. `/tests/tools/test_multi_account_admin.py`
   - Test admin tools with multiple accounts
   - Mock request state with different credentials
   - Verify correct credentials used per call

4. `/tests/tools/test_multi_account_reporting.py`
   - Test reporting tools with multiple accounts
   - Verify data isolation between accounts

**Update existing tests**:
- Add `ctx: Context` parameter to tool calls
- Mock request state in fixtures
- Ensure backward compatibility (ADC fallback)

---

### 6.2 Integration Testing

**Test Scenarios**:

1. **Local Development (No Auth)**:
   ```bash
   ENABLE_AUTH=false python -m analytics_mcp.server
   ```
   - Should use ADC credentials
   - Should work with existing tools

2. **Single Account (Bearer Token)**:
   ```bash
   curl -H "Authorization: Bearer $(echo '{"account_id":"dealer_001"}' | base64)" \
        http://localhost:3334/mcp/tools/get_account_summaries
   ```
   - Should use dealer_001 credentials
   - Should return dealer_001 data only

3. **Multi-Account Queries**:
   - Call multiple tools with different account tokens
   - Verify data isolation
   - Verify correct property data returned

4. **Token Refresh**:
   - Use expired token
   - Verify automatic refresh
   - Verify continued operation

---

### 6.3 MCP Inspector Testing

**Test with MCP Inspector**:
```bash
npx @modelcontextprotocol/inspector \
  docker run -p 3334:3334 \
    -e ENABLE_AUTH=false \
    analytics-mcp:latest
```

**Test checklist**:
- [ ] Server starts successfully
- [ ] Tools list appears
- [ ] Can call tools with parameters
- [ ] Multi-account tools work
- [ ] Error handling works

---

## Phase 7: Documentation

### 7.1 Update CLAUDE.md

**Add sections**:
1. Multi-account architecture overview
2. Credential broker pattern explanation
3. OAuth2 token management
4. Docker deployment guide
5. Multi-account configuration examples
6. Troubleshooting guide

### 7.2 Create OAuth Setup Guide

**File**: `/docs/OAUTH_SETUP.md`

**Contents**:
1. Creating Google Cloud OAuth2 credentials
2. Obtaining refresh tokens for each dealer
3. Configuring `dealers.json`
4. Testing credentials
5. Troubleshooting OAuth errors

### 7.3 Create Deployment Guide

**File**: `/docs/DEPLOYMENT.md`

**Contents**:
1. Building Docker image
2. Pushing to registry
3. Running on client infrastructure
4. Environment variable configuration
5. Health check endpoints
6. Monitoring and logging

---

## Phase 8: Use Case Implementation (Future)

### 8.1 Dealer Benchmarking Tools

**New tools to create** (Phase 2):

```python
@mcp.tool()
async def compare_dealer_sessions(
    dealer_ids: List[str],
    date_range: Dict[str, str],
    ctx: Context
) -> Dict[str, Any]:
    """Compare session counts across multiple dealers."""
    results = {}
    for dealer_id in dealer_ids:
        # Get credentials for this dealer
        creds = broker.get_credentials(dealer_id)
        # Run report
        data = await run_report(...)
        results[dealer_id] = data

    # Calculate regional average
    avg = calculate_average(results)

    return {
        "dealers": results,
        "regional_average": avg,
        "performance_index": calculate_index(results, avg)
    }
```

### 8.2 Vehicle Interest Analysis Tools

**New tools to create** (Phase 2):

```python
@mcp.tool()
async def analyze_vehicle_interest(
    dealer_ids: List[str],
    date_range: Dict[str, str],
    ctx: Context
) -> Dict[str, Any]:
    """Aggregate vehicle interest metrics across dealers."""
    # Query all dealers
    # Aggregate by model
    # Calculate interest share
    # Identify trends
    pass
```

---

## Implementation Timeline

### Week 1: Infrastructure
- [ ] Phase 1.1: Dockerfile ✅
- [ ] Phase 1.2: pyproject.toml
- [ ] Phase 1.3: CI/CD workflows
- [ ] Test: Docker build and run

### Week 2: Authentication
- [ ] Phase 2.1: Credential broker
- [ ] Phase 2.2: Auth middleware
- [ ] Phase 2.3: Utils update
- [ ] Test: Token management

### Week 3: Server & Tools
- [ ] Phase 3: Server architecture
- [ ] Phase 4.1: Admin tools
- [ ] Phase 4.2: Reporting tools
- [ ] Test: Multi-account queries

### Week 4: Configuration & Testing
- [ ] Phase 5: Config files
- [ ] Phase 6: Testing
- [ ] Phase 7: Documentation
- [ ] Deploy: Client POC

### Week 5+: Use Cases (Optional)
- [ ] Phase 8: Benchmarking tools
- [ ] Phase 8: Vehicle interest tools

---

## Success Criteria

- [ ] Docker image builds successfully
- [ ] Server starts with HTTP transport
- [ ] Multiple dealer accounts can be configured
- [ ] OAuth tokens refresh automatically
- [ ] Tools route to correct account credentials
- [ ] Data isolation between accounts verified
- [ ] Backward compatibility maintained (ADC fallback works)
- [ ] All existing tests pass
- [ ] New multi-account tests pass
- [ ] CI/CD pipeline works end-to-end
- [ ] Documentation complete

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Google OAuth token expiry (1h) | Implement proactive refresh 5min before expiry |
| Rate limiting per account | Track quota usage, implement backoff |
| Credential leaks | .gitignore, encryption at rest, audit logging |
| Breaking changes to existing tools | Maintain backward compatibility, add Context gradually |
| Complex multi-account queries | Start simple (single account), add aggregation later |
| Testing without real credentials | Mock credential broker, use fake tokens |

---

## Open Questions

1. **ECR Registry**: Which AWS account/region for ECR?
2. **Client Infrastructure**: Where will containers run? (EKS, ECS, VMs?)
3. **Credential Distribution**: How will dealers provide OAuth credentials?
4. **Jarvis Integration**: Will this integrate with existing Jarvis deployment?
5. **Regional Definitions**: How are dealer regions/groups defined?
6. **Property Mapping**: Do we need property_id → dealer_id mapping logic?

---

## Next Steps

1. **Review this plan** - Approve sections to implement
2. **Clarify open questions** - Answer infrastructure questions
3. **Begin implementation** - Start with approved phases
4. **Iterative testing** - Test each phase before proceeding
5. **POC deployment** - Deploy to client environment for validation

