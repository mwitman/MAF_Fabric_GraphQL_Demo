# M365 Agents SDK + Microsoft Agent Framework — Implementation Overview

This document describes the architecture, authentication flow, and services used by the **Fabric Agents Orchestrator** — an M365-channel-compatible bot that orchestrates three Microsoft Fabric data agents using the **Microsoft Agent Framework (MAF)** with the Azure OpenAI Responses API and hosted MCP tool execution.

---

## Table of Contents

- [M365 Agents SDK + Microsoft Agent Framework — Implementation Overview](#m365-agents-sdk--microsoft-agent-framework--implementation-overview)
  - [Table of Contents](#table-of-contents)
  - [Architecture Summary](#architecture-summary)
    - [Data Flow](#data-flow)
  - [Key Services \& Components](#key-services--components)
    - [SDK Packages (`requirements.txt`)](#sdk-packages-requirementstxt)
  - [Authentication \& Authorization](#authentication--authorization)
    - [Why User Identity Is Required](#why-user-identity-is-required)
    - [SSO / On-Behalf-Of Flow](#sso--on-behalf-of-flow)
    - [Manual UserTokenClient Pattern](#manual-usertokenclient-pattern)
    - [Invoke Handlers](#invoke-handlers)
    - [Pending Command Restoration](#pending-command-restoration)
    - [Local Development Fallback](#local-development-fallback)
  - [Fabric Data Agents (MCP)](#fabric-data-agents-mcp)
  - [Microsoft Agent Framework Integration](#microsoft-agent-framework-integration)
  - [Teams App Manifest](#teams-app-manifest)
  - [Conversation Sessions](#conversation-sessions)
  - [Project Structure](#project-structure)
  - [Environment Variables](#environment-variables)

---

## Architecture Summary

```
┌──────────────────────────────────────────────────────────────────────┐
│  Microsoft Teams / M365 Channel                                      │
│  ┌────────────────────┐                                              │
│  │  User sends message │                                             │
│  └────────┬───────────┘                                              │
│           │                                                          │
│           ▼                                                          │
│  ┌────────────────────┐      ┌───────────────────────────────┐       │
│  │ Azure Bot Service   │────▶ OAuth Connection (FabricOAuth)│       │
│  │ (Channel connector) │◀───│ SSO token exchange + OBO      │       │
│  └────────┬───────────┘      └───────────────────────────────┘       │
│           │                                                          │
│           ▼                                                          │
│  ┌────────────────────────────────────────────────┐                  │
│  │ Azure App Service  (Python 3.11, aiohttp)      │                  │
│  │  ┌──────────────────────────────────────────┐  │                  │
│  │  │ M365 Agents SDK  (v0.8.0)                │  │                  │
│  │  │  CloudAdapter + MsalConnectionManager    │  │                  │
│  │  │  Manual UserTokenClient SSO/OBO          │  │                  │
│  │  └──────────────┬───────────────────────────┘  │                  │
│  │                 │                              │                  │
│  │                 ▼                              │                  │
│  │  ┌──────────────────────────────────────────┐  │                  │
│  │  │ Microsoft Agent Framework (MAF)          │  │                  │
│  │  │  AzureOpenAIResponsesClient + as_agent() │  │                  │
│  │  │  get_mcp_tool() for per-user MCP tools   │  │                  │
│  │  │  Sessions for multi-turn history         │  │                  │
│  │  └──────────────┬───────────────────────────┘  │                  │
│  │                 │                              │                  │
│  │                 ▼                              │                  │
│  │  ┌──────────────────────────────────────────┐  │                  │
│  │  │ Azure OpenAI  (Responses API)            │  │                  │
│  │  │  Hosted MCP tool execution               │  │                  │
│  │  │  3 Fabric data agent MCP tools           │  │                  │
│  │  └──────────────┬───────────────────────────┘  │                  │
│  └─────────────────┼──────────────────────────────┘                  │
│                    │                                                 │
│                    ▼                                                 │
│  ┌──────────────────────────────────────────────────┐                │
│  │ Microsoft Fabric                                 │                │
│  │  ┌──────────┐  ┌──────────────┐  ┌────────────┐  │                │
│  │  │ Sales    │  │ Customer     │  │ Product    │  │                │
│  │  │ Agent    │  │ Agent        │  │ Agent      │  │                │
│  │  └──────────┘  └──────────────┘  └────────────┘  │                │
│  └──────────────────────────────────────────────────┘                │
└──────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. User sends a message in Teams (or another M365 channel).
2. Azure Bot Service routes the activity to the App Service `/api/messages` endpoint.
3. The M365 Agents SDK (`CloudAdapter`) validates the JWT and hydrates `TurnContext` including `UserTokenClient`.
4. The bot acquires a Fabric-scoped user token via SSO token exchange / OBO.
5. Per-user MCP tools are created via `MAF_CLIENT.get_mcp_tool()` with the user's Fabric bearer token.
6. The user message is sent to the MAF `ORCHESTRATOR_AGENT.run()` method along with the per-user tools and a conversation session.
7. MAF delegates to Azure OpenAI (Responses API) which executes MCP tool calls server-side against Fabric data agents.
8. MAF returns the structured result which the bot sends back to the user.

---

## Key Services & Components

| Service | Purpose | SKU / Version |
|---------|---------|---------------|
| **Azure Bot Service** | Channel connector — routes Teams activities to the bot endpoint; manages OAuth connections for SSO/OBO | Standard |
| **Azure App Service** | Hosts the Python bot (aiohttp server on port 8080) | Linux, Python 3.11 |
| **M365 Agents SDK (Python)** | `CloudAdapter`, `AgentApplication`, `MsalConnectionManager`, activity model | v0.8.0 (pinned) |
| **Microsoft Agent Framework** | `AzureOpenAIResponsesClient`, `as_agent()`, `get_mcp_tool()`, sessions | `1.0.0b251007` (agent-framework-azure-ai), `1.0.0rc3` (agent-framework-core) |
| **Azure OpenAI** | Responses API with hosted MCP tool execution (called via MAF) | SDK default `"preview"` API version |
| **Microsoft Fabric** | Three data agent MCP endpoints (Sales, Customer, Product) — delegated access only | Fabric workspace with data agents |
| **Entra ID (Azure AD)** | Single-tenant app registration — exposes `access_as_user` scope for Teams SSO, requests Fabric delegated permissions | App ID: matches bot ID |

### SDK Packages (`requirements.txt`)

```
microsoft-agents-hosting-aiohttp==0.8.0
microsoft-agents-hosting-core==0.8.0
microsoft-agents-authentication-msal==0.8.0
microsoft-agents-activity==0.8.0
agent-framework-azure-ai==1.0.0b251007
agent-framework-core==1.0.0rc3
openai==2.8.1
azure-identity>=1.19.0
python-dotenv
aiohttp==3.11.11
```

> **Important:** The `openai` SDK version is pinned to `2.8.1` because different versions construct Azure OpenAI URLs differently. Do NOT set `AZURE_OPENAI_API_VERSION` — the MAF SDK default (`"preview"`) is correct.

---

## Authentication & Authorization

### Why User Identity Is Required

Fabric data agents enforce **delegated (user) access only**. App-only tokens and managed-identity tokens are rejected by the Fabric API by design. This means the signed-in Teams user's identity must flow through to every Fabric MCP call. The authentication path is:

```
Teams user → Teams SSO → Bot Service OAuth → OBO token → Fabric API
```

### SSO / On-Behalf-Of Flow

The end-to-end auth flow works as follows:

1. **Teams sends an SSO token** — When a user messages the bot, Teams silently includes an SSO token (a JWT issued by Entra ID with `aud` = the bot's App ID).
2. **Bot Service exchanges the token** — The `FabricOAuth` OAuth connection on the Azure Bot resource performs an OBO (On-Behalf-Of) flow: it exchanges the Teams SSO token for a Fabric-scoped access token.
3. **Scopes requested during exchange:**
   ```
   openid
   offline_access
   https://api.fabric.microsoft.com/DataAgent.Execute.All
   https://api.fabric.microsoft.com/DataAgent.Read.All
   https://api.fabric.microsoft.com/Item.Execute.All
   https://api.fabric.microsoft.com/Item.Read.All
   https://api.fabric.microsoft.com/Workspace.Read.All
   ```
4. **Fabric token used in MCP calls** — The resulting token is attached as a `Bearer` header on each MCP tool definition sent to the Azure OpenAI Responses API.

### Manual UserTokenClient Pattern

The implementation does **not** use the SDK's built-in `Authorization` / `AuthHandler` abstraction. Instead, it manually accesses the `UserTokenClient` from `context.turn_state`. This pattern provides:

- **Full control** over token acquisition, exchange, and error handling.
- **Detailed diagnostic logging** at every auth step (JWT claims decoded and logged).
- **Explicit sign-in retry logic** with pending command replay.

Key functions:

| Function | Role |
|----------|------|
| `_get_user_token_client(context)` | Extracts `UserTokenClient` from `turn_state` |
| `_get_token_with_magic_code(...)` | Calls `user_token.get_token()` — retrieves cached token or redeems a verification code |
| `_try_token_exchange_from_invoke(...)` | Calls `user_token.exchange_token()` — performs SSO silent token exchange |
| `_send_oauth_card(...)` | Builds `TokenExchangeState`, calls `_get_token_or_sign_in_resource()`, sends `SigninCard` |
| `fetch_token_or_prompt(context)` | **Orchestrator** — tries get_token → exchange_token → send OAuth card |

### Invoke Handlers

Teams sends `invoke` activities for various SSO lifecycle events. The bot handles three:

| Invoke Name | Purpose | Action |
|-------------|---------|--------|
| `signin/tokenExchange` | Teams sends the SSO token for silent exchange | Exchange token → replay pending command on success, return 409 on failure (Teams retries) |
| `signin/verifyState` | User completes manual sign-in and a magic code is submitted | Redeem code → replay pending command on success |
| `signin/failure` | Teams reports that sign-in failed | Notify user; suggest admin consent may be needed |

### Pending Command Restoration

When a user's first message triggers a sign-in flow, their original question is stored in an in-memory dictionary (`_pending_commands`, keyed by conversation ID). Once sign-in completes successfully (via token exchange or magic code), the bot automatically replays the stored command so the user doesn't need to re-type their question.

### Local Development Fallback

When `USE_ANONYMOUS_MODE=True`, the bot skips MSAL/Bot Service authentication and instead uses `DefaultAzureCredential` (typically `az login`) to obtain a Fabric token with the developer's own identity. This enables local testing with the Bot Framework Emulator without needing a full Azure Bot registration.

---

## Fabric Data Agents (MCP)

Three Fabric data agents are exposed as MCP (Model Context Protocol) server endpoints:

| Agent | Data Domain | MCP URL Pattern |
|-------|-------------|-----------------|
| **Sales Agent** | Customer orders, order status, order totals, line items | `https://api.fabric.microsoft.com/v1/mcp/workspaces/{workspace-id}/dataagents/{agent-id}/agent` |
| **Customer Agent** | Customer identity, addresses (billing, shipping) | Same pattern, different agent ID |
| **Product Agent** | Products, categories, models, descriptions | Same pattern, different agent ID |

These MCP endpoints are called **server-side by Azure OpenAI** (hosted tool execution). The bot creates per-user MCP tools via the Microsoft Agent Framework:

```python
MAF_CLIENT.get_mcp_tool(
    name="Sales Agent",
    url=_FABRIC_SALES_URL,
    headers={
        "Authorization": f"Bearer {user_fabric_token}",
        "Content-Type": "application/json",
    },
    approval_mode="never_require",
)
```

Tools are created dynamically per-request (not at agent construction time) so that each user's Fabric token is used for their own MCP calls.

---

## Microsoft Agent Framework Integration

The bot uses the **Microsoft Agent Framework (MAF)** as the orchestration layer between the M365 Agents SDK (bot hosting) and Azure OpenAI:

- **Client:** `AzureOpenAIResponsesClient` — connects to Azure OpenAI with `endpoint` + `api_key` + `deployment_name`.
- **Agent:** Created at module level via `client.as_agent(name=..., instructions=...)` — no tools at construction; tools are per-request.
- **MCP Tools:** Built per-request via `client.get_mcp_tool(name, url, headers, approval_mode)` with the user's Fabric bearer token.
- **Execution:** `agent.run(user_text, session=session, tools=[...])` — MAF manages the Responses API call, tool execution, and response parsing.
- **Sessions:** `agent.create_session()` handles multi-turn conversation history automatically (replaces manual in-memory history).
- **System Prompt:** Defined in `prompts/orchestrator_agent.md` and passed as `instructions` to `as_agent()`.
- **Tool Execution:** Hosted MCP — Azure OpenAI calls the Fabric MCP endpoints directly (server-side).

---

## Teams App Manifest

The manifest (`appPackage/manifest.json`) uses schema **v1.21** and includes critical sections for SSO:

- **`webApplicationInfo`** — contains the bot's App ID and the Entra ID identifier URI (`api://botid-{app-id}`). This is required for Teams SSO token issuance.
- **`copilotAgents.customEngineAgents`** — registers the bot as a custom engine agent for Copilot extensibility.
- **`validDomains`** — includes `token.botframework.com`, `login.microsoftonline.com`, and `login.windows.net` alongside the App Service hostname.
- **`commandLists`** — three sample helper questions (sales, customer, product) shown to users in the Teams chat compose box.

---

## Conversation Sessions

Conversation state is managed by **MAF sessions** (`agent.create_session()`). Sessions are stored in-memory in a `dict` keyed by conversation ID. The Agent Framework handles conversation history tracking, message ordering, and context windowing internally.

> **Note:** In-memory sessions are lost on App Service restart. For production use, MAF sessions support serialization via `session.to_dict()` / `AgentSession.from_dict()` for persistence to Redis, Cosmos DB, etc.

---

## Project Structure

```
m365_agents_orchestrator/
├── appPackage/
│   ├── manifest.json        # Teams app manifest (v1.21)
│   ├── color.png            # App icon 192×192
│   └── outline.png          # App outline icon 32×32
├── prompts/
│   └── orchestrator_agent.md  # System prompt for Azure OpenAI
├── src/
│   ├── __init__.py
│   ├── agent.py             # Core bot logic — auth, tools, LLM, handlers
│   ├── main.py              # Entry point — wires up AGENT_APP + CONNECTION_MANAGER
│   └── start_server.py      # aiohttp server on /api/messages
├── env.TEMPLATE             # Template for required environment variables
├── requirements.txt         # Python dependencies (pinned)
├── startup.sh               # Azure App Service startup command
└── README.md
```

---

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `USE_ANONYMOUS_MODE` | Skip MSAL auth for local Emulator testing | `False` |
| `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID` | Bot App ID (Entra ID app registration) | `46b2e0d8-...` |
| `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTSECRET` | Bot App client secret | `u4Q8Q~...` |
| `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID` | Entra tenant ID | `72d0cd1a-...` |
| `FABRIC_ABS_OAUTH_CONNECTION_NAME` | Name of the Bot Service OAuth connection | `FabricOAuth` |
| `AOAI_ENDPOINT` | Azure OpenAI endpoint URL | `https://<name>.openai.azure.com/` |
| `AOAI_KEY` | Azure OpenAI API key | `sk-...` |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Model deployment name | `gpt-4o` |
| `FABRIC_SALES_AGENT_MCP_URL` | Fabric Sales data agent MCP endpoint | `https://api.fabric.microsoft.com/v1/mcp/workspaces/.../agent` |
| `FABRIC_CUSTOMER_AGENT_MCP_URL` | Fabric Customer data agent MCP endpoint | Same pattern |
| `FABRIC_PRODUCT_AGENT_MCP_URL` | Fabric Product data agent MCP endpoint | Same pattern |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | Enables Oryx build (pip install) on zip deploy | `true` |

> **Do NOT set** `AZURE_OPENAI_API_VERSION`. The MAF SDK default (`"preview"`) is the correct value. Setting a dated version causes 400 errors.
