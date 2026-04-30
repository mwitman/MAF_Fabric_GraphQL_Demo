# M365 Deployment Guide — GraphQL Agents Orchestrator

Full step-by-step guide to deploy the GraphQL Agents Orchestrator (`m365_graphql_orchestrator/`) to Azure and make it available in **Microsoft Teams** and **M365 Copilot**.

---

## Overview

The deployment creates:

1. **Entra ID app registration** — bot identity + Fabric OAuth
2. **Azure Bot resource** — routes M365 channel messages
3. **Azure Container Apps** — hosts the containerised Python bot
4. **Teams app package** — sideloaded to Teams/Copilot

---

## 1. Entra ID App Registration

### Create the Registration

1. **Entra ID → App registrations → New registration**
2. Name: `GraphQL Agents Bot`
3. Supported account types: **Single tenant**
4. Redirect URI: **Web** — `https://token.botframework.com/.auth/web/redirect`
5. Note the **Application (client) ID** and **Directory (tenant) ID**

### Client Secret

- **Certificates & secrets → New client secret**
- Copy the value immediately

### API Permissions (Delegated)

| API | Permission | Type |
|-----|------------|------|
| Microsoft Fabric (`https://api.fabric.microsoft.com`) | `Fabric.Read.All` | Delegated |
| Microsoft Graph | `openid` | Delegated |
| Microsoft Graph | `profile` | Delegated |
| Microsoft Graph | `offline_access` | Delegated |

Click **Grant admin consent** after adding all permissions.

### Expose an API (Required for Teams SSO)

1. **Set Application ID URI** to:
   ```
   api://botid-<your-client-id>
   ```
2. **Add a scope**: `access_as_user` (Admins and users can consent)
3. **Add authorized client applications**:
   - `1fec8e78-bce4-4aaf-ab1b-5451cc387264` — Teams desktop/web
   - `5e3ce6c0-2b1f-4285-8d4b-75ee78787346` — Teams mobile

   Authorize both for the `access_as_user` scope.

### Authentication (Optional)

If SSO token exchange fails, enable under **Authentication → Implicit grant**:
- ☑ ID tokens

---

## 2. Azure Bot Resource

```powershell
az bot create `
  --resource-group <your-rg> `
  --name <your-bot-name> `
  --app-type SingleTenant `
  --appid <your-client-id> `
  --tenant-id <your-tenant-id>
```

### Fabric OAuth Connection

In **Azure Portal → Bot resource → Settings → Configuration → Add OAuth Connection Setting**:

| Field | Value |
|-------|-------|
| Name | `FabricOAuth` |
| Service Provider | Azure Active Directory v2 |
| Client ID | `<your-client-id>` |
| Client Secret | `<your-client-secret>` |
| Tenant ID | `<your-tenant-id>` |
| Scopes | `https://api.fabric.microsoft.com/.default` |

### Enable the Teams Channel

```powershell
az bot msteams create --resource-group <your-rg> --name <your-bot-name>
```

---

## 3. Azure Container Apps

### Build and Push the Docker Image

```powershell
cd m365_graphql_orchestrator
docker build -t <your-acr>.azurecr.io/m365-graphql-orchestrator:latest .
az acr login --name <your-acr>
docker push <your-acr>.azurecr.io/m365-graphql-orchestrator:latest
```

> **Note**: The Dockerfile installs `openai==2.8.1` separately to override the `agent-framework-core` constraint (`openai<2`). This is required for `mem0ai==2.0.0` compatibility with gpt-5 series models.

### Create the Container App

```powershell
az containerapp create `
  --name <your-app-name> `
  --resource-group <your-rg> `
  --environment <your-container-env> `
  --image <your-acr>.azurecr.io/m365-graphql-orchestrator:latest `
  --registry-server <your-acr>.azurecr.io `
  --registry-username <your-acr> `
  --registry-password <your-acr-password> `
  --target-port 8000 `
  --ingress external `
  --min-replicas 1 `
  --env-vars `
    USE_ANONYMOUS_MODE=False `
    CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID=<your-client-id> `
    CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTSECRET=<your-client-secret> `
    CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID=<your-tenant-id> `
    FABRIC_ABS_OAUTH_CONNECTION_NAME=FabricOAuth `
    AOAI_ENDPOINT=<your-aoai-endpoint> `
    AOAI_KEY=<your-aoai-key> `
    AZURE_OPENAI_DEPLOYMENT_NAME=<your-deployment-name> `
    FABRIC_SALES_GRAPHQL_URL=<your-fabric-graphql-url> `
    FABRIC_CUSTOMER_GRAPHQL_URL=<your-fabric-graphql-url> `
    FABRIC_PRODUCT_GRAPHQL_URL=<your-fabric-graphql-url> `
    AZURE_AI_SEARCH_SERVICE_NAME=<your-search-service> `
    AZURE_AI_SEARCH_API_KEY=<your-search-admin-key> `
    AOAI_EMBEDDING_DEPLOYMENT_NAME=text-embedding-3-small `
    AOAI_EMBEDDING_API_VERSION=2024-06-01
```

