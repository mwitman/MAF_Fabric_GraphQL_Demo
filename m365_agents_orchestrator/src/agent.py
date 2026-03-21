"""Fabric Data Agents Orchestrator — M365 Agents SDK version.

This module creates an M365-channel-compatible agent (Teams, Outlook, Copilot,
etc.) that orchestrates three Fabric data agent MCP tools (Sales, Customer,
Product) via the Azure OpenAI Responses API with hosted MCP execution.

Messages arrive through the M365 Agents SDK ``AgentApplication`` (backed by
aiohttp) and are forwarded to Azure OpenAI, which calls the Fabric MCP
endpoints server-side and returns a combined response.
"""

import logging
import sys
import time
import traceback
from os import environ
from pathlib import Path

from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from openai import AsyncAzureOpenAI

from microsoft_agents.hosting.aiohttp import CloudAdapter
from microsoft_agents.authentication.msal import MsalConnectionManager
from microsoft_agents.hosting.core import (
    Authorization,
    AgentApplication,
    TurnState,
    TurnContext,
    MemoryStorage,
)
from microsoft_agents.activity import load_configuration_from_env

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
load_dotenv()
agents_sdk_config = load_configuration_from_env(environ)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
_prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "orchestrator_agent.md"
_instructions = _prompt_path.read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# M365 Agents SDK infrastructure
# ---------------------------------------------------------------------------
STORAGE = MemoryStorage()
CONNECTION_MANAGER = MsalConnectionManager(**agents_sdk_config)
ADAPTER = CloudAdapter(connection_manager=CONNECTION_MANAGER)
AUTHORIZATION = Authorization(STORAGE, CONNECTION_MANAGER, **agents_sdk_config)

AGENT_APP = AgentApplication[TurnState](
    storage=STORAGE,
    adapter=ADAPTER,
    authorization=AUTHORIZATION,
    **agents_sdk_config,
)

# ---------------------------------------------------------------------------
# Entra ID authentication for Fabric MCP endpoints
# ---------------------------------------------------------------------------
FABRIC_DATA_AGENT_SCOPE = "https://api.fabric.microsoft.com/.default"

_credential = DefaultAzureCredential()
_cached_token = _credential.get_token(FABRIC_DATA_AGENT_SCOPE)

# Refresh the token if it expires within this many seconds
_TOKEN_REFRESH_BUFFER_SECS = 300  # 5 minutes


def _get_fabric_headers() -> dict[str, str]:
    """Return Fabric MCP headers with a valid bearer token.

    Refreshes the token automatically when it is expired or about to expire
    (within ``_TOKEN_REFRESH_BUFFER_SECS`` seconds of expiry).
    """
    global _cached_token

    if time.time() >= _cached_token.expires_on - _TOKEN_REFRESH_BUFFER_SECS:
        logger.info("Fabric access token expired or near expiry — refreshing")
        _cached_token = _credential.get_token(FABRIC_DATA_AGENT_SCOPE)

    return {
        "Authorization": f"Bearer {_cached_token.token}",
        "Content-Type": "application/json",
    }

# ---------------------------------------------------------------------------
# Azure OpenAI client (Responses API)
# ---------------------------------------------------------------------------
CLIENT = AsyncAzureOpenAI(
    api_version=environ.get("AZURE_OPENAI_API_VERSION", "2025-03-01-preview"),
    azure_endpoint=environ["AOAI_ENDPOINT"],
    api_key=environ["AOAI_KEY"],
)

_DEPLOYMENT = environ["AZURE_OPENAI_DEPLOYMENT_NAME"]

# ---------------------------------------------------------------------------
# MCP tool definitions for the Responses API
# ---------------------------------------------------------------------------
_FABRIC_SALES_URL = environ["FABRIC_SALES_AGENT_MCP_URL"]
_FABRIC_CUSTOMER_URL = environ["FABRIC_CUSTOMER_AGENT_MCP_URL"]
_FABRIC_PRODUCT_URL = environ["FABRIC_PRODUCT_AGENT_MCP_URL"]


def _build_mcp_tools() -> list[dict]:
    """Build the MCP tools list with fresh Fabric auth headers.

    Called on each request so that expired tokens are never sent to
    Azure OpenAI as part of the hosted MCP tool definitions.
    """
    headers = _get_fabric_headers()
    return [
        {
            "type": "mcp",
            "server_label": "Sales Agent",
            "server_url": _FABRIC_SALES_URL,
            "headers": headers,
            "require_approval": "never",
        },
        {
            "type": "mcp",
            "server_label": "Customer Agent",
            "server_url": _FABRIC_CUSTOMER_URL,
            "headers": headers,
            "require_approval": "never",
        },
        {
            "type": "mcp",
            "server_label": "Product Agent",
            "server_url": _FABRIC_PRODUCT_URL,
            "headers": headers,
            "require_approval": "never",
        },
    ]

# ---------------------------------------------------------------------------
# Conversation history (in-memory, keyed by conversation ID)
# ---------------------------------------------------------------------------
_conversation_history: dict[str, list[dict]] = {}

MAX_HISTORY_TURNS = 20


def _get_history(conversation_id: str) -> list[dict]:
    """Return (and lazily initialize) the message history for a conversation."""
    if conversation_id not in _conversation_history:
        _conversation_history[conversation_id] = []
    return _conversation_history[conversation_id]


def _trim_history(history: list[dict]) -> None:
    """Keep only the most recent turns to avoid exceeding token limits."""
    while len(history) > MAX_HISTORY_TURNS * 2:
        history.pop(0)


# ---------------------------------------------------------------------------
# Activity handlers
# ---------------------------------------------------------------------------
@AGENT_APP.conversation_update("membersAdded")
async def on_members_added(context: TurnContext, _state: TurnState):
    await context.send_activity(
        "👋 Welcome! I'm the **Fabric Data Agents Orchestrator**.\n\n"
        "Ask me anything about sales orders, customers, or products and "
        "I'll query the right Fabric data agents to get your answer."
    )
    return True


@AGENT_APP.activity("message")
async def on_message(context: TurnContext, _state: TurnState):
    """Handle an incoming user message by calling Azure OpenAI with MCP tools."""
    user_text = context.activity.text
    if not user_text:
        return

    conversation_id = context.activity.conversation.id if context.activity.conversation else "default"
    history = _get_history(conversation_id)
    history.append({"role": "user", "content": user_text})
    _trim_history(history)

    try:
        # Build the input messages: system prompt + conversation history
        messages = [{"role": "system", "content": _instructions}] + history

        response = await CLIENT.responses.create(
            model=_DEPLOYMENT,
            input=messages,
            tools=_build_mcp_tools(),
        )

        # Extract the assistant's text output
        assistant_text = ""
        for item in response.output:
            if hasattr(item, "content"):
                for block in item.content:
                    if hasattr(block, "text"):
                        assistant_text += block.text

        if not assistant_text:
            assistant_text = "I wasn't able to generate a response. Please try rephrasing your question."

        history.append({"role": "assistant", "content": assistant_text})
        _trim_history(history)

        await context.send_activity(assistant_text)

    except Exception as exc:
        logger.error("Error calling Azure OpenAI: %s", exc)
        await context.send_activity(
            "⚠️ Sorry, I encountered an error while processing your request. "
            "Please try again in a moment."
        )


@AGENT_APP.error
async def on_error(context: TurnContext, error: Exception):
    """Global error handler."""
    print(f"\n[on_turn_error] unhandled error: {error}", file=sys.stderr)
    traceback.print_exc()
    await context.send_activity(
        "⚠️ The agent encountered an unexpected error. Please try again."
    )
