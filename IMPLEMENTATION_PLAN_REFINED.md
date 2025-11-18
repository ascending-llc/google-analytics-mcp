# Multi-Account GA4 MCP Server - POC-Focused Implementation Plan

## POC Objective

**Primary Goal**: Prove that multi-account Google Analytics 4 data can be queried through a single MCP server using secure, per-dealer credential management.

**Success Criteria**:
- ✅ Multiple dealer GA4 accounts can be configured
- ✅ Each dealer's data is isolated (can't see other dealers' data)
- ✅ Jarvis can query any dealer's GA4 data by specifying account_id
- ✅ OAuth tokens refresh automatically
- ✅ System runs stably in containerized environment

**Out of Scope for POC**:
- ❌ Sophisticated analytics/aggregation (can add later)
- ❌ Regional benchmarking calculations (future work)
- ❌ Vehicle model detection algorithms (TBD)
- ❌ Custom UI/dashboards (use Jarvis LibreChat)

---

## Architecture: What We're Building

### Current State (Single Account)
```
User → Jarvis → GA4 MCP (stdio) → [ADC] → Google Analytics API (single account)
```

### Target State (Multi-Account POC)
```
User → Jarvis → GA4 MCP (HTTP) → [Credential Broker] → Google Analytics API
                                        ├─ Dealer 1 OAuth
                                        ├─ Dealer 2 OAuth
                                        ├─ Dealer 3 OAuth
                                        └─ Dealer N OAuth
```

### Key Components to Build

1. **Credential Broker** - Manages OAuth tokens for N dealers
2. **Authentication Middleware** - Routes requests to correct dealer credentials
3. **HTTP Transport** - Enables deployment in Docker/Kubernetes
4. **Updated Tools** - Accept context to determine which account to query

---

## Implementation Phases (POC-Focused)

## Phase 1: Containerization ✅ (Started)

**Goal**: Get the server running in Docker

### 1.1 Dockerfile ✅ DONE
- Multi-stage build with Python 3.10 alpine
- Non-root user
- Port 3334 exposed

### 1.2 Update pyproject.toml

**Add dependencies**:
```toml
dependencies = [
    # Existing
    "google-analytics-data==0.19.0",
    "google-analytics-admin==0.26.0",
    "google-auth~=2.40",
    "mcp[cli]>=1.2.0",

    # NEW for HTTP transport
    "httpx>=0.28.1",
    "uvicorn>=0.30.0",
    "starlette>=0.37.0",

    # NEW for OAuth2
    "google-auth-oauthlib>=1.2.0",

    # NEW for logging
    "loguru>=0.7.0",
]
```

**Test**:
```bash
pip install -e .
python -m analytics_mcp.server --help
```

### 1.3 Create .dockerignore

```
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.egg-info/
dist/
build/
.git/
.github/
tests/
*.md
config/dealers.json  # Don't bake credentials into image
.env
```

### 1.4 Test Docker Build

```bash
docker build -t analytics-mcp:poc .
docker run -p 3334:3334 -e ENABLE_AUTH=false analytics-mcp:poc
```

**Expected**: Server starts, listens on 3334, can call with ADC fallback

---

## Phase 2: Multi-Account Authentication

**Goal**: Support multiple dealer OAuth credentials

### 2.1 Create Credential Data Structures

**File**: `analytics_mcp/auth/models.py`

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class DealerCredentials:
    """OAuth credentials for a single dealer"""
    dealer_id: str
    account_id: str
    name: str
    client_id: str
    client_secret: str
    refresh_token: str
    access_token: Optional[str] = None
    token_expiry: Optional[datetime] = None

    def is_expired(self) -> bool:
        """Check if access token needs refresh"""
        if not self.token_expiry:
            return True
        # Refresh 5 minutes before actual expiry
        return datetime.utcnow() >= self.token_expiry - timedelta(minutes=5)
```

### 2.2 Create Credential Broker

**File**: `analytics_mcp/auth/credential_broker.py`

```python
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional
from loguru import logger
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

