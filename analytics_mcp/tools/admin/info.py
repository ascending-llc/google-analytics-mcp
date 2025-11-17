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

"""Tools for gathering Google Analytics account and property information."""

from typing import Any, Dict, List

from analytics_mcp.coordinator import mcp
from analytics_mcp.tools.service_decorator import require_analytics_service
from analytics_mcp.tools.utils import (
    construct_property_rn,
    proto_to_dict,
)
from google.analytics import admin_v1beta, admin_v1alpha


@mcp.tool()
@require_analytics_service("admin")
async def get_account_summaries(
    client,
    user_email: str,
) -> List[Dict[str, Any]]:
    """Retrieves information about the user's Google Analytics accounts and properties.

    Args:
        user_email: User's Google email address for authentication.
    """
    # Uses an async list comprehension so the pager returned by
    # list_account_summaries retrieves all pages.
    summary_pager = await client.list_account_summaries()
    all_pages = [
        proto_to_dict(summary_page) async for summary_page in summary_pager
    ]
    return all_pages


@mcp.tool(title="List links to Google Ads accounts")
@require_analytics_service("admin")
async def list_google_ads_links(
    client,
    property_id: int | str,
    user_email: str,
) -> List[Dict[str, Any]]:
    """Returns a list of links to Google Ads accounts for a property.

    Args:
        property_id: The Google Analytics property ID. Accepted formats are:
          - A number
          - A string consisting of 'properties/' followed by a number
        user_email: User's Google email address for authentication.
    """
    request = admin_v1beta.ListGoogleAdsLinksRequest(
        parent=construct_property_rn(property_id)
    )
    # Uses an async list comprehension so the pager returned by
    # list_google_ads_links retrieves all pages.
    links_pager = await client.list_google_ads_links(request=request)
    all_pages = [
        proto_to_dict(link_page) async for link_page in links_pager
    ]
    return all_pages


@mcp.tool(title="Gets details about a property")
@require_analytics_service("admin")
async def get_property_details(
    client,
    property_id: int | str,
    user_email: str,
) -> Dict[str, Any]:
    """Returns details about a property.
    Args:
        property_id: The Google Analytics property ID. Accepted formats are:
          - A number
          - A string consisting of 'properties/' followed by a number
        user_email: User's Google email address for authentication.
    """
    request = admin_v1beta.GetPropertyRequest(
        name=construct_property_rn(property_id)
    )
    response = await client.get_property(request=request)
    return proto_to_dict(response)


@mcp.tool(title="Gets property annotations for a property")
@require_analytics_service("admin_alpha")
async def list_property_annotations(
    client,
    property_id: int | str,
    user_email: str,
) -> List[Dict[str, Any]]:
    """Returns annotations for a property.

    Annotations are a feature that allows you to leave notes on GA4 for specific dates or periods.
    They are typically used to record service releases, marketing campaign launches or changes,
    and rapid traffic increases or decreases due to external factors.

    Args:
        property_id: The Google Analytics property ID. Accepted formats are:
          - A number
          - A string consisting of 'properties/' followed by a number
        user_email: User's Google email address for authentication.
    """
    request = admin_v1alpha.ListReportingDataAnnotationsRequest(
        parent=construct_property_rn(property_id)
    )
    annotations_pager = await client.list_reporting_data_annotations(
        request=request
    )
    all_pages = [
        proto_to_dict(annotation_page)
        async for annotation_page in annotations_pager
    ]
    return all_pages
