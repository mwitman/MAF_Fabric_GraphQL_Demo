# Local Testing Guide

Three ways to test the GraphQL Agents Orchestrator locally before deploying to Azure:

1. **DevUI** — MAF built-in browser chat UI (lightest weight, no frontend build needed)
2. **Custom UX** — React + FastAPI chat app with Mem0 memory (full-featured)
3. **Bot Framework Emulator** — tests the full M365 Agents SDK bot pipeline

All three use `DefaultAzureCredential` (`az login`) for Fabric authentication.

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| Python 3.11+ | Required runtime |
| Node.js 18+ | Custom UX frontend only |
| Azure CLI | Authenticated via `az login` with Fabric workspace access |
| Azure OpenAI | API key + deployment name |
| Fabric workspace | With GraphQL API endpoints |

---

## Option 1: DevUI (Quickest Start)

DevUI is a browser-based chat interface provided by the `agent-framework-devui` package. It discovers the agent from `graphql_agents/orchestrator_agent/__init__.py` and runs it directly — no frontend build, no FastAPI, no bot framework.

### Setup

```powershell
# From the repo root
python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r graphql_agents\requirements.txt
```

### Configure

```powershell
Copy-Item graphql_agents\.env.template graphql_agents\.env
# Edit graphql_agents/.env with your Azure OpenAI and Fabric GraphQL details
```

### Run

```powershell
az login
python graphql_agents\run.py
```

Opens a browser UI at `http://localhost:8080`. Type a question and the orchestrator routes it to the appropriate sub-agent.

You can also run DevUI directly via the CLI:

```powershell
devui .\graphql_agents --port 8080
```

### When to Use

- Fastest way to test agent behaviour and prompt changes
- No Node.js or frontend build required
- Debugging sub-agent routing and GraphQL query generation
- Quick demos

---

## Option 2: Custom UX (Full-Featured)

The Custom UX (`graphql_agents/`) provides the production-style React + FastAPI chat interface with streaming responses and Mem0 persistent memory.

### Setup

```powershell
# From the repo root (reuse the same venv)
pip install -r graphql_agents\backend\requirements.txt

cd graphql_agents\frontend
npm install
cd ..\..
```

### Configure

```powershell
Copy-Item graphql_agents\.env.template graphql_agents\.env
# Edit graphql_agents/.env with your Azure OpenAI and Fabric details
```

### Run

```powershell
az login
cd graphql_agents
.\start_ui.ps1
```

Open `http://localhost:5173`.

### When to Use

- Iterating on the frontend UI
- Testing Mem0 persistent memory
- Testing the full streaming SSE pipeline
- Production-like demos

---

## Option 3: Bot Framework Emulator

The Emulator tests the full M365 Agents SDK pipeline — activity routing, SSO handler stubs, and MAF orchestration — using anonymous auth locally.

### Install the Emulator

Download from: https://github.com/microsoft/BotFramework-Emulator/releases

### Setup

```powershell
# From the repo root (reuse the same venv)
pip install -r m365_graphql_orchestrator\requirements.txt
```

### Configure

```powershell
Copy-Item m365_graphql_orchestrator\env.TEMPLATE m365_graphql_orchestrator\.env
```

Edit `m365_graphql_orchestrator/.env` with the key setting:

```env
USE_ANONYMOUS_MODE=True

# Azure OpenAI
AOAI_ENDPOINT=https://<your-aoai>.openai.azure.com/
AOAI_KEY=<your-api-key>
AZURE_OPENAI_DEPLOYMENT_NAME=<your-deployment>

# Fabric GraphQL API endpoints
FABRIC_SALES_GRAPHQL_URL=https://...
FABRIC_CUSTOMER_GRAPHQL_URL=https://...
FABRIC_PRODUCT_GRAPHQL_URL=https://...
```

> Bot registration settings (`CLIENTID`, `CLIENTSECRET`, `TENANTID`) are not needed in anonymous mode.

### Run

```powershell
az login
cd m365_graphql_orchestrator
python -m src.main
```

Server starts at `http://localhost:8000/api/messages`.

### Connect the Emulator

1. Open **Bot Framework Emulator**
2. Click **Open Bot**
3. Bot URL: `http://localhost:8000/api/messages`
4. Leave **Microsoft App ID** and **Password** blank
5. Click **Connect**

