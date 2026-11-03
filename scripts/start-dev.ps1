param([switch]$ApiOnly, [switch]$Demo)

$ErrorActionPreference = 'Stop'
# Restore overrides even if startup fails; a later normal start in the same terminal must
# not accidentally retain demo settings. Child processes inherit the temporary values.
$overrideNames = @('MARKET_PROVIDER', 'DATABASE_URL', 'CHECKPOINT_SQLITE_PATH', 'LLM_API_KEY', 'APP_API_KEY', 'APP_ENVIRONMENT')
$previousEnvironment = @{}
foreach ($name in $overrideNames) { $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
try {
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeDir = Join-Path $projectRoot '.runtime'
$manifestPath = Join-Path $runtimeDir 'dev-processes.json'
$apiDir = Join-Path $projectRoot 'apps/api'
$webDir = Join-Path $projectRoot 'apps/web'
$pythonExe = Join-Path $apiDir '.venv/Scripts/python.exe'

# Demo creates an isolated local database for repeatable browser tests. It never edits .env.
if ($Demo) {
    $env:MARKET_PROVIDER = 'demo'
    $env:DATABASE_URL = 'sqlite:///./e2e.db'
    $env:CHECKPOINT_SQLITE_PATH = './e2e-checkpoints.db'
    $env:LLM_API_KEY = ' '
    $env:APP_API_KEY = ' '
    $env:APP_ENVIRONMENT = 'development'
}

if (Test-Path -LiteralPath $manifestPath) {
    throw 'A process manifest already exists. Run scripts/stop-dev.ps1 before starting again.'
}
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Run uv sync in apps/api first.' }
if (-not $ApiOnly -and -not (Test-Path -LiteralPath (Join-Path $webDir 'node_modules/vite/bin/vite.js'))) {
    throw 'Run pnpm install at the project root first.'
}
$ports = if ($ApiOnly) { @(8001) } else { @(8001, 5173) }
foreach ($port in $ports) {
    $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($listener) { throw "Port $port is already in use. No existing process was stopped." }
}

New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
Push-Location $apiDir
try {
    & $pythonExe -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
} finally { Pop-Location }

# Start-Process detaches services from this shell. Redirect BOTH output streams so no child
# keeps the tool's stdout pipe open. Record start time as well as PID to avoid PID reuse.
$tracked = @()
try {
    $apiProcess = Start-Process -FilePath $pythonExe -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8001') -WorkingDirectory $apiDir -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeDir 'api.stdout.log') -RedirectStandardError (Join-Path $runtimeDir 'api.stderr.log') -PassThru
    $tracked += @{ name = 'api'; pid = $apiProcess.Id; startedAt = $apiProcess.StartTime.ToUniversalTime().ToString('o') }
    ConvertTo-Json -InputObject @($tracked) | Set-Content -LiteralPath $manifestPath -Encoding UTF8

    $workerProcess = Start-Process -FilePath $pythonExe -ArgumentList @('-m', 'app.worker') -WorkingDirectory $apiDir -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeDir 'worker.stdout.log') -RedirectStandardError (Join-Path $runtimeDir 'worker.stderr.log') -PassThru
    $tracked += @{ name = 'worker'; pid = $workerProcess.Id; startedAt = $workerProcess.StartTime.ToUniversalTime().ToString('o') }
    ConvertTo-Json -InputObject @($tracked) | Set-Content -LiteralPath $manifestPath -Encoding UTF8

    if (-not $ApiOnly) {
        $nodeExe = (& node -p 'process.execPath').Trim()
        $viteEntry = Join-Path $webDir 'node_modules/vite/bin/vite.js'
        $webProcess = Start-Process -FilePath $nodeExe -ArgumentList @(('"' + $viteEntry + '"'), '--host', '127.0.0.1') -WorkingDirectory $webDir -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeDir 'web.stdout.log') -RedirectStandardError (Join-Path $runtimeDir 'web.stderr.log') -PassThru
        $tracked += @{ name = 'web'; pid = $webProcess.Id; startedAt = $webProcess.StartTime.ToUniversalTime().ToString('o') }
        ConvertTo-Json -InputObject @($tracked) | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    }

    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/health' -TimeoutSec 1
            $webReady = $true
            if (-not $ApiOnly) {
                $web = Invoke-WebRequest -Uri 'http://127.0.0.1:5173' -UseBasicParsing -TimeoutSec 1
                $webReady = $web.StatusCode -eq 200
            }
            if ($health.status -eq 'ok' -and $webReady) { $ready = $true; break }
        } catch { Start-Sleep -Milliseconds 300 }
    }
    if (-not $ready) { throw 'Services did not become ready. Inspect logs in .runtime.' }
    if (-not $ApiOnly) { Write-Output 'Web: http://127.0.0.1:5173' }
    Write-Output 'API: http://127.0.0.1:8001/docs'
    Write-Output 'Public quotes load asynchronously; inspect the market status panel and worker logs.'
    Write-Output "Process manifest: $manifestPath"
} catch {
    & (Join-Path $PSScriptRoot 'stop-dev.ps1')
    throw
}
} finally {
    if ($Demo) {
        foreach ($name in $overrideNames) { [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], 'Process') }
    }
}
