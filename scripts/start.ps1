param(
    [string]$ImageName = "pm-mvp-app",
    [int]$Port = 8000
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $scriptDir "..")

Write-Host "Building Docker image: $ImageName"
docker build -t $ImageName .

Write-Host "Starting container on port $Port"
docker run --env-file .env --rm -d -p $Port:8000 --name $ImageName $ImageName
Write-Host "Container started. Visit http://localhost:$Port"