### What Anonymous Mode Does

| Component | Normal (Teams) | Anonymous (Emulator) |
|-----------|---------------|---------------------|
| Auth middleware | JWT validation | Fake claims — no validation |
| Connection manager | MSAL authentication | Skipped |
| Fabric token | SSO → OBO via user's identity | `DefaultAzureCredential` via `az login` |

The agent logic, MAF orchestration, and GraphQL queries are identical in both modes.

### When to Use

- Testing the full bot pipeline (activity handlers, invoke handlers)
- Debugging M365 Agents SDK behaviour
- When tenant restrictions prevent Teams app sideloading
- Verifying the `on_message` and `on_invoke` handlers

---

## Option 4: Dev Tunnel (Teams with Local Code)

To test the M365 bot **in Teams** while running code locally:

```powershell
# 1. Create a dev tunnel
devtunnel create --allow-anonymous
devtunnel port create -p 8000
devtunnel host

# 2. Copy the tunnel URL (e.g. https://abc123.devtunnels.ms)

# 3. Set as the bot messaging endpoint
az bot update `
  --resource-group <your-rg> `
  --name <your-bot-name> `
  --endpoint "https://<tunnel-url>/api/messages"

# 4. Run the bot locally (NOT anonymous mode)
cd m365_graphql_orchestrator
# Ensure USE_ANONYMOUS_MODE=False in .env
python -m src.main
```

Now test in Teams — messages route through the dev tunnel to your local code.

> Remember to set `USE_ANONYMOUS_MODE=False` and provide the full bot registration settings in `.env`.

---

## Comparison

| | DevUI | Custom UX | Bot Emulator | Dev Tunnel |
|---|---|---|---|---|
| **What it tests** | Agent + MAF + GraphQL | Agent + FastAPI + Mem0 + UI | Full bot pipeline | Full bot + Teams |
| **Auth** | `az login` | `az login` | `az login` (anon mode) | Teams SSO → OBO |
| **Fabric token** | Developer identity | Developer identity | Developer identity | User identity |
| **Setup** | Minimal (Python only) | Python + Node.js | Emulator install | Dev tunnel + Bot reg |
| **Memory** | No | Yes (Mem0) | No | No |
| **SSO testing** | No | No | No | Yes |
| **Best for** | Quick agent testing | UI dev, production demo | Bot pipeline, handlers | End-to-end Teams |

> **Note:** Only the dev tunnel option tests the Teams SSO/OBO authentication flow. To test SSO, you must have the bot registered in Azure and sideloaded to Teams.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `DefaultAzureCredential` fails | Not signed in | Run `az login` |
| Fabric returns 401/403 | Identity lacks workspace access | Verify Fabric permissions |
| `ModuleNotFoundError` | Missing dependencies | `pip install -r requirements.txt` in the correct folder |
| Emulator can't connect | Bot server not running | Verify `python -m src.main` is running |
| Emulator returns 500 | Server error | Check terminal output for stack trace |
| Dev tunnel connection reset | Tunnel not hosting | Ensure `devtunnel host` is running |
| DevUI shows no agent | Wrong working directory | Run from repo root: `python graphql_agents\run.py` |
# Local Testing Guide

Two ways to test the GraphQL Agents Orchestrator locally before deploying to Azure:

1. **Custom UX** — React + FastAPI chat app (fastest for iterating on agent behavior)
2. **Bot Framework Emulator** — tests the full M365 Agents SDK bot pipeline

Both use `DefaultAzureCredential` (`az login`) for Fabric authentication.

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| Python 3.11+ | Required runtime |
| Node.js 18+ | Custom UX frontend only |
| Azure CLI | Authenticated via `az login` with Fabric workspace access |
| Azure OpenAI | API key + deployment name |
| Fabric workspace | With GraphQL API endpoints |

---

## Option 1: Custom UX (Recommended for Agent Development)

The Custom UX (`graphql_agents/`) provides a full chat interface with streaming responses and Mem0 memory.

### Setup

```powershell
# From the repo root
python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r graphql_agents\backend\requirements.txt
cd graphql_agents\frontend
npm install
cd ..\..
```

### Configure

```powershell
Copy-Item graphql_agents\.env.template graphql_agents\.env
# Edit graphql_agents/.env with your Azure OpenAI and Fabric details
```

### Run

```powershell
az login
cd graphql_agents
.\start_ui.ps1
```

Open `http://localhost:5173`.

