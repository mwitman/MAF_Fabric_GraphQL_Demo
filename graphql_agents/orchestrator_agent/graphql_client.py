"""Fabric GraphQL client — authenticated HTTP client for Fabric GraphQL APIs.

Handles Entra ID token acquisition and refresh, and executes GraphQL
queries against Microsoft Fabric GraphQL API endpoints.
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
    """Authenticated client for executing GraphQL queries against Fabric APIs.

    Supports two authentication modes:
    - **Static token**: pass a pre-acquired bearer token (e.g. from SSO/OBO).
    - **Credential-based**: uses ``DefaultAzureCredential`` (or a supplied
      credential) and refreshes the token automatically.
    """

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
        """Execute a GraphQL query against a Fabric GraphQL API endpoint.

        Args:
            endpoint_url: Full URL of the Fabric GraphQL API endpoint.
            query: GraphQL query string.
            variables: Optional dictionary of GraphQL variables.

        Returns:
            Parsed JSON response from the GraphQL API.
        """
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
                resp.raise_for_status()
                result = await resp.json()

        if "errors" in result:
            logger.warning("GraphQL errors: %s", json.dumps(result["errors"], indent=2))

        return result
