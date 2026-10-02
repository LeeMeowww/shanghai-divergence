$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$localPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if ((Test-Path (Join-Path $PSScriptRoot '.deps\fastapi')) -and (Test-Path $bundledPython)) {
    $appPython = $bundledPython
} elseif (Test-Path $localPython) {
    $appPython = $localPython
} else {
    $appPython = (Get-Command python -ErrorAction Stop).Source
}
# Codex's disconnected loopback proxy is not an actual user proxy.
foreach ($proxyName in @('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY')) {
    if ([Environment]::GetEnvironmentVariable($proxyName, 'Process') -eq 'http://127.0.0.1:9') {
        [Environment]::SetEnvironmentVariable($proxyName, $null, 'Process')
    }
}
& $appPython run.py
if ($LASTEXITCODE -ne 0) { Read-Host 'Startup failed. Press Enter to close' }