### When to Use

- Iterating on orchestrator or sub-agent prompts
- Testing GraphQL query generation and results
- Developing the frontend UI
- Quick demos with persistent memory

---

## Option 2: Bot Framework Emulator

The Emulator tests the full M365 Agents SDK pipeline — activity routing, SSO handler stubs, and MAF orchestration — using anonymous auth locally.

### Install the Emulator

Download from: https://github.com/microsoft/BotFramework-Emulator/releases

### Setup

```powershell
# From the repo root (reuse the same venv)
pip install -r m365_graphql_orchestrator\requirements.txt
```

### Configure

```powershell
Copy-Item m365_graphql_orchestrator\env.TEMPLATE m365_graphql_orchestrator\.env
```

Edit `m365_graphql_orchestrator/.env` with the key setting:

```env
USE_ANONYMOUS_MODE=True

# Azure OpenAI
AOAI_ENDPOINT=https://<your-aoai>.openai.azure.com/
AOAI_KEY=<your-api-key>
AZURE_OPENAI_DEPLOYMENT_NAME=<your-deployment>

# Fabric GraphQL API endpoints
FABRIC_SALES_GRAPHQL_URL=https://...
FABRIC_CUSTOMER_GRAPHQL_URL=https://...
FABRIC_PRODUCT_GRAPHQL_URL=https://...
```

> Bot registration settings (`CLIENTID`, `CLIENTSECRET`, `TENANTID`) are not needed in anonymous mode.

### Run

```powershell
az login
cd m365_graphql_orchestrator
python -m src.main
```

Server starts at `http://localhost:8000/api/messages`.

### Connect the Emulator

1. Open **Bot Framework Emulator**
2. Click **Open Bot**
3. Bot URL: `http://localhost:8000/api/messages`
4. Leave **Microsoft App ID** and **Password** blank
5. Click **Connect**

### What Anonymous Mode Does

| Component | Normal (Teams) | Anonymous (Emulator) |
|-----------|---------------|---------------------|
| Auth middleware | JWT validation | Fake claims — no validation |
| Connection manager | MSAL authentication | Skipped |
| Fabric token | SSO → OBO via user's identity | `DefaultAzureCredential` via `az login` |

The agent logic, MAF orchestration, and GraphQL queries are identical in both modes.

### When to Use

- Testing the full bot pipeline (activity handlers, invoke handlers)
- Debugging M365 Agents SDK behavior
- When tenant restrictions prevent Teams app sideloading
- Verifying the `on_message` and `on_invoke` handlers

---

## Option 3: Dev Tunnel (Teams with Local Code)

To test the M365 bot **in Teams** while running code locally:

```powershell
# 1. Create a dev tunnel
devtunnel create --allow-anonymous
devtunnel port create -p 8000
devtunnel host

# 2. Copy the tunnel URL (e.g. https://abc123.devtunnels.ms)

# 3. Set as the bot messaging endpoint
az bot update `
  --resource-group <your-rg> `
  --name <your-bot-name> `
  --endpoint "https://<tunnel-url>/api/messages"

