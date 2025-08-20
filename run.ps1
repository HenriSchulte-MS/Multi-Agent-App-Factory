# PowerShell script to run dev tunnel and servers
Write-Host "Setting up dev tunnel..." -ForegroundColor Green

# Clear devtunnel welcome message
devtunnel --version | Out-Null

# Read configuration from .env file
$envFile = ".env"
$tunnelName = $null
$tunnelPort = $null

if (Test-Path $envFile) {
    Write-Host "Reading configuration from .env file..." -ForegroundColor Green
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^DEV_TUNNEL_NAME\s*=\s*(.+)") {
            $tunnelName = $matches[1].Trim('"')
        }
        elseif ($_ -match "^DEV_TUNNEL_PORT\s*=\s*(.+)") {
            $tunnelPort = $matches[1].Trim('"')
        }
    }
} else {
    Write-Host "Error: .env file not found. Please create .env file with required tunnel configuration." -ForegroundColor Red
    exit 1
}

# Validate required parameters
if (-not $tunnelName -or -not $tunnelPort) {
    Write-Host "Error: Missing required tunnel configuration in .env file:" -ForegroundColor Red
    if (-not $tunnelName) { Write-Host "  - DEV_TUNNEL_NAME is required" -ForegroundColor Red }
    if (-not $tunnelPort) { Write-Host "  - DEV_TUNNEL_PORT is required" -ForegroundColor Red }
    exit 1
}

Write-Host "Tunnel Name: $tunnelName" -ForegroundColor Cyan
Write-Host "Tunnel Port: $tunnelPort" -ForegroundColor Cyan

# Check if tunnel exists
Write-Host "Checking if tunnel exists..." -ForegroundColor Green
$tunnelExists = $false
$tunnelId = ""

# Just try to list tunnels, ignore any errors
$existingTunnels = @()

$tunnelListResponse = devtunnel list --json | ConvertFrom-Json
if ($tunnelListResponse.tunnels) {
    $existingTunnels = $tunnelListResponse.tunnels
}

$matchingTunnels = $existingTunnels | Where-Object { $_.tunnelId -match "^$tunnelName\.[a-z0-9]+$" }
if ($matchingTunnels) {
    $tunnelExists = $true
    $tunnelId = $matchingTunnels[0].tunnelId
}

if ($tunnelExists) {
    Write-Host "Using existing tunnel '$tunnelId'" -ForegroundColor Green
} else {
    Write-Host "Creating tunnel '$tunnelName'..." -ForegroundColor Yellow
    devtunnel create $tunnelName
    devtunnel port create -p $tunnelPort

    # After creating, get the actual tunnel ID with region
    $tunnelListResponse = devtunnel list --json | ConvertFrom-Json
    $existingTunnels = $tunnelListResponse.tunnels
    $matchingTunnels = $existingTunnels | Where-Object { $_.tunnelId -match "^$tunnelName\.[a-z0-9]+$" }
    $tunnelId = $matchingTunnels[0].tunnelId
    Write-Host "Tunnel created with ID: $tunnelId and port $tunnelPort" -ForegroundColor Cyan
}

# Now that we have the tunnel ID (with region), construct the URL
$tunnelId -match "^[^.]+\.([a-z0-9]+)$" | Out-Null
$tunnelRegion = $matches[1]
$devTunnelUrl = "https://$tunnelName-$tunnelPort.$tunnelRegion.devtunnels.ms"
$env:CALL_SERVER_HOST = $devTunnelUrl

# Start hosting the tunnel in background
Write-Host "Starting dev tunnel host..." -ForegroundColor Green
Start-Job -ScriptBlock { 
    param($id)
    devtunnel host $id --allow-anonymous 
} -ArgumentList $tunnelId -Name "DevTunnel"

# Wait a moment for tunnel to initialize
Start-Sleep -Seconds 5

# Start the main app
Write-Host "Starting main app..." -ForegroundColor Green
python app_factory.py

# Clean up jobs when script ends
Write-Host "Cleaning up background jobs..." -ForegroundColor Yellow
Get-Job | Stop-Job
Get-Job | Remove-Job
