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

The bot also includes a **Mem0** persistent memory layer backed by **Azure AI Search**, storing conversation context per user and enriching each interaction with relevant prior memories.

## Prerequisites

- **Python 3.11+**
- **Azure CLI** — logged in to the correct tenant
- **Azure Bot registration** — with Client ID, Client Secret, and Tenant ID
- **Azure OpenAI** deployment with API key access (e.g. `gpt-5.4`)
- **Microsoft Fabric** workspace with a GraphQL API
- **Azure AI Search** service — for Mem0 persistent memory vector store
- **Docker** — for building and pushing container images

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
├── .dockerignore                # Docker build exclusions
├── env.TEMPLATE                 # Environment variable template
├── Dockerfile                   # Container image (Python 3.12-slim)
├── push_to_acr.ps1              # Build & push to Azure Container Registry
├── requirements.txt             # Python dependencies
├── startup.sh                   # App Service startup command (legacy)
├── appPackage/
│   └── manifest.json            # Teams app manifest
├── prompts/
│   ├── orchestrator_agent.md    # Orchestrator system prompt
│   ├── sales_agent.md           # Sales sub-agent prompt + GraphQL schema
│   ├── customer_agent.md        # Customer sub-agent prompt + GraphQL schema
│   └── product_agent.md         # Product sub-agent prompt + GraphQL schema
└── src/
    ├── main.py                  # Entrypoint (aiohttp server)
    ├── agent.py                 # Bot activity handlers + MAF orchestrator + Mem0
    ├── memory.py                # Mem0 config (Azure OpenAI + Azure AI Search)
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

| Package | Version | Notes |
|---------|---------|-------|
| `agent-framework-core` | `1.0.0b251007` | MAF core |
| `agent-framework-azure-ai` | `1.0.0b251007` | Azure AI integration |
| `openai` | `2.8.1` | Installed separately (overrides `<2` constraint) |
| `mem0ai` | `2.0.0` | Pinned — 2.0.1 regresses gpt-5 `max_tokens` handling |
| `microsoft-agents-hosting-aiohttp` | `0.8.0` | M365 Agents SDK |
| `microsoft-agents-authentication-msal` | `0.8.0` | M365 Agents SDK auth |

## Deployment

Deployed as a **Docker container** on **Azure Container Apps**:

```powershell
# Build
cd m365_graphql_orchestrator
docker build -t <acr>.azurecr.io/m365-graphql-orchestrator:latest .

# Push
az acr login --name <acr>
docker push <acr>.azurecr.io/m365-graphql-orchestrator:latest

# Deploy new revision
az containerapp update `
  --name <app-name> `
  --resource-group <rg> `
  --image <acr>.azurecr.io/m365-graphql-orchestrator:latest `
  --revision-suffix <revision-name>
```

See the full guide: **[M365 Deployment Guide](../docs/m365-deployment-guide.md)**