# 4. Run the bot locally (NOT anonymous mode)
cd m365_graphql_orchestrator
# Ensure USE_ANONYMOUS_MODE=False in .env
python -m src.main
```

Now test in Teams — messages route through the dev tunnel to your local code.

> Remember to set `USE_ANONYMOUS_MODE=False` and provide the full bot registration settings in `.env`.

---

## Comparison

| | Custom UX | Bot Emulator | Dev Tunnel |
|---|---|---|---|
| **What it tests** | Agent + FastAPI + UI | Full bot pipeline | Full bot + Teams |
| **Auth** | `az login` | `az login` (anon mode) | Teams SSO → OBO |
| **Fabric token** | Developer identity | Developer identity | User identity |
| **Setup** | Minimal | Emulator install | Dev tunnel + Bot registration |
| **SSO testing** | No | No | Yes |
| **Best for** | Agent prompts, queries, UI | Bot pipeline, handlers | End-to-end Teams testing |

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `DefaultAzureCredential` fails | Not signed in | Run `az login` |
| Fabric returns 401/403 | Identity lacks workspace access | Verify Fabric permissions |
| `ModuleNotFoundError` | Missing dependencies | `pip install -r requirements.txt` in the correct folder |
| Emulator can't connect | Bot server not running | Verify `python -m src.main` is running |
| Emulator returns 500 | Server error | Check terminal output for stack trace |
| Dev tunnel connection reset | Tunnel not hosting | Ensure `devtunnel host` is running |
# Local Testing Guide

This guide covers two ways to test the Fabric Agents Orchestrator locally before deploying to Azure:

1. **DevUI** — browser-based chat UI (fastest for iterating on agent behavior)
2. **Bot Framework Emulator** — tests the full M365 Agents SDK bot pipeline locally

Both approaches use `DefaultAzureCredential` (`az login`) for Fabric authentication instead of the Teams SSO/OBO flow.

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| **Python 3.11+** | Required runtime |
| **Azure CLI** | Authenticated via `az login` with an identity that has access to the Fabric workspace |
| **Azure OpenAI resource** | With a deployment supporting the Responses API |
| **Fabric workspace access** | Your `az login` identity must have at least Viewer role on the workspace containing the data agents |

---

## Option 1: DevUI (Recommended for Agent Development)

DevUI is a browser-based chat interface provided by the `agent-framework-devui` package. It loads the agent from `agents/orchestrator_agent/` and runs it directly — no bot framework involved.

### Setup

```bash
# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r agents/requirements.txt

# Authenticate to Azure (provides Fabric token via DefaultAzureCredential)
az login
```

### Configure Environment

Create `agents/.env` (gitignored) with your Azure OpenAI and Fabric settings:

```env
AOAI_ENDPOINT=https://<your-aoai>.openai.azure.com/
AOAI_KEY=<your-api-key>
AZURE_OPENAI_DEPLOYMENT_NAME=<your-deployment>

# NOTE: Do NOT set AZURE_OPENAI_API_VERSION — the MAF SDK default ("preview") is correct.

FABRIC_SALES_AGENT_MCP_URL=https://api.fabric.microsoft.com/v1/mcp/workspaces/<workspace-id>/dataagents/<sales-agent-id>/agent
FABRIC_CUSTOMER_AGENT_MCP_URL=https://api.fabric.microsoft.com/v1/mcp/workspaces/<workspace-id>/dataagents/<customer-agent-id>/agent
FABRIC_PRODUCT_AGENT_MCP_URL=https://api.fabric.microsoft.com/v1/mcp/workspaces/<workspace-id>/dataagents/<product-agent-id>/agent
```

### Run

```bash
python run.py
```

Opens a browser UI at `http://localhost:8080`. Type a question and the agent will query Fabric data agents using your `az login` identity.

### When to Use DevUI

- Iterating on the system prompt (`prompts/orchestrator_agent.md`)
- Testing MCP tool wiring and Fabric data agent responses
- Debugging agent behavior without bot framework overhead
- Quick demos

---

## Option 2: Bot Framework Emulator

The Bot Framework Emulator tests the full M365 Agents SDK pipeline — activity routing, turn handlers, the MAF orchestration layer — but uses anonymous auth locally instead of Teams SSO.

### Install the Emulator

Download the **Bot Framework Emulator** from:
https://github.com/microsoft/BotFramework-Emulator/releases

### Setup

```bash
# From the repo root
cd m365_agents_orchestrator

# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Authenticate to Azure
az login
```

### Configure Environment

Create `m365_agents_orchestrator/.env` (gitignored). The key setting is `USE_ANONYMOUS_MODE=True`:

