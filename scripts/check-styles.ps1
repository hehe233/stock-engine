param([switch]$Worker)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeDir = Join-Path $projectRoot '.runtime'
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
if ($Worker) {
    Set-Location -LiteralPath $projectRoot
    & pnpm --filter @stock-engine/web exec node --experimental-strip-types tests/component-less.test.ts
    $result = $LASTEXITCODE
    Set-Content -LiteralPath (Join-Path $runtimeDir 'styles.exit-code') -Value $result
    exit $result
}
Set-Content -LiteralPath (Join-Path $runtimeDir 'styles.exit-code') -Value 'running'
$process = Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'), '-Worker') -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeDir 'styles.stdout.log') -RedirectStandardError (Join-Path $runtimeDir 'styles.stderr.log') -PassThru
@{ pid = $process.Id; startedAt = $process.StartTime.ToUniversalTime().ToString('o') } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtimeDir 'styles-process.json') -Encoding UTF8
Write-Output "Style checks started (PID $($process.Id)). Read .runtime/styles.exit-code for the result."
