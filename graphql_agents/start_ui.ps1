<#
.SYNOPSIS
    Start the Fabric GraphQL Agents UI for local development.
    Launches the FastAPI backend (port 8080) and the Vite dev server (port 5173).
#>
param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $repoRoot) { $repoRoot = Split-Path -Parent $PSScriptRoot }
$graphqlDir = Join-Path $repoRoot "graphql_agents"
$venvPython = Join-Path $repoRoot ".venv" "Scripts" "python.exe"

# Ensure venv python exists
if (-not (Test-Path $venvPython)) {
    Write-Error "Virtual environment not found at $venvPython. Run: python -m venv .venv && .venv\Scripts\pip install -r graphql_agents\backend\requirements.txt"
    return
}

# -- Backend --
if (-not $FrontendOnly) {
    Write-Host "`n[Backend] Starting FastAPI on http://localhost:8080 ..." -ForegroundColor Cyan
    $backendJob = Start-Job -ScriptBlock {
        param($py, $dir)
        Set-Location $dir
        & $py -m uvicorn backend.server:app --host 127.0.0.1 --port 8080 --reload
    } -ArgumentList $venvPython, $graphqlDir
    Write-Host "[Backend] Job started (ID $($backendJob.Id))" -ForegroundColor Green
}

# -- Frontend --
if (-not $BackendOnly) {
    # Ensure node_modules
    $frontendDir = Join-Path $graphqlDir "frontend"
    if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
        Write-Host "`n[Frontend] Installing npm dependencies ..." -ForegroundColor Cyan
        Push-Location $frontendDir
        npm install
        Pop-Location
    }

    Write-Host "`n[Frontend] Starting Vite dev server on http://localhost:5173 ..." -ForegroundColor Cyan
    $frontendJob = Start-Job -ScriptBlock {
        param($dir)
        Set-Location $dir
        npm run dev
    } -ArgumentList $frontendDir
    Write-Host "[Frontend] Job started (ID $($frontendJob.Id))" -ForegroundColor Green

    Write-Host "`n  Open http://localhost:5173 in your browser" -ForegroundColor Yellow
}

Write-Host "`nPress Ctrl+C to stop all servers.`n" -ForegroundColor DarkGray

try {
    while ($true) {
        # Print any job output
        if ($backendJob) { Receive-Job $backendJob -ErrorAction SilentlyContinue }
        if ($frontendJob) { Receive-Job $frontendJob -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 2
    }
}
finally {
    Write-Host "`nStopping servers ..." -ForegroundColor Cyan
    if ($backendJob) { Stop-Job $backendJob -ErrorAction SilentlyContinue; Remove-Job $backendJob -ErrorAction SilentlyContinue }
    if ($frontendJob) { Stop-Job $frontendJob -ErrorAction SilentlyContinue; Remove-Job $frontendJob -ErrorAction SilentlyContinue }
}
