param([switch]$Worker, [switch]$Analyze)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeDir = Join-Path $projectRoot '.runtime'
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null

if ($Worker) {
    Set-Location -LiteralPath $projectRoot
    if ($Analyze) { $env:STOCK_BUNDLE_REPORT = '1' }
    & pnpm build
    $buildExitCode = $LASTEXITCODE
    Set-Content -LiteralPath (Join-Path $runtimeDir 'build.exit-code') -Value $buildExitCode
    exit $buildExitCode
}

# A detached wrapper owns build output; no descendant keeps the caller's stdout open.
Set-Content -LiteralPath (Join-Path $runtimeDir 'build.exit-code') -Value 'running'
$buildArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'), '-Worker')
if ($Analyze) { $buildArgs += '-Analyze' }
$build = Start-Process -FilePath 'powershell.exe' -ArgumentList $buildArgs -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeDir 'build.stdout.log') -RedirectStandardError (Join-Path $runtimeDir 'build.stderr.log') -PassThru
@{ pid = $build.Id; startedAt = $build.StartTime.ToUniversalTime().ToString('o') } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtimeDir 'build-process.json') -Encoding UTF8
Write-Output "Build started (PID $($build.Id)). Logs: .runtime/build.stdout.log and build.stderr.log"
