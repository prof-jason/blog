# Check first rather than discarding "docker rm" errors (see start-windows.ps1).
if (docker ps -aq --filter "name=^blog-app$") {
    docker rm -f blog-app | Out-Null
    Write-Host "App stopped."
} else {
    Write-Host "App was not running."
}