class CredentialBroker:
    """Manages OAuth credentials for multiple dealer accounts"""

    def __init__(self, config_path: str):
        self._credentials: Dict[str, DealerCredentials] = {}
        self._lock = threading.Lock()
        self._load_from_config(config_path)

    def _load_from_config(self, config_path: str):
        """Load dealer credentials from JSON config"""
        with open(config_path, 'r') as f:
            config = json.load(f)

        for dealer in config.get('dealers', []):
            creds = DealerCredentials(
                dealer_id=dealer['dealer_id'],
                account_id=dealer['account_id'],
                name=dealer['name'],
                client_id=dealer['oauth']['client_id'],
                client_secret=dealer['oauth']['client_secret'],
                refresh_token=dealer['oauth']['refresh_token']
            )
            self._credentials[dealer['dealer_id']] = creds

        logger.info(f"Loaded credentials for {len(self._credentials)} dealers")

    def get_credentials(self, dealer_id: str) -> Optional[Credentials]:
        """Get Google auth credentials for a dealer, refreshing if needed"""
        with self._lock:
            dealer_creds = self._credentials.get(dealer_id)
            if not dealer_creds:
                logger.error(f"No credentials found for dealer: {dealer_id}")
                return None

            # Create Google credentials object
            creds = Credentials(
                token=dealer_creds.access_token,
                refresh_token=dealer_creds.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=dealer_creds.client_id,
                client_secret=dealer_creds.client_secret,
                scopes=["https://www.googleapis.com/auth/analytics.readonly"]
            )

            # Refresh if expired
            if not creds.valid:
                logger.info(f"Refreshing token for dealer: {dealer_id}")
                creds.refresh(Request())
                # Update stored credentials
                dealer_creds.access_token = creds.token
                dealer_creds.token_expiry = creds.expiry

            return creds

    def list_dealers(self) -> list:
        """Get list of configured dealers"""
        return [
            {"dealer_id": d.dealer_id, "name": d.name}
            for d in self._credentials.values()
        ]
