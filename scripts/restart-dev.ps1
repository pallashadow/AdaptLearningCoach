$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$pythonPath = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonPath)) {
  throw ".venv is missing or broken: $pythonPath"
}

function Stop-ByPort {
  param([int[]]$Ports)

  foreach ($port in $Ports) {
    $lines = netstat -ano | Select-String ":$port\s+.*LISTENING"
    foreach ($line in $lines) {
      $parts = ($line.ToString() -split "\s+") | Where-Object { $_ -ne "" }
      if ($parts.Count -lt 5) {
        continue
      }
      $procId = $parts[-1]
      if ($procId -match "^\d+$") {
        cmd /c "taskkill /PID $procId /F" | Out-Null
      }
    }
  }
}

function Stop-ByProcessPattern {
  param([string]$RepoRootPath)

  $escapedRepoRoot = [Regex]::Escape($RepoRootPath)
  $candidates = Get-CimInstance Win32_Process | Where-Object {
    ($_.Name -match "^(python|node|npm|npm\.cmd)(\.exe)?$") -and
    (
      $_.CommandLine -match $escapedRepoRoot -or
      $_.CommandLine -match "uvicorn main:app" -or
      $_.CommandLine -match "vite"
    )
  }

  foreach ($proc in $candidates) {
    $procId = [string]$proc.ProcessId
    if ($procId -match "^\d+$") {
      cmd /c "taskkill /PID $procId /F" | Out-Null
    }
  }
}

Stop-ByPort -Ports @(8001, 5173, 5174, 5175)
Stop-ByProcessPattern -RepoRootPath $repoRoot
Start-Sleep -Seconds 1

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backendOut = Join-Path $repoRoot "uvicorn.out.$timestamp.log"
$backendErr = Join-Path $repoRoot "uvicorn.err.$timestamp.log"
$frontendOut = Join-Path $repoRoot "frontend\vite.out.$timestamp.log"
$frontendErr = Join-Path $repoRoot "frontend\vite.err.$timestamp.log"

$backendProc = Start-Process `
  -FilePath $pythonPath `
  -ArgumentList "-m uvicorn main:app --host 127.0.0.1 --port 8001 --reload" `
  -WorkingDirectory $repoRoot `
  -RedirectStandardOutput $backendOut `
  -RedirectStandardError $backendErr `
  -PassThru

$frontendProc = Start-Process `
  -FilePath "npm.cmd" `
  -ArgumentList "run dev" `
  -WorkingDirectory (Join-Path $repoRoot "frontend") `
  -RedirectStandardOutput $frontendOut `
  -RedirectStandardError $frontendErr `
  -PassThru

Start-Sleep -Seconds 3

Write-Output "Backend PID: $($backendProc.Id)"
Write-Output "Frontend PID: $($frontendProc.Id)"
Write-Output "Backend URL: http://127.0.0.1:8001"
Write-Output "Frontend URL: http://127.0.0.1:5173"
Write-Output "Logs:"
Write-Output "  $backendOut"
Write-Output "  $backendErr"
Write-Output "  $frontendOut"
Write-Output "  $frontendErr"
