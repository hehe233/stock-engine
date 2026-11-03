$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $projectRoot '.runtime/dev-processes.json'
if (-not (Test-Path -LiteralPath $manifestPath)) {
    Write-Output 'No project process manifest found.'
    return
}

# Windows PowerShell 5.1 may emit a JSON array as one pipeline object. Wrapping the
# pipeline in @() adds another array level and turns entry.startedAt into an array.
$tracked = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$allProcesses = @(Get-CimInstance Win32_Process)
foreach ($entry in $tracked) {
    $process = Get-Process -Id $entry.pid -ErrorAction SilentlyContinue
    if (-not $process) { continue }
    $recordedStart = [DateTimeOffset]::Parse($entry.startedAt).UtcDateTime
    if ([Math]::Abs(($process.StartTime.ToUniversalTime() - $recordedStart).TotalSeconds) -gt 1) {
        Write-Warning "PID $($entry.pid) was reused; skipping it."
        continue
    }
    # Stop only this project's recorded process tree. Never kill every node/python process.
    $tree = [System.Collections.Generic.List[int]]::new()
    $tree.Add([int]$entry.pid)
    for ($index = 0; $index -lt $tree.Count; $index++) {
        foreach ($child in $allProcesses) {
            if ($child.ParentProcessId -eq $tree[$index]) { $tree.Add([int]$child.ProcessId) }
        }
    }
    for ($index = $tree.Count - 1; $index -ge 0; $index--) {
        Stop-Process -Id $tree[$index] -Force -ErrorAction SilentlyContinue
    }
    Write-Output "Stopped $($entry.name) process tree (root PID $($entry.pid))."
}
Remove-Item -LiteralPath $manifestPath
foreach ($port in @(8000, 8001, 5173)) {
    $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($listener) { Write-Warning "Port $port is still in use by PID $($listener.OwningProcess -join ', ')." }
    else { Write-Output "Port $port is free." }
}