### Deploy a New Revision

After code changes, rebuild, push, and update:

```powershell
docker build -t <your-acr>.azurecr.io/m365-graphql-orchestrator:latest .
docker push <your-acr>.azurecr.io/m365-graphql-orchestrator:latest
az containerapp update `
  --name <your-app-name> `
  --resource-group <your-rg> `
  --image <your-acr>.azurecr.io/m365-graphql-orchestrator:latest `
  --revision-suffix <revision-name>
```

---

## 4. Bot Messaging Endpoint

```powershell
az bot update `
  --resource-group <your-rg> `
  --name <your-bot-name> `
  --endpoint "https://<your-container-app-fqdn>/api/messages"
```

> Get the FQDN with: `az containerapp show --name <your-app-name> --resource-group <your-rg> --query properties.configuration.ingress.fqdn -o tsv`

---

## 5. Teams App Manifest

Edit `appPackage/manifest.json`:

1. Replace all `00000000-0000-0000-0000-000000000000` with your **bot Client ID**
2. Update `validDomains`:
   ```json
   "validDomains": [
     "<your-app-name>.azurewebsites.net",
     "token.botframework.com",
     "login.microsoftonline.com",
     "login.windows.net"
   ]
   ```
3. Update `webApplicationInfo`:
   ```json
   "webApplicationInfo": {
     "id": "<your-client-id>",
     "resource": "api://botid-<your-client-id>"
   }
   ```

---

## 6. Package and Sideload

Create two icon files in `appPackage/`:
- `color.png` — 192×192 px
- `outline.png` — 32×32 px (transparent background, white foreground)

```powershell
cd appPackage
Compress-Archive -Path manifest.json, color.png, outline.png -DestinationPath graphql-agents.zip -Force
```

In **Teams → Apps → Manage your apps → Upload a custom app** → select the `.zip`.

---

## 7. Access in M365 Copilot

Once sideloaded:

- **Teams**: Search for "GraphQL Agents Orchestrator" and start a chat
- **M365 Copilot**: Type `@GraphQL Agents Orchestrator` followed by your question

> **Requirements**: M365 Copilot license + tenant admin approval in **Teams Admin Center → Manage apps**.

---

## Authentication Flow (SSO → OBO)

```
Teams User → Teams SSO Token → Bot Service
  → tokenExchange invoke → OBO Token Exchange
  → Fabric Bearer Token → GraphQL API
```

1. Teams silently provides an SSO token via `signin/tokenExchange` invoke
2. The bot exchanges it using the `FabricOAuth` connection for a Fabric-scoped token
3. Each sub-agent's GraphQL client uses that token in the `Authorization` header
4. If SSO fails, the bot sends an OAuth card for manual sign-in

---

## Environment Variables Reference

| Variable | Description |
|----------|-------------|
| `USE_ANONYMOUS_MODE` | `True` for local Emulator testing (no bot auth) |
| `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID` | Bot app registration client ID |
| `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTSECRET` | Bot app registration client secret |
| `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID` | Azure AD tenant ID |
| `FABRIC_ABS_OAUTH_CONNECTION_NAME` | Name of the OAuth connection on the Bot resource |
| `AOAI_ENDPOINT` | Azure OpenAI endpoint URL |
| `AOAI_KEY` | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Azure OpenAI deployment name (e.g. `gpt-5.4`) |
| `FABRIC_SALES_GRAPHQL_URL` | Fabric GraphQL endpoint for sales data |
| `FABRIC_CUSTOMER_GRAPHQL_URL` | Fabric GraphQL endpoint for customer data |
| `FABRIC_PRODUCT_GRAPHQL_URL` | Fabric GraphQL endpoint for product data |
| `AZURE_AI_SEARCH_SERVICE_NAME` | Azure AI Search service name (Mem0 vector store) |
| `AZURE_AI_SEARCH_API_KEY` | Azure AI Search admin API key |
| `AOAI_EMBEDDING_DEPLOYMENT_NAME` | Embedding model deployment (e.g. `text-embedding-3-small`) |
| `AOAI_EMBEDDING_API_VERSION` | Embedding API version (e.g. `2024-06-01`) |

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Bot returns 401 | Client ID/secret mismatch | Verify `.env` matches the Entra ID app registration |
| SSO token exchange fails | Missing Expose an API config | Configure Application ID URI + authorized clients |
| Fabric returns 403 | Missing delegated permission | Add `Fabric.Read.All` and grant admin consent |
| Bot offline in Teams | Messaging endpoint wrong | Verify it points to `https://<container-app-fqdn>/api/messages` |
| No response from bot | Container crashed | Check logs: `az containerapp logs show --name <app> --resource-group <rg> --tail 100` |
| Mem0 extraction fails (400) | `max_tokens` incompatibility | Ensure `mem0ai==2.0.0` is pinned in requirements.txt |
| Mem0 not writing to Search | LLM extraction error | Check container logs for `LLM extraction failed` messages |
