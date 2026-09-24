# Build the image and (re)start the app at http://localhost:8000
# Only this computer can reach it by default. To let other devices on the network (e.g. students'
# laptops) reach it, first run: $env:BLOG_HOST = "0.0.0.0"
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path ".env")) {
    Write-Error "Missing .env in the project root (it needs OPENROUTER_API_KEY)."
    exit 1
}

$bindHost = if ($env:BLOG_HOST) { $env:BLOG_HOST } else { "127.0.0.1" }

docker build -t blog-app .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Check for an old container instead of running "docker rm" and discarding its error: with
# $ErrorActionPreference = "Stop", Windows PowerShell 5.1 turns redirected stderr from a native
# command into a terminating error, so "No such container" would abort the script.
if (docker ps -aq --filter "name=^blog-app$") {
    docker rm -f blog-app | Out-Null
}

docker run -d --name blog-app --restart unless-stopped -p "${bindHost}:8000:8000" --env-file .env blog-app | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "App running at http://localhost:8000"
