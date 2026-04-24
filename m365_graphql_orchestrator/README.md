# GraphQL Agents Orchestrator — M365 Channels

An orchestrator agent built with the [Microsoft 365 Agents SDK](https://github.com/microsoft/Agents) and the **Microsoft Agent Framework (MAF)** that delegates to three sub-agents — **Sales**, **Customer**, and **Product** — each querying Microsoft Fabric GraphQL APIs. Exposed through M365 channels: Teams, Outlook, and M365 Copilot.

This is the M365-channel companion to the [Custom UX](../graphql_agents/) in the same repository. Both share the same architecture (orchestrator → sub-agents → Fabric GraphQL).

## Architecture

```
        ┌──────────────────────────────────────────────┐
        │       M365 Channels (Teams / Outlook / …)    │
        └──────────────────┬───────────────────────────┘
                           │  Azure Bot Service
                           ▼
        ┌──────────────────────────────────────────────┐
        │  M365 Agents SDK (aiohttp — /api/messages)   │
        │  ┌────────────────────────────────────────┐  │
        │  │  GraphQL Agents Orchestrator           │  │
        │  │  (ChatAgent + Azure OpenAI)            │  │
        │  └───────────────┬────────────────────────┘  │
        └──────────────────┼───────────────────────────┘
                           │  agent-as-tool delegation
                           ▼
        ┌──────────────────────────────────────────────┐
        │          Azure OpenAI (Responses API)        │
        │ ┌──────────┐ ┌────────────┐ ┌─────────────┐ │
        │ │  Sales   │ │  Customer  │ │   Product   │ │
        │ │  Agent   │ │   Agent    │ │    Agent    │ │
        │ └────┬─────┘ └─────┬──────┘ └──────┬──────┘ │
        └──────┼─────────────┼───────────────┼─────────┘
               │             │               │
               ▼             ▼               ▼
     ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
     │ Sales GraphQL│ │ Customer     │ │ Product      │
     │  (Fabric)    │ │ GraphQL      │ │ GraphQL      │
     └──────────────┘ └──────────────┘ └──────────────┘
```

Each sub-agent is a `ChatAgent` with its own system prompt and an `@ai_function` tool that executes GraphQL queries against the corresponding Fabric endpoint. The orchestrator delegates via `as_tool()`.

## Prerequisites

- **Python 3.11+**
- **Azure CLI** — logged in to the correct tenant
- **Azure Bot registration** — with Client ID, Client Secret, and Tenant ID
- **Azure OpenAI** deployment with API key access
- **Microsoft Fabric** workspace with a GraphQL API

## Quick Start

### 1. Install dependencies

```powershell
# From the repo root (shared venv)
pip install -r m365_graphql_orchestrator\requirements.txt
```

### 2. Configure environment

```powershell
Copy-Item m365_graphql_orchestrator\env.TEMPLATE m365_graphql_orchestrator\.env
# Edit .env with your values
```

### 3. Run locally (anonymous mode)

```powershell
cd m365_graphql_orchestrator
python -m src.main
```

Server starts at `http://localhost:8000/api/messages`. Connect with the [Bot Framework Emulator](https://github.com/microsoft/BotFramework-Emulator).

### 4. Deploy to Azure

See [DEPLOYMENT.md](DEPLOYMENT.md) for the full step-by-step guide covering:
- Entra ID app registration + Fabric OAuth
- Azure Bot resource + Teams channel
- Azure App Service deployment
- Teams app manifest packaging + sideloading
- M365 Copilot access

## File Structure

```
├── env.TEMPLATE                 # Environment variable template
├── DEPLOYMENT.md                # Full deployment walkthrough
├── requirements.txt             # Python dependencies
├── startup.sh                   # App Service startup command
├── appPackage/
│   └── manifest.json            # Teams app manifest
├── prompts/
│   ├── orchestrator_agent.md    # Orchestrator system prompt
│   ├── sales_agent.md           # Sales sub-agent prompt + GraphQL schema
│   ├── customer_agent.md        # Customer sub-agent prompt + GraphQL schema
│   └── product_agent.md         # Product sub-agent prompt + GraphQL schema
└── src/
    ├── main.py                  # Entrypoint (aiohttp server)
    ├── agent.py                 # Bot activity handlers + MAF orchestrator
    ├── graphql_client.py        # Async Fabric GraphQL client
    ├── subagents.py             # Sub-agent factory functions
    └── start_server.py          # Server bootstrap
```

## Authentication

| Mode | Auth | Fabric Token | Use Case |
|------|------|-------------|----------|
| **Anonymous** (`USE_ANONYMOUS_MODE=True`) | None | `DefaultAzureCredential` | Local testing with Emulator |
| **Normal** (`USE_ANONYMOUS_MODE=False`) | Bot JWT validation | SSO → OBO exchange | Deployed to Teams/Copilot |

## SDK Versions

| Package | Version |
|---------|---------|
| `agent-framework-core` | `1.0.0b251007` |
| `agent-framework-azure-ai` | `1.0.0b251007` |
| `openai` | `2.8.1` |
| `microsoft-agents-hosting-aiohttp` | `0.8.0` |
| `microsoft-agents-authentication-msal` | `0.8.0` |
# GraphQL Agents Orchestrator — M365 Channels

An orchestrator agent built with the [Microsoft 365 Agents SDK](https://github.com/microsoft/Agents) that uses **Agent Framework sub-agents** with **Fabric GraphQL APIs** for data retrieval, exposed through **M365 channels** — Teams, Outlook, Copilot, and more.

This is the M365-channel companion to the [DevUI-based GraphQL orchestrator](../graphql_agents/orchestrator_agent/) in the same repository. Both share the same architecture (orchestrator → sub-agents → Fabric GraphQL), but this version uses the M365 Agents SDK to serve responses through Azure Bot Service channels instead of DevUI.

## Architecture

```
        ┌──────────────────────────────────────────────┐
        │       M365 Channels (Teams / Outlook / …)    │
        └──────────────────┬───────────────────────────┘
                           │  Azure Bot Service
                           ▼
        ┌──────────────────────────────────────────────┐
        │  M365 Agents SDK (aiohttp — /api/messages)   │
        │  ┌────────────────────────────────────────┐  │
        │  │  GraphQL Agents Orchestrator           │  │
        │  │  (AgentApplication + Azure OpenAI)     │  │
        │  └───────────────┬────────────────────────┘  │
        └──────────────────┼───────────────────────────┘
                           │  Agent-as-Tool delegation
                           ▼
        ┌──────────────────────────────────────────────┐
        │          Azure OpenAI (Responses API)        │
        │ ┌──────────┐ ┌────────────┐ ┌─────────────┐ │
        │ │  Sales   │ │  Customer  │ │   Product   │ │
        │ │  Agent   │ │   Agent    │ │    Agent    │ │
        │ └────┬─────┘ └─────┬──────┘ └──────┬──────┘ │
        └──────┼─────────────┼───────────────┼─────────┘
               │             │               │
               ▼             ▼               ▼
     ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
     │ Sales GraphQL│ │ Customer     │ │ Product      │
     │  (Fabric)    │ │ GraphQL      │ │ GraphQL      │
     └──────────────┘ └──────────────┘ └──────────────┘
```

Each sub-agent is a full Agent Framework agent with its own system prompt and a `FunctionTool` that executes GraphQL queries against the corresponding Fabric GraphQL API endpoint. The orchestrator delegates to sub-agents via agent-as-tool conversion.

## Key Differences from the Fabric Data Agents Version

| Aspect | Fabric Data Agents (`m365_agents_orchestrator/`) | GraphQL Agents (`m365_graphql_orchestrator/`) |
|--------|--------------------------------------------------|-----------------------------------------------|
| **Data retrieval** | Hosted MCP endpoints (server-side) | Fabric GraphQL APIs (client-side function tools) |
| **Sub-agents** | None — single agent with 3 MCP tools | 3 Agent Framework agents (Sales, Customer, Product) |
| **Tool execution** | Azure OpenAI executes MCP tools server-side | Python function tools execute GraphQL queries locally |
| **Orchestration** | Single agent, multiple tools | Multi-agent: orchestrator delegates to sub-agents |

## Prerequisites

- **Python 3.11+**
- **Azure CLI** — logged in to the correct tenant
- **Azure Bot registration** — with Client ID, Client Secret, and Tenant ID
- **Azure OpenAI** deployment with API key access (model supporting Responses API)
- **Microsoft Fabric** workspace with three GraphQL APIs configured (Sales, Customer, Product)
- **Dev tunnel** (for local development)

## Quick Start

### 1. Clone and create virtual environment

```bash
cd m365_graphql_orchestrator
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp env.TEMPLATE .env
```

Fill in your Azure OpenAI, Bot registration, and Fabric GraphQL API endpoint values.

### 3. Run locally

```bash
python -m src.main
```

The server starts on `http://localhost:8000/api/messages`.

### 4. Update sub-agent prompts

Replace the placeholder prompts in `prompts/` with detailed instructions for each sub-agent:

- `prompts/sales_agent.md` — Sales domain instructions + GraphQL schema
- `prompts/customer_agent.md` — Customer domain instructions + GraphQL schema
- `prompts/product_agent.md` — Product domain instructions + GraphQL schema