```env
# ── Anonymous mode — enables local testing without bot registration ──
USE_ANONYMOUS_MODE=True

# ── M365 Agents SDK — not needed in anonymous mode ──
# CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID=...
# CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTSECRET=...
# CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID=...

# ── Azure OpenAI ──
AOAI_ENDPOINT=https://<your-aoai>.openai.azure.com/
AOAI_KEY=<your-api-key>
AZURE_OPENAI_DEPLOYMENT_NAME=<your-deployment>

# NOTE: Do NOT set AZURE_OPENAI_API_VERSION

# ── Fabric Data Agent MCP URLs ──
FABRIC_SALES_AGENT_MCP_URL=https://api.fabric.microsoft.com/v1/mcp/workspaces/<workspace-id>/dataagents/<sales-agent-id>/agent
FABRIC_CUSTOMER_AGENT_MCP_URL=https://api.fabric.microsoft.com/v1/mcp/workspaces/<workspace-id>/dataagents/<customer-agent-id>/agent
FABRIC_PRODUCT_AGENT_MCP_URL=https://api.fabric.microsoft.com/v1/mcp/workspaces/<workspace-id>/dataagents/<product-agent-id>/agent
```

### Run the Bot

```bash
python -m src.main
```

The server starts on `http://localhost:8000/api/messages`.

### Connect the Emulator

1. Open **Bot Framework Emulator**.
2. Click **Open Bot**.
3. Set **Bot URL** to: `http://localhost:8000/api/messages`
4. Leave **Microsoft App ID** and **Microsoft App Password** blank.
5. Click **Connect**.

Send a message — the bot processes it through the full M365 Agents SDK pipeline and returns a response.

### What `USE_ANONYMOUS_MODE=True` Does

When anonymous mode is enabled, the bot:

| Component | Normal (Teams) | Anonymous (Emulator) |
|-----------|---------------|---------------------|
| **Auth middleware** | `jwt_authorization_middleware` validates Bot Service JWTs | `anonymous_claims_middleware` injects fake claims — no JWT validation |
| **Connection manager** | `MsalConnectionManager` authenticates with Entra ID | `None` — skipped entirely |
| **Fabric token** | SSO → OBO via `UserTokenClient` (user's identity) | `DefaultAzureCredential` via `az login` (developer's identity) |
| **MCP tool headers** | Per-user Fabric bearer token from OBO exchange | Shared Fabric bearer token from `az login` |

The agent logic, MAF orchestration, MCP tool wiring, and Azure OpenAI calls are identical in both modes.

### When to Use the Emulator

- **Custom app sideloading is restricted** — if your tenant doesn't allow uploading custom Teams apps (common in enterprise environments requiring IT admin approval), the Emulator lets you test the full bot pipeline without a Teams deployment
- Testing the full bot pipeline (activity handlers, invoke handlers, turn context)
- Debugging M365 Agents SDK behavior (e.g., message routing, error handling)
- Verifying the `on_message` and `on_invoke` handlers work correctly
- Testing before deploying to Azure App Service

---

## Comparison

| | DevUI | Bot Framework Emulator |
|---|---|---|
| **What it tests** | Agent + MAF + Azure OpenAI + Fabric MCP | Full bot pipeline + Agent + MAF + Azure OpenAI + Fabric MCP |
| **Auth** | `DefaultAzureCredential` | `DefaultAzureCredential` (anonymous mode) |
| **Setup complexity** | Minimal | Requires Emulator app + `USE_ANONYMOUS_MODE` |
| **Speed** | Fast — direct agent invocation | Slightly slower — full HTTP activity pipeline |
| **SSO/OBO testing** | No | No (requires deployed bot + Teams) |
| **Best for** | Agent behavior, prompts, MCP tools | Bot framework integration, activity handlers |

> **Note:** Neither local option tests the Teams SSO/OBO authentication flow. To test SSO, you must deploy to Azure App Service and use the bot in Teams.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `DefaultAzureCredential` fails | Not logged in to Azure CLI | Run `az login` |
| Fabric MCP calls return 401/403 | Your `az login` identity lacks workspace access | Ensure your identity has at least Viewer role on the Fabric workspace |
| `ModuleNotFoundError` | Dependencies not installed | Run `pip install -r requirements.txt` in the correct directory |
| 400 "API version not supported" | `AZURE_OPENAI_API_VERSION` is set in `.env` | Remove the variable — the MAF SDK default (`"preview"`) is correct |
| Emulator shows "Cannot connect" | Bot server not running or wrong port | Verify `python -m src.main` is running and URL is `http://localhost:8000/api/messages` |
| Emulator returns 500 | Check terminal output for stack trace | The bot logs detailed errors to stdout — look for `[ERROR]` lines |
