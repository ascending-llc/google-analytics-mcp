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

"""Authentication module for Analytics MCP.

Note: The old OAuth callback-based authentication has been replaced
with JWT token-based authentication via UserTokenMiddleware.

Old auth files are prefixed with _UNUSED_ and kept for reference only.
"""

# Export only the scopes that might still be useful
from analytics_mcp.auth.scopes import DEFAULT_SCOPES

__all__ = ["DEFAULT_SCOPES"]
