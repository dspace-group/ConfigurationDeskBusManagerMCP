<#
.SYNOPSIS
    Launch the MCP Inspector against the ConfigurationDesk MCP Server.

.DESCRIPTION
    Starts the browser-based MCP Inspector (npx @modelcontextprotocol/inspector)
    and wires it to this server over stdio. The Inspector spawns the server as a
    child process; pressing Ctrl+C stops both.

    Requires Node.js 18+ (for npx) and either uv for a source checkout or a
    downloaded `configurationdesk-mcp.exe`.

.EXAMPLE
    .\scripts\inspect.ps1
    .\scripts\inspect.ps1 -ExecutablePath C:\path\to\configurationdesk-mcp.exe
#>

[CmdletBinding()]
param(
    [string]$ExecutablePath
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

# 1. Verify npx (Node.js) is available.
if (-not (Get-Command npx -ErrorAction SilentlyContinue)) {
    Write-Error "npx not found. Install Node.js 18+ from https://nodejs.org and retry."
    exit 1
}

# 2. Resolve the server command. An explicitly supplied executable takes
#    priority, followed by the development entry point and uv fallback.
if ($ExecutablePath) {
    $ServerCommand = (Resolve-Path -LiteralPath $ExecutablePath -ErrorAction Stop).Path
    $ServerArgs = @()
} else {
    $VenvExe = Join-Path $RepoRoot ".venv\Scripts\configurationdesk-mcp.exe"
    if (Test-Path $VenvExe) {
    $ServerCommand = $VenvExe
    $ServerArgs = @()
    } elseif (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Warning "venv entry point not found - using 'uv run configurationdesk-mcp' to create or update the environment."
    $ServerCommand = "uv"
    $ServerArgs = @("run", "configurationdesk-mcp")
    Set-Location $RepoRoot
    } else {
    Write-Error "Neither .venv entry point nor uv found. Install uv from https://astral.sh/uv and retry."
    exit 1
    }
}

# 3. Launch the Inspector. It opens http://localhost:6274 (default) in your browser.
Write-Host "Starting MCP Inspector for the ConfigurationDesk MCP Server..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the Inspector and the server." -ForegroundColor DarkGray
npx -y @modelcontextprotocol/inspector $ServerCommand @ServerArgs
