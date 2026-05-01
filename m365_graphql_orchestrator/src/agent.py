"""GraphQL Agents Orchestrator — M365 Agents SDK version.

This module creates an M365-channel-compatible agent (Teams, Outlook, Copilot,
etc.) that orchestrates three Agent Framework sub-agents (Sales, Customer,
Product), each using Fabric GraphQL APIs for data retrieval.

Authentication strategy (modelled after the Fabric Data Agents version):
--------------------------------------------------------------------------
Fabric GraphQL APIs require the **signed-in user's identity** (delegated access).

*  **Teams / M365 channels** — manual ``UserTokenClient`` access for SSO
   token-exchange and OBO via the Bot Service OAuth connection.
*  **Local dev / Emulator** — ``DefaultAzureCredential`` (``az login``) supplies
   the developer's own Fabric token.
"""

import base64
import json
import logging
import os
import sys
import time
import traceback
from os import environ
from pathlib import Path
from typing import Any, Optional

from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from agent_framework import ChatAgent
from agent_framework.azure import AzureOpenAIResponsesClient
from agent_framework._types import TextContent
from agent_framework._threads import AgentThread

from .subagents import create_sales_agent, create_customer_agent, create_product_agent
from .memory import create_memory

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
    force=True,
)
logging.getLogger("azure.identity").setLevel(logging.INFO)

from microsoft_agents.hosting.aiohttp import CloudAdapter
from microsoft_agents.authentication.msal import MsalConnectionManager
from microsoft_agents.hosting.core import (
    AgentApplication,
    TurnState,
    TurnContext,
    MemoryStorage,
)
from microsoft_agents.activity import (
    Activity,
    ActivityTypes,
    CardAction,
    SigninCard,
    TokenExchangeState,
    load_configuration_from_env,
)

from .graphql_client import FabricGraphQLClient

# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
load_dotenv()
agents_sdk_config = load_configuration_from_env(environ)

USE_ANONYMOUS_MODE = environ.get("USE_ANONYMOUS_MODE", "false").lower() == "true"

OAUTH_CONNECTION_NAME = environ.get("FABRIC_ABS_OAUTH_CONNECTION_NAME", "FabricOAuth")

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------
_prompts_dir = Path(__file__).resolve().parent.parent / "prompts"
_orchestrator_instructions = (_prompts_dir / "orchestrator_agent.md").read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# Fabric GraphQL auth
# ---------------------------------------------------------------------------
FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"

# ---------------------------------------------------------------------------
# M365 Agents SDK infrastructure
# ---------------------------------------------------------------------------
STORAGE = MemoryStorage()

if USE_ANONYMOUS_MODE:
    logger.info("Anonymous mode — skipping MSAL auth (local dev only)")
    CONNECTION_MANAGER = None
    ADAPTER = CloudAdapter(connection_manager=None)
else:
    CONNECTION_MANAGER = MsalConnectionManager(**agents_sdk_config)
    ADAPTER = CloudAdapter(connection_manager=CONNECTION_MANAGER)

AGENT_APP = AgentApplication[TurnState](
    storage=STORAGE,
    adapter=ADAPTER,
    **agents_sdk_config,
)

# ---------------------------------------------------------------------------
# Pending command store
# ---------------------------------------------------------------------------
_pending_commands: dict[str, str] = {}

# ---------------------------------------------------------------------------
# DefaultAzureCredential — LOCAL-DEV FALLBACK ONLY
# ---------------------------------------------------------------------------
_credential: DefaultAzureCredential | None = None
_cached_token = None
_TOKEN_REFRESH_BUFFER_SECS = 300


def _ensure_credential() -> DefaultAzureCredential:
    global _credential
    if _credential is None:
        logger.info("Creating DefaultAzureCredential (local-dev fallback)")
        _credential = DefaultAzureCredential(
            logging_enable=True,
            exclude_managed_identity_credential=True,
        )
    return _credential


