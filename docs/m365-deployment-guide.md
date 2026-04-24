# M365 Deployment Guide — GraphQL Agents Orchestrator

Full step-by-step guide to deploy the GraphQL Agents Orchestrator (`m365_graphql_orchestrator/`) to Azure and make it available in **Microsoft Teams** and **M365 Copilot**.

---

## Overview

The deployment creates:

1. **Entra ID app registration** — bot identity + Fabric OAuth
2. **Azure Bot resource** — routes M365 channel messages
3. **Azure App Service** — hosts the Python bot
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

## 3. Azure App Service

### Create the App Service

```powershell
az appservice plan create `
  --name <your-plan-name> `
  --resource-group <your-rg> `
  --sku B1 `
  --is-linux

az webapp create `
  --name <your-app-name> `
  --resource-group <your-rg> `
  --plan <your-plan-name> `
  --runtime "PYTHON:3.12"
```

### Configure App Settings

```powershell
az webapp config appsettings set `
  --name <your-app-name> `
  --resource-group <your-rg> `
  --settings `
    SCM_DO_BUILD_DURING_DEPLOYMENT=true `
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
    FABRIC_PRODUCT_GRAPHQL_URL=<your-fabric-graphql-url>
```

### Set Startup Command

```powershell
az webapp config set `
  --name <your-app-name> `
  --resource-group <your-rg> `
  --startup-file "python -m src.main"
```

### Deploy the Code

```powershell
cd m365_graphql_orchestrator
az webapp up --name <your-app-name> --resource-group <your-rg>
```

---

## 4. Bot Messaging Endpoint

```powershell
az bot update `
  --resource-group <your-rg> `
  --name <your-bot-name> `
  --endpoint "https://<your-app-name>.azurewebsites.net/api/messages"
```

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
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Azure OpenAI deployment name |
| `FABRIC_SALES_GRAPHQL_URL` | Fabric GraphQL endpoint for sales data |
| `FABRIC_CUSTOMER_GRAPHQL_URL` | Fabric GraphQL endpoint for customer data |
| `FABRIC_PRODUCT_GRAPHQL_URL` | Fabric GraphQL endpoint for product data |

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Bot returns 401 | Client ID/secret mismatch | Verify `.env` matches the Entra ID app registration |
| SSO token exchange fails | Missing Expose an API config | Configure Application ID URI + authorized clients |
| Fabric returns 403 | Missing delegated permission | Add `Fabric.Read.All` and grant admin consent |
| Bot offline in Teams | Messaging endpoint wrong | Verify it points to `https://<app>.azurewebsites.net/api/messages` |
| No response from bot | App Service crashed | Check App Service logs: `az webapp log tail --name <app> --resource-group <rg>` |
