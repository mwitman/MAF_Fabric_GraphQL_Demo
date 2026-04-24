# Fabric GraphQL Agents — Microsoft Agent Framework Demo

An orchestrator agent built with the **Microsoft Agent Framework (MAF)** that delegates to three sub-agents — **Sales**, **Customer**, and **Product** — each querying Microsoft Fabric GraphQL APIs. Two deployment options ship from the same codebase:

| Interface | Folder | Purpose |
|-----------|--------|---------|
| **Custom UX** | `graphql_agents/` | React + FastAPI chat app with Mem0 memory, containerised for Azure Container Apps |
| **M365 Channels** | `m365_graphql_orchestrator/` | Azure Bot Service bot for Teams, Outlook, and M365 Copilot |

Both share the same multi-agent architecture: one orchestrator agent that routes questions to domain-specific sub-agents via agent-as-tool delegation.

---

## Architecture

```
                 ┌──────────────────────────────────────────────────┐
                 │              User Interfaces                     │
                 │                                                  │
                 │  ┌──────────────────┐  ┌──────────────────────┐ │
                 │  │   Custom UX      │  │   M365 Channels      │ │
                 │  │  React + FastAPI  │  │  Teams / Outlook /   │ │
                 │  │   (graphql_      │  │  M365 Copilot        │ │
                 │  │    agents/)      │  │  (m365_graphql_      │ │
                 │  │                  │  │   orchestrator/)     │ │
                 │  └────────┬─────────┘  └──────────┬───────────┘ │
                 └───────────┼───────────────────────┼─────────────┘
                             │                       │
                             ▼                       ▼
                 ┌──────────────────────────────────────────────────┐
                 │        Orchestrator Agent (ChatAgent)            │
                 │  ┌──────────┐ ┌────────────┐ ┌───────────────┐  │
                 │  │  Sales   │ │  Customer  │ │   Product     │  │
                 │  │  Agent   │ │   Agent    │ │    Agent      │  │
                 │  │ (tool)   │ │  (tool)    │ │   (tool)      │  │
                 │  └────┬─────┘ └─────┬──────┘ └──────┬────────┘  │
                 └───────┼─────────────┼───────────────┼───────────┘
                         │             │               │
                         ▼             ▼               ▼
               ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
               │ Sales GraphQL│ │ Customer     │ │ Product      │
               │  (Fabric)    │ │  GraphQL     │ │  GraphQL     │
               └──────────────┘ └──────────────┘ └──────────────┘
```

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| **Python 3.11+** | Required runtime |
| **Node.js 18+** | For the Custom UX frontend (Vite + React) |
| **Azure CLI** | Authenticated via `az login` for local development |
| **Azure OpenAI resource** | Deployment supporting the Responses API (e.g. `gpt-4o`, `gpt-5`) |
| **Microsoft Fabric workspace** | With a GraphQL API exposing Sales, Customer, and Product tables |

---

## Quick Start — Custom UX

The Custom UX is a React + Tailwind frontend backed by a FastAPI server with Mem0 persistent memory.

```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install backend dependencies
pip install -r graphql_agents\backend\requirements.txt

# 3. Configure environment
Copy-Item graphql_agents\.env.template graphql_agents\.env
# Edit graphql_agents/.env with your Azure OpenAI and Fabric GraphQL details

# 4. Sign in to Azure (for Fabric token)
az login

# 5. Start the backend + frontend
cd graphql_agents
.\start_ui.ps1
```

The backend runs at `http://localhost:8080` and the frontend at `http://localhost:5173`.

See the full guide: **[Custom UX Setup](docs/custom-ux-setup.md)**

---

## Quick Start — M365 Channels (Teams / Copilot)

The M365 version deploys as an Azure Bot Service bot, using the M365 Agents SDK.

```powershell
# 1. Install dependencies (same venv as above)
pip install -r m365_graphql_orchestrator\requirements.txt

# 2. Configure environment
Copy-Item m365_graphql_orchestrator\env.TEMPLATE m365_graphql_orchestrator\.env
# Edit .env with Bot registration, Azure OpenAI, and Fabric details

# 3. Run locally (anonymous mode for testing)
cd m365_graphql_orchestrator
python -m src.main
```

Connects to the Bot Framework Emulator at `http://localhost:8000/api/messages`.

See the full guides:
- **[M365 Deployment Guide](docs/m365-deployment-guide.md)** — step-by-step Azure deployment
- **[Local Testing Guide](docs/local-testing-guide.md)** — Bot Framework Emulator + dev tunnel