def _decode_token_claims(token: str) -> dict:
    """Decode JWT payload (no verification) — for diagnostic logging only."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (4 - len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        return {k: claims.get(k) for k in (
            "aud", "iss", "oid", "upn", "name", "appid",
            "app_displayname", "idtyp", "scp", "roles",
            "tid", "exp", "iat",
        )}
    except Exception as e:
        return {"decode_error": str(e)}


def _log_token_claims(token: str, hint: str = "token") -> None:
    claims = _decode_token_claims(token)
    logger.info("%s claims: %s", hint, json.dumps(claims, indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# Manual UserTokenClient helpers (adapted from GEV-SAA pattern)
# ═══════════════════════════════════════════════════════════════════════════

def _get_user_token_client(context: TurnContext) -> Optional[Any]:
    try:
        if hasattr(context, "turn_state"):
            client = context.turn_state.get("UserTokenClient")
            if client:
                return client
            for key, val in context.turn_state.items():
                if "UserTokenClient" in str(key):
                    return val
    except (AttributeError, KeyError, TypeError):
        pass
    return None


def _get_user_id(context: TurnContext) -> Optional[str]:
    if hasattr(context.activity, "from_property"):
        aad_id = getattr(context.activity.from_property, "aad_object_id", None)
        if aad_id:
            return aad_id
        return getattr(context.activity.from_property, "id", None)
    actor = getattr(context.activity, "from", None)
    return getattr(actor, "id", None)


def _get_channel_id(context: TurnContext) -> str:
    return getattr(context.activity, "channel_id", "msteams")


def _get_ms_app_id(context: TurnContext) -> Optional[str]:
    app_id = getattr(context, "app_id", None)
    if app_id:
        return app_id
    for key in (
        "MICROSOFT_APP_ID",
        "MicrosoftAppId",
        "CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID",
    ):
        val = environ.get(key)
        if val:
            return val
    return None


def _extract_magic_code(activity) -> Optional[str]:
    try:
        if hasattr(activity, "value") and isinstance(activity.value, dict):
            code = activity.value.get("code")
            if code:
                return str(code).strip()
            auth = activity.value.get("authentication", {})
            if isinstance(auth, dict) and auth.get("code"):
                return str(auth["code"]).strip()
        text_val = (getattr(activity, "text", "") or "").strip()
        if text_val and text_val.isdigit() and 3 <= len(text_val) <= 12:
            return text_val
    except Exception:
        pass
    return None


async def _get_token_with_magic_code(
    user_token_client, user_id, channel_id, connection_name, code,
) -> Optional[str]:
    if not user_token_client or not user_id:
        return None
    try:
        token_response = await user_token_client.user_token.get_token(
            user_id=user_id,
            connection_name=connection_name,
            channel_id=channel_id,
            code=code,
        )
        token_value = getattr(token_response, "token", None)
        if token_value:
            _log_token_claims(token_value, "Fabric user-token")
            return token_value
    except Exception as exc:
        logger.warning("Token service get_token error: %s", exc)
    return None


async def _try_token_exchange_from_invoke(
    context, user_token_client, user_id, channel_id, connection_name,
) -> Optional[str]:
    payload = getattr(context.activity, "value", None)
    if not isinstance(payload, dict) or not payload.get("token"):
        return None
    effective_conn = payload.get("connectionName") or connection_name
    try:
        exchange_response = await user_token_client.user_token.exchange_token(
            user_id=user_id,
            connection_name=effective_conn,
            channel_id=channel_id,
            body=payload,
        )
        exchange_token = getattr(exchange_response, "token", None)
        if exchange_token:
            logger.info("SSO token exchange succeeded connection=%s", effective_conn)
            _log_token_claims(exchange_token, "SSO-exchanged Fabric token")
            return exchange_token
    except Exception as exc:
        logger.warning("SSO token exchange failed connection=%s error=%s", effective_conn, exc)
    return None


async def _send_oauth_card(
    context, user_token_client, user_id, channel_id, connection_name, ms_app_id,
) -> None:
    try:
        conversation_ref = (
            context.activity.get_conversation_reference()
            if hasattr(context.activity, "get_conversation_reference")
            else None
        )
        if not conversation_ref or not ms_app_id:
            await context.send_activity(
                "⚠️ Sign-in is required but I couldn't build the sign-in card. "
                "Please try again."
            )
            return

        token_state = TokenExchangeState(
            connection_name=connection_name,
            conversation=conversation_ref,
            relates_to=getattr(context.activity, "relates_to", None),
            agent_url=getattr(context.activity, "service_url", None),
            ms_app_id=ms_app_id,
        )
        encoded_state = token_state.get_encoded_state()

        token_or_sign_in = (
            await user_token_client.user_token._get_token_or_sign_in_resource(
                user_id, connection_name, channel_id, encoded_state,
            )
        )

        token_resp = getattr(token_or_sign_in, "token_response", None)
        if token_resp and getattr(token_resp, "token", None):
            return

        sign_in_resource = getattr(token_or_sign_in, "sign_in_resource", None)
        if sign_in_resource and getattr(sign_in_resource, "sign_in_link", None):
            signin_card = SigninCard(
                text=(
                    "**Sign in required**\n\n"
                    "To query Fabric data on your behalf, please sign in.\n\n"
                    "If you receive a verification code, paste it in this chat."
                ),
                buttons=[
                    CardAction(
                        type="signin",
                        title="Sign in to Fabric",
                        value=sign_in_resource.sign_in_link,
                    )
                ],
            )
            await context.send_activity(
                Activity(
                    type=ActivityTypes.message,
                    attachments=[
                        {
                            "contentType": "application/vnd.microsoft.card.signin",
                            "content": signin_card.model_dump(
                                by_alias=True, exclude_none=True,
                            ),
                        }
                    ],
                )
            )
            return

        await context.send_activity(
            "⚠️ I couldn't initiate sign-in. Please try sending your question again."
        )

    except Exception as exc:
        logger.error("Failed to send OAuth card: %s", exc, exc_info=True)
        await context.send_activity(
            f"⚠️ Authentication error: `{exc}`\n\n"
            "Please try again. If you see a verification code, paste it here."
        )


async def fetch_token_or_prompt(
    context: TurnContext,
    connection_name: str = OAUTH_CONNECTION_NAME,
) -> Optional[str]:
    """Fetch a user token from the Bot token service, or prompt sign-in."""
    user_token_client = _get_user_token_client(context)
    user_id = _get_user_id(context)
    channel_id = _get_channel_id(context)
    magic_code = _extract_magic_code(context.activity)

    if not user_token_client or not user_id:
        logger.error("UserTokenClient or user_id missing from turn state")
        return None

    # Step 1: Try get_token (cached or magic-code redemption)
    token = await _get_token_with_magic_code(
        user_token_client, user_id, channel_id, connection_name, magic_code,
    )
    if token:
        return token

    # Step 2: Try SSO token exchange from invoke payload
    exchanged = await _try_token_exchange_from_invoke(
        context, user_token_client, user_id, channel_id, connection_name,
    )
    if exchanged:
        return exchanged

    # Step 3: Send OAuth card
    ms_app_id = _get_ms_app_id(context)
    await _send_oauth_card(
        context, user_token_client, user_id, channel_id, connection_name, ms_app_id,
    )
    return None


# ---------------------------------------------------------------------------
# Fabric GraphQL header builders
# ---------------------------------------------------------------------------

def _get_fabric_token_local() -> str:
    """Fabric token via DefaultAzureCredential (local dev / az login)."""
    global _cached_token
    cred = _ensure_credential()
    need_refresh = (
        _cached_token is None
        or time.time() >= _cached_token.expires_on - _TOKEN_REFRESH_BUFFER_SECS
    )
    if need_refresh:
        _cached_token = cred.get_token(FABRIC_SCOPE)
        _log_token_claims(_cached_token.token, "DefaultAzureCredential Fabric token")
    return _cached_token.token


# ---------------------------------------------------------------------------
# Azure OpenAI client
# ---------------------------------------------------------------------------
MAF_CLIENT = AzureOpenAIResponsesClient(
    endpoint=environ["AOAI_ENDPOINT"],
    api_key=environ["AOAI_KEY"],
    deployment_name=environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
)


# ---------------------------------------------------------------------------
# Orchestrator builder — rebuilt per-request with user-specific Fabric token
# ---------------------------------------------------------------------------

def _build_orchestrator(*, user_token: str | None = None) -> ChatAgent:
    """Build the orchestrator ChatAgent with per-user Fabric auth.

    Each call creates fresh sub-agents bound to the user's Fabric token
    (SSO/OBO in M365) or the developer's DefaultAzureCredential (local dev).
    """
    logger.info(
        "=== Building orchestrator (user_token=%s) ===",
        "present" if user_token else "None — using DefaultAzureCredential",
    )

    if user_token:
        graphql_client = FabricGraphQLClient(token=user_token)
    else:
        token = _get_fabric_token_local()
        graphql_client = FabricGraphQLClient(token=token)

    # Create sub-agents with per-user GraphQL client
    sales_agent = create_sales_agent(MAF_CLIENT, graphql_client)
    customer_agent = create_customer_agent(MAF_CLIENT, graphql_client)
    product_agent = create_product_agent(MAF_CLIENT, graphql_client)

    # Convert sub-agents to tools for the orchestrator
    sales_tool = sales_agent.as_tool(
        name="sales_agent",
        description="Delegate to the Sales Agent for sales-related queries.",
    )
    customer_tool = customer_agent.as_tool(
        name="customer_agent",
        description="Delegate to the Customer Agent for customer-related queries.",
    )
    product_tool = product_agent.as_tool(
        name="product_agent",
        description="Delegate to the Product Agent for product-related queries.",
    )

    return ChatAgent(
        MAF_CLIENT,
        instructions=_orchestrator_instructions,
        name="GraphQL Agents Orchestrator",
        description=(
            "Orchestrates three Agent Framework sub-agents (Sales, Customer, Product) "
            "that use Fabric GraphQL APIs for data retrieval."
        ),
        tools=[sales_tool, customer_tool, product_tool],
    )


# ---------------------------------------------------------------------------
# Conversation threads
# ---------------------------------------------------------------------------
_threads: dict[str, AgentThread] = {}

# ---------------------------------------------------------------------------
# Mem0 memory layer — long-term context across sessions
# ---------------------------------------------------------------------------
try:
    memory = create_memory()
    logger.info("Mem0 memory layer initialised (Azure AI Search)")
except Exception as _e:
    logger.warning("Mem0 unavailable — running without memory: %s", _e)
    memory = None


# ═══════════════════════════════════════════════════════════════════════════
# Core message handler
# ═══════════════════════════════════════════════════════════════════════════

async def _run_agent_pipeline(
    context: TurnContext,
    user_text: str,
    conversation_id: str,
) -> None:
    """Acquire token → build orchestrator → run → stream response to client."""

    user_token: str | None = None

    if USE_ANONYMOUS_MODE:
        logger.info("Anonymous mode — using DefaultAzureCredential for Fabric")
    else:
        logger.info("Requesting Fabric user-token via manual SSO/OBO flow …")
        user_token = await fetch_token_or_prompt(context, OAUTH_CONNECTION_NAME)
        if user_token is None:
            logger.info("No token yet (sign-in initiated). Storing pending command.")
            _pending_commands[conversation_id] = user_text
            return

    # Build orchestrator with per-user sub-agents
    orchestrator = _build_orchestrator(user_token=user_token)

    # Get or create conversation thread
    if conversation_id not in _threads:
        _threads[conversation_id] = AgentThread()
    thread = _threads[conversation_id]

    # --- Mem0: retrieve relevant memories and prepend as context ---
    user_id = _get_user_id(context) or "default_user"
    enriched_message = user_text
    if memory:
        try:
            results = memory.search(query=user_text, filters={"user_id": user_id}, limit=5)
            memories_list = results.get("results", []) if isinstance(results, dict) else results
            if memories_list:
                mem_lines = "\n".join(f"- {m['memory']}" for m in memories_list)
                enriched_message = (
                    f"[Relevant context from previous conversations]\n{mem_lines}\n\n"
                    f"{user_text}"
                )
                logger.info("Mem0: injected %d memories for user=%s", len(memories_list), user_id)
        except Exception as exc:
            logger.warning("Mem0 search failed: %s", exc)

    logger.info("Running orchestrator: conversation=%s", conversation_id)

    # Stream the response to the client via M365 Agents SDK streaming
    context.streaming_response._interval = 0.5  # reduce Teams default (1s) for snappier updates
    context.streaming_response.set_generated_by_ai_label(True)
    context.streaming_response.set_feedback_loop(True)
    context.streaming_response.queue_informative_update("Querying Fabric data…")

    full_response: list[str] = []
    try:
        async for update in orchestrator.run_stream(enriched_message, thread=thread):
            for content in update.contents:
                if isinstance(content, TextContent) and content.text:
                    full_response.append(content.text)
                    context.streaming_response.queue_text_chunk(content.text)
    except Exception as exc:
        logger.error("Error during streaming: %s", exc, exc_info=True)
        context.streaming_response.queue_text_chunk(
            f"\n\n⚠️ An error occurred: {str(exc)[:300]}"
        )
    finally:
        await context.streaming_response.end_stream()

    # --- Mem0: store the exchange for future recall ---
    if memory and full_response:
        try:
            exchange = [
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": "".join(full_response)},
            ]
            memory.add(exchange, user_id=user_id)
        except Exception as exc:
            logger.warning("Mem0 add failed: %s", exc)

    logger.info("Streaming complete for conversation=%s", conversation_id)


# ═══════════════════════════════════════════════════════════════════════════
# Activity handlers
# ═══════════════════════════════════════════════════════════════════════════

@AGENT_APP.activity("invoke")
async def on_invoke(context: TurnContext, _state: TurnState) -> None:
    """Handle Bot Framework invoke activities for SSO and token exchange."""
    invoke_name = getattr(context.activity, "name", None)
    payload = getattr(context.activity, "value", None) or {}

    logger.info(
        "INVOKE received: name=%s payload_keys=%s",
        invoke_name,
        list(payload.keys()) if isinstance(payload, dict) else [],
    )

    conversation_id = (
        getattr(getattr(context.activity, "conversation", None), "id", None)
        or "default"
    )

    if invoke_name == "signin/tokenExchange":
        user_token_client = _get_user_token_client(context)
        user_id = _get_user_id(context)
        channel_id = _get_channel_id(context)

        token = None
        if user_token_client and user_id:
            token = await _try_token_exchange_from_invoke(
                context, user_token_client, user_id, channel_id, OAUTH_CONNECTION_NAME,
            )

        if token:
            await context.send_activity(
                Activity(type=ActivityTypes.invoke_response, value={"status": 200, "body": {}})
            )
            pending = _pending_commands.pop(conversation_id, None)
            if pending:
                await context.send_activity("✅ Sign-in complete! Running your request…")
                try:
                    await _run_agent_pipeline(context, pending, conversation_id)
                except Exception as exc:
                    logger.error("Error replaying pending command: %s", exc, exc_info=True)
                    await context.send_activity(f"⚠️ Error processing your request: {str(exc)[:300]}")
        else:
            await context.send_activity(
                Activity(
                    type=ActivityTypes.invoke_response,
                    value={"status": 409, "body": {"failureDetail": "Token exchange failed"}},
                )
            )
        return

    if invoke_name in ("signin/verifystate", "signin/verifyState"):
        magic_code = None
        if isinstance(payload, dict):
            magic_code = payload.get("state")

        token = None
        if magic_code:
            user_token_client = _get_user_token_client(context)
            user_id = _get_user_id(context)
            channel_id = _get_channel_id(context)
            if user_token_client and user_id:
                token = await _get_token_with_magic_code(
                    user_token_client, user_id, channel_id,
                    OAUTH_CONNECTION_NAME, str(magic_code),
                )

        await context.send_activity(
            Activity(type=ActivityTypes.invoke_response, value={"status": 200, "body": {}})
        )

        if token:
            pending = _pending_commands.pop(conversation_id, None)
            if pending:
                await context.send_activity("✅ Sign-in complete! Running your request…")
                try:
                    await _run_agent_pipeline(context, pending, conversation_id)
                except Exception as exc:
                    logger.error("Error replaying pending command: %s", exc, exc_info=True)
                    await context.send_activity(f"⚠️ Error processing your request: {str(exc)[:300]}")
            else:
                await context.send_activity("✅ Sign-in complete! Please re-send your question.")
        return

    if invoke_name == "signin/failure":
        logger.warning("Teams reported sign-in failure payload=%s", payload)
        await context.send_activity(
            Activity(type=ActivityTypes.invoke_response, value={"status": 200})
        )
        await context.send_activity(
            "⚠️ Sign-in failed. Please try sending your question again."
        )
        return

    # Unrecognised invoke
    await context.send_activity(
        Activity(type=ActivityTypes.invoke_response, value={"status": 200})
    )


import re  # noqa: E402 — needed for mention stripping


def _strip_mentions(text: str) -> str:
    """Remove Teams bot mention XML tags and collapse whitespace."""
    cleaned = re.sub(r"<at[^>]*>.*?</at>", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip()


@AGENT_APP.activity("message")
async def on_message(context: TurnContext, _state: TurnState):
    """Handle an incoming user message."""
    raw_text = (context.activity.text or "").strip()
    user_text = _strip_mentions(raw_text)
    conversation_id = (
        getattr(getattr(context.activity, "conversation", None), "id", None)
        or "default"
    )

    logger.info("on_message: raw=%r  cleaned=%r", raw_text, user_text)

    # Handle sign-out command — clears cached Fabric token
    if user_text.lower() in ("signout", "sign out", "logout", "log out"):
        user_token_client = _get_user_token_client(context)
        user_id = _get_user_id(context)
        if user_token_client and user_id:
            try:
                await user_token_client.user_token.sign_out(
                    user_id=user_id,
                    connection_name=OAUTH_CONNECTION_NAME,
                    channel_id=_get_channel_id(context),
                )
                await context.send_activity("✅ Signed out. Send a new message to trigger re-authentication.")
            except Exception as exc:
                logger.warning("Sign-out failed: %s", exc)
                await context.send_activity(f"⚠️ Sign-out error: {exc}")
        else:
            await context.send_activity("⚠️ Could not access token service for sign-out.")
        return

    # Check if message is a magic code
    magic_code = _extract_magic_code(context.activity)
    if magic_code and not user_text.replace(magic_code, "").strip():
        user_token_client = _get_user_token_client(context)
        user_id = _get_user_id(context)
        channel_id = _get_channel_id(context)

        token = None
        if user_token_client and user_id:
            token = await _get_token_with_magic_code(
                user_token_client, user_id, channel_id,
                OAUTH_CONNECTION_NAME, magic_code,
            )

        if token:
            pending = _pending_commands.pop(conversation_id, None)
            if pending:
                await context.send_activity("✅ Sign-in complete! Running your request…")
                try:
                    await _run_agent_pipeline(context, pending, conversation_id)
                except Exception as exc:
                    logger.error("Error replaying pending command: %s", exc, exc_info=True)
                    await context.send_activity(f"⚠️ Error processing your request: {str(exc)[:300]}")
            else:
                await context.send_activity("✅ Sign-in complete! Please send your question.")
        else:
            await context.send_activity("⚠️ Could not redeem that code. Please click the sign-in card again.")
        return

    if not user_text:
        return

    _pending_commands.pop(conversation_id, None)

    try:
        logger.info(">>> on_message: user_text=%r  conversation=%s", user_text, conversation_id)
        await _run_agent_pipeline(context, user_text, conversation_id)
    except Exception as exc:
        logger.error("!!! Error in agent pipeline: %s", exc, exc_info=True)
        await context.send_activity(
            f"⚠️ Error: {str(exc)[:500]}\n\n"
            "_Check the App Service logs for full diagnostics._"
        )


@AGENT_APP.error
async def on_error(context: TurnContext, error: Exception):
    """Global error handler."""
    print(f"\n[on_turn_error] unhandled error: {error}", file=sys.stderr)
    traceback.print_exc()
    await context.send_activity(
        "⚠️ The agent encountered an unexpected error. Please try again."
    )
