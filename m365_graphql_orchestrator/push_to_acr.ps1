param(
    [Parameter(Mandatory)][string]$AcrName,
    [string]$ImageName = "m365-graphql-orchestrator",
    [string]$Tag = "latest"
)

$ErrorActionPreference = "Stop"

# Normalize: strip .azurecr.io if the user passed the full login server
$registry = $AcrName -replace '\.azurecr\.io$', ''
$loginServer = "$registry.azurecr.io"
$fullImage  = "$loginServer/${ImageName}:${Tag}"

Write-Host "==> Logging in to ACR: $loginServer" -ForegroundColor Cyan
az acr login --name $registry
if ($LASTEXITCODE -ne 0) { throw "ACR login failed" }

Write-Host "==> Building image: $fullImage" -ForegroundColor Cyan
docker build -t $fullImage .
if ($LASTEXITCODE -ne 0) { throw "Docker build failed" }

Write-Host "==> Pushing image: $fullImage" -ForegroundColor Cyan
docker push $fullImage
if ($LASTEXITCODE -ne 0) { throw "Docker push failed" }

Write-Host "==> Done! Image pushed to $fullImage" -ForegroundColor Green
