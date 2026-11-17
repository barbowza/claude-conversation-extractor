# claude-convos: run the Claude Conversation Extractor web UI (claude-web) in the background
# and open it in the default browser. Windows only (macOS/Linux use scripts/launchers/claude-convos).
#
# Usage: claude-convos [start|stop|restart|status|log|help]
# Port: 8765. Override with CLAUDE_CONVOS_PORT.
# CLAUDE_CONVOS_NO_BROWSER=1 skips opening the page (for tests).
# Exit codes: 0 ok/running, 1 problem or port taken, 2 unknown command, 3 not running (status only).
#
# Setup: docs/user/LAUNCHER.md. Put only a .cmd shim on PATH that calls this file by its full path.
# claude-web comes from `uv tool install .` run in the repo.

param([string]$Command = 'start')

$ErrorActionPreference = 'Stop'
$Port     = if ($env:CLAUDE_CONVOS_PORT) { [int]$env:CLAUDE_CONVOS_PORT } else { 8765 }
$Url      = "http://localhost:$Port/"
$StateDir = Join-Path $env:LOCALAPPDATA 'claude-convos'
$PidFile  = Join-Path $StateDir 'server.pid'
$LogFile  = Join-Path $StateDir 'server.log'
$ErrFile  = Join-Path $StateDir 'server.err.log'
$AppDir   = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path

function Get-ServerExe {
    $cmd = Get-Command claude-web.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd) { return $cmd.Source }
    $dirs = @()
    if ($env:UV_TOOL_BIN_DIR) { $dirs += $env:UV_TOOL_BIN_DIR }
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        $d = (& uv tool dir --bin 2>$null)
        if ($d) { $dirs += $d.Trim() }
    }
    $dirs += Join-Path $env:USERPROFILE '.local\bin'
    foreach ($d in $dirs) {
        $p = Join-Path $d 'claude-web.exe'
        if (Test-Path $p) { return $p }
    }
    return $null
}

function Test-Up {
    try {
        # Check on 127.0.0.1: "localhost" tries ::1 first and stalls ~2s (server listens on IPv4 only).
        $null = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        return $true
    } catch {
        # Any HTTP answer (even an error status) means something is listening.
        return [bool]$_.Exception.Response
    }
}

function Get-ProcInfo([int]$Id) {
    Get-CimInstance Win32_Process -Filter "ProcessId=$Id" -ErrorAction SilentlyContinue
}

# True if this process, or its parent, is claude-web (uv's claude-web.exe starts a python child).
function Test-IsClaudeWeb([int]$Id) {
    $p = Get-ProcInfo $Id
    for ($i = 0; $p -and $i -lt 2; $i++) {
        if ("$($p.CommandLine) $($p.ExecutablePath)" -match 'claude-web') { return $true }
        $p = Get-ProcInfo $p.ParentProcessId
    }
    return $false
}

# Returns the PID of our server, or $null.
function Get-ServerPid {
    if (Test-Path $PidFile) {
        $saved = [int](Get-Content $PidFile -Raw).Trim()
        if ((Get-Process -Id $saved -ErrorAction SilentlyContinue) -and (Test-IsClaudeWeb $saved)) { return $saved }
    }
    $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($l in $listeners) {
        if (Test-IsClaudeWeb $l) {
            # Prefer the top claude-web process (the launcher) so stop kills the whole tree.
            $parent = (Get-ProcInfo $l).ParentProcessId
            if ($parent -and (Test-IsClaudeWeb $parent) -and ((Get-ProcInfo $parent).CommandLine -match 'claude-web')) { return [int]$parent }
            return [int]$l
        }
    }
    return $null
}

