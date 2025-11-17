#!/usr/bin/env python

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

"""Entry point for the Google Analytics MCP server."""

import os
import logging

from starlette.requests import Request
from starlette.responses import HTMLResponse

from analytics_mcp.coordinator import mcp
from analytics_mcp.auth.google_auth import handle_auth_callback
from analytics_mcp.auth.oauth_config import get_oauth_config
from analytics_mcp.auth.oauth_responses import (
    create_error_response,
    create_success_response,
    create_server_error_response,
)
from analytics_mcp.auth.oauth21_session_store import get_oauth21_session_store
from analytics_mcp.auth.scopes import DEFAULT_SCOPES

# The following imports are necessary to register the tools with the `mcp`
# object, even though they are not directly used in this file.
# The `# noqa: F401` comment tells the linter to ignore the "unused import"
# warning.
from analytics_mcp.tools.admin import info  # noqa: F401
from analytics_mcp.tools.reporting import realtime  # noqa: F401
from analytics_mcp.tools.reporting import core  # noqa: F401

logger = logging.getLogger(__name__)


@mcp.custom_route("/oauth2callback", methods=["GET"])
async def oauth2_callback(request: Request) -> HTMLResponse:
    """
    OAuth 2.0 callback endpoint.

    Handles the redirect from Google after user authorizes access.
    Exchanges authorization code for tokens and stores them.
    """
    state = request.query_params.get("state")
    code = request.query_params.get("code")
    error = request.query_params.get("error")

    if error:
        msg = f"Authentication failed: Google returned an error: {error}. State: {state}."
        logger.error(msg)
        return create_error_response(msg)

    if not code:
        msg = "Authentication failed: No authorization code received from Google."
        logger.error(msg)
        return create_error_response(msg)

    try:
        config = get_oauth_config()
        logger.info(f"OAuth callback: Received code (state: {state}).")

        # Get MCP session ID if available
        mcp_session_id = None
        if hasattr(request, 'state') and hasattr(request.state, 'session_id'):
            mcp_session_id = request.state.session_id

        # Exchange code for tokens
        user_email, credentials = handle_auth_callback(
            scopes=DEFAULT_SCOPES,
            authorization_response=str(request.url),
            redirect_uri=config.redirect_uri,
            session_id=mcp_session_id
        )

        logger.info(f"OAuth callback: Successfully authenticated user: {user_email}.")

        # Store credentials in session store (for current session)
        try:
            store = get_oauth21_session_store()

            store.store_session(
                user_email=user_email,
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_uri=credentials.token_uri,
                client_id=credentials.client_id,
                client_secret=credentials.client_secret,
                scopes=credentials.scopes,
                expiry=credentials.expiry,
                session_id=f"google-{state}",
                mcp_session_id=mcp_session_id,
                issuer="https://accounts.google.com",
            )
            logger.info(f"Stored Google credentials in session store for {user_email}")
        except Exception as e:
            logger.error(f"Failed to store credentials in session store: {e}")

        return create_success_response(user_email)

    except Exception as e:
        logger.error(f"Error processing OAuth callback: {str(e)}", exc_info=True)
        return create_server_error_response(str(e))


def main() -> None:
    """Runs the MCP server using the FastMCP transports."""
    transport = os.getenv("MCP_TRANSPORT", "streamable-http")

    if transport == "streamable-http":
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


def run_server() -> None:
    """Runs the server.

    Serves as the entrypoint for the 'runmcp' command.
    """
    main()


if __name__ == "__main__":
    run_server()
