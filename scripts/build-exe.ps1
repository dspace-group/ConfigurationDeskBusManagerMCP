<#
.SYNOPSIS
Builds and validates the ConfigurationDesk MCP Windows executable.

.DESCRIPTION
Builds a one-file console executable with PyInstaller, verifies that its version
and tool list match the source server, and writes a SHA-256 checksum.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$DistPath = Join-Path $RepoRoot "dist"
$WorkPath = Join-Path $RepoRoot "build\pyinstaller"
$ExePath = Join-Path $DistPath "configurationdesk-mcp.exe"
$ChecksumPath = Join-Path $DistPath "configurationdesk-mcp.exe.sha256"
$LicenseBundlePath = Join-Path $DistPath "configurationdesk-mcp-third-party-licenses.zip"

function Get-ServerVersion {
    $manifestPath = Join-Path $RepoRoot "ConfigurationDeskMCP\pyproject.toml"
    $versionLine = Get-Content -LiteralPath $manifestPath | Where-Object {
        $_ -match '^version\s*=\s*"[^"]+"\s*$'
    } | Select-Object -First 1
    $match = [regex]::Match($versionLine, '"([^"]+)"')
    if (-not $match.Success) {
        throw "Could not read the server version from $manifestPath."
    }
    return $match.Groups[1].Value
}

    Remove-Item -LiteralPath $DistPath -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $WorkPath -Recurse -Force -ErrorAction SilentlyContinue

    Push-Location $RepoRoot
    try {
        $expectedVersion = Get-ServerVersion
        $sourceTools = @(& uv run --frozen configurationdesk-mcp --list-tools)
        if ($LASTEXITCODE -ne 0) {
            throw "Could not list tools from the source server."
        }

        & uv run --frozen --group build pyinstaller packaging\pyinstaller.spec --noconfirm --clean `
            --distpath $DistPath --workpath $WorkPath
        if ($LASTEXITCODE -ne 0) {
            throw "PyInstaller failed."
        }

        if (-not (Test-Path -LiteralPath $ExePath)) {
            throw "Expected executable was not produced at $ExePath."
        }

        & $ExePath --help | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "The executable help command failed."
        }

        $actualVersion = (& $ExePath --version).Trim()
        if ($LASTEXITCODE -ne 0 -or $actualVersion -ne $expectedVersion) {
            throw "Executable version '$actualVersion' does not match '$expectedVersion'."
        }

        $executableTools = @(& $ExePath --list-tools)
        if ($LASTEXITCODE -ne 0) {
            throw "Could not list tools from the executable."
        }

        $difference = Compare-Object ($sourceTools | Sort-Object) ($executableTools | Sort-Object)
        if ($difference) {
            throw "The executable tool list does not match the source server."
        }

        & uv run --frozen --group build python scripts\bundle-third-party-licenses.py $LicenseBundlePath --notice THIRD-PARTY-NOTICES.md
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $LicenseBundlePath)) {
            throw "Could not create the third-party license bundle."
        }

        $hash = (Get-FileHash -LiteralPath $ExePath -Algorithm SHA256).Hash
        "$hash  $(Split-Path -Leaf $ExePath)" | Set-Content -LiteralPath $ChecksumPath -Encoding ascii

        Write-Host "Built $ExePath" -ForegroundColor Green
        Write-Host "SHA-256 written to $ChecksumPath" -ForegroundColor Green
        Write-Host "Third-party licenses written to $LicenseBundlePath" -ForegroundColor Green
    } finally {
        Pop-Location
    }
