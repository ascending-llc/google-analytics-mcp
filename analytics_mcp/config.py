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

"""Configuration for Google Analytics API clients."""

import os
from dataclasses import dataclass
from typing import Literal


@dataclass
class AnalyticsConfig:
    """Google Analytics API configuration.

    Handles authentication for Google Analytics via OAuth 2.0.
    """

    auth_type: Literal["oauth", "service_account"]
    oauth_token: str | None = None  # User's OAuth access token
    user_email: str | None = None  # User's email from JWT claims
    service_account_credentials: str | None = None  # Path to service account JSON
    property_id: str | None = None  # Optional default property ID

    @classmethod
    def from_env(cls) -> "AnalyticsConfig":
        """Create configuration from environment variables.

        For server-level service account credentials.

        Returns:
            AnalyticsConfig with values from environment variables

        Raises:
            ValueError: If required environment variables are missing
        """
        # Check for service account credentials
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

        if credentials_path:
            if not os.path.exists(credentials_path):
                raise ValueError(
                    f"Service account credentials file not found: {credentials_path}"
                )
            return cls(
                auth_type="service_account",
                service_account_credentials=credentials_path,
            )

        # OAuth mode - credentials come from request headers
        return cls(auth_type="oauth")

    @classmethod
    def from_user_token(
        cls, oauth_token: str, user_email: str, property_id: str | None = None
    ) -> "AnalyticsConfig":
        """Create configuration for a specific user with OAuth token.

        Args:
            oauth_token: User's OAuth access token
            user_email: User's email address
            property_id: Optional default property ID for this user

        Returns:
            AnalyticsConfig configured for the specific user
        """
        return cls(
            auth_type="oauth",
            oauth_token=oauth_token,
            user_email=user_email,
            property_id=property_id,
        )

    def is_auth_configured(self) -> bool:
        """Check if authentication is configured.

        Returns:
            True if authentication is properly configured
        """
        if self.auth_type == "service_account":
            return self.service_account_credentials is not None
        elif self.auth_type == "oauth":
            return self.oauth_token is not None
        return False
