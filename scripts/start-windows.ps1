# Build the image and (re)start the app at http://localhost:8000
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path ".env")) {
    Write-Error "Missing .env in the project root (it needs OPENROUTER_API_KEY)."
    exit 1
}

docker build -t blog-app .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
docker rm -f blog-app 2>$null | Out-Null
docker run -d --name blog-app -p 8000:8000 --env-file .env blog-app | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "App running at http://localhost:8000"
