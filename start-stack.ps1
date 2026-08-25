# Starts all three Mindlens dev processes - backend, ngrok tunnel, frontend
# - each in its own window, left running, then runs check-stack.ps1 to
# confirm they actually came up.
#
#     powershell -ExecutionPolicy Bypass -File .\start-stack.ps1
#
# MongoDB needs an elevated shell to start (see CLAUDE.md) - this script
# elevates only that one step via a single UAC prompt; everything else runs
# at this window's own privilege level.
#
# The ngrok domain is pinned explicitly with --url rather than relying on a
# free account's "only reserved domain" auto-selection - see docs/
# DEPLOYMENT.md's "Start the tunnel" section for why that default existed
# and why pinning it here is more robust (survives a second domain ever
# being reserved on this account). --domain works too but ngrok flags it as
# deprecated in favour of --url as of this ngrok version.
#
# ASCII only on purpose - see check-stack.ps1's header for why.

$ErrorActionPreference = 'SilentlyContinue'
$root = $PSScriptRoot
$ngrokDomain = 'playroom-operative-ninth.ngrok-free.dev'
$ngrokExe = Join-Path $root 'tools\ngrok.exe'

Write-Host ""
Write-Host "Starting Mindlens dev stack" -ForegroundColor Cyan
Write-Host "---------------------------"

# 1. MongoDB - elevated, does not reliably survive sleep/restart.
$mongo = Get-Service MongoDB -ErrorAction SilentlyContinue
if (-not $mongo) {
    Write-Host "  DOWN MongoDB service not found - is it installed?" -ForegroundColor Red
} elseif ($mongo.Status -eq 'Running') {
    Write-Host "  OK   MongoDB already running" -ForegroundColor Green
} else {
    Write-Host "  Starting MongoDB (elevated - a UAC prompt will appear)..." -ForegroundColor Yellow
    Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile', '-Command', 'Start-Service MongoDB' -Wait
    Start-Sleep -Seconds 2
    $mongo = Get-Service MongoDB
    if ($mongo.Status -eq 'Running') {
        Write-Host "  OK   MongoDB started" -ForegroundColor Green
    } else {
        Write-Host "  DOWN MongoDB still not running - start it manually in an admin shell" -ForegroundColor Red
    }
}

# 2. Backend - new window, left running.
Write-Host "  Starting backend..." -ForegroundColor Yellow
$backendCmd = "cd '$root\backend'; ..\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
Start-Process powershell -ArgumentList '-NoExit', '-Command', $backendCmd

# 3. ngrok - pinned to the reserved dev domain, new window.
if (Test-Path $ngrokExe) {
    Write-Host "  Starting ngrok ($ngrokDomain)..." -ForegroundColor Yellow
    $ngrokCmd = "& '$ngrokExe' http 8000 --url=https://$ngrokDomain"
    Start-Process powershell -ArgumentList '-NoExit', '-Command', $ngrokCmd
} else {
    Write-Host "  DOWN ngrok.exe not found at $ngrokExe - see README 'The ngrok tunnel'" -ForegroundColor Red
}

# 4. Frontend - new window, local dev only (the Vercel deploy doesn't need this).
Write-Host "  Starting frontend..." -ForegroundColor Yellow
$frontendCmd = "cd '$root\frontend'; npm run dev"
Start-Process powershell -ArgumentList '-NoExit', '-Command', $frontendCmd

Write-Host ""
Write-Host "All three launched in separate windows. Waiting 20s for the backend" -ForegroundColor Cyan
Write-Host "to load its five models, then checking..." -ForegroundColor Cyan
Start-Sleep -Seconds 20
& (Join-Path $root 'check-stack.ps1')
