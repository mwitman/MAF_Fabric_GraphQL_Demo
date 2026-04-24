# Deploying GraphQL Agents Orchestrator to M365 (Teams + Copilot)

## Prerequisites

- **Azure subscription** with permissions to create resources
- **Azure CLI** (`az login` completed)
- **M365 tenant** with Teams enabled
- **M365 Copilot license** (for Copilot access; Teams bot works without it)
- **Python 3.12+**

---

## 1. Create the Entra ID App Registration

1. Go to **Entra ID → App registrations → New registration**
2. **Name**: `GraphQL Agents Bot`
3. **Supported account types**: Single tenant
4. **Redirect URI**: Web — `https://token.botframework.com/.auth/web/redirect`
5. Note the **Application (client) ID** and **Directory (tenant) ID**

### Client Secret

- **Certificates & secrets → New client secret**
- Copy the secret value immediately (you won't see it again)

### API Permissions (Delegated)

| API | Permission | Type |
|-----|------------|------|
| Microsoft Fabric (`https://api.fabric.microsoft.com`) | `Fabric.Read.All` | Delegated |
| Microsoft Graph | `openid` | Delegated |
| Microsoft Graph | `profile` | Delegated |
| Microsoft Graph | `offline_access` | Delegated |

Click **Grant admin consent** after adding.

### Expose an API (required for Teams SSO)

1. **Expose an API → Set Application ID URI** to:
   ```
   api://botid-<your-client-id>
   ```
2. **Add a scope**:
   - Scope name: `access_as_user`
   - Who can consent: Admins and users
   - Admin consent display name: `Access as user`
3. **Add authorized client applications** (for Teams SSO):
   - `1fec8e78-bce4-4aaf-ab1b-5451cc387264` — Teams desktop/web
   - `5e3ce6c0-2b1f-4285-8d4b-75ee78787346` — Teams mobile

   Authorize both for the `access_as_user` scope.

### Authentication (optional)

If SSO token exchange fails, enable under **Authentication → Implicit grant**:
- ☑ ID tokens

---

## 2. Create the Azure Bot Resource

```powershell
az bot create `
  --resource-group <your-rg> `
  --name <your-bot-name> `
  --app-type SingleTenant `
  --appid <your-client-id> `
  --tenant-id <your-tenant-id>
```

### Configure the Fabric OAuth Connection

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

## 3. Deploy to Azure App Service

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

## 4. Set the Bot Messaging Endpoint

```powershell
az bot update `
  --resource-group <your-rg> `
  --name <your-bot-name> `
  --endpoint "https://<your-app-name>.azurewebsites.net/api/messages"
```

---

## 5. Update the Teams App Manifest

Edit `appPackage/manifest.json`:

1. Replace all `00000000-0000-0000-0000-000000000000` with your **bot Client ID**
2. Update `validDomains` with your App Service domain:
   ```json
   "validDomains": [
     "<your-app-name>.azurewebsites.net",
     "token.botframework.com",
     "login.microsoftonline.com",
     "login.windows.net"
   ]
   ```
3. Update `webApplicationInfo.resource`:
   ```json
   "webApplicationInfo": {
     "id": "<your-client-id>",
     "resource": "api://botid-<your-client-id>"
   }
   ```

---

## 6. Package and Sideload to Teams

You need two icon files in `appPackage/`:
- `color.png` — 192×192 px
- `outline.png` — 32×32 px (transparent background, white foreground)

```powershell
cd appPackage
Compress-Archive -Path manifest.json, color.png, outline.png -DestinationPath graphql-agents.zip -Force
```

Then in **Teams → Apps → Manage your apps → Upload a custom app** → select the `.zip`.

---

## 7. Access in M365 Copilot

Once the app is sideloaded:

- **Teams**: Open a chat with the bot directly (search for "GraphQL Agents Orchestrator")
- **M365 Copilot**: Type `@GraphQL Agents Orchestrator` followed by your question

> **Note**: M365 Copilot requires a Copilot license. The tenant admin may need to approve the app in **Teams Admin Center → Manage apps**.

---

## Local Development (Optional)

For testing without deploying:

1. Set `USE_ANONYMOUS_MODE=True` in `.env`
2. Run:
   ```powershell
   cd m365_graphql_orchestrator
   python -m src.main
   ```
3. Use the [Bot Framework Emulator](https://github.com/Microsoft/BotFramework-Emulator) against `http://localhost:8000/api/messages`

Or use a **dev tunnel** to test in Teams directly:
```powershell
devtunnel create --allow-anonymous
devtunnel port create -p 8000
devtunnel host
```
Then set the tunnel URL as the bot messaging endpoint.
