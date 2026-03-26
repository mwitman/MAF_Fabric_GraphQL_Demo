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
