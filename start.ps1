<#
.SYNOPSIS
    Start DevUI for the Fabric Data Agent demo.

.DESCRIPTION
    Launches DevUI (agents/) on port 8080. No local MCP server is needed —
    the Fabric data agent MCP endpoints are cloud-hosted.

    Requires:
      - az login (with the appropriate Entra ID account)
      - pip install -r agents/requirements.txt

.EXAMPLE
    .\start.ps1
    .\start.ps1 -Port 8080
#>
param(
    [int]$Port = 8080
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$AgentsDir = Join-Path $Root "agents"

# ── Resolve DevUI ────────────────────────────────────────────
$devuiExe = (Get-Command devui -ErrorAction SilentlyContinue).Source
if (-not $devuiExe) {
    # Fallback: check common pip install locations
    $candidates = @(
        (Join-Path $env:APPDATA "Python\Python311\Scripts\devui.exe"),
        (Join-Path $env:APPDATA "Python\Python312\Scripts\devui.exe"),
        (Join-Path $env:APPDATA "Python\Python313\Scripts\devui.exe")
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $devuiExe = $c; break }
    }
    if (-not $devuiExe) {
        Write-Error "DevUI not found. Install: pip install agent-framework-devui"
    }
}

# ── Kill anything already on the target port ─────────────────
Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    Select-Object OwningProcess -Unique |
    ForEach-Object {
        Write-Host "[cleanup] Killing existing process on port $Port (PID $($_.OwningProcess))" -ForegroundColor Yellow
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }

# ── Start DevUI ──────────────────────────────────────────────
Write-Host ""
Write-Host "=== Fabric Data Agent — DevUI ===" -ForegroundColor Cyan
Write-Host "UI: http://localhost:$Port" -ForegroundColor Green
Write-Host ""
Write-Host "Make sure you have run 'az login' with the appropriate account." -ForegroundColor DarkGray
Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray
Write-Host ""

try {
    & $devuiExe $AgentsDir --port $Port
} finally {
    Write-Host ""
    Write-Host "Shutting down..." -ForegroundColor Yellow
    Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object OwningProcess -Unique |
        ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}
