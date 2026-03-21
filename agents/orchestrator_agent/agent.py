"""Fabric Data Agents Orchestrator — single agent wired to 3 Fabric data agent MCP tools.

This module creates an Agent that can query Sales, Customer, and Product
data through Fabric data agent MCP endpoints, authenticated via Entra ID.

DevUI discovers this agent via the __init__.py that exports `agent`.
"""

import os
from pathlib import Path

from azure.identity import DefaultAzureCredential
from agent_framework import AgentMiddleware
from agent_framework.azure import AzureOpenAIResponsesClient
from dotenv import load_dotenv

# Load shared .env from agents/ directory, then any local .env
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

# ---------------------------------------------------------------------------
# Load system prompt from markdown
# ---------------------------------------------------------------------------
_prompt_path = Path(__file__).resolve().parent / "prompts" / "orchestrator_agent.md"
_instructions = _prompt_path.read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# Entra ID authentication
# ---------------------------------------------------------------------------
# DefaultAzureCredential supports az login (local dev) and managed identity
# (production). A Fabric token is requested explicitly for MCP headers.
# The token is refreshed before every agent invocation via middleware so that
# long-running DevUI sessions never hit 401s from expired tokens.
FABRIC_DATA_AGENT_SCOPE = "https://api.fabric.microsoft.com/.default"

credential = DefaultAzureCredential()

# Shared headers dict — get_mcp_tool stores a *reference*, so mutating
# this dict in-place before each call propagates to all MCP tools.
fabric_headers = {
    "Authorization": "",
    "Content-Type": "application/json",
}


def _refresh_fabric_token():
    """Refresh the Fabric bearer token in-place.

    DefaultAzureCredential.get_token() caches internally and only hits
    the network when the token is actually expired, so calling this
    before every request is cheap.
    """
    token = credential.get_token(FABRIC_DATA_AGENT_SCOPE).token
    fabric_headers["Authorization"] = f"Bearer {token}"


class RefreshTokenMiddleware(AgentMiddleware):
    """Agent middleware that refreshes the Fabric token before each invocation."""

    async def process(self, context, call_next):
        _refresh_fabric_token()
        await call_next()


# Fetch an initial token so tool registration succeeds
_refresh_fabric_token()

# ---------------------------------------------------------------------------
# Azure OpenAI client (API key auth)
# ---------------------------------------------------------------------------
client = AzureOpenAIResponsesClient(
    endpoint=os.environ["AOAI_ENDPOINT"],
    api_key=os.environ["AOAI_KEY"],
    deployment_name=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
)

# ---------------------------------------------------------------------------
# Fabric Data Agent MCP tools (hosted — executed server-side by Azure OpenAI)
# ---------------------------------------------------------------------------
sales_tool = client.get_mcp_tool(
    name="Sales Agent",
    url=os.environ["FABRIC_SALES_AGENT_MCP_URL"],
    headers=fabric_headers,
    approval_mode="never_require",
)

customer_tool = client.get_mcp_tool(
    name="Customer Agent",
    url=os.environ["FABRIC_CUSTOMER_AGENT_MCP_URL"],
    headers=fabric_headers,
    approval_mode="never_require",
)

product_tool = client.get_mcp_tool(
    name="Product Agent",
    url=os.environ["FABRIC_PRODUCT_AGENT_MCP_URL"],
    headers=fabric_headers,
    approval_mode="never_require",
)

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
agent = client.as_agent(
    name="Fabric Data Agents Orchestrator",
    description=(
        "Orchestrates three Fabric data agent MCP tools (Sales, Customer, Product) "
        "to answer business questions across orders, customers, addresses, products, "
        "categories, and more."
    ),
    instructions=_instructions,
    tools=[sales_tool, customer_tool, product_tool],
    middleware=[RefreshTokenMiddleware()],
)
