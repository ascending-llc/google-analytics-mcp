"""
Google Analytics API Scopes

Defines the OAuth scopes required for Google Analytics API access.
"""

# Read-only access to Google Analytics
ANALYTICS_READONLY_SCOPE = (
    "https://www.googleapis.com/auth/analytics.readonly"
)

# Full access to Google Analytics (for future write operations)
ANALYTICS_SCOPE = "https://www.googleapis.com/auth/analytics"

# User profile info (required to get user email for identification)
USERINFO_EMAIL_SCOPE = "https://www.googleapis.com/auth/userinfo.email"

# Default scopes for all Analytics MCP operations
# Using readonly for now - can be expanded later for write operations
DEFAULT_SCOPES = [
    ANALYTICS_READONLY_SCOPE,
    USERINFO_EMAIL_SCOPE,
]
