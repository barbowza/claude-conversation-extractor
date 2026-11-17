# claude-convos launcher

`claude-convos` starts the web UI (`claude-web`) in the background and opens it in
your default browser. You can type it in any folder.

The steps below are written so that a person or an AI assistant can follow them after
a fresh clone. Do them in order. Each step has a check.

| System | Launcher file in this repo |
|---|---|
| macOS, Linux, WSL | `scripts/launchers/claude-convos` (bash) |
| Windows | `scripts/launchers/claude-convos.ps1` (PowerShell), called through a `.cmd` shim |

The launcher is not copied. A link (macOS/Linux) or a shim (Windows) points at the file
in the repo, so `git pull` updates it.

## Commands

| Command | What it does |
|---|---|
| `claude-convos` | Start the server (or reuse a running one) and open `http://localhost:8765/` |
| `claude-convos stop` | Stop the server |
| `claude-convos restart` | Stop, then start |
| `claude-convos status` | Show if the server runs |
| `claude-convos log` | Show the end of the server log |
| `claude-convos help` | Show help |

- Port: `8765`. To use another port, set `CLAUDE_CONVOS_PORT`.
- `CLAUDE_CONVOS_NO_BROWSER=1` stops the page from opening. Use it for tests.
- Exit codes: `0` ok or running, `1` problem or port taken by another program,
  `2` unknown command, `3` not running (`status` only).
- State and log: `~/.cache/claude-convos/` (macOS/Linux), `%LOCALAPPDATA%\claude-convos\` (Windows).

## Setup on macOS, Linux or WSL

Run every command from the root of the clone.

1. **Install uv** if `uv --version` fails.
   - macOS: `brew install uv`
   - Linux/WSL: `curl -LsSf https://astral.sh/uv/install.sh | sh`

   Check: `uv --version` prints a version.

2. **Install the tool.**

   ```bash
   uv tool install . --reinstall
   ```

   This puts `claude-web` (and the other `claude-*` commands) in uv's tool bin folder,
   `~/.local/bin` by default. If that folder is not on PATH, run `uv tool update-shell`
   and open a new terminal.

   Check: `command -v claude-web` prints a path.

3. **Pick a PATH folder for the launcher.** Use the user's personal scripts folder if
   it is already on PATH (for example `~/bin`). If not, use `~/.local/bin`.

   Check: `echo "$PATH" | tr : '\n'` lists the folder.

4. **Link the launcher** (replace `~/bin` with the folder from step 3).

   ```bash
   ln -sfn "$(pwd)/scripts/launchers/claude-convos" ~/bin/claude-convos
   ```

   If `~/bin/claude-convos` already exists as a normal file (an older copy), stop a
   running server with it first (`~/bin/claude-convos stop`), then make the link.

   Check: `ls -l ~/bin/claude-convos` shows `->` pointing into this repo.

5. **Test without opening the browser.**

   ```bash
   claude-convos status; echo $?                   # "Not running.", 3
   CLAUDE_CONVOS_NO_BROWSER=1 claude-convos | cat  # "Server started at ...". Must return, not hang.
   claude-convos status; echo $?                   # "Running at ...", 0
   CLAUDE_CONVOS_NO_BROWSER=1 claude-convos        # "Server already running ..."
   claude-convos stop                              # "Server stopped ..."
   ```

6. **Real run.** Type `claude-convos`. The page opens in the default browser.

## Setup on Windows

Run every command in PowerShell from the root of the clone.

1. **Install uv** if `uv --version` fails.

   ```powershell
   winget install --id=astral-sh.uv -e
   ```

   Open a new terminal. Check: `uv --version` prints a version.

2. **Install the tool.**

   ```powershell
   uv tool install . --reinstall
   ```

   This puts `claude-web.exe` in uv's tool bin folder, `%USERPROFILE%\.local\bin` by
   default. If that folder is not on PATH, run `uv tool update-shell` and open a new
   terminal.

   Check: `Get-Command claude-web.exe` finds it.

3. **Pick a PATH folder for the shim.** Use the user's personal scripts folder if it is
   already on the user PATH (for example `%USERPROFILE%\bin`). If not, use
   `%USERPROFILE%\.local\bin`.

   Check: `$env:Path -split ';'` lists the folder.

4. **Make the shim.** Put **only** a `.cmd` file in the PATH folder. Do not put a
   `claude-convos.ps1` there: PowerShell runs a `.ps1` on PATH before a `.cmd`, and the
   default execution policy can block it. If an older `claude-convos.ps1` or
   `claude-convos.cmd` is in the folder, run `claude-convos stop` first, then remove both.

   ```powershell
   $bin  = "$env:USERPROFILE\bin"    # the folder from step 3
   $repo = (Get-Location).Path
   Set-Content -Path "$bin\claude-convos.cmd" -Encoding ascii -Value `
     "@powershell -NoProfile -ExecutionPolicy Bypass -File `"$repo\scripts\launchers\claude-convos.ps1`" %*"
   ```

   The quotes around the path matter: the clone path can contain spaces.

   Check: `Get-Content "$bin\claude-convos.cmd"` shows the full path to the `.ps1`.

5. **Test without opening the browser.**

   ```powershell
   $env:CLAUDE_CONVOS_NO_BROWSER = '1'
   claude-convos status; $LASTEXITCODE    # "Not running.", 3
   claude-convos | Out-String             # "Server started at ...". Must return, not hang.
   claude-convos status; $LASTEXITCODE    # "Running at ...", 0
   claude-convos                          # "Server already running ..."
   claude-convos stop                     # "Server stopped ..."
   Remove-Item Env:CLAUDE_CONVOS_NO_BROWSER
   ```

   Also check the shim from `cmd.exe`. Type the two commands on separate lines: on one
   line joined with `&`, `%ERRORLEVEL%` expands too early and shows `0`.

   ```bat
   claude-convos status
   echo %ERRORLEVEL%
   ```

6. **Real run.** Type `claude-convos`. The page opens in the default browser.

## After `git pull`

The launcher updates by itself. The tool does not, so reinstall it:

```bash
claude-convos stop
uv tool install . --reinstall
```

On Windows, stop the server first: Windows locks `claude-web.exe` while it runs, and the
reinstall fails.

## Notes

- The up-check uses `127.0.0.1`, not `localhost`. The server listens on IPv4 only, and
  `localhost` can try IPv6 (`::1`) first and stall. The browser still opens `localhost`,
  because the server only accepts `localhost`, `127.0.0.1` and `::1` as host names.
- Windows: uv's `claude-web.exe` is a small launcher that starts a `python.exe` child, and
  the child owns the socket. So the script checks the parent process too, and `stop` uses
  `taskkill /T` to end the whole tree.
- The server starts with the state folder as its working folder, not the folder you are in.
- The server must not keep the caller's output open, or `claude-convos | ...` (and any AI
  tool that reads the output) waits until the server stops. Bash: the background subshell
  `exec`s the server with all three streams redirected. Windows: the server starts through
  WMI (`Win32_Process.Create`), because `Start-Process` lets it inherit the output handle.
- Windows PowerShell 5.1 reads the UTF-8 log as ANSI unless told, so `log` uses
  `Get-Content -Encoding UTF8`.
- If port 8765 is taken by another program, the launcher stops with an error. It never
  kills a process that is not `claude-web`.
