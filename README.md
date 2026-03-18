# Orchestrating Fabric Data Agents

An orchestrator agent built with the [Microsoft Agent Framework](https://github.com/microsoft/agent-framework) that queries three Microsoft Fabric data agents (Sales, Customer, Product) via hosted MCP endpoints and exposes the experience through DevUI.

## Architecture

```
          ┌──────────────────────────────────┐
          │          DevUI (port 8080)       │
          │  ┌────────────────────────────┐  │
          │  │  Fabric Data Agents        │  │
          │  │  Orchestrator (Agent)      │  │
          │  └──────────┬─────────────────┘  │
          │             │ get_mcp_tool()     │
          └─────────────┼────────────────────┘
                        │
                        │ Azure OpenAI Responses API
                        │ (hosted MCP — server-side execution)
                        ▼
          ┌──────────────────────────────┐
          │  Azure OpenAI (gpt-5-chat)   │
          └──────┬──────────┬──────────┬─┘
                 │          │          │
                 ▼          ▼          ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │ Sales Agent  │ │  Customer    │ │  Product     │
    │ (Fabric MCP) │ │ Agent (MCP)  │ │ Agent (MCP)  │
    └──────────────┘ └──────────────┘ └──────────────┘
```

The agent uses **hosted MCP execution** — Azure OpenAI calls the Fabric data agent MCP endpoints directly (server-side), rather than the agent framework calling them locally. This avoids the need for a local MCP server.

## Prerequisites

- **Python 3.11+**
- **Azure CLI** — logged in to the correct tenant
- **Azure OpenAI** deployment with API key access
- **Microsoft Fabric** workspace with three data agents configured (Sales, Customer, Product)

## Quick Start

### 1. Clone and create virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r agents/requirements.txt
```

### 2. Configure environment variables

Copy and edit `agents/.env`:

```dotenv
# Azure OpenAI
AOAI_ENDPOINT=https://<your-aoai>.openai.azure.com/
AOAI_KEY=<your-api-key>
AZURE_OPENAI_DEPLOYMENT_NAME=<your-deployment>

# Fabric Data Agent MCP URLs
FABRIC_SALES_AGENT_MCP_URL=https://api.fabric.microsoft.com/v1/mcp/workspaces/<workspace-id>/dataagents/<sales-agent-id>/agent
FABRIC_CUSTOMER_AGENT_MCP_URL=https://api.fabric.microsoft.com/v1/mcp/workspaces/<workspace-id>/dataagents/<customer-agent-id>/agent
FABRIC_PRODUCT_AGENT_MCP_URL=https://api.fabric.microsoft.com/v1/mcp/workspaces/<workspace-id>/dataagents/<product-agent-id>/agent
```

### 3. Log in to Azure (for Fabric token)

```powershell
az login --tenant "<your-tenant>.onmicrosoft.com"
```

The agent uses `DefaultAzureCredential` → `AzureCliCredential` to obtain a Fabric bearer token for MCP authentication.

### 4. Launch DevUI

```powershell
python run.py
# or
.\start.ps1
```

Open [http://127.0.0.1:8080](http://127.0.0.1:8080) in your browser.

## Project Structure

```
agents/
├── .env                          # Environment variables (not committed)
├── requirements.txt              # Python dependencies
└── data_agent/
    ├── __init__.py               # DevUI auto-discovery export
    ├── agent.py                  # Agent definition + MCP tool wiring
    └── prompts/
        └── data_agent.md         # System prompt (tool routing, output formatting)
run.py                            # DevUI launcher
start.ps1                         # PowerShell launcher (kills stale port, starts DevUI)
```

## How It Works

1. **Authentication** — `DefaultAzureCredential` obtains a Fabric access token (`https://api.fabric.microsoft.com/.default`), which is passed as a bearer token in HTTP headers to each MCP endpoint.
2. **Tool Registration** — `client.get_mcp_tool()` registers each Fabric data agent as a hosted MCP tool on the Azure OpenAI Responses API. Azure OpenAI calls these endpoints server-side during inference.
3. **Agent Execution** — The orchestrator agent receives a user question, Azure OpenAI decides which MCP tool(s) to invoke, executes them server-side, and streams back the combined response.
4. **DevUI Rendering** — The agent framework DevUI renders the conversation, tool calls (with arguments), and tool results in the browser.

## Fabric Data Agents

| Agent | Data |
|-------|------|
| **Sales Agent** | Orders, order details, order status, order totals |
| **Customer Agent** | Customer identity, addresses (billing/shipping) |
| **Product Agent** | Products, categories, models, descriptions |

---

## Adapting This Solution for Your Own Fabric Data Agents

This section walks through how to take this demo and connect it to your own Microsoft Fabric data agents.

### Step 1: Create Your Fabric Data Agents

In Microsoft Fabric, navigate to your workspace and create one or more **data agents**. Each data agent exposes a lakehouse, warehouse, or other Fabric data source through a natural-language query interface.

1. Open your Fabric workspace → **+ New** → **Data Agent**
2. Configure each agent with the appropriate data source (e.g., a lakehouse table, SQL endpoint)
3. Test each agent in the Fabric portal to confirm it answers queries correctly
4. Note the **workspace ID** and **data agent ID** for each agent — you'll find these in the URL:
   ```
   https://app.fabric.microsoft.com/groups/<workspace-id>/dataagents/<data-agent-id>
   ```

### Step 2: Construct MCP Endpoint URLs

Each Fabric data agent has an MCP endpoint in this format:

```
https://api.fabric.microsoft.com/v1/mcp/workspaces/<workspace-id>/dataagents/<data-agent-id>/agent
```

Build one URL per data agent you want to integrate.

### Step 3: Update Environment Variables

Edit `agents/.env` and replace the MCP URLs with your own:

```dotenv
# Azure OpenAI — point to your own deployment
AOAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AOAI_KEY=<your-api-key>
AZURE_OPENAI_DEPLOYMENT_NAME=<your-deployment-name>

# Your Fabric Data Agent MCP URLs
FABRIC_SALES_AGENT_MCP_URL=https://api.fabric.microsoft.com/v1/mcp/workspaces/<your-workspace>/dataagents/<agent-1-id>/agent
FABRIC_CUSTOMER_AGENT_MCP_URL=https://api.fabric.microsoft.com/v1/mcp/workspaces/<your-workspace>/dataagents/<agent-2-id>/agent
FABRIC_PRODUCT_AGENT_MCP_URL=https://api.fabric.microsoft.com/v1/mcp/workspaces/<your-workspace>/dataagents/<agent-3-id>/agent
```

> **Tip:** You can rename the environment variable keys (e.g., `FABRIC_INVENTORY_AGENT_MCP_URL`) — just update the corresponding `os.environ[...]` references in `agent.py`.

### Step 4: Add, Remove, or Rename Tools

In `agents/data_agent/agent.py`, each tool is registered with `client.get_mcp_tool()`. To adapt:

**Add a new tool:**
```python
inventory_tool = client.get_mcp_tool(
    name="Inventory Agent",
    url=os.environ["FABRIC_INVENTORY_AGENT_MCP_URL"],
    headers=fabric_headers,
    approval_mode="never_require",
)
```

**Remove a tool:** Delete the `get_mcp_tool()` call and remove it from the `tools=[...]` list in `client.as_agent()`.

**Rename a tool:** Change the `name=` parameter. This is the label the LLM sees when deciding which tool to call, so make it descriptive.

Then update the `tools` list passed to the agent:
```python
agent = client.as_agent(
    name="My Orchestrator",
    instructions=_instructions,
    tools=[sales_tool, inventory_tool, product_tool],  # your tools here
)
```

### Step 5: Update the System Prompt

Edit `agents/data_agent/prompts/data_agent.md` to reflect your tools and data:

- Update the **capabilities table** with your tool names and what they query
- Adjust the **output guidelines** for your data (e.g., column names, relationships, expected formats)
- Modify the **query routing logic** to describe when each tool should be used

The system prompt is what guides the LLM to pick the right tool for a given question, so be specific about what each agent can answer.

### Step 6: Configure Authentication

The agent authenticates to Fabric using the Azure CLI credential. Ensure the logged-in identity has:

- **Viewer** (or higher) access to the Fabric workspace
- Access to the underlying data sources each data agent queries

```powershell
# Log in with the correct tenant
az login --tenant "<your-tenant>.onmicrosoft.com"

# Verify the right account is active
az account show
```

For production or shared deployments, consider using a **service principal** or **managed identity** instead of the CLI credential. `DefaultAzureCredential` supports both automatically.

### Step 7: Launch and Test

```powershell
python run.py
```

Open http://127.0.0.1:8080, select your agent, and ask a question. Verify in the **Tools** panel that:
- The correct tool is invoked
- Arguments contain the user question
- The result shows the data agent's response

### Common Customizations

| Scenario | What to change |
|----------|---------------|
| **Different number of agents** | Add/remove `get_mcp_tool()` calls and update the `tools` list |
| **Different Azure OpenAI model** | Change `AZURE_OPENAI_DEPLOYMENT_NAME` in `.env` |
| **Entra ID auth (no API key)** | Replace `api_key=` with `credential=DefaultAzureCredential()` in `AzureOpenAIResponsesClient` |
| **Custom port** | Change `"8080"` in `run.py` |
| **Multi-turn memory** | Add `context_providers` or `history_providers` to the agent (see `_maf_ref/02-agents/context_providers/`) |
| **Workflow orchestration** | Wrap the agent in a workflow for approval flows, parallel tool calls, etc. (see `_maf_ref/03-workflows/`) |

---

## Modification Notes

The following patches were applied to the installed `agent-framework-devui` and `agent-framework` packages to support hosted MCP tool call/result rendering in DevUI. These are fixes for gaps in the current RC releases and will likely be resolved in future versions.

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