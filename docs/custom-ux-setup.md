# Custom UX Setup — GraphQL Agents

Local development and Docker deployment guide for the **Custom UX** (`graphql_agents/`) — a React + FastAPI chat application backed by the Microsoft Agent Framework orchestrator with Mem0 persistent memory.

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| Python 3.11+ | Backend |
| Node.js 18+ | Frontend dev server (Vite) |
| Azure CLI | Authenticated via `az login` for Fabric token |
| Azure OpenAI | API key + deployment name |
| Fabric workspace | With a GraphQL API endpoint |

---

## 1. Create and Activate a Virtual Environment

From the repo root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

---

## 2. Install Dependencies

### Backend (Python)

```powershell
pip install -r graphql_agents\backend\requirements.txt
```

Key packages: `agent-framework-core`, `agent-framework-azure-ai`, `fastapi`, `uvicorn`, `mem0ai`, `azure-identity`.

### Frontend (Node.js)

```powershell
cd graphql_agents\frontend
npm install
```

---

## 3. Configure Environment Variables

```powershell
Copy-Item graphql_agents\.env.template graphql_agents\.env
```

Edit `graphql_agents/.env`:

```env
# Azure OpenAI
AOAI_ENDPOINT=https://<your-aoai>.openai.azure.com/
AOAI_KEY=<your-api-key>
AZURE_OPENAI_DEPLOYMENT_NAME=<your-deployment>

# Fabric GraphQL API endpoints (all three can point to the same API if it covers all tables)
FABRIC_SALES_GRAPHQL_URL=https://api.fabric.microsoft.com/v1/workspaces/<workspace-id>/graphqlapis/<api-id>/graphql
FABRIC_CUSTOMER_GRAPHQL_URL=https://...
FABRIC_PRODUCT_GRAPHQL_URL=https://...
```

> **Do not set** `AZURE_OPENAI_API_VERSION` — the MAF SDK default (`"preview"`) is correct.

---

## 4. Sign In to Azure

```powershell
az login
```

The backend uses `DefaultAzureCredential` to obtain a Fabric bearer token. Your signed-in identity must have at least Viewer access on the Fabric workspace.

---

## 5. Run Locally

### Option A: PowerShell Launcher (recommended)

```powershell
cd graphql_agents
.\start_ui.ps1
```

Starts both the backend (port 8080) and the Vite dev server (port 5173). Open `http://localhost:5173`.

### Option B: Manual Start

Terminal 1 — Backend:
```powershell
cd graphql_agents
..\.venv\Scripts\python.exe -m uvicorn backend.server:app --host 127.0.0.1 --port 8080
```

Terminal 2 — Frontend:
```powershell
cd graphql_agents\frontend
npm run dev
```

Open `http://localhost:5173`.

---

## 6. Test

Try prompts like:

- "Show the top 5 products by total sales"
- "Find customer details for customer ID 100"
- "List recent orders including product names"

The orchestrator routes to the appropriate sub-agent, which executes a GraphQL query against Fabric and returns the result.

---

## Mem0 Persistent Memory

The Custom UX uses [Mem0](https://github.com/mem0ai/mem0) to maintain cross-conversation memory. Configuration is in `backend/memory.py`:

- **LLM**: Azure OpenAI (same deployment as the agent)
- **Embedder**: Azure OpenAI `text-embedding-3-small`
- **Vector store**: Qdrant (in-memory for local dev; swap to a hosted instance for production)

Memory is stored per user. Before each message, the backend searches for relevant memories and injects them as context. After each response, new facts are extracted and persisted.

> **Note**: With the default in-memory Qdrant, memories are lost when the server restarts. For persistent storage, configure Qdrant with a volume or use the hosted Qdrant Cloud option.

---

## Docker Build

The `Dockerfile` uses a multi-stage build:

1. **Stage 1 (Node)**: Builds the React frontend into static assets
2. **Stage 2 (Python)**: Installs frozen Python dependencies and copies the built frontend

### Build and Run Locally

```powershell
cd graphql_agents
docker build -t fabric-graphql-agents .
docker run -p 8080:8080 --env-file .env fabric-graphql-agents
```

Open `http://localhost:8080` (FastAPI serves the built frontend as static files).

### Push to Azure Container Registry

```powershell
.\push_to_acr.ps1 -AcrName <your-acr-name>
```

Optional parameters:
- `-ImageName` (default: `fabric-graphql-agents`)
- `-Tag` (default: `latest`)

### Deploy to Azure Container Apps

```powershell
az containerapp create `
  --name graphql-agents `
  --resource-group <your-rg> `
  --environment <your-env> `
  --image <your-acr>.azurecr.io/fabric-graphql-agents:latest `
  --target-port 8080 `
  --ingress external `
  --env-vars AOAI_ENDPOINT=... AOAI_KEY=... AZURE_OPENAI_DEPLOYMENT_NAME=... `
             FABRIC_SALES_GRAPHQL_URL=... FABRIC_CUSTOMER_GRAPHQL_URL=... FABRIC_PRODUCT_GRAPHQL_URL=...
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `DefaultAzureCredential` fails | Azure CLI not signed in | Run `az login` |
| 401/403 from Fabric | Identity lacks workspace access | Verify Fabric permissions |
| `ModuleNotFoundError` | Dependencies missing | Run `pip install -r graphql_agents\backend\requirements.txt` |
| `KeyError` for env vars | Missing `.env` values | Check `graphql_agents/.env` |
| Frontend shows connection error | Backend not running | Ensure backend is on port 8080 |
| Docker build fails on pip | Stale frozen requirements | Regenerate `requirements-frozen.txt` |
