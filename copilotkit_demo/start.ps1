<#
.SYNOPSIS
    Start both the AG-UI backend and CopilotKit frontend for the Fabric demo.
.DESCRIPTION
    Launches the Python FastAPI backend (port 8888) and Next.js frontend (port 3000)
    in separate terminal windows.
#>

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=== Fabric Data Agents — CopilotKit Demo ===" -ForegroundColor Cyan
Write-Host ""

# --- Backend ---
Write-Host "[1/2] Starting AG-UI backend (port 8888)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$root\backend'; python server.py"
)

# --- Frontend ---
Write-Host "[2/2] Starting CopilotKit frontend (port 3000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$root\frontend'; npm run dev"
)

Write-Host ""
Write-Host "Backend:  http://localhost:8888" -ForegroundColor Green
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Green
Write-Host ""
Write-Host "Close the spawned terminal windows to stop the servers." -ForegroundColor DarkGray