function Test-PortInUse {
    [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Open-Page {
    if ($env:CLAUDE_CONVOS_NO_BROWSER) { return }
    Start-Process $Url
}

function Start-Server {
    if ((Test-Up) -or (Test-PortInUse)) {
        $sp = Get-ServerPid
        if (-not $sp) {
            Write-Host "Port $Port is in use by another program, not claude-web."
            Write-Host "Stop that program, or pick another port:  `$env:CLAUDE_CONVOS_PORT = 8766"
            exit 1
        }
        Write-Host "Server already running at $Url (pid $sp)"
        Open-Page
        return
    }
    $exe = Get-ServerExe
    if (-not $exe) {
        Write-Host "Cannot find claude-web.exe. Install it with:"
        Write-Host "  cd `"$AppDir`"; uv tool install . --reinstall"
        exit 1
    }
    New-Item -ItemType Directory -Force $StateDir | Out-Null
    $env:PYTHONUNBUFFERED = '1'   # so the log fills as the server writes
    $proc = Start-Process -FilePath $exe -ArgumentList '--port', $Port, '--no-browser' `
        -WorkingDirectory $StateDir -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $LogFile -RedirectStandardError $ErrFile
    Set-Content -Path $PidFile -Value $proc.Id -NoNewline

    $deadline = (Get-Date).AddSeconds(10)
    while ((Get-Date) -lt $deadline) {
        if (Test-Up) {
            Write-Host "Server started at $Url (pid $($proc.Id))"
            Open-Page
            return
        }
        if ($proc.HasExited) { break }
        Start-Sleep -Milliseconds 300
    }
    Write-Host "Server did not start. Last log lines:"
    foreach ($f in $LogFile, $ErrFile) { if (Test-Path $f) { Get-Content $f -Tail 20 } }
    Stop-Server -Quiet
    exit 1
}

function Stop-Server([switch]$Quiet) {
    $sp = Get-ServerPid
    if (-not $sp) {
        if (-not $Quiet) { Write-Host 'Server is not running.' }
        Remove-Item $PidFile -ErrorAction SilentlyContinue
        return
    }
    # /T kills the python child too.
    & taskkill.exe /PID $sp /T /F 2>&1 | Out-Null
    $deadline = (Get-Date).AddSeconds(5)
    while ((Get-Date) -lt $deadline -and (Get-ServerPid)) { Start-Sleep -Milliseconds 200 }
    Remove-Item $PidFile -ErrorAction SilentlyContinue
    if (Get-ServerPid) { Write-Host "Could not stop server (pid $sp)."; exit 1 }
    if (-not $Quiet) { Write-Host "Server stopped (pid $sp)." }
}

function Show-Status {
    $sp = Get-ServerPid
    if ($sp -and (Test-Up)) { Write-Host "Running at $Url (pid $sp)"; return }
    if ($sp) { Write-Host "Process $sp exists but $Url does not answer."; exit 1 }
    if (Test-PortInUse) { Write-Host "Not running. Port $Port is in use by another program."; exit 1 }
    Write-Host 'Not running.'
    exit 3
}

function Show-Log {
    $found = $false
    foreach ($f in $LogFile, $ErrFile) {
        if (Test-Path $f) { $found = $true; Write-Host "== $f"; Get-Content $f -Tail 50 }
    }
    if (-not $found) { Write-Host "No log yet ($LogFile)." }
}

function Show-Help {
    @"
claude-convos - Claude Conversation Extractor web UI ($Url)

  claude-convos            start the server in the background and open the page
  claude-convos start      same
  claude-convos stop       stop the server
  claude-convos restart    stop, then start
  claude-convos status     show if the server runs
  claude-convos log        show the end of the server log
  claude-convos help       show this help

Port: $Port. Override with CLAUDE_CONVOS_PORT.
State and log: $StateDir
Repo: $AppDir
"@ | Write-Host
}

switch ($Command.ToLower()) {
    'start'   { Start-Server }
    'stop'    { Stop-Server }
    'restart' { Stop-Server -Quiet; Start-Server }
    'status'  { Show-Status }
    'log'     { Show-Log }
    { $_ -in 'help', '-h', '--help', '/?' } { Show-Help }
    default   { Write-Host "Unknown command: $Command"; Show-Help; exit 2 }
}
