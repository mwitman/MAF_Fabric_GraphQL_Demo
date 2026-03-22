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
    AuthHandler,
    Authorization,
    AgentApplication,
    TurnState,
    TurnContext,
    MemoryStorage,
)
from microsoft_agents.activity import load_configuration_from_env

# ---------------------------------------------------------------------------
# Anonymous mode flag — set USE_ANONYMOUS_MODE=True in .env to test locally
# with the Bot Framework Emulator without real bot credentials.
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
load_dotenv()
agents_sdk_config = load_configuration_from_env(environ)

USE_ANONYMOUS_MODE = environ.get("USE_ANONYMOUS_MODE", "false").lower() == "true"

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
_prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "orchestrator_agent.md"
_instructions = _prompt_path.read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# Fabric MCP auth constants
# ---------------------------------------------------------------------------
FABRIC_DATA_AGENT_SCOPE = "https://api.fabric.microsoft.com/.default"
FABRIC_AUTH_HANDLER_ID = "fabric_auth"

# ---------------------------------------------------------------------------
# M365 Agents SDK infrastructure
# ---------------------------------------------------------------------------
STORAGE = MemoryStorage()

if USE_ANONYMOUS_MODE:
    logger.info("Anonymous mode enabled — skipping MSAL auth (local dev only)")
    CONNECTION_MANAGER = None
    ADAPTER = CloudAdapter(connection_manager=None)
    AUTHORIZATION = None
else:
    CONNECTION_MANAGER = MsalConnectionManager(**agents_sdk_config)
    ADAPTER = CloudAdapter(connection_manager=CONNECTION_MANAGER)

    # SSO/OBO: get a Fabric-scoped token on behalf of the signed-in Teams user.
    _fabric_abs_conn = environ.get("FABRIC_ABS_OAUTH_CONNECTION_NAME", "FabricOAuth")
    AUTHORIZATION = Authorization(
        STORAGE,
        CONNECTION_MANAGER,
        auth_handlers={
            FABRIC_AUTH_HANDLER_ID: AuthHandler(
                name=FABRIC_AUTH_HANDLER_ID,
                auth_type="UserAuthorization",
                abs_oauth_connection_name=_fabric_abs_conn,
                obo_connection_name="SERVICE_CONNECTION",
                scopes=[FABRIC_DATA_AGENT_SCOPE],
                title="Sign In to Fabric",
                text="Please sign in so I can query Fabric data agents on your behalf.",
            ),
        },
        auto_sign_in=True,
        **agents_sdk_config,
    )

AGENT_APP = AgentApplication[TurnState](
    storage=STORAGE,
    adapter=ADAPTER,
    authorization=AUTHORIZATION,
    **agents_sdk_config,
)

# ---------------------------------------------------------------------------
# Entra ID authentication for Fabric MCP endpoints
# ---------------------------------------------------------------------------

if USE_ANONYMOUS_MODE:
    # Local dev — use DefaultAzureCredential (your az login session).
    _credential = DefaultAzureCredential()
    _cached_token = _credential.get_token(FABRIC_DATA_AGENT_SCOPE)
    _TOKEN_REFRESH_BUFFER_SECS = 300  # 5 minutes
else:
    _credential = None
    _cached_token = None
    _TOKEN_REFRESH_BUFFER_SECS = 0


def _get_fabric_headers_local() -> dict[str, str]:
    """Return Fabric MCP headers using DefaultAzureCredential (local dev).

    Refreshes the token automatically when it is expired or about to expire.
    """
    global _cached_token
    assert _credential is not None, "DefaultAzureCredential not initialised — are you in anonymous mode?"

    if time.time() >= _cached_token.expires_on - _TOKEN_REFRESH_BUFFER_SECS:
        logger.info("Fabric access token expired or near expiry — refreshing")
        _cached_token = _credential.get_token(FABRIC_DATA_AGENT_SCOPE)

    return {
        "Authorization": f"Bearer {_cached_token.token}",
        "Content-Type": "application/json",
    }


def _fabric_headers_from_token(token: str) -> dict[str, str]:
    """Build Fabric MCP headers from an SSO/OBO user token (Teams mode)."""
    return {
        "Authorization": f"Bearer {token}",
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


def _build_mcp_tools(*, user_token: str | None = None) -> list[dict]:
    """Build the MCP tools list with Fabric auth headers.

    Args:
        user_token: If provided (Teams SSO/OBO), uses this bearer token.
                    If ``None``, falls back to ``DefaultAzureCredential`` (local dev).
    """
    headers = (
        _fabric_headers_from_token(user_token)
        if user_token
        else _get_fabric_headers_local()
    )
    return [
        {
            "type": "mcp",
            "server_label": "Sales-Agent",
            "server_url": _FABRIC_SALES_URL,
            "headers": headers,
            "require_approval": "never",
        },
        {
            "type": "mcp",
            "server_label": "Customer-Agent",
            "server_url": _FABRIC_CUSTOMER_URL,
            "headers": headers,
            "require_approval": "never",
        },
        {
            "type": "mcp",
            "server_label": "Product-Agent",
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
        # Obtain Fabric auth headers — per-user SSO/OBO in Teams, local cred otherwise
        if USE_ANONYMOUS_MODE:
            tools = _build_mcp_tools()  # DefaultAzureCredential (az login)
        else:
            token_response = await AUTHORIZATION.get_token(
                context, FABRIC_AUTH_HANDLER_ID
            )
            if not token_response or not token_response.token:
                await context.send_activity(
                    "\u26a0\ufe0f I need access to Fabric on your behalf. "
                    "Please complete the sign-in prompt and try your question again."
                )
                return
            tools = _build_mcp_tools(user_token=token_response.token)

        # Build the input messages: system prompt + conversation history
        messages = [{"role": "system", "content": _instructions}] + history

        response = await CLIENT.responses.create(
            model=_DEPLOYMENT,
            input=messages,
            tools=tools,
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