---

## Project Structure

```
graphql_agents/                          # Custom UX (React + FastAPI + Mem0)
├── .env.template                        # Template for required env vars
├── Dockerfile                           # Multi-stage build for Container Apps
├── push_to_acr.ps1                      # Build & push Docker image to ACR
├── run.py                               # Python launcher
├── start_ui.ps1                         # PowerShell launcher (backend + frontend)
├── backend/
│   ├── server.py                        # FastAPI backend with SSE streaming + Mem0
│   ├── memory.py                        # Mem0 configuration (Azure OpenAI + Qdrant)
│   ├── requirements.txt                 # Python dependencies
│   └── static/                          # Built frontend assets (served by FastAPI)
├── frontend/
│   ├── src/                             # React + Tailwind + Vite source
│   ├── package.json
│   └── vite.config.ts
└── orchestrator_agent/
    ├── agent.py                         # Orchestrator + sub-agent wiring
    ├── graphql_client.py                # Async Fabric GraphQL client
    ├── prompts/                         # System prompts per agent
    └── subagents/                       # Sales, Customer, Product sub-agents

m365_graphql_orchestrator/               # M365 Channels (Teams / Outlook / Copilot)
├── env.TEMPLATE                         # Template for required env vars
├── DEPLOYMENT.md                        # Full deployment walkthrough
├── requirements.txt                     # Python dependencies
├── startup.sh                           # App Service startup command
├── appPackage/
│   └── manifest.json                    # Teams app manifest
├── prompts/                             # System prompts per agent
└── src/
    ├── main.py                          # Entrypoint
    ├── agent.py                         # Bot logic — M365 SDK + MAF + SSO/OBO
    ├── graphql_client.py                # Async Fabric GraphQL client
    ├── subagents.py                     # Sub-agent factories
    └── start_server.py                  # aiohttp server bootstrap

docs/                                    # Documentation
├── custom-ux-setup.md                   # Custom UX local dev + Docker guide
├── m365-deployment-guide.md             # Full M365 deployment to Azure
└── local-testing-guide.md               # Bot Emulator + dev tunnel testing
```

---

## How It Works

### Multi-Agent Architecture

Each sub-agent is a `ChatAgent` with:
- A domain-specific system prompt (with full GraphQL schema documentation)
- An `@ai_function` tool that executes GraphQL queries against Fabric

The orchestrator sees each sub-agent as a tool (via `as_tool()`) and routes user questions to the appropriate domain.

### Authentication

| Interface | Auth Method | Fabric Token Source |
|-----------|-------------|---------------------|
| **Custom UX** | `DefaultAzureCredential` (`az login`) | Developer's own identity |
| **M365** | Bot Service SSO → OBO token exchange | Signed-in user's identity (delegated) |

### Mem0 Memory (Custom UX only)

