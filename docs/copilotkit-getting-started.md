# CopilotKit Custom App — Getting Started Guide

This guide covers how to set up and run the **MedSurg Stitch** demo — a custom chat application built with CopilotKit, AG-UI, and the Microsoft Agent Framework, connected to Fabric Data Agents.

## Overview

The CopilotKit demo (`copilotkit_demo/`) is a standalone application separate from the DevUI demo. It provides a branded, production-style chat interface with:

- **Solventum-branded UI** — custom colors, logo, favicon
- **Fabric Data Agent integration** — Sales, Customer, and Product MCP tools
- **AG-UI protocol** — streaming agent responses via Server-Sent Events
- **Tool call visualization** — inline cards showing which Fabric agents are queried
- **Mobile-responsive layout** — sidebar auto-collapses on small screens

## Prerequisites

| Requirement | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Backend server |
| Node.js | 18+ | Frontend dev server |
| Azure CLI | Latest | Fabric Entra ID authentication (`az login`) |
| Azure OpenAI | — | Chat completion model (e.g., GPT-4o, GPT-5) |
| Fabric Workspace | — | Three data agents with MCP endpoints configured |

## Required Configuration

### Step 1: Azure OpenAI + Fabric MCP URLs (`agents/.env`)

The backend reads from `agents/.env` at the repository root. This file is shared with the DevUI demo.

```env
# ── Azure OpenAI (API key auth) ──────────────────────────────
AOAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AOAI_KEY=<your-api-key>
AZURE_OPENAI_DEPLOYMENT_NAME=<deployment-name>

# ── Fabric Data Agent MCP URLs ────────────────────────────────
FABRIC_SALES_AGENT_MCP_URL=https://api.fabric.microsoft.com/v1/mcp/workspaces/<workspace-id>/dataagents/<agent-id>/agent
FABRIC_CUSTOMER_AGENT_MCP_URL=https://api.fabric.microsoft.com/v1/mcp/workspaces/<workspace-id>/dataagents/<agent-id>/agent
FABRIC_PRODUCT_AGENT_MCP_URL=https://api.fabric.microsoft.com/v1/mcp/workspaces/<workspace-id>/dataagents/<agent-id>/agent
```

> **How to get Fabric MCP URLs:** Open your Fabric workspace → Data Agents → select an agent → copy the MCP endpoint URL from the agent settings.

### Step 2: Azure CLI Login

The backend uses `DefaultAzureCredential` to obtain Entra ID tokens for Fabric MCP calls:

```powershell
az login
```

Tokens auto-refresh during the session. If the session expires after several hours, re-run `az login` and restart the backend.

### Step 3: Frontend Environment (`copilotkit_demo/frontend/.env.local`)

A `.env.local.example` is provided. Copy it:

```powershell
cd copilotkit_demo/frontend
copy .env.local.example .env.local
```

Default contents:

```env
BACKEND_URL=http://localhost:8888
NEXT_PUBLIC_COPILOTKIT_DEV_CONSOLE=false
```

## Installation

### Backend (Python)

```powershell
cd copilotkit_demo/backend
pip install -r requirements.txt
```

Key packages:
- `agent-framework-azure-ai` — Microsoft Agent Framework with Azure OpenAI
- `agent-framework-ag-ui` — AG-UI protocol adapter
- `fastapi` / `uvicorn` — HTTP server
- `azure-identity` — Entra ID authentication

### Frontend (Node.js)

```powershell
cd copilotkit_demo/frontend
npm install
```

Key packages:
- `@copilotkit/react-core` — CopilotKit v2 chat components
- `@copilotkit/runtime` — CopilotKit runtime with AG-UI agent support
- `next` — React framework
- `zod` — Schema validation

## Running the Demo

### Start the backend (port 8888)

```powershell
cd copilotkit_demo/backend
python server.py
```

You should see:
```
Starting AG-UI backend on port 8888...
INFO:     Uvicorn running on http://0.0.0.0:8888
```

### Start the frontend (port 3000)

```powershell
cd copilotkit_demo/frontend
npm run dev
```

You should see:
```
▲ Next.js 15.x
- Local: http://localhost:3000
✓ Ready
```

### Open the app

Navigate to **http://localhost:3000** in your browser.

## How It Works

### Request Flow

1. User types a message in the CopilotKit chat UI
2. CopilotKit sends a POST to `/api/copilotkit` (Next.js API route)
3. The Next.js route proxies to the backend at `http://localhost:8888/fabric_orchestrator`
4. The backend wraps the orchestrator agent via `AgentFrameworkAgent` and streams AG-UI events
5. The agent calls Azure OpenAI, which invokes Fabric MCP tools (Sales/Customer/Product)
6. Responses stream back as Server-Sent Events through the AG-UI protocol
7. CopilotKit renders the streaming text and tool call cards in the chat UI

### Backend Workarounds

The backend includes two important workarounds for compatibility:

- **Tool message stripping**: Azure OpenAI's Responses API cannot replay previous MCP tool call/result messages. The backend strips these from CopilotKit's conversation history to prevent `400` errors.
- **MessagesSnapshotEvent filtering**: The AG-UI adapter emits snapshot events that reset CopilotKit's message list. These are filtered to preserve tool call renders across turns.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `CredentialUnavailableError` | Azure CLI token expired | Run `az login`, restart backend |
| `No tool output found for function call` | Stale tool messages in history | Start a new chat; backend strips these automatically |
| `Server returned 424` | Transient Fabric MCP error | Retry the query |
| No response in chat | Backend not running or crashed | Check backend terminal for errors |
| `Agent 'fabric_orchestrator' not found` | Agent ID mismatch | Verify `agentId` in `route.ts` matches |
| Next.js dev indicator showing | Config not picked up | Restart Next.js after changing `next.config.js` |

## Comparison with DevUI Demo

| Feature | DevUI Demo | CopilotKit Demo |
|---|---|---|
| **UI** | Built-in DevUI framework | Custom CopilotKit + Next.js |
| **Protocol** | DevUI internal | AG-UI (open standard) |
| **Branding** | Generic | Solventum-branded |
| **Deployment** | `python run.py` | Separate backend + frontend |
| **Tool visualization** | DevUI built-in | Custom `ToolCallRenderer` |
| **Agent code** | Shared `agents/orchestrator_agent/` | Same, referenced by backend |
