"""
OAuth Configuration Management for Analytics MCP

Centralizes OAuth-related configuration to eliminate hardcoded values.
Provides environment variable support and sensible defaults.
"""

import os
from typing import List, Optional


class OAuthConfig:
    """
    Centralized OAuth configuration management for Analytics MCP.

    Provides a single source of truth for all OAuth-related configuration values.
    """

    def __init__(self):
        # Base server configuration
        self.base_uri = os.getenv("ANALYTICS_MCP_BASE_URI", "http://localhost")

        # Extract port number (handle Kubernetes service URL format)
        port_env = os.getenv("ANALYTICS_MCP_PORT", "3334")
        if "://" in port_env:
            # Kubernetes sets this to tcp://IP:PORT, extract just the port
            port_env = port_env.split(":")[-1]
        self.port = int(port_env)  # Default port for Analytics MCP
        self.base_url = f"{self.base_uri}:{self.port}"

        # External URL for reverse proxy scenarios (e.g., Jarvis)
        self.external_url = os.getenv("ANALYTICS_EXTERNAL_URL")

        # OAuth client configuration
        self.client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")

        # OAuth 2.1 configuration (optional, for future)
        self.oauth21_enabled = os.getenv("MCP_ENABLE_OAUTH21", "false").lower() == "true"

        # Stateless mode configuration (no file-based credential storage)
        self.stateless_mode = os.getenv("ANALYTICS_MCP_STATELESS_MODE", "false").lower() == "true"
        if self.stateless_mode and not self.oauth21_enabled:
            raise ValueError("ANALYTICS_MCP_STATELESS_MODE requires MCP_ENABLE_OAUTH21=true")

        # Transport mode (will be set at runtime)
        self._transport_mode = "streamable-http"  # Default for Jarvis

        # Redirect URI configuration
        self.redirect_uri = self._get_redirect_uri()

    def _get_redirect_uri(self) -> str:
        """
        Get the OAuth redirect URI, supporting reverse proxy configurations.

        Returns:
            The configured redirect URI
        """
        explicit_uri = os.getenv("GOOGLE_OAUTH_REDIRECT_URI")
        if explicit_uri:
            return explicit_uri
        return f"{self.get_oauth_base_url()}/oauth2callback"

    def get_redirect_uris(self) -> List[str]:
        """
        Get all valid OAuth redirect URIs.

        Returns:
            List of all supported redirect URIs
        """
        uris = []

        # Primary redirect URI
        uris.append(self.redirect_uri)

        # Custom redirect URIs from environment
        custom_uris = os.getenv("OAUTH_CUSTOM_REDIRECT_URIS")
        if custom_uris:
            uris.extend([uri.strip() for uri in custom_uris.split(",")])

        # Remove duplicates while preserving order
        return list(dict.fromkeys(uris))

    def get_allowed_origins(self) -> List[str]:
        """
        Get allowed CORS origins for OAuth endpoints.

        Returns:
            List of allowed origins for CORS
        """
        origins = []

        # Server's own origin
        origins.append(self.base_url)

        # Jarvis origins
        if self.external_url:
            origins.append(self.external_url)

        # Custom origins from environment
        custom_origins = os.getenv("OAUTH_ALLOWED_ORIGINS")
        if custom_origins:
            origins.extend([origin.strip() for origin in custom_origins.split(",")])

        return list(dict.fromkeys(origins))

    def is_configured(self) -> bool:
        """
        Check if OAuth is properly configured.

        Returns:
            True if OAuth client credentials are available
        """
        return bool(self.client_id and self.client_secret)

    def get_oauth_base_url(self) -> str:
        """
        Get OAuth base URL for constructing OAuth endpoints.

        Uses ANALYTICS_EXTERNAL_URL if set (for reverse proxy scenarios like Jarvis),
        otherwise falls back to constructed base_url with port.

        Returns:
            Base URL for OAuth endpoints
        """
        if self.external_url:
            return self.external_url
        return self.base_url

    def validate_redirect_uri(self, uri: str) -> bool:
        """
        Validate if a redirect URI is allowed.

        Args:
            uri: The redirect URI to validate

        Returns:
            True if the URI is allowed, False otherwise
        """
        allowed_uris = self.get_redirect_uris()
        return uri in allowed_uris

    def get_environment_summary(self) -> dict:
        """
        Get a summary of the current OAuth configuration.

        Returns:
            Dictionary with configuration summary (excluding secrets)
        """
        return {
            "base_url": self.base_url,
            "external_url": self.external_url,
            "effective_oauth_url": self.get_oauth_base_url(),
            "redirect_uri": self.redirect_uri,
            "client_configured": bool(self.client_id),
            "oauth21_enabled": self.oauth21_enabled,
            "stateless_mode": self.stateless_mode,
            "transport_mode": self._transport_mode,
            "total_redirect_uris": len(self.get_redirect_uris()),
            "total_allowed_origins": len(self.get_allowed_origins()),
        }

    def set_transport_mode(self, mode: str) -> None:
        """
        Set the current transport mode for OAuth callback handling.

        Args:
            mode: Transport mode ("stdio", "streamable-http", etc.)
        """
        self._transport_mode = mode

    def get_transport_mode(self) -> str:
        """
        Get the current transport mode.

        Returns:
            Current transport mode
        """
        return self._transport_mode

    def is_oauth21_enabled(self) -> bool:
        """
        Check if OAuth 2.1 mode is enabled.

        Returns:
            True if OAuth 2.1 is enabled
        """
        return self.oauth21_enabled

    def is_stateless_mode(self) -> bool:
        """
        Check if stateless mode is enabled.

        Returns:
            True if stateless mode is enabled
        """
        return self.stateless_mode


# Global configuration instance
_oauth_config: Optional[OAuthConfig] = None


def get_oauth_config() -> OAuthConfig:
    """
    Get the global OAuth configuration instance.

    Returns:
        The singleton OAuth configuration instance
    """
    global _oauth_config
    if _oauth_config is None:
        _oauth_config = OAuthConfig()
    return _oauth_config


def reload_oauth_config() -> OAuthConfig:
    """
    Reload the OAuth configuration from environment variables.

    This is useful for testing or when environment variables change.

    Returns:
        The reloaded OAuth configuration instance
    """
    global _oauth_config
    _oauth_config = OAuthConfig()
    return _oauth_config


# Convenience functions for backward compatibility
def get_oauth_base_url() -> str:
    """Get OAuth base URL."""
    return get_oauth_config().get_oauth_base_url()


def get_redirect_uris() -> List[str]:
    """Get all valid OAuth redirect URIs."""
    return get_oauth_config().get_redirect_uris()


def get_allowed_origins() -> List[str]:
    """Get allowed CORS origins."""
    return get_oauth_config().get_allowed_origins()


def is_oauth_configured() -> bool:
    """Check if OAuth is properly configured."""
    return get_oauth_config().is_configured()


def set_transport_mode(mode: str) -> None:
    """Set the current transport mode."""
    get_oauth_config().set_transport_mode(mode)


def get_transport_mode() -> str:
    """Get the current transport mode."""
    return get_oauth_config().get_transport_mode()


def is_oauth21_enabled() -> bool:
    """Check if OAuth 2.1 is enabled."""
    return get_oauth_config().is_oauth21_enabled()


def get_oauth_redirect_uri() -> str:
    """Get the primary OAuth redirect URI."""
    return get_oauth_config().redirect_uri


def is_stateless_mode() -> bool:
    """Check if stateless mode is enabled."""
    return get_oauth_config().stateless_mode
