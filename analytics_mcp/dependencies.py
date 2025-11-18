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

"""Dependency providers for Google Analytics API clients with context awareness."""

import logging
from typing import TYPE_CHECKING

from fastmcp import Context
from fastmcp.server.dependencies import get_http_request
from google.analytics import admin_v1beta, data_v1beta, admin_v1alpha
from google.api_core.gapic_v1.client_info import ClientInfo
from google.oauth2.credentials import Credentials
from importlib import metadata
from starlette.requests import Request

from analytics_mcp.config import AnalyticsConfig

if TYPE_CHECKING:
    from analytics_mcp.context import AppContext

logger = logging.getLogger("analytics-mcp.dependencies")


def _get_package_version_with_fallback():
    """Returns the version of the package.

    Falls back to 'unknown' if the version can't be resolved.
    """
    try:
        return metadata.version("analytics-mcp")
    except:
        return "unknown"


# Client information that adds a custom user agent to all API requests.
_CLIENT_INFO = ClientInfo(
    user_agent=f"analytics-mcp/{_get_package_version_with_fallback()}"
)


def _create_user_credentials(oauth_token: str) -> Credentials:
    """Create Google OAuth credentials from user's access token.

    Args:
        oauth_token: User's OAuth access token

    Returns:
        Credentials object configured for the user
    """
    return Credentials(token=oauth_token)


async def get_analytics_admin_client(
    ctx: Context,
) -> admin_v1beta.AnalyticsAdminServiceAsyncClient:
    """Returns an Analytics Admin API client for the current request context.

    Args:
        ctx: The FastMCP context

    Returns:
        AnalyticsAdminServiceAsyncClient instance for the current user

    Raises:
        ValueError: If configuration or credentials are invalid
    """
    logger.debug(f"get_analytics_admin_client: ENTERED. Context ID: {id(ctx)}")

    try:
        request: Request = get_http_request()
        logger.debug(
            f"get_analytics_admin_client: In HTTP request context. Request URL: {request.url}"
        )

        # Check if client is already cached in request state
        if hasattr(request.state, "admin_client") and request.state.admin_client:
            logger.debug("get_analytics_admin_client: Returning cached client")
            return request.state.admin_client

        # Extract user token from request state (set by UserTokenMiddleware)
        user_token = getattr(request.state, "user_google_token", None)
        user_email = getattr(request.state, "user_email", None)

        if not user_token:
            raise ValueError(
                "User Google OAuth token not found in request state. "
                "Ensure UserTokenMiddleware is properly configured."
            )

        logger.info(
            f"Creating user-specific Admin API client for user {user_email} "
            f"(token ...{str(user_token)[-8:]})"
        )

        # Create user-specific credentials
        credentials = _create_user_credentials(user_token)

        # Create and cache the client
        client = admin_v1beta.AnalyticsAdminServiceAsyncClient(
            client_info=_CLIENT_INFO, credentials=credentials
        )

        # Cache in request state for this request duration
        # Token validation happens naturally when the actual API call is made
        request.state.admin_client = client
        logger.debug(
            f"get_analytics_admin_client: Created client for user {user_email}"
        )
        return client

    except RuntimeError:
        logger.error("Not in an HTTP request context")
        raise ValueError(
            "Analytics Admin API client requires HTTP request context with OAuth token"
        )


async def get_analytics_data_client(
    ctx: Context,
) -> data_v1beta.BetaAnalyticsDataAsyncClient:
    """Returns an Analytics Data API client for the current request context.

    Args:
        ctx: The FastMCP context

    Returns:
        BetaAnalyticsDataAsyncClient instance for the current user

    Raises:
        ValueError: If configuration or credentials are invalid
    """
    logger.debug(f"get_analytics_data_client: ENTERED. Context ID: {id(ctx)}")

    try:
        request: Request = get_http_request()
        logger.debug(
            f"get_analytics_data_client: In HTTP request context. Request URL: {request.url}"
        )

        # Check if client is already cached in request state
        if hasattr(request.state, "data_client") and request.state.data_client:
            logger.debug("get_analytics_data_client: Returning cached client")
            return request.state.data_client

        # Extract user token from request state (set by UserTokenMiddleware)
        user_token = getattr(request.state, "user_google_token", None)
        user_email = getattr(request.state, "user_email", None)

        if not user_token:
            raise ValueError(
                "User Google OAuth token not found in request state. "
                "Ensure UserTokenMiddleware is properly configured."
            )

        logger.info(
            f"Creating user-specific Data API client for user {user_email} "
            f"(token ...{str(user_token)[-8:]})"
        )

        # Create user-specific credentials
        credentials = _create_user_credentials(user_token)

        # Create and cache the client
        client = data_v1beta.BetaAnalyticsDataAsyncClient(
            client_info=_CLIENT_INFO, credentials=credentials
        )

        # Cache in request state for this request duration
        request.state.data_client = client
        return client

    except RuntimeError:
        logger.error("Not in an HTTP request context")
        raise ValueError(
            "Analytics Data API client requires HTTP request context with OAuth token"
        )


async def get_analytics_admin_alpha_client(
    ctx: Context,
) -> admin_v1alpha.AnalyticsAdminServiceAsyncClient:
    """Returns an Analytics Admin API (alpha) client for the current request context.

    Args:
        ctx: The FastMCP context

    Returns:
        AnalyticsAdminServiceAsyncClient (alpha) instance for the current user

    Raises:
        ValueError: If configuration or credentials are invalid
    """
    logger.debug(f"get_analytics_admin_alpha_client: ENTERED. Context ID: {id(ctx)}")

    try:
        request: Request = get_http_request()
        logger.debug(
            f"get_analytics_admin_alpha_client: In HTTP request context. Request URL: {request.url}"
        )

        # Check if client is already cached in request state
        if (
            hasattr(request.state, "admin_alpha_client")
            and request.state.admin_alpha_client
        ):
            logger.debug("get_analytics_admin_alpha_client: Returning cached client")
            return request.state.admin_alpha_client

        # Extract user token from request state (set by UserTokenMiddleware)
        user_token = getattr(request.state, "user_google_token", None)
        user_email = getattr(request.state, "user_email", None)

        if not user_token:
            raise ValueError(
                "User Google OAuth token not found in request state. "
                "Ensure UserTokenMiddleware is properly configured."
            )

        logger.info(
            f"Creating user-specific Admin Alpha API client for user {user_email} "
            f"(token ...{str(user_token)[-8:]})"
        )

        # Create user-specific credentials
        credentials = _create_user_credentials(user_token)

        # Create and cache the client
        client = admin_v1alpha.AnalyticsAdminServiceAsyncClient(
            client_info=_CLIENT_INFO, credentials=credentials
        )

        # Cache in request state for this request duration
        request.state.admin_alpha_client = client
        return client

    except RuntimeError:
        logger.error("Not in an HTTP request context")
        raise ValueError(
            "Analytics Admin Alpha API client requires HTTP request context with OAuth token"
        )
