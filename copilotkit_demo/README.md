# MedSurg Stitch — CopilotKit + AG-UI Demo

A custom chat application built with [CopilotKit](https://docs.copilotkit.ai/) and the [AG-UI protocol](https://docs.ag-ui.com/), backed by the Microsoft Agent Framework orchestrator that queries **Sales**, **Customer**, and **Product** data agents in Microsoft Fabric.

## Architecture

```
┌──────────────────────────┐      AG-UI/SSE       ┌──────────────────────────────┐
│  Next.js + CopilotKit    │ ────────────────────▶ │  FastAPI (AG-UI protocol)    │
│  (localhost:3000)        │ ◀──────────────────── │  (localhost:8888)            │
│                          │                       │                              │
│  • Solventum-branded UI  │                       │  Azure OpenAI Responses API  │
│  • Tool call rendering   │                       │  ┌────────────────────────┐  │
│  • Chat history sidebar  │                       │  │ Sales MCP Tool         │  │
│  • Mobile responsive     │                       │  │ Customer MCP Tool      │  │
└──────────────────────────┘                       │  │ Product MCP Tool       │  │
                                                   │  └────────────────────────┘  │
                                                   └──────────────────────────────┘
```

## Prerequisites

| Requirement | Details |
|---|---|
| **Python** | 3.11+ |
| **Node.js** | 18+ |
| **Azure CLI** | Logged in (`az login`) — needed for Fabric Entra ID tokens |
| **Azure OpenAI** | Endpoint + API key with a GPT model deployment |
| **Fabric Data Agents** | Three data agents (Sales, Customer, Product) with MCP URLs |

## Configuration

### 1. Backend configuration (`agents/.env`)

The backend reads from the shared `agents/.env` file in the repo root. Create or verify it contains:

```env
# ── Azure OpenAI (API key auth) ──────────────────────────────
AOAI_ENDPOINT=https://<your-aoai-resource>.openai.azure.com/
AOAI_KEY=<your-azure-openai-api-key>
AZURE_OPENAI_DEPLOYMENT_NAME=<your-chat-deployment-name>

# ── Fabric Data Agent MCP URLs ────────────────────────────────
FABRIC_SALES_AGENT_MCP_URL=https://api.fabric.microsoft.com/v1/mcp/workspaces/<workspace-id>/dataagents/<agent-id>/agent
FABRIC_CUSTOMER_AGENT_MCP_URL=https://api.fabric.microsoft.com/v1/mcp/workspaces/<workspace-id>/dataagents/<agent-id>/agent
FABRIC_PRODUCT_AGENT_MCP_URL=https://api.fabric.microsoft.com/v1/mcp/workspaces/<workspace-id>/dataagents/<agent-id>/agent
```

### 2. Frontend configuration (`copilotkit_demo/frontend/.env.local`)

```env
BACKEND_URL=http://localhost:8888
NEXT_PUBLIC_COPILOTKIT_DEV_CONSOLE=false
```

### 3. Azure CLI authentication

The backend uses `DefaultAzureCredential` to get Fabric tokens for MCP tool calls. Before starting:

```powershell
az login
```

The token auto-refreshes during the session. If the CLI session expires (after several hours), re-run `az login` and restart the backend.

## Quick Start

### Option 1: Start both servers manually

**Terminal 1 — Backend (port 8888):**

```powershell
cd copilotkit_demo/backend
pip install -r requirements.txt
python server.py
```

**Terminal 2 — Frontend (port 3000):**

```powershell
cd copilotkit_demo/frontend
npm install
npm run dev
```

### Option 2: Use the startup script

```powershell
cd copilotkit_demo
.\start.ps1
```

Then open **http://localhost:3000**.

## Project Structure

```
copilotkit_demo/
├── backend/
│   ├── server.py              # FastAPI + custom AG-UI endpoint
│   └── requirements.txt       # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── api/copilotkit/route.ts   # CopilotKit runtime → AG-UI proxy
│   │   │   ├── layout.tsx                # Root layout + metadata
│   │   │   ├── page.tsx                  # CopilotKit provider + chat history
│   │   │   ├── globals.css               # Solventum theme overrides
│   │   │   └── favicon.png               # Solventum favicon
│   │   └── components/
│   │       ├── FabricChat.tsx            # Main chat UI + sidebar layout
│   │       ├── ChatHistory.tsx           # Sidebar with thread management
│   │       └── ToolCallRenderer.tsx      # Custom tool call card component
│   ├── public/
│   │   └── solventumlogo.svg             # Solventum logo
│   ├── .env.local                        # Frontend env vars
│   ├── .env.local.example
│   ├── next.config.js
│   ├── package.json
│   └── tsconfig.json
├── start.ps1                  # Launch both servers
└── README.md                  # This file
```

## Key Implementation Details

### Tool Message Stripping

Azure OpenAI's Responses API with hosted MCP tools cannot replay previous tool call/result messages. The backend strips these from CopilotKit's conversation history replay to prevent `400` errors on multi-turn conversations.

### MessagesSnapshotEvent Filtering

The AG-UI adapter emits `MessagesSnapshotEvent` after each turn, which resets CopilotKit's message list. The backend filters these out to preserve tool call renders across turns.

### Fabric Token Refresh

Fabric MCP tools require Entra ID bearer tokens. The backend caches the token and refreshes it automatically when within 5 minutes of expiry via HTTP middleware.

## Troubleshooting

| Issue | Solution |
|---|---|
| `CredentialUnavailableError: Failed to invoke the Azure CLI` | Run `az login` and restart the backend |
| `No tool output found for function call` | Backend tool stripping should handle this; restart backend if it persists |
| `Server returned 424` | Transient Fabric MCP error; retry the query |
| UI shows no response | Check the backend terminal for errors; ensure both servers are running |
| Agent not found error in browser console | Verify `agentId: "fabric_orchestrator"` matches in route.ts and page.tsx |
