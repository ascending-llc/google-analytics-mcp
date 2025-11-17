# Google Analytics MCP - OAuth Setup Guide

This guide covers the complete OAuth setup for integrating the Google Analytics MCP server with Jarvis.

## Overview

The OAuth flow works as follows:
1. User attempts to use an Analytics tool in Jarvis
2. Jarvis detects `requiresOAuth: true` and no valid token exists
3. Jarvis redirects user to Google OAuth consent screen
4. User authorizes access to their Google Analytics data
5. Google redirects back to Jarvis with authorization code
6. Jarvis exchanges code for access/refresh tokens
7. Jarvis stores tokens and associates them with the user's session
8. Jarvis passes tokens to analytics-mcp server with each MCP request
9. MCP server uses tokens to query Google Analytics APIs on behalf of the user

---

## Part 1: Google Cloud Platform (GCP) Setup

### Prerequisites
- Access to a Google Cloud Platform project (your sandbox GCP account)
- Admin permissions to create OAuth credentials

### Step 1: Enable Required APIs

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your sandbox GCP project
3. Navigate to **APIs & Services > Library**
4. Enable the following APIs:
   - **Google Analytics Admin API**
     - Search for "Google Analytics Admin API"
     - Click "Enable"
   - **Google Analytics Data API**
     - Search for "Google Analytics Data API"
     - Click "Enable"

### Step 2: Configure OAuth Consent Screen

1. Navigate to **APIs & Services > OAuth consent screen**
2. Choose user type:
   - **Internal** - If testing only with @ascendingdc.com users
   - **External** - For broader testing (requires verification for production)
3. Fill in required fields:
   - **App name**: `Jarvis Analytics Integration` (or your preferred name)
   - **User support email**: Your email
   - **Developer contact email**: Your email
4. Click **Save and Continue**

5. **Add Scopes** (Step 2 of consent screen setup):
   - Click **Add or Remove Scopes**
   - Add the following scopes:
     ```
     https://www.googleapis.com/auth/userinfo.email
     https://www.googleapis.com/auth/userinfo.profile
     openid
     https://www.googleapis.com/auth/analytics.readonly
     ```
   - Explanation of scopes:
     - `openid` - OpenID Connect authentication
     - `userinfo.email` - User's email address (used as identifier in MCP)
     - `userinfo.profile` - User's basic profile info
     - `analytics.readonly` - Read-only access to Google Analytics data
   - Click **Update** then **Save and Continue**

6. **Test Users** (if using External type):
   - Add email addresses that can test the OAuth flow
   - Click **Save and Continue**

7. Review and click **Back to Dashboard**

### Step 3: Create OAuth 2.0 Client Credentials

1. Navigate to **APIs & Services > Credentials**
2. Click **+ Create Credentials** > **OAuth client ID**
3. Configure the OAuth client:
   - **Application type**: Web application
   - **Name**: `Jarvis Analytics MCP Client`

4. **Authorized redirect URIs** - Add the following URIs:
   ```
   https://jarvis-demo.ascendingdc.com/oauth/mcp/analytics/callback
   ```
   - This is the callback URL where Jarvis will receive the authorization code
   - The pattern is: `https://{jarvis-domain}/oauth/mcp/{mcp-server-name}/callback`
   - For local testing, you could also add: `http://localhost:3334/oauth2callback` (optional)

5. Click **Create**

6. **Save your credentials** - You'll see a dialog with:
   - **Client ID** (looks like: `123456789-xxxxxxxxxxxxx.apps.googleusercontent.com`)
   - **Client Secret** (looks like: `GOCSPX-xxxxxxxxxxxxxxxxxxxxxxxx`)
   - **Important**: Copy both of these - you'll need them for the Jarvis configuration

### Step 4: Grant Analytics Access (Testing)

For testing, ensure the Google account you'll authenticate with has access to at least one Google Analytics 4 property:

