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

## 3. Deploy to Azure Container Apps

### Prerequisites

- **Azure Container Registry (ACR)** — to host the Docker image
- **Docker** installed locally

### Build & Push the Container Image

```powershell
cd m365_graphql_orchestrator
.\push_to_acr.ps1 -AcrName <your-acr-name>
```

Or manually:
```powershell
az acr login --name <your-acr>
docker build -t <your-acr>.azurecr.io/m365-graphql-orchestrator:latest .
docker push <your-acr>.azurecr.io/m365-graphql-orchestrator:latest
```

### Create the Container Apps Environment (if needed)

```powershell
az containerapp env create `
  --name <your-env-name> `
  --resource-group <your-rg> `
  --location <your-region>
```

### Create the Container App

```powershell
az containerapp create `
  --name <your-container-app> `
  --resource-group <your-rg> `
  --environment <your-env-name> `
  --image <your-acr>.azurecr.io/m365-graphql-orchestrator:latest `
  --registry-server <your-acr>.azurecr.io `
  --registry-username <acr-admin-user> `
  --registry-password <acr-admin-password> `
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
    FABRIC_PRODUCT_GRAPHQL_URL=<your-fabric-graphql-url>
```

### (Optional) Managed Identity for ACR Pull

Instead of using admin credentials for ACR, you can use managed identity:

```powershell
# Enable system-assigned managed identity
az containerapp identity assign `
  --name <your-container-app> `
  --resource-group <your-rg> `
  --system-assigned

# Grant AcrPull on the registry
$principalId = az containerapp show `
  --name <your-container-app> `
  --resource-group <your-rg> `
  --query "identity.principalId" -o tsv

$acrId = az acr show --name <your-acr> --query "id" -o tsv

az role assignment create --assignee $principalId --role AcrPull --scope $acrId

# Switch registry auth to managed identity
az containerapp registry set `
  --name <your-container-app> `
  --resource-group <your-rg> `
  --server <your-acr>.azurecr.io `
  --identity system
```

> **Note on Fabric access**: The container app's identity is NOT used for Fabric GraphQL.
> The bot uses the **signed-in Teams user's identity** (SSO → OBO token exchange) to call
> Fabric. Each user must have Fabric workspace access granted to their own Entra ID account.

### Get the Container App FQDN

```powershell
az containerapp show `
  --name <your-container-app> `
  --resource-group <your-rg> `
  --query "properties.configuration.ingress.fqdn" -o tsv
```

---

## 4. Set the Bot Messaging Endpoint

```powershell
az bot update `
  --resource-group <your-rg> `
  --name <your-bot-name> `
  --endpoint "https://<your-container-app-fqdn>/api/messages"
```

---

## 5. Update the Teams App Manifest

Edit `appPackage/manifest.json`:

1. Replace all `00000000-0000-0000-0000-000000000000` with your **bot Client ID**
2. Update `validDomains` with your Container App FQDN:
   ```json
   "validDomains": [
     "<your-container-app-fqdn>",
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

## Updating the Deployment

After code changes, rebuild and push the new image, then update the container:

```powershell
cd m365_graphql_orchestrator
.\push_to_acr.ps1 -AcrName <your-acr-name> -Tag v2

az containerapp update `
  --name <your-container-app> `
  --resource-group <your-rg> `
  --image <your-acr>.azurecr.io/m365-graphql-orchestrator:v2
```

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
