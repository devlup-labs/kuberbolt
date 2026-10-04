# Start Kuberbolt Financial Pod gRPC Server (:6001) on Windows PowerShell
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

# Check if Docker container is already holding port 6001
$dockerRunning = docker ps --filter "name=agent-pod-financial-pod-1" -q
if ($dockerRunning) {
    Write-Host "[!] Docker container 'agent-pod-financial-pod-1' is currently using port 6001." -ForegroundColor Yellow
    Write-Host "    Stopping Docker container so local Go binary can bind to :6001..." -ForegroundColor Yellow
    docker stop agent-pod-financial-pod-1
}

# Free port 6001 if another local process is holding it
$portProcess = Get-NetTCPConnection -LocalPort 6001 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
if ($portProcess) {
    foreach ($pidToKill in $portProcess) {
        Write-Host "[!] Killing existing process ($pidToKill) holding port 6001..." -ForegroundColor Yellow
        Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "⚡ Starting Financial Pod gRPC Server (:6001) via Go" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

New-Item -ItemType Directory -Force "$HOME\.kuberbolt\provider" | Out-Null

Set-Location "$repoRoot\agent-pod\financial-pod"
go run ./cmd/financialpod --config "$repoRoot\kuberbolt-config\buyer.yaml"
