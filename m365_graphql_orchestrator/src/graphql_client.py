"""Fabric GraphQL client — authenticated HTTP client for Fabric GraphQL APIs.

Handles Entra ID token acquisition and refresh, and executes GraphQL
queries against Microsoft Fabric GraphQL API endpoints.

Supports both credential-based auth (local dev via DefaultAzureCredential)
and static token auth (SSO/OBO user tokens from M365 channels).
"""

import json
import logging
import time
from typing import Any

import aiohttp
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)

FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"
_TOKEN_REFRESH_BUFFER_SECS = 300  # 5 minutes


class FabricGraphQLClient:
    """Authenticated client for executing GraphQL queries against Fabric APIs."""

    def __init__(self, *, credential=None, token: str | None = None):
        if token:
            self._static_token = token
            self._credential = None
            self._cached_token = None
        else:
            self._static_token = None
            self._credential = credential or DefaultAzureCredential()
            self._cached_token = None

    def _get_bearer_token(self) -> str:
        """Return a valid Fabric bearer token, refreshing if necessary."""
        if self._static_token:
            return self._static_token

        need_refresh = (
            self._cached_token is None
            or time.time() >= self._cached_token.expires_on - _TOKEN_REFRESH_BUFFER_SECS
        )
        if need_refresh:
            logger.info("Acquiring/refreshing Fabric token via credential …")
            self._cached_token = self._credential.get_token(FABRIC_SCOPE)
            logger.info(
                "Token acquired (expires in %.0f s)",
                self._cached_token.expires_on - time.time(),
            )
        return self._cached_token.token

    async def execute(
        self,
        endpoint_url: str,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a GraphQL query against a Fabric GraphQL API endpoint."""
        token = self._get_bearer_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        logger.debug("GraphQL request to %s", endpoint_url)
        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint_url, headers=headers, json=payload) as resp:
                if resp.status >= 400:
                    error_body = await resp.text()
                    logger.error(
                        "GraphQL HTTP %d from %s — body: %s",
                        resp.status, endpoint_url, error_body,
                    )
                    return {
                        "errors": [{
                            "message": f"Fabric returned HTTP {resp.status}",
                            "status": resp.status,
                            "detail": error_body,
                        }]
                    }
                result = await resp.json()

        if "errors" in result:
            logger.warning("GraphQL errors: %s", json.dumps(result["errors"], indent=2))

        return result