1. Go to [Google Analytics](https://analytics.google.com/)
2. If you don't have a GA4 property, create a test property
3. Ensure your test user email (e.g., alexander.groman@ascendingdc.com) has at least **Viewer** access to the property

---

## Part 2: Jarvis Deployment Configuration

### Step 1: Add MCP Server Configuration

Edit `jarvis-deployment/ascending/saas-account/terraform/jarvis-demo/values.yaml`

**Location 1: Add to `mcpServers` section** (around line 268, after cloudwatch):

```yaml
      cloudwatch:
        type: streamable-http
        url: http://cloudwatch-mcp:3334/mcp
        timeout: 120000
      analytics:
        type: streamable-http
        url: http://analytics-mcp:3334/mcp
        timeout: 120000
        requiresOAuth: true
        oauth:
          client_id: "YOUR_CLIENT_ID_FROM_GCP"
          client_secret: "YOUR_CLIENT_SECRET_FROM_GCP"
          authorization_url: "https://accounts.google.com/o/oauth2/v2/auth"
          token_url: "https://oauth2.googleapis.com/token"
          scope: "openid https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/analytics.readonly"
        customToolArgs:
          user_email: "{{LIBRECHAT_USER_EMAIL}}"
```

**Important Configuration Details:**

- `requiresOAuth: true` - Tells Jarvis this MCP server requires OAuth
- `oauth.client_id` - Replace with your GCP Client ID
- `oauth.client_secret` - Replace with your GCP Client Secret
- `oauth.authorization_url` - Google's OAuth authorization endpoint
- `oauth.token_url` - Google's OAuth token exchange endpoint
- `oauth.scope` - Space-separated list of OAuth scopes (must match GCP consent screen)
- `customToolArgs.user_email` - Auto-injects authenticated user's email into all tool calls

**Location 2: Add to `mcpConfigs` section** (around line 722, after cloudwatch-mcp):

```yaml
  - name: cloudwatch-mcp
    enabled: true
    image:
      repository: 897729109735.dkr.ecr.us-east-1.amazonaws.com/jarvis/cloudwatch_mcp_server
      tag: latest
    serviceAccount:
      name: cloudwatch-mcp-service-account
      annotations:
        eks.amazonaws.com/role-arn: "arn:aws:iam::897729109735:role/CloudWatchMCPServerRole"
    service:
      port: 3334

  - name: analytics-mcp
    enabled: true
    image:
      repository: 897729109735.dkr.ecr.us-east-1.amazonaws.com/jarvis/ga_mcp_server
      tag: latest
    service:
      port: 3334
```

**Configuration Details:**

- `name: analytics-mcp` - Kubernetes service name (used in URL: `http://analytics-mcp:3334/mcp`)
- `enabled: true` - Deploy this MCP server
- `image.repository` - ECR repository URL (already created)
- `image.tag: latest` - Use the latest image tag
- `service.port: 3334` - Port the MCP server listens on (matches our Dockerfile)

### Step 2: Commit and Deploy

```bash
# Navigate to jarvis-deployment
cd /Users/alexandergroman/Development/jarvis-deployment

# Check what changed
git diff

# Add and commit
git add ascending/saas-account/terraform/jarvis-demo/values.yaml
git commit -m "feat: add Google Analytics MCP server with OAuth"

# Push to trigger deployment (if using GitOps)
git push origin main
```

### Step 3: Apply with Terraform

```bash
# Navigate to terraform directory
cd ascending/saas-account/terraform/jarvis-demo

# Plan the changes
terraform plan

# Apply if plan looks good
terraform apply
```

---

## Part 3: Testing the OAuth Flow

### Step 1: Access Jarvis Demo

1. Navigate to https://jarvis-demo.ascendingdc.com
2. Log in with your ascendingdc.com account

### Step 2: Verify MCP Server is Connected

1. In Jarvis, check the MCP connections/tools menu
2. You should see "Analytics" connection listed
3. It should show as "Not Authenticated" initially

### Step 3: Test OAuth Flow

1. Try to use any Analytics tool, for example:
   - "Get my Google Analytics account summaries"
   - Or use the tool picker to select `get_account_summaries`

2. If not authenticated, Jarvis should:
   - Redirect you to Google OAuth consent screen
   - Show the scopes being requested
   - Show "Jarvis Analytics Integration" (or your app name)

3. Click **Allow** to grant access

4. You should be redirected back to Jarvis

5. The tool should now execute and return your GA4 account/property list

### Step 4: Verify Tools Work

Test various tools to ensure OAuth is working:

```
# Get account summaries
"Show me my Google Analytics accounts"

# Get property details (replace with your property ID)
"Get details for Google Analytics property 123456789"

# Run a report
"Run a Google Analytics report for property 123456789
 showing pageViews and sessions by date
 for the last 7 days"
```

### Step 5: Verify Token Persistence

1. Refresh the page or start a new conversation
2. Try using an Analytics tool again
3. You should NOT be prompted to re-authenticate
4. Tools should work immediately using stored tokens

---

## Troubleshooting

### Error: "redirect_uri_mismatch"

**Cause**: The redirect URI in your request doesn't match what's configured in GCP.

**Fix**:
1. Go to GCP Console > APIs & Services > Credentials
2. Edit your OAuth client
3. Ensure redirect URI is exactly: `https://jarvis-demo.ascendingdc.com/oauth/mcp/analytics/callback`
4. No trailing slashes, exact match required

### Error: "access_denied" or "restricted"

**Cause**: OAuth app is restricted to certain users/domains.

**Fix**:
1. Check OAuth consent screen configuration
2. If "Internal" - ensure you're using an @ascendingdc.com account
3. If "External" - ensure testing user is added to test users list

### Error: "Invalid scope"

**Cause**: Requested scope not enabled in OAuth consent screen.

**Fix**:
1. Go to OAuth consent screen in GCP
2. Edit scopes and ensure `analytics.readonly` is added
3. Save and retry

### Tools return "authentication_required" error

**Cause**: OAuth flow completed but tokens aren't being passed to MCP server.

**Fix**:
1. Check MCP server logs: `kubectl logs -n default -l app=analytics-mcp`
2. Verify `customToolArgs.user_email` is configured in values.yaml
3. Verify user_email is being extracted in middleware

### MCP server not receiving user credentials

**Cause**: Session middleware not extracting tokens properly.

**Fix**:
1. Check that Jarvis is passing tokens in MCP session context
2. Verify our `MCPSessionMiddleware` is correctly extracting user info
3. Check server logs for authentication errors

---

## Architecture Summary

### OAuth Token Flow

```
┌─────────┐                 ┌─────────┐                ┌──────────┐               ┌─────────────┐
│  User   │────(1)────────> │ Jarvis  │───(2)───────>  │  Google  │               │ Analytics   │
│ Browser │                 │   API   │                │  OAuth   │               │  MCP Server │
└─────────┘                 └─────────┘                └──────────┘               └─────────────┘
     │                            │                          │                            │
     │                            │                          │                            │
     │    (3) Redirect to         │                          │                            │
     │    OAuth consent           │                          │                            │
     │<───────────────────────────│                          │                            │
     │                                                       │                            │
     │    (4) User authorizes                                │                            │
     │──────────────────────────────────────────────────────>│                            │
     │                                                       │                            │
     │    (5) Redirect with code                             │                            │
     │<──────────────────────────────────────────────────────│                            │
     │                                                       │                            │
     │    (6) Code to Jarvis                                 │                            │
     │──────────────────────────────>│                       │                            │
     │                               │                       │                            │
     │                               │  (7) Exchange code    │                            │
     │                               │──────────────────────>│                            │
     │                               │                       │                            │
     │                               │  (8) Return tokens    │                            │
     │                               │<──────────────────────│                            │
     │                               │                                                    │
     │                               │  (9) Store tokens                                  │
     │                               │  in session                                        │
     │                               │                                                    │
     │   (10) Tool call with tokens  │                                                    │
     │──────────────────────────────>│  (11) MCP request                                  │
     │                               │    with user_email                                 │
     │                               │    and session context                             │
     │                               │───────────────────────────────────────────────────>│
     │                               │                                                    │
     │                               │                        (12) Extract user_email     │
     │                               │                             Load credentials       │
     │                               │                             Create GA API client   │
     │                               │                             Execute tool           │
     │                               │                                                    │
     │                               │  (13) Tool response                                │
     │                               │<───────────────────────────────────────────────────│
     │                               │                                                    │
     │  (14) Response to user        │                                                    │
     │<──────────────────────────────│                                                    │
```

### Key Components

1. **GCP OAuth App**: Provides client credentials and handles authorization
2. **Jarvis OAuth Middleware**: Handles OAuth flow, token exchange, and storage
3. **Analytics MCP Server**: Receives tokens via session, creates authenticated API clients
4. **Session Binding**: Tokens are bound to user sessions for security

### Security Features

- **Per-user authentication**: Each user authenticates separately
- **Session isolation**: One user cannot access another's credentials
- **Token encryption**: Tokens stored encrypted in Jarvis
- **Scope limitation**: Only requested scopes are granted
- **Refresh tokens**: Long-lived access without re-authentication

---

## Reference: Complete values.yaml Snippet

Here's the complete configuration to add to `values.yaml`:

```yaml
# In mcpServers section (around line 268)
    mcpServers:
      # ... other servers ...
      cloudwatch:
        type: streamable-http
        url: http://cloudwatch-mcp:3334/mcp
        timeout: 120000
      analytics:
        type: streamable-http
        url: http://analytics-mcp:3334/mcp
        timeout: 120000
        requiresOAuth: true
        oauth:
          client_id: "YOUR_CLIENT_ID_FROM_GCP"
          client_secret: "YOUR_CLIENT_SECRET_FROM_GCP"
          authorization_url: "https://accounts.google.com/o/oauth2/v2/auth"
          token_url: "https://oauth2.googleapis.com/token"
          scope: "openid https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/analytics.readonly"
        customToolArgs:
          user_email: "{{LIBRECHAT_USER_EMAIL}}"

# In mcpConfigs section (around line 722)
mcpConfigs:
  # ... other MCP configs ...
  - name: cloudwatch-mcp
    enabled: true
    image:
      repository: 897729109735.dkr.ecr.us-east-1.amazonaws.com/jarvis/cloudwatch_mcp_server
      tag: latest
    serviceAccount:
      name: cloudwatch-mcp-service-account
      annotations:
        eks.amazonaws.com/role-arn: "arn:aws:iam::897729109735:role/CloudWatchMCPServerRole"
    service:
      port: 3334

  - name: analytics-mcp
    enabled: true
    image:
      repository: 897729109735.dkr.ecr.us-east-1.amazonaws.com/jarvis/ga_mcp_server
      tag: latest
    service:
      port: 3334
```

---

## Next Steps After Successful Deployment

1. **Monitor logs**: `kubectl logs -n default -l app=analytics-mcp -f`
2. **Test all tools**: Verify each tool works correctly
3. **Production OAuth**: Create separate OAuth credentials for production
4. **User documentation**: Document available Analytics tools for Jarvis users
5. **Scope refinement**: Add write scopes if needed for future admin features
