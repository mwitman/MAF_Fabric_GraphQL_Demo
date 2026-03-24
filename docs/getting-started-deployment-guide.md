# Getting Started — Deployment Guide

This guide walks through every step required to replicate the **Fabric Agents Orchestrator** bot in a new environment. By the end, you will have a working M365 bot deployed to Azure App Service that queries Microsoft Fabric data agents via Teams using the signed-in user's identity.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [1. Create the Entra ID App Registration](#1-create-the-entra-id-app-registration)
- [2. Create the Azure Bot Service Resource](#2-create-the-azure-bot-service-resource)
- [3. Configure the OAuth Connection (FabricOAuth)](#3-configure-the-oauth-connection-fabricoauth)
- [4. Create the Azure App Service](#4-create-the-azure-app-service)
- [5. Set Up Fabric Data Agents](#5-set-up-fabric-data-agents)
- [6. Provision Azure OpenAI](#6-provision-azure-openai)
- [7. Configure Environment Variables](#7-configure-environment-variables)
- [8. Deploy the Bot Code](#8-deploy-the-bot-code)
- [9. Build & Upload the Teams App Package](#9-build--upload-the-teams-app-package)
- [10. Admin Consent & Permissions](#10-admin-consent--permissions)
- [11. Test in Teams](#11-test-in-teams)
- [Troubleshooting](#troubleshooting)
- [Reference: Environment Variable Template](#reference-environment-variable-template)

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| **Azure subscription** | With permissions to create App Service, Bot Service, and OpenAI resources |
| **Entra ID (Azure AD)** | Global Admin or Application Administrator to create app registrations and grant consent |
| **Microsoft Fabric workspace** | With three data agents (Sales, Customer, Product) already created |
| **Azure OpenAI resource** | With a deployment that supports the Responses API (e.g., `gpt-4o`) |
| **Python 3.11+** | For local development and testing |
| **Azure CLI** | `az` CLI authenticated to your subscription |
| **Teams admin access** | To upload custom app packages (or your tenant allows sideloading) |

---

## 1. Create the Entra ID App Registration

1. Go to **Azure Portal → Entra ID → App registrations → New registration**.
2. Settings:
   - **Name:** `Fabric Agents Orchestrator` (or your preferred name)
   - **Supported account types:** Single tenant (accounts in this organizational directory only)
   - **Redirect URI:** Web — `https://token.botframework.com/.auth/web/redirect`

3. After creation, note:
   - **Application (client) ID** — this is your bot's App ID
   - **Directory (tenant) ID**

### Create a Client Secret

1. Go to **Certificates & secrets → New client secret**.
2. Set a description (e.g., `FabricOAuth`) and expiry.
3. **Copy the secret value immediately** — you cannot retrieve it later.

### Set the Identifier URI

1. Go to **Expose an API → Set** next to "Application ID URI".
2. Set it to: `api://botid-{your-app-id}` (e.g., `api://botid-46b2e0d8-c4c6-48e5-86d3-707e54c5ca03`).

### Add the `access_as_user` Scope

1. Under **Expose an API → Add a scope**:
   - **Scope name:** `access_as_user`
   - **Who can consent:** Admins and users
   - **Admin consent display name:** Access as user
   - **Admin consent description:** Allows Teams to get a token on behalf of the user
   - **State:** Enabled

### Pre-authorize Teams Clients

Under **Expose an API → Add a client application**, add each of these Teams client IDs and check the `access_as_user` scope:

| Client | Application ID |
|--------|---------------|
| Teams desktop / mobile | `1fec8e78-bce4-4aaf-ab1b-5451cc387264` |
| Teams web | `5e3ce6c0-2b1f-4285-8d4b-75ee78787346` |
| Office web | `4765445b-32c6-49b0-83e6-1d93765276ca` |
| Office desktop | `0ec893e0-5785-4de6-99da-4ed124e5296c` |
| Outlook desktop / mobile | `d3590ed6-52b3-4102-aeff-aad2292ab01c` |
| Outlook web | `bc59ab01-8403-45c6-8796-ac3ef710b3e3` |

### Add Fabric API Permissions

1. Go to **API permissions → Add a permission → APIs my organization uses**.
2. Search for **Microsoft Fabric** (or use Resource ID `00000009-0000-0000-c000-000000000000`).
3. Select **Delegated permissions** and add:
   - `DataAgent.Execute.All`
   - `DataAgent.Read.All`
   - `Item.Execute.All`
   - `Item.Read.All`
   - `Workspace.Read.All`
4. Click **Grant admin consent** for your tenant.

### Enable Implicit Grant (optional, for SSO fallback)

1. Go to **Authentication → Implicit grant and hybrid flows**.
2. Check: **Access tokens** and **ID tokens**.

---

## 2. Create the Azure Bot Service Resource

1. Go to **Azure Portal → Create a resource → Azure Bot**.
2. Settings:
   - **Bot handle:** Unique name (e.g., `fabric-agents-bot`)
   - **Pricing tier:** Standard
   - **Microsoft App ID:** Use the App ID from step 1 (select "Use existing app registration — Single Tenant")
   - **App Tenant ID:** Your Entra tenant ID

3. After creation, go to **Configuration → Messaging endpoint** and set:
   ```
   https://<your-app-service>.azurewebsites.net/api/messages
   ```

4. Under **Channels**, ensure **Microsoft Teams** is enabled.

---

## 3. Configure the OAuth Connection (FabricOAuth)

This is the most critical step for SSO/OBO to work.

1. Go to **Azure Bot resource → Configuration → OAuth Connection Settings → Add setting**.
2. Fill in:

   | Field | Value |
   |-------|-------|
   | **Name** | `FabricOAuth` |
   | **Service Provider** | `Azure Active Directory v2` |
   | **Client ID** | Your bot's App ID (same as step 1) |
   | **Client Secret** | The client secret you created in step 1 |
   | **Tenant ID** | Your Entra tenant ID |
   | **Scopes** | `openid offline_access https://api.fabric.microsoft.com/DataAgent.Execute.All https://api.fabric.microsoft.com/DataAgent.Read.All https://api.fabric.microsoft.com/Item.Execute.All https://api.fabric.microsoft.com/Item.Read.All https://api.fabric.microsoft.com/Workspace.Read.All` |
   | **Token Exchange URL** | `api://botid-{your-app-id}` |

3. Click **Save**.

> **IMPORTANT:** The client secret **must** be saved via the Azure Portal UI. ARM/REST API and CLI `az bot authsetting` commands have a known issue where the client secret is not persisted. Always verify by clicking "Test Connection" in the Portal after saving.

---

## 4. Create the Azure App Service

1. Go to **Azure Portal → Create a resource → Web App**.
2. Settings:
   - **Runtime stack:** Python 3.11
   - **OS:** Linux
   - **Region:** Same region as your Azure OpenAI resource
   - **App Service Plan:** Choose an appropriate tier (B1 or higher)

3. After creation, configure the **Startup Command**:
   - Go to **Configuration → General settings → Startup Command**:
     ```
     python -m src.main
     ```

4. Enable **System-assigned managed identity** (Settings → Identity → System assigned → On).
   - This is used for App Service operations, **not** for Fabric auth.

---

## 5. Set Up Fabric Data Agents

In your Microsoft Fabric workspace, create three data agents (or use existing ones):

1. **Sales Agent** — connected to sales/orders data (e.g., SalesOrderHeader, SalesOrderDetail)
2. **Customer Agent** — connected to customer data (e.g., Customer, CustomerAddress)
3. **Product Agent** — connected to product catalog data (e.g., Product, ProductCategory, ProductModel)

For each agent, note the **MCP URL**:
```
https://api.fabric.microsoft.com/v1/mcp/workspaces/{workspace-id}/dataagents/{agent-id}/agent
```

You can find the workspace ID and agent IDs in the Fabric portal URL or via the Fabric REST API.

### Workspace Access

Ensure that the **users who will use the bot** have at least **Viewer** role on the Fabric workspace. The bot uses their delegated identity, so Fabric enforces their permissions.

---

## 6. Provision Azure OpenAI

1. Create an **Azure OpenAI** resource (or use an existing one).
2. Deploy a model that supports the **Responses API** with hosted MCP tools (e.g., `gpt-4o`).
3. Note:
   - **Endpoint URL** (e.g., `https://your-aoai.openai.azure.com/`)
   - **API Key**
   - **Deployment name**

> **Important:** Do NOT set `AZURE_OPENAI_API_VERSION` as an App Setting or environment variable. The MAF SDK default (`"preview"`) is the correct value. Setting an explicit dated version (e.g., `2025-03-01-preview`) causes a 400 error with the hosted MCP URL path.

---

## 7. Configure Environment Variables

Set the following environment variables on your Azure App Service:

**Azure Portal → App Service → Configuration → Application settings**

| Variable | Value |
|----------|-------|
| `USE_ANONYMOUS_MODE` | `False` |
| `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID` | Bot App ID |
| `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTSECRET` | Bot client secret |
| `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID` | Entra tenant ID |
| `FABRIC_ABS_OAUTH_CONNECTION_NAME` | `FabricOAuth` |
| `AOAI_ENDPOINT` | `https://<your-aoai>.openai.azure.com/` |
| `AOAI_KEY` | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Your deployment name (e.g., `gpt-4o`) |
| `FABRIC_SALES_AGENT_MCP_URL` | Full MCP URL for your Sales data agent |
| `FABRIC_CUSTOMER_AGENT_MCP_URL` | Full MCP URL for your Customer data agent |
| `FABRIC_PRODUCT_AGENT_MCP_URL` | Full MCP URL for your Product data agent |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` (tells Oryx to run `pip install` from `requirements.txt` during zip deploy) |

> **Do NOT set** `AZURE_OPENAI_API_VERSION`. The MAF SDK default (`"preview"`) is correct. Setting an explicit dated version causes a 400 error.

A template file is provided at `m365_agents_orchestrator/env.TEMPLATE`.

---

## 8. Deploy the Bot Code

### Option A: ZIP Deploy (recommended)

1. From the repo root, create a deployment zip of the `m365_agents_orchestrator/` directory:

   ```powershell
   $base = "path\to\Solventum_MAF_Fabric_Demo"
   $zipPath = "$env:TEMP\m365-bot-deploy.zip"
   
   # Remove old zip if it exists
   if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
   
   # Create zip from the m365_agents_orchestrator directory
   Add-Type -AssemblyName System.IO.Compression.FileSystem
   [System.IO.Compression.ZipFile]::CreateFromDirectory(
       "$base\m365_agents_orchestrator", $zipPath
   )
   ```

2. Deploy to Azure App Service:

   ```powershell
   az webapp deploy `
       --resource-group <your-rg> `
       --name <your-app-service> `
       --src-path $zipPath `
       --type zip `
       --async false
   ```

3. Verify the deployment status:

   ```powershell
   az rest --method GET `
       --url "https://<your-app>.scm.azurewebsites.net/api/deployments/latest" `
       --resource "https://management.azure.com" `
       --query "{status:status,complete:complete,active:active}"
   ```

### Option B: Local Development

1. Clone the repo and navigate to `m365_agents_orchestrator/`.
2. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   # .venv\Scripts\Activate.ps1  # Windows PowerShell
   pip install -r requirements.txt
   ```

3. Copy `env.TEMPLATE` to `.env` and fill in your values.
4. Set `USE_ANONYMOUS_MODE=True` for local testing with the Bot Framework Emulator.
5. Run:

   ```bash
   python -m src.main
   ```

6. The bot starts on `http://localhost:8080/api/messages`.

---

## 9. Build & Upload the Teams App Package

### Update the Manifest

Edit `m365_agents_orchestrator/appPackage/manifest.json`:

1. Replace the `id` field with your bot's App ID.
2. Replace `botId` in the `bots` array with your bot's App ID.
3. Replace the `id` in `copilotAgents.customEngineAgents` with your bot's App ID.
4. Update `webApplicationInfo`:
   ```json
   "webApplicationInfo": {
     "id": "YOUR-BOT-APP-ID",
     "resource": "api://botid-YOUR-BOT-APP-ID"
   }
   ```
5. Update `validDomains` to include your App Service hostname:
   ```json
   "validDomains": [
     "your-app-service.azurewebsites.net",
     "token.botframework.com",
     "login.microsoftonline.com",
     "login.windows.net"
   ]
   ```
6. Update `developer.name` and other metadata as appropriate.

### Build the ZIP

The app package must contain exactly three files: `manifest.json`, `color.png` (192×192), and `outline.png` (32×32).

```powershell
$appPkg = "path\to\m365_agents_orchestrator\appPackage"
$zipPath = "path\to\YourAppPackage.zip"

Add-Type -AssemblyName System.IO.Compression
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

$zip = [System.IO.Compression.ZipFile]::Open($zipPath, 'Create')
foreach ($f in @("manifest.json", "color.png", "outline.png")) {
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
        $zip, "$appPkg\$f", $f
    ) | Out-Null
}
$zip.Dispose()
```

### Upload to Teams

1. Open **Microsoft Teams → Apps → Manage your apps → Upload a custom app**.
2. Select "Upload an app to your org's app catalog" (if you have Teams admin access) or "Upload a custom app" for personal sideloading.
3. Select the ZIP file.
4. The bot should appear in your Teams app list. Add it to a personal chat to begin testing.

---

## 10. Admin Consent & Permissions

### User Consent

The first time a user interacts with the bot, Teams will attempt SSO silently. If the user (or their tenant) has not yet consented to the Fabric API permissions, they will see a sign-in card.

### Tenant Admin Consent

If your tenant has a **risk-based consent policy** or disables user consent:

1. A **Global Administrator** must grant tenant-wide consent:
   - Go to **Entra ID → App registrations → Your app → API permissions → Grant admin consent for {tenant}**.
2. Alternatively, the admin can consent via URL:
   ```
   https://login.microsoftonline.com/{tenant-id}/adminconsent?client_id={app-id}
   ```

### Fabric Workspace Permissions

Users must have at least **Viewer** role on the Fabric workspace. The bot uses the user's delegated identity — Fabric enforces their access level.

---

## 11. Test in Teams

1. Open the bot in Teams (personal chat).
2. Send a test message, e.g.: `What were the top 10 sales orders last quarter?`
3. Expected behavior:
   - **First time:** A sign-in card appears. Complete the sign-in flow (or paste the magic code if prompted).
   - **After sign-in:** The bot acquires a Fabric token, queries the relevant data agent(s) via Azure OpenAI, and returns a formatted answer.

4. Try cross-domain questions: `What products did customer Contoso order?` — this should invoke both the Customer and Sales/Product agents.

---

## Troubleshooting

### Common Issues

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| "Sign-in is required but I couldn't build the sign-in card" | `ms_app_id` is `None` — the env var `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID` is not set | Verify the App Service application settings include the bot's App ID |
| Sign-in card appears but "Test Connection" fails in Azure Portal | Client secret is not saved on the OAuth connection | Re-enter and save the client secret in Portal (do not use CLI/ARM API) |
| `409` from tokenExchange, sign-in loops | `webApplicationInfo` missing from manifest, or `resource` / `id` mismatch | Ensure manifest v1.21 includes `webApplicationInfo` with matching bot App ID and identifier URI |
| "Consent required" error | User or tenant hasn't consented to Fabric API permissions | Ask a tenant admin to grant admin consent |
| Bot responds but MCP tool calls fail | Fabric token audience is wrong, or user lacks workspace access | Check App Service logs for JWT claims; verify the user's Fabric workspace role |
| 400 "API version not supported" | `AZURE_OPENAI_API_VERSION` is set as an App Setting, overriding the MAF default | Remove the `AZURE_OPENAI_API_VERSION` App Setting entirely — the MAF SDK default (`"preview"`) is correct |
| `ModuleNotFoundError: No module named 'src'` after App Setting change | Removing/adding an App Setting restarts the app but the venv wasn't persisted from the last deploy | Redeploy the zip to trigger an Oryx build (this recreates the venv with `pip install`) |
| 500 from Bot Framework token service | Bot Service messaging endpoint URL doesn't match App Service | Verify `https://<app>.azurewebsites.net/api/messages` in Bot Configuration |

### Checking Logs

Enable App Service application logging:

```powershell
az webapp log config `
    --resource-group <your-rg> `
    --name <your-app-service> `
    --application-logging filesystem `
    --level verbose `
    --docker-container-logging filesystem
```

Stream logs in real-time:

```powershell
az webapp log tail --resource-group <your-rg> --name <your-app-service>
```

The bot outputs detailed logging at every auth step, including decoded JWT claims, token exchange results, and MCP tool definitions.

---

## Reference: Environment Variable Template

```env
# ── Anonymous mode (set True for local emulator testing without bot registration)
USE_ANONYMOUS_MODE=False

# ── M365 Agents SDK — Azure Bot registration
CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID=<your-bot-app-id>
CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTSECRET=<your-bot-client-secret>
CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID=<your-tenant-id>

# ── Fabric SSO/OBO
FABRIC_ABS_OAUTH_CONNECTION_NAME=FabricOAuth

# ── Azure OpenAI
AOAI_ENDPOINT=https://<your-aoai>.openai.azure.com/
AOAI_KEY=<your-api-key>
AZURE_OPENAI_DEPLOYMENT_NAME=<your-deployment>
# NOTE: Do NOT set AZURE_OPENAI_API_VERSION — the MAF SDK default ("preview") is correct.

# ── Fabric Data Agent MCP URLs
FABRIC_SALES_AGENT_MCP_URL=https://api.fabric.microsoft.com/v1/mcp/workspaces/<workspace-id>/dataagents/<sales-agent-id>/agent
FABRIC_CUSTOMER_AGENT_MCP_URL=https://api.fabric.microsoft.com/v1/mcp/workspaces/<workspace-id>/dataagents/<customer-agent-id>/agent
FABRIC_PRODUCT_AGENT_MCP_URL=https://api.fabric.microsoft.com/v1/mcp/workspaces/<workspace-id>/dataagents/<product-agent-id>/agent
```
