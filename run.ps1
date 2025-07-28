# PowerShell script to run dev tunnel and servers
Write-Host "Setting up dev tunnel..." -ForegroundColor Green

# Create dev tunnel with anonymous access
devtunnel create --allow-anonymous

# Create port mapping for port 8080
devtunnel port create -p 8080

# Start hosting the tunnel in background
Write-Host "Starting dev tunnel host..." -ForegroundColor Green
Start-Job -ScriptBlock { devtunnel host } -Name "DevTunnel"

# Wait a moment for tunnel to initialize
Start-Sleep -Seconds 3

# Start the calling server in background
Write-Host "Starting calling server..." -ForegroundColor Green
Start-Job -ScriptBlock { 
    Set-Location $using:PWD
    python calling_server.py 
} -Name "CallingServer"

# Wait a moment
Start-Sleep -Seconds 2

# Start the main app
Write-Host "Starting main app..." -ForegroundColor Green
python app.py

# Clean up jobs when script ends
Write-Host "Cleaning up background jobs..." -ForegroundColor Yellow
Get-Job | Stop-Job
Get-Job | Remove-Job
