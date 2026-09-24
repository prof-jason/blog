docker rm -f blog-app 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) { Write-Host "App stopped." } else { Write-Host "App was not running." }
