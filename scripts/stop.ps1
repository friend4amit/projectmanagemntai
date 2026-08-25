param(
    [string]$ContainerName = "pm-mvp-app"
)

Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

Write-Host "Stopping container: $ContainerName"
docker stop $ContainerName | Out-Null
Write-Host "Container stopped."