```

**Key Features**:
- Thread-safe credential access
- Automatic token refresh
- Simple JSON config loading
- Returns standard Google `Credentials` object

### 2.3 Create Config Schema

**File**: `config/dealers.example.json`

```json
{
  "dealers": [
    {
      "dealer_id": "dealer_001",
      "account_id": "12345678",
      "name": "Sample Dealer - Downtown",
      "region": "northeast",
      "oauth": {
        "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
        "client_secret": "GOCSPX-YOUR_CLIENT_SECRET",
        "refresh_token": "1//YOUR_REFRESH_TOKEN"
      }
    },
    {
      "dealer_id": "dealer_002",
      "account_id": "87654321",
      "name": "Sample Dealer - Westside",
      "region": "northeast",
      "oauth": {
        "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
        "client_secret": "GOCSPX-YOUR_CLIENT_SECRET",
        "refresh_token": "1//YOUR_REFRESH_TOKEN"
      }
    }
  ]
}
```

**Add to .gitignore**:
```
config/dealers.json
config/*-credentials.json
```

### 2.4 Create Simple Middleware (Optional for POC)

**File**: `analytics_mcp/auth/middleware.py`

**For POC**: This can be simplified or skipped. Instead, tools can directly accept `dealer_id` parameter.

**Reason**: Middleware is more complex and the simpler approach is: each tool accepts `dealer_id` as a parameter, looks up credentials from broker.

---

## Phase 3: Update Core Infrastructure

**Goal**: Make existing tools work with credential broker

### 3.1 Update Utils Module

**File**: `analytics_mcp/tools/utils.py`

**Changes**:

1. Add module-level credential broker:
```python
from analytics_mcp.auth.credential_broker import CredentialBroker
import os

# Global credential broker (initialized by server)
_credential_broker: Optional[CredentialBroker] = None

def init_credential_broker(config_path: str):
    """Initialize the global credential broker"""
    global _credential_broker
    _credential_broker = CredentialBroker(config_path)

def get_credential_broker() -> CredentialBroker:
    """Get the global credential broker"""
    if _credential_broker is None:
        raise RuntimeError("Credential broker not initialized")
    return _credential_broker
```

2. Update `_create_credentials()`:
```python
def _create_credentials(dealer_id: Optional[str] = None) -> google.auth.credentials.Credentials:
    """Returns credentials with read-only scope.

    Args:
        dealer_id: Optional dealer ID for multi-account support.
                   If None, falls back to ADC (for local dev).

    Returns:
        Google auth credentials
    """
    # If dealer_id provided, use credential broker
    if dealer_id:
        broker = get_credential_broker()
        creds = broker.get_credentials(dealer_id)
        if creds:
            logger.info(f"Using credentials for dealer: {dealer_id}")
            return creds
        else:
            raise ValueError(f"No credentials found for dealer: {dealer_id}")

    # Fall back to ADC for local development
    logger.info("Using ADC credentials (local development)")
    (credentials, _) = google.auth.default(scopes=[_READ_ONLY_ANALYTICS_SCOPE])
    return credentials
```

3. Update API client functions:
```python
def create_admin_api_client(dealer_id: Optional[str] = None) -> admin_v1beta.AnalyticsAdminServiceAsyncClient:
    """Returns a properly configured Google Analytics Admin API async client.

    Args:
        dealer_id: Optional dealer ID for multi-account support
    """
    return admin_v1beta.AnalyticsAdminServiceAsyncClient(
        client_info=_CLIENT_INFO,
        credentials=_create_credentials(dealer_id)
    )

def create_data_api_client(dealer_id: Optional[str] = None) -> data_v1beta.BetaAnalyticsDataAsyncClient:
    """Returns a properly configured Google Analytics Data API async client.

    Args:
        dealer_id: Optional dealer ID for multi-account support
    """
    return data_v1beta.BetaAnalyticsDataAsyncClient(
        client_info=_CLIENT_INFO,
        credentials=_create_credentials(dealer_id)
    )

def create_admin_alpha_api_client(dealer_id: Optional[str] = None) -> admin_v1alpha.AnalyticsAdminServiceAsyncClient:
    """Returns a properly configured Google Analytics Admin API (alpha) async client.

    Args:
        dealer_id: Optional dealer ID for multi-account support
    """
    return admin_v1alpha.AnalyticsAdminServiceAsyncClient(
        client_info=_CLIENT_INFO,
        credentials=_create_credentials(dealer_id)
    )
```

**Key Point**: All API client functions now accept optional `dealer_id` parameter. If not provided, falls back to ADC (backward compatible).

### 3.2 Update Server Entry Point

**File**: `analytics_mcp/server.py`

```python
#!/usr/bin/env python

import os
from loguru import logger

from analytics_mcp.coordinator import mcp
from analytics_mcp.tools.utils import init_credential_broker

# Import tools to register them
from analytics_mcp.tools.admin import info  # noqa: F401
from analytics_mcp.tools.reporting import realtime  # noqa: F401
from analytics_mcp.tools.reporting import core  # noqa: F401


def main() -> None:
    """Runs the server."""

    logger.info('Initializing Google Analytics MCP server (multi-account)...')

    # Initialize credential broker if config provided
    creds_path = os.getenv('GA_CREDENTIALS_PATH')
    if creds_path and os.path.exists(creds_path):
        logger.info(f'Loading dealer credentials from: {creds_path}')
        init_credential_broker(creds_path)
    else:
        logger.warning('No GA_CREDENTIALS_PATH set - using ADC for single-account mode')

    # Configure server transport
    transport = os.getenv('MCP_TRANSPORT', 'stdio')

    if transport == 'streamable-http':
        host = os.getenv('ANALYTICS_MCP_HOST', '0.0.0.0')
        port = int(os.getenv('ANALYTICS_MCP_PORT', '3334'))
        logger.info(f'Starting HTTP server on {host}:{port}')
        mcp.run(transport='streamable-http', host=host, port=port)
    else:
        logger.info('Starting stdio server')
        mcp.run()  # Default stdio transport


if __name__ == "__main__":
    main()
```

**Key Features**:
- Initializes credential broker on startup
- Supports both stdio (backward compatible) and HTTP transport
- Gracefully falls back to ADC if no credential config

---

## Phase 4: Update Tool Implementations (Minimal Changes)

**Goal**: Add `dealer_id` parameter to existing tools

### Pattern for All Tools

**Before**:
```python
@mcp.tool()
async def get_account_summaries() -> List[Dict[str, Any]]:
    summary_pager = await create_admin_api_client().list_account_summaries()
    all_pages = [proto_to_dict(summary_page) async for summary_page in summary_pager]
    return all_pages
```

**After**:
```python
@mcp.tool()
async def get_account_summaries(dealer_id: str = None) -> List[Dict[str, Any]]:
    """Retrieves information about Google Analytics accounts and properties.

    Args:
        dealer_id: Optional dealer ID for multi-account support. If not provided,
                   uses ADC credentials (for local development).
    """
    summary_pager = await create_admin_api_client(dealer_id).list_account_summaries()
    all_pages = [proto_to_dict(summary_page) async for summary_page in summary_pager]
    return all_pages
```

### Tools to Update

**Admin Tools** (`analytics_mcp/tools/admin/info.py`):
- `get_account_summaries(dealer_id: str = None)`
- `get_property_details(property_id, dealer_id: str = None)`
- `list_google_ads_links(property_id, dealer_id: str = None)`
- `list_property_annotations(property_id, dealer_id: str = None)`

**Reporting Tools** (`analytics_mcp/tools/reporting/core.py`):
- `run_report(..., dealer_id: str = None)`

**Reporting Tools** (`analytics_mcp/tools/reporting/metadata.py`):
- `get_custom_dimensions_and_metrics(property_id, dealer_id: str = None)`

**Realtime Tools** (`analytics_mcp/tools/reporting/realtime.py`):
- Any realtime tools: add `dealer_id: str = None` parameter

**Key Point**: This is a **minimal change** - just add one parameter to each tool and pass it through to the API client. Backward compatible (optional parameter).

---

## Phase 5: Simple Use Case Demonstrations

**Goal**: Show multi-account queries work

### 5.1 Helper Tool: List Dealers

**File**: `analytics_mcp/tools/admin/info.py` (add to existing file)

```python
@mcp.tool()
async def list_configured_dealers() -> List[Dict[str, Any]]:
    """Lists all dealers configured in the credential broker.

    Returns list of dealers with dealer_id and name.
    Useful for discovering which dealer_ids can be queried.
    """
    from analytics_mcp.tools.utils import get_credential_broker

    try:
        broker = get_credential_broker()
        return broker.list_dealers()
    except RuntimeError:
        # No credential broker configured (using ADC)
        return []
```

**Use**: User can ask Jarvis "Which dealers are configured?" and get a list of dealer_ids.

### 5.2 Simple Comparison Tool (POC)

**File**: `analytics_mcp/tools/benchmarking/__init__.py` (new directory)

```python
from typing import List, Dict, Any
from analytics_mcp.coordinator import mcp
from analytics_mcp.tools.reporting.core import run_report

@mcp.tool()
async def compare_dealer_sessions(
    dealer_ids: List[str],
    property_ids: List[str],  # One per dealer
    start_date: str,
    end_date: str
) -> Dict[str, Any]:
    """Simple POC: Compare session counts across multiple dealers.

    Args:
        dealer_ids: List of dealer IDs to compare
        property_ids: List of GA4 property IDs (must match length of dealer_ids)
        start_date: Start date in YYYY-MM-DD format or relative (e.g., "30daysAgo")
        end_date: End date in YYYY-MM-DD format or relative (e.g., "today")

    Returns:
        Dict with dealer_id -> session count mapping
    """
    if len(dealer_ids) != len(property_ids):
        raise ValueError("dealer_ids and property_ids must have same length")

    results = {}

    for dealer_id, property_id in zip(dealer_ids, property_ids):
        # Run simple session count query
        report = await run_report(
            property_id=property_id,
            date_ranges=[{"start_date": start_date, "end_date": end_date}],
            dimensions=[],  # No dimensions, just total
            metrics=["sessions"],
            dealer_id=dealer_id  # KEY: Use specific dealer credentials
        )

        # Extract session count
        if report.get('rows'):
            sessions = report['rows'][0]['metric_values'][0]['value']
        else:
            sessions = 0

        results[dealer_id] = {
            "sessions": int(sessions),
            "property_id": property_id
        }

    # Calculate simple average
    total_sessions = sum(r["sessions"] for r in results.values())
    avg_sessions = total_sessions / len(results) if results else 0

    return {
        "dealers": results,
        "regional_average": avg_sessions,
        "total_dealers": len(results)
    }
```

**Example Usage** (via Jarvis):
```
User: "Compare sessions for dealer_001 and dealer_002 in the last 30 days"

Jarvis calls: compare_dealer_sessions(
    dealer_ids=["dealer_001", "dealer_002"],
    property_ids=["123456789", "987654321"],
    start_date="30daysAgo",
    end_date="today"
)

Returns:
{
  "dealers": {
    "dealer_001": {"sessions": 45200, "property_id": "123456789"},
    "dealer_002": {"sessions": 38500, "property_id": "987654321"}
  },
  "regional_average": 41850,
  "total_dealers": 2
}

Jarvis responds: "Dealer 001 had 45,200 sessions vs Dealer 002's 38,500 sessions.
The average across both dealers was 41,850 sessions."
```

### 5.3 Vehicle Interest POC (Simplified)

**File**: `analytics_mcp/tools/benchmarking/__init__.py` (add to same file)

```python
@mcp.tool()
async def get_top_pages_by_dealer(
    dealer_id: str,
    property_id: str,
    start_date: str,
    end_date: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """Simple POC: Get top pages for a dealer by sessions.

    Can be used to identify top vehicle pages by looking at page paths.

    Args:
        dealer_id: Dealer ID
        property_id: GA4 property ID
        start_date: Start date
        end_date: End date
        limit: Number of top pages to return

    Returns:
        List of pages with session counts
    """
    report = await run_report(
        property_id=property_id,
        date_ranges=[{"start_date": start_date, "end_date": end_date}],
        dimensions=["pagePath", "pageTitle"],
        metrics=["sessions", "eventCount"],
        order_bys=[{"metric": {"metric_name": "sessions"}, "desc": True}],
        limit=limit,
        dealer_id=dealer_id
    )

    results = []
    for row in report.get('rows', []):
        results.append({
            "page_path": row['dimension_values'][0]['value'],
            "page_title": row['dimension_values'][1]['value'],
            "sessions": int(row['metric_values'][0]['value']),
            "events": int(row['metric_values'][1]['value'])
        })

    return results
```

**Example Usage**:
```
User: "What are the top pages for dealer_001 in the last 90 days?"

Jarvis calls: get_top_pages_by_dealer(
    dealer_id="dealer_001",
    property_id="123456789",
    start_date="90daysAgo",
    end_date="today",
    limit=10
)

Returns:
[
  {"page_path": "/inventory/rav4-hybrid", "page_title": "RAV4 Hybrid", "sessions": 2500, "events": 8200},
  {"page_path": "/inventory/tacoma", "page_title": "Tacoma", "sessions": 2100, "events": 6800},
  ...
]

Jarvis responds: "Top pages for Dealer 001:
1. RAV4 Hybrid - 2,500 sessions
2. Tacoma - 2,100 sessions
..."
```

---

## Phase 6: Testing

**Goal**: Verify multi-account functionality works

### 6.1 Unit Tests

**File**: `tests/auth/test_credential_broker.py`

```python
import pytest
from analytics_mcp.auth.credential_broker import CredentialBroker

def test_load_credentials(tmp_path):
    """Test loading credentials from config file"""
    config_file = tmp_path / "dealers.json"
    config_file.write_text('''
    {
      "dealers": [
        {
          "dealer_id": "test_001",
          "account_id": "12345",
          "name": "Test Dealer",
          "oauth": {
            "client_id": "test.apps.googleusercontent.com",
            "client_secret": "test_secret",
            "refresh_token": "test_token"
          }
        }
      ]
    }
    ''')

    broker = CredentialBroker(str(config_file))
    dealers = broker.list_dealers()

    assert len(dealers) == 1
    assert dealers[0]['dealer_id'] == 'test_001'

def test_get_credentials():
    """Test retrieving credentials for a dealer"""
    # TODO: Mock Google OAuth refresh
    pass
```

**File**: `tests/tools/test_multi_account.py`

```python
import pytest
from analytics_mcp.tools.admin.info import get_account_summaries

@pytest.mark.asyncio
async def test_get_account_summaries_with_dealer_id():
    """Test that dealer_id parameter is accepted"""
    # TODO: Mock API client
    result = await get_account_summaries(dealer_id="test_dealer")
    # Assertions...
```

### 6.2 Integration Test

**Manual test script**: `tests/manual/test_multi_account.py`

```python
"""Manual test script for multi-account functionality.

Requires:
1. config/dealers.json with valid OAuth credentials
2. Valid property IDs for each dealer

Usage:
    python tests/manual/test_multi_account.py
"""

import asyncio
from analytics_mcp.tools.utils import init_credential_broker
from analytics_mcp.tools.admin.info import get_account_summaries, list_configured_dealers
from analytics_mcp.tools.benchmarking import compare_dealer_sessions

async def main():
    # Initialize
    init_credential_broker('config/dealers.json')

    # Test 1: List dealers
    print("=== Test 1: List Configured Dealers ===")
    dealers = await list_configured_dealers()
    print(f"Found {len(dealers)} dealers:")
    for dealer in dealers:
        print(f"  - {dealer['dealer_id']}: {dealer['name']}")

    # Test 2: Get account summaries for first dealer
    if dealers:
        dealer_id = dealers[0]['dealer_id']
        print(f"\n=== Test 2: Get Account Summaries for {dealer_id} ===")
        summaries = await get_account_summaries(dealer_id=dealer_id)
        print(f"Found {len(summaries)} accounts/properties")

    # Test 3: Compare sessions (if we have 2+ dealers)
    if len(dealers) >= 2:
        print(f"\n=== Test 3: Compare Dealer Sessions ===")
        # NOTE: You need to manually fill in property IDs
        property_ids = ["PROPERTY_ID_1", "PROPERTY_ID_2"]  # TODO: Fill in
        dealer_ids = [d['dealer_id'] for d in dealers[:2]]

        comparison = await compare_dealer_sessions(
            dealer_ids=dealer_ids,
            property_ids=property_ids,
            start_date="30daysAgo",
            end_date="today"
        )
        print(f"Comparison results: {comparison}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Phase 7: Deployment & Documentation

### 7.1 Docker Deployment

**Build and run**:
```bash
# Build image
docker build -t analytics-mcp:v1 .

# Run with config mounted
docker run -d \
  --name analytics-mcp \
  -p 3334:3334 \
  -e MCP_TRANSPORT=streamable-http \
  -e ANALYTICS_MCP_HOST=0.0.0.0 \
  -e ANALYTICS_MCP_PORT=3334 \
  -e GA_CREDENTIALS_PATH=/app/config/dealers.json \
  -e FASTMCP_LOG_LEVEL=INFO \
  -v $(pwd)/config/dealers.json:/app/config/dealers.json:ro \
  analytics-mcp:v1

# Check logs
docker logs -f analytics-mcp

# Test endpoint
curl http://localhost:3334/health
```

### 7.2 Environment Variables Reference

Create **`.env.example`**:
```bash
# Server Configuration
MCP_TRANSPORT=streamable-http  # or "stdio" for local dev
ANALYTICS_MCP_HOST=0.0.0.0
ANALYTICS_MCP_PORT=3334

# Credentials
GA_CREDENTIALS_PATH=/app/config/dealers.json  # Path to dealer config

# Logging
FASTMCP_LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR

# Optional: For local dev with ADC
GOOGLE_APPLICATION_CREDENTIALS=/path/to/adc.json
```

### 7.3 Update CLAUDE.md

Add section on multi-account usage:

```markdown
## Multi-Account Configuration

This server supports querying multiple GA4 accounts using OAuth credentials.

### Setup

1. Create `config/dealers.json` with dealer credentials (see `config/dealers.example.json`)
2. Set environment variable: `GA_CREDENTIALS_PATH=config/dealers.json`
3. Start server: `python -m analytics_mcp.server`

### Usage

All tools accept optional `dealer_id` parameter:

```python
# List configured dealers
await list_configured_dealers()

# Get data for specific dealer
await get_account_summaries(dealer_id="dealer_001")
await run_report(property_id="123456789", ..., dealer_id="dealer_001")

# Compare across dealers
await compare_dealer_sessions(
    dealer_ids=["dealer_001", "dealer_002"],
    property_ids=["123456789", "987654321"],
    start_date="30daysAgo",
    end_date="today"
)
```

### Obtaining OAuth Credentials

See [OAuth Setup Guide](docs/OAUTH_SETUP.md) for detailed instructions.
```

### 7.4 Create OAuth Setup Guide

**File**: `docs/OAUTH_SETUP.md`

```markdown
# OAuth Setup Guide for Multi-Account GA4 Access

## Overview

Each dealer needs to authorize this application to access their GA4 data using OAuth.

## Steps

### 1. Create OAuth Client (One-Time, Done by Admin)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create or select a project
3. Enable Google Analytics Admin API and Data API
4. Go to "APIs & Services" > "Credentials"
5. Click "Create Credentials" > "OAuth client ID"
6. Application type: "Web application" or "Desktop application"
7. Add authorized redirect URIs (if web): `http://localhost:8080/oauth2callback`
8. Download client secret JSON

### 2. Obtain Refresh Token (Per Dealer)

Use Google's OAuth playground or a simple script:

```python
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/analytics.readonly']

flow = InstalledAppFlow.from_client_secrets_file(
    'client_secret.json',
    scopes=SCOPES
)

# This will open a browser window for the dealer to authorize
credentials = flow.run_local_server(port=8080)

print("Refresh Token:", credentials.refresh_token)
print("Access Token:", credentials.token)
print("Expires:", credentials.expiry)
```

### 3. Add to Configuration

Add dealer's credentials to `config/dealers.json`:

```json
{
  "dealer_id": "dealer_001",
  "account_id": "12345678",
  "name": "Dealer Name",
  "oauth": {
    "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
    "client_secret": "GOCSPX-YOUR_SECRET",
    "refresh_token": "1//REFRESH_TOKEN_FROM_STEP_2"
  }
}
```

### 4. Restart Server

The server will load the new credentials on startup.
```

---

## Success Criteria for POC

### Technical Validation
- [x] Dockerfile builds successfully
- [ ] Server runs in Docker container
- [ ] Multiple dealer OAuth credentials can be configured
- [ ] Tokens refresh automatically before expiry
- [ ] Each tool works with `dealer_id` parameter
- [ ] Data isolation: dealer A can't access dealer B's data
- [ ] Falls back to ADC when no credentials configured
- [ ] Integration with Jarvis LibreChat works

### Functional Validation
- [ ] Can list all configured dealers
- [ ] Can query GA4 data for specific dealer
- [ ] Can compare session counts across 2+ dealers
- [ ] Can get top pages for a dealer
- [ ] Error handling works (invalid dealer_id, expired creds)

### Deployment Validation
- [ ] Docker container runs stably for 24+ hours
- [ ] Logs are helpful for debugging
- [ ] Can deploy to client infrastructure
- [ ] Can scale to 10+ dealers without issues

---

## Out of Scope (Future Enhancements)

The following are **intentionally NOT included** in this POC:

### Sophisticated Analytics
- ❌ Statistical significance testing
- ❌ Trend detection algorithms
- ❌ Anomaly detection
- ❌ Predictive analytics
- ❌ Advanced segmentation

### Vehicle Model Detection
- ❌ URL parsing logic
- ❌ Custom dimension mapping
- ❌ Model taxonomy
- ❌ Category classification (SUV/Sedan/Truck)

### Regional Benchmarking
- ❌ Complex aggregation logic
- ❌ Percentile calculations (top 10%, bottom 25%)
- ❌ Cohort analysis (similar dealers)
- ❌ Geographic grouping logic

### Advanced Features
- ❌ Caching layer
- ❌ Rate limit management
- ❌ Query optimization
- ❌ Result pagination
- ❌ Custom dashboards
- ❌ Scheduled reports
- ❌ Alerting

**Rationale**: The POC focuses on **proving the multi-account architecture works**. Sophisticated analytics can be layered on top once the foundation is solid.

---

## Timeline (POC)

### Week 1: Infrastructure
- Days 1-2: Complete Phase 1 (Docker)
- Days 3-5: Complete Phase 2 (Authentication)

### Week 2: Integration
- Days 1-3: Complete Phase 3 (Utils updates)
- Days 4-5: Complete Phase 4 (Tool updates)

### Week 3: Validation
- Days 1-2: Complete Phase 5 (Simple use cases)
- Days 3-4: Complete Phase 6 (Testing)
- Day 5: Complete Phase 7 (Docs)

### Week 4: Deployment & Demo
- Days 1-2: Deploy to test environment
- Day 3: Onboard 3-5 test dealers
- Days 4-5: Demo to stakeholders

**Total**: 4 weeks to working POC

---

## Key Design Decisions

1. **Simple Tool API**: Tools accept `dealer_id` as optional parameter (not middleware-based)
   - **Pro**: Simpler, more explicit, easier to test
   - **Con**: Every tool needs the parameter (but it's just one line)

2. **Global Credential Broker**: Single broker instance initialized at server startup
   - **Pro**: Simple, thread-safe, easy to test
   - **Con**: Can't add dealers dynamically (need restart)

3. **Minimal Use Cases**: Simple comparison tools only, no sophisticated analytics
   - **Pro**: Faster POC, proves architecture without over-engineering
   - **Con**: Limited demo value (but that's okay for POC)

4. **Config File for Credentials**: JSON file with OAuth tokens
   - **Pro**: Simple, no database needed, easy to version control template
   - **Con**: Not ideal for production (but fine for POC)

---

## Next Steps After POC

### If POC Succeeds

1. **Add Sophisticated Analytics** (Phase 8 from original plan)
   - Regional benchmarking with statistical significance
   - Vehicle interest detection with ML
   - Trend analysis and forecasting

2. **Improve Credential Management**
   - Database or secrets manager instead of JSON file
   - UI for dealer onboarding
   - Self-service OAuth flow

3. **Add More Data Sources**
   - Salesforce CRM MCP server
   - Inventory API MCP server
   - Advertising platform MCP servers

4. **Production Hardening**
   - Caching layer
   - Rate limit management
   - High availability deployment
   - Monitoring and alerting

### If POC Needs Iteration

- Identify blockers (OAuth complexity? API quotas? Performance?)
- Refine architecture based on learnings
- Adjust scope if needed

---

## Questions to Answer During POC

1. **OAuth Onboarding**: How difficult is it to get refresh tokens from dealers?
2. **Token Management**: Do tokens refresh reliably? Any edge cases?
3. **Performance**: How fast are multi-dealer queries? Any bottlenecks?
4. **Error Handling**: What errors occur in practice? How to handle gracefully?
5. **Jarvis Integration**: Does the tool API work well with LLM queries?
6. **Scalability**: Can we support 50+ dealers without issues?

---

## Appendix: Example Queries

### Query 1: List Dealers
```
User → Jarvis: "Which dealers are configured?"
Jarvis → MCP: list_configured_dealers()
MCP → Jarvis: [{"dealer_id": "dealer_001", "name": "Downtown"}, ...]
Jarvis → User: "You have 3 dealers configured: Downtown, Westside, and Suburbs"
```

### Query 2: Get Data for One Dealer
```
User → Jarvis: "Show me sessions for dealer_001 in the last 30 days"
Jarvis → MCP: run_report(property_id="123456789", dealer_id="dealer_001", ...)
MCP → Jarvis: {"rows": [...], "row_count": 1, "totals": {"sessions": 45200}}
Jarvis → User: "Dealer 001 had 45,200 sessions in the last 30 days"
```

### Query 3: Compare Dealers
```
User → Jarvis: "Compare sessions for dealer_001 and dealer_002"
Jarvis → MCP: compare_dealer_sessions(["dealer_001", "dealer_002"], ...)
MCP → Jarvis: {"dealers": {...}, "regional_average": 41850}
Jarvis → User: "Dealer 001: 45,200 | Dealer 002: 38,500 | Average: 41,850"
```

---

**This POC-focused plan prioritizes getting the multi-account infrastructure working with minimal complexity. Advanced analytics can be added once the foundation is proven.**
