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
    for ($attempt = 0; $attempt -lt 3; $attempt++) {
      $procIds = netstat -ano |
        Select-String ":$port\s+.*LISTENING" |
        ForEach-Object {
          $parts = ($_.ToString() -split "\s+") | Where-Object { $_ -ne "" }
          if ($parts.Count -ge 5) { $parts[-1] } else { $null }
        } |
        Where-Object { $_ -match "^\d+$" } |
        Sort-Object -Unique

      if (-not $procIds -or $procIds.Count -eq 0) {
        break
      }

      foreach ($procId in $procIds) {
        cmd /c "taskkill /PID $procId /F" | Out-Null
      }

      Start-Sleep -Milliseconds 150
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

function Test-PortListening {
  param([int]$Port)

  $line = netstat -ano | Select-String ":$Port\s+.*LISTENING" | Select-Object -First 1
  return $null -ne $line
}

function Wait-ForPortListening {
  param(
    [int]$Port,
    [int]$TimeoutMs = 8000,
    [int]$PollIntervalMs = 200
  )

  $deadline = (Get-Date).AddMilliseconds($TimeoutMs)
  while ((Get-Date) -lt $deadline) {
    if (Test-PortListening -Port $Port) {
      return $true
    }
    Start-Sleep -Milliseconds $PollIntervalMs
  }
  return $false
}

Stop-ByPort -Ports @(8001, 5173, 5174, 5175)
Stop-ByProcessPattern -RepoRootPath $repoRoot

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logsDir = Join-Path $repoRoot "logs"
if (-not (Test-Path $logsDir)) {
  New-Item -ItemType Directory -Path $logsDir | Out-Null
}

$backendOut = Join-Path $logsDir "uvicorn.out.$timestamp.log"
$backendErr = Join-Path $logsDir "uvicorn.err.$timestamp.log"
$frontendOut = Join-Path $logsDir "vite.out.$timestamp.log"
$frontendErr = Join-Path $logsDir "vite.err.$timestamp.log"

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

$backendReady = Wait-ForPortListening -Port 8001
$frontendReady = Wait-ForPortListening -Port 5173

Write-Output "Backend PID: $($backendProc.Id)"
Write-Output "Frontend PID: $($frontendProc.Id)"
Write-Output "Backend URL: http://127.0.0.1:8001"
Write-Output "Frontend URL: http://127.0.0.1:5173"
Write-Output "Backend Ready: $backendReady"
Write-Output "Frontend Ready: $frontendReady"
Write-Output "Logs:"
Write-Output "  $backendOut"
Write-Output "  $backendErr"
Write-Output "  $frontendOut"
Write-Output "  $frontendErr"
