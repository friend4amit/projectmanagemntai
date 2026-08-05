param(
    [string]$ContainerName = "pm-mvp-app"
)

Write-Host "Stopping container: $ContainerName"
docker stop $ContainerName | Out-Null
Write-Host "Container stopped."