The Custom UX includes [Mem0](https://github.com/mem0ai/mem0) for persistent cross-conversation memory. The agent remembers facts from previous sessions and incorporates them into future responses.

---

## SDK Versions

| Package | Version | Notes |
|---------|---------|-------|
| `agent-framework-core` | `1.0.0b251007` | MAF core runtime |
| `agent-framework-azure-ai` | `1.0.0b251007` | MAF Azure AI integration |
| `openai` | `2.8.1` | Pinned — URL construction varies across versions |
| `microsoft-agents-hosting-aiohttp` | `0.8.0` | M365 Agents SDK (M365 path only) |
| `microsoft-agents-authentication-msal` | `0.8.0` | M365 Agents SDK (M365 path only) |

> **Do not set** `AZURE_OPENAI_API_VERSION`. The MAF SDK default (`"preview"`) is correct.

---

## Data Domain

| Agent | Data Domain | Key Tables |
|-------|-------------|------------|
| **Sales Agent** | Orders, order status, totals, line items | SalesOrderHeader, SalesOrderDetail |
| **Customer Agent** | Customer identity, addresses | Customer, CustomerAddress, Address |
| **Product Agent** | Products, categories, models, descriptions | Product, ProductCategory, ProductModel |

GraphQL endpoint pattern:
```
https://api.fabric.microsoft.com/v1/workspaces/<workspace-id>/graphqlapis/<api-id>/graphql
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [Custom UX Setup](docs/custom-ux-setup.md) | Local dev, Docker build, ACR push |
| [M365 Deployment Guide](docs/m365-deployment-guide.md) | Full Azure deployment to Teams/Copilot |
| [Local Testing Guide](docs/local-testing-guide.md) | Bot Framework Emulator + dev tunnel |
| [M365 Orchestrator DEPLOYMENT.md](m365_graphql_orchestrator/DEPLOYMENT.md) | Quick-reference deployment steps |

---

## License

See [LICENSE](LICENSE).
# Orchestrating Fabric Data Agents

An orchestrator agent built with the **Microsoft Agent Framework (MAF)** that queries three Microsoft Fabric data agents — **Sales**, **Customer**, and **Product** — via hosted MCP endpoints. The Azure OpenAI Responses API executes MCP tools server-side, so no local MCP server is needed.

Two interfaces ship from the same codebase:

| Interface | Folder | Purpose |
|-----------|--------|---------|
| **DevUI** | `agents/` | Local development & testing via browser UI |
| **M365 Channels** | `m365_agents_orchestrator/` | Azure App Service bot for Teams, Outlook, Copilot |

Both share the same system prompt (`prompts/orchestrator_agent.md`) and the same agent wiring pattern.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        User Interfaces                              │
│                                                                     │
│  ┌──────────────┐            ┌─────────────────────────────────┐    │
│  │    DevUI     │            │  M365 Channels                  │    │
│  │  (localhost) │            │  (Teams / Outlook / Copilot)    │    │
│  └──────┬───────┘            └───────────────┬─────────────────┘    │
│         │                                    │                      │
│         │  agents/                           │  m365_agents_        │
│         │  orchestrator_agent/               │  orchestrator/       │
│         │  agent.py                          │  src/agent.py        │
└─────────┼────────────────────────────────────┼──────────────────────┘
          │                                    │
          │  DefaultAzureCredential            │  SSO → OBO token
          │  (az login)                        │  (Bot Service OAuth)
          ▼                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   Microsoft Agent Framework (MAF)                   │
│                                                                     │
│  AzureOpenAIResponsesClient                                         │
│    ├── get_mcp_tool("Sales Agent",    url, headers)                 │
│    ├── get_mcp_tool("Customer Agent", url, headers)                 │
│    ├── get_mcp_tool("Product Agent",  url, headers)                 │
│    └── as_agent(tools=[...], instructions=prompt)                   │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  Azure OpenAI Responses API                         │
│           (hosted MCP tool execution — server-side)                 │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                ┌────────────────┼────────────────┐
                ▼                ▼                ▼
       ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
       │ Sales Agent  │ │Customer Agent│ │Product Agent │
       │ (Fabric MCP) │ │ (Fabric MCP) │ │ (Fabric MCP) │
       └──────────────┘ └──────────────┘ └──────────────┘
```

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| **Python 3.11+** | Required runtime |
| **Azure CLI** | Authenticated via `az login` for local development |
| **Azure OpenAI resource** | Deployment supporting the Responses API (e.g., `gpt-4o`) |
| **Microsoft Fabric workspace** | With three data agents (Sales, Customer, Product) created and MCP endpoints enabled |
| **Entra ID permissions** | Your identity (or managed identity) must have access to the Fabric workspace |

---

## Quick Start — DevUI (Local Development)

### 1. Create a virtual environment

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r agents/requirements.txt
```

### 3. Create `agents/.env`

```env
AOAI_ENDPOINT=https://<your-aoai-resource>.openai.azure.com/
AOAI_KEY=<your-api-key>
AZURE_OPENAI_DEPLOYMENT_NAME=<your-deployment-name>

# NOTE: Do NOT set AZURE_OPENAI_API_VERSION — the MAF SDK default ("preview")
# is correct. Setting an explicit dated version causes 400 errors.

FABRIC_SALES_AGENT_MCP_URL=https://api.fabric.microsoft.com/v1/mcp/workspaces/<workspace-id>/dataagents/<sales-agent-id>/agent
FABRIC_CUSTOMER_AGENT_MCP_URL=https://api.fabric.microsoft.com/v1/mcp/workspaces/<workspace-id>/dataagents/<customer-agent-id>/agent
FABRIC_PRODUCT_AGENT_MCP_URL=https://api.fabric.microsoft.com/v1/mcp/workspaces/<workspace-id>/dataagents/<product-agent-id>/agent
```

### 4. Authenticate to Azure

```bash
az login
```

This provides `DefaultAzureCredential` with a Fabric token for MCP endpoint authentication.

### 5. Launch DevUI

```bash
python run.py
```

Opens a browser UI at `http://localhost:8080` where you can chat with the orchestrator agent.

---

## M365 Channels (Teams / Outlook / Copilot)

The M365 deployment requires Azure Bot Service, App Service, Entra ID app registration, and an OAuth connection for Fabric SSO/OBO.

See the full deployment walkthrough:

- **[Getting Started — Deployment Guide](docs/getting-started-deployment-guide.md)** — step-by-step setup from scratch
- **[M365 Implementation Overview](docs/m365-implementation-overview.md)** — architecture, auth flow, and code walkthrough

The environment variable template is at [`m365_agents_orchestrator/env.TEMPLATE`](m365_agents_orchestrator/env.TEMPLATE).

---

## Project Structure

```
agents/                              # DevUI version (local development)
├── .env                             # Environment variables (not committed)
├── requirements.txt                 # Python dependencies
└── orchestrator_agent/
    ├── __init__.py
    ├── agent.py                     # Agent definition + MCP tool wiring
    └── prompts/
        └── orchestrator_agent.md    # Shared system prompt

m365_agents_orchestrator/            # M365 Channels version (Teams, Outlook, Copilot)
├── .env                             # Local-only env vars (not committed)
├── env.TEMPLATE                     # Template for required environment variables
├── requirements.txt                 # Python dependencies (pinned)
├── startup.sh                       # App Service startup command
├── README.md
├── appPackage/
│   ├── manifest.json                # Teams app manifest
│   ├── color.png
│   └── outline.png
├── prompts/
│   └── orchestrator_agent.md        # Shared system prompt
└── src/
    ├── __init__.py
    ├── main.py                      # Entrypoint
    ├── agent.py                     # Core bot logic — MAF + SSO/OBO + handlers
    └── start_server.py              # aiohttp server bootstrap

docs/                                # Documentation
├── getting-started-deployment-guide.md   # Full deployment walkthrough
└── m365-implementation-overview.md       # Architecture & code deep-dive

run.py                               # DevUI launcher
start.ps1                            # PowerShell launcher
```

---

## How It Works

### Authentication

| Interface | Auth Method | Fabric Token Source |
|-----------|-------------|---------------------|
| **DevUI** | `DefaultAzureCredential` (`az login`) | Developer's own identity |
| **M365** | Bot Service SSO → OBO token exchange | Signed-in user's identity (delegated) |

Fabric data agents require **delegated (user) access** — app-only / managed-identity tokens are rejected by design.

### Tool Registration

Each Fabric data agent is registered as a hosted MCP tool via the MAF SDK:

```python
client = AzureOpenAIResponsesClient(
    endpoint=os.environ["AOAI_ENDPOINT"],
    api_key=os.environ["AOAI_KEY"],
    deployment_name=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
)

sales_tool = client.get_mcp_tool(
    name="Sales Agent",
    url=os.environ["FABRIC_SALES_AGENT_MCP_URL"],
    headers=fabric_headers,  # Bearer token for Fabric API
    approval_mode="never_require",
)
```

### Agent Execution

The agent is created with `as_agent()` and invoked with `agent.run()` (DevUI) or within the M365 bot's turn handler:

```python
agent = client.as_agent(
    name="Fabric Data Agents Orchestrator",
    instructions=_instructions,
    tools=[sales_tool, customer_tool, product_tool],
)
```

Azure OpenAI's Responses API handles MCP tool execution server-side — the orchestrator sends the tool definitions and Fabric bearer token, and Azure OpenAI calls the MCP endpoints directly.

### Sessions

- **DevUI** — each browser session is a separate conversation with its own history.
- **M365** — conversation state is managed per Teams conversation via `MemoryStorage`. The M365 version also handles `signin/tokenExchange`, `signin/verifystate`, and `signin/failure` invoke activities for SSO flow.

---

## Fabric Data Agents

| Agent | Data Domain | Key Tables |
|-------|-------------|------------|
| **Sales Agent** | Orders, order status, order totals, line items | SalesOrderHeader, SalesOrderDetail |
| **Customer Agent** | Customer identity, addresses (billing/shipping) | Customer, CustomerAddress, Address |
| **Product Agent** | Products, categories, models, descriptions | Product, ProductCategory, ProductModel, ProductDescription |

MCP endpoint pattern:
```
https://api.fabric.microsoft.com/v1/mcp/workspaces/<workspace-id>/dataagents/<agent-id>/agent
```

See each agent's Fabric workspace page for endpoint details and schemas.

---

## SDK Versions

> **Important:** The `openai` SDK version matters — different versions construct Azure OpenAI URLs differently, which can cause silent failures or 4xx errors.

| Package | Version | Notes |
|---------|---------|-------|
| `agent-framework-azure-ai` | `1.0.0b251007` | MAF Azure AI integration |
| `agent-framework-core` | `1.0.0rc3` | MAF core runtime |
| `openai` | `2.8.1` | Pinned — URL construction varies across versions |
| `microsoft-agents-hosting-aiohttp` | `0.8.0` | M365 Agents SDK |
| `microsoft-agents-hosting-core` | `0.8.0` | M365 Agents SDK |
| `microsoft-agents-authentication-msal` | `0.8.0` | M365 Agents SDK |
| `microsoft-agents-activity` | `0.8.0` | M365 Agents SDK |
| `azure-identity` | `≥1.19.0` | Entra ID / DefaultAzureCredential |

### AZURE_OPENAI_API_VERSION — Do Not Set

Do **not** set the `AZURE_OPENAI_API_VERSION` environment variable. The MAF SDK uses a default value (`"preview"`) that works correctly with the Responses API. Setting an explicit dated version (e.g., `2025-03-01-preview`) causes **400 errors**.

---

## Adapting for Your Own Fabric Data Agents

1. **Create Fabric data agents** in your workspace — each agent exposes a lakehouse, warehouse, or other Fabric data source through a natural-language query interface.
2. **Update `.env`** with the new MCP URLs for each agent (format: `https://api.fabric.microsoft.com/v1/mcp/workspaces/<workspace-id>/dataagents/<agent-id>/agent`).
3. **Add or remove `get_mcp_tool()` calls** in `agent.py` to match your agents, and update the `tools=[...]` list in `as_agent()`.
4. **Update the system prompt** in `prompts/orchestrator_agent.md` — describe each agent's capabilities so the orchestrator routes queries correctly.
5. **Configure auth** — ensure your identity (local dev via `az login`) or the bot's OAuth connection (M365) has access to the Fabric workspace.

---

## Modification Notes — DevUI Patches

Two files in the installed `agent-framework-devui` and `agent-framework` packages required local patches for correct MCP tool rendering in the DevUI. These fix gaps in the current RC releases and will likely be resolved in future versions.

### `agent_framework_devui/_mapper.py`

**Problem:** DevUI displayed `"Warning: Unknown content type: Content"` for every MCP tool call and result because the mapper's `content_mappers` dict had no entries for `mcp_server_tool_call` or `mcp_server_tool_result` content types.

**Changes:**
1. **Registered handlers** in `content_mappers` for `mcp_server_tool_call` and `mcp_server_tool_result`.
2. **`_map_mcp_server_tool_call_content`** — New method that maps MCP tool calls to the same `ResponseOutputItemAddedEvent` + `ResponseFunctionCallArgumentsDeltaEvent` events used by regular function calls. Includes deduplication logic: only emits the "added" event once per `call_id`, so streaming argument deltas don't create duplicate tool bubbles.
3. **`_map_mcp_server_tool_result_content`** — New method that maps MCP tool results to `ResponseFunctionResultComplete`. Returns `None` when output is empty (suppresses the premature in-progress result that arrives before the actual output).

### `agent_framework/openai/_responses_client.py`

**Problem:** MCP tool arguments and results were not captured from Azure OpenAI streaming events. The `response.output_item.added` event arrives with `McpCall.output=None` (in-progress state), and the actual data comes through separate streaming events that were unhandled.

**Changes:**
1. **MCP call ID tracking** — In the `response.output_item.added` → `mcp_call` handler, added registration to `function_call_ids` so argument delta events can look up the call by `output_index`.
2. **`response.output_item.done` handler** — New case that captures the completed `McpCall` (with `output` populated) and emits `Content.from_mcp_server_tool_result` with the actual result text.
3. **`response.mcp_call_arguments.delta` / `.done` handlers** — New cases that convert MCP argument streaming events into `Content.from_mcp_server_tool_call` with the argument data, so DevUI can display what was sent to each tool.

> **Note:** These patches live in `.venv/Lib/site-packages/` and will be lost on `pip install --force-reinstall`. They should be re-applied after dependency updates until the framework ships native support.

---

## Documentation

| Document | Description |
|----------|-------------|
| [Getting Started — Deployment Guide](docs/getting-started-deployment-guide.md) | Full step-by-step M365 deployment |
| [M365 Implementation Overview](docs/m365-implementation-overview.md) | Architecture, auth flow, code walkthrough |
| [Local Testing Guide](docs/local-testing-guide.md) | DevUI and Bot Framework Emulator setup |

---

## License

See [LICENSE](LICENSE).