<#
.SYNOPSIS
Validates public-release content, source behavior, and optional executable output.

.DESCRIPTION
Runs deterministic checks for the sanitized public repository. It is suitable for
local handoff and GitHub Actions. Use -RequireCleanExport only before creating a
new Git repository; CI checkouts naturally contain .git and virtual environments.
#>

[CmdletBinding()]
param(
    [string]$ExpectedVersion,
    [string]$ExecutablePath,
    [switch]$SkipPackageBuild,
    [switch]$SkipCommandChecks,
    [switch]$RequireCleanExport
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

function Assert-Condition {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Get-PackageVersion {
    param([string]$ManifestPath)

    $versionLine = Get-Content -LiteralPath $ManifestPath | Where-Object {
        $_ -match '^version\s*=\s*"[^"]+"\s*$'
    } | Select-Object -First 1
    $match = [regex]::Match($versionLine, '"([^"]+)"')
    Assert-Condition $match.Success "Could not read version from $ManifestPath."
    return $match.Groups[1].Value
}

function Invoke-CheckedCommand {
    param(
        [string]$Description,
        [scriptblock]$Command
    )

    Write-Host "Validating: $Description" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE."
    }
}

Push-Location $RepoRoot
try {
    $serverManifest = Join-Path $RepoRoot "ConfigurationDeskMCP\pyproject.toml"
    $bridgeManifest = Join-Path $RepoRoot "configurationdesk_com_bridge\pyproject.toml"
    $serverVersion = Get-PackageVersion $serverManifest
    $bridgeVersion = Get-PackageVersion $bridgeManifest
    if (-not $ExpectedVersion) {
        $ExpectedVersion = $serverVersion
    }

    Assert-Condition ($serverVersion -eq $bridgeVersion) "Package versions do not match."
    Assert-Condition ($serverVersion -eq $ExpectedVersion) "Expected version $ExpectedVersion, found $serverVersion."

    $requiredFiles = @(
        "LICENSE",
        "THIRD-PARTY-NOTICES.md",
        "CHANGELOG.md",
        ".gitattributes",
        "AGENTS.md",
        "GOVERNANCE.md",
        "ConfigurationDeskMCP\README.md",
        "packaging\pyinstaller.spec",
        "scripts\bundle-third-party-licenses.py",
        "scripts\build-exe.ps1",
        "scripts\validate-release.ps1"
    )
    foreach ($relativePath in $requiredFiles) {
        Assert-Condition (Test-Path -LiteralPath (Join-Path $RepoRoot $relativePath)) "Missing required file: $relativePath"
    }

    $forbiddenPaths = @(
        ".agents",
        ".github\agents",
        ".vscode",
        "pip.ini",
        "test_assets",
        "docs\usecase",
        "ConfigurationDeskMCP\tests\live",
        "ConfigurationDeskMCP\tests\usecases",
        "ConfigurationDeskMCP\tests\test_usecase_parity.py"
    )
    if ($RequireCleanExport) {
        $forbiddenPaths += @(".git", ".venv", ".pytest_cache", ".ruff_cache", "build", "dist")
    }
    foreach ($relativePath in $forbiddenPaths) {
        Assert-Condition (-not (Test-Path -LiteralPath (Join-Path $RepoRoot $relativePath))) "Forbidden export path exists: $relativePath"
    }
    Assert-Condition (-not (Test-Path -LiteralPath (Join-Path $RepoRoot ".env"))) "A local .env file must not be included."

    $attributes = Get-Content -LiteralPath (Join-Path $RepoRoot ".gitattributes") -Raw
    Assert-Condition ($attributes -match '(?m)^\* text=auto\s*$') ".gitattributes must enable text normalization."

    $lockText = Get-Content -LiteralPath (Join-Path $RepoRoot "uv.lock") -Raw
    Assert-Condition ($lockText -notmatch 'private-package-registry|private-package-host\.invalid|private-development-label') "uv.lock contains an internal package host."

    $skipDirectories = @(".git", ".venv", "build", "dist", "__pycache__", ".pytest_cache", ".ruff_cache")
    $textExtensions = @(".md", ".py", ".toml", ".ps1", ".yml", ".yaml", ".json", ".ini", ".txt")
    $textFiles = Get-ChildItem -LiteralPath $RepoRoot -Recurse -File | Where-Object {
        $_.Extension -in $textExtensions -and
        $_.FullName -ne $PSCommandPath -and
        -not ($_.FullName -split "[\\/]" | Where-Object { $skipDirectories -contains $_ })
    }
    $forbiddenText = 'private-test-host|private-development-label|private-package-host\.invalid|docs/usecase|test_assets|tests/live|tests/usecases|PRIVATE_LIVE_TEST|@<MAINTAINER>|<SECURITY-CONTACT|<CONDUCT-CONTACT|C:[\\/]Users[\\/]LOCAL-USER'
    $contentMatches = @(Select-String -LiteralPath $textFiles.FullName -Pattern $forbiddenText -CaseSensitive:$false)
    if ($contentMatches.Count -gt 0) {
        $locations = $contentMatches | ForEach-Object { "$($_.Path):$($_.LineNumber)" }
        throw "Forbidden public-content references found: $($locations -join '; ')"
    }

    if (-not $SkipCommandChecks) {
        Invoke-CheckedCommand "dependency resolution" { uv lock }
        Invoke-CheckedCommand "Ruff lint" { uv run --frozen ruff check . }
        Invoke-CheckedCommand "Ruff format" { uv run --frozen ruff format --check . }
        Invoke-CheckedCommand "deterministic tests" { uv run --frozen pytest ConfigurationDeskMCP/tests }

        $sourceVersion = (& uv run --frozen configurationdesk-mcp --version).Trim()
        Assert-Condition ($sourceVersion -eq $ExpectedVersion) "Source CLI version $sourceVersion does not match $ExpectedVersion."
        $sourceTools = @(& uv run --frozen configurationdesk-mcp --list-tools)
        Assert-Condition ($sourceTools.Count -ge 75) "Source CLI registered fewer than 75 tools."
    } else {
        $sourceTools = @()
    }

    if (-not $SkipPackageBuild) {
        $packageOutput = Join-Path ([System.IO.Path]::GetTempPath()) "configurationdesk-mcp-package-build"
        Remove-Item -LiteralPath $packageOutput -Recurse -Force -ErrorAction SilentlyContinue
        New-Item -ItemType Directory -Path $packageOutput -Force | Out-Null
        Invoke-CheckedCommand "bridge package build" { uv build configurationdesk_com_bridge --out-dir $packageOutput }
        Invoke-CheckedCommand "server package build" { uv build ConfigurationDeskMCP --out-dir $packageOutput }
        Assert-Condition ((Get-ChildItem -LiteralPath $packageOutput -File).Count -ge 4) "Package builds did not produce expected artifacts."
    }

    if ($ExecutablePath) {
        $resolvedExecutable = (Resolve-Path -LiteralPath $ExecutablePath -ErrorAction Stop).Path
        $executableVersion = (& $resolvedExecutable --version).Trim()
        Assert-Condition ($executableVersion -eq $ExpectedVersion) "Executable version $executableVersion does not match $ExpectedVersion."
        $executableTools = @(& $resolvedExecutable --list-tools)
        Assert-Condition ($executableTools.Count -ge 75) "Executable registered fewer than 75 tools."
        if ($sourceTools.Count -gt 0) {
            Assert-Condition (-not (Compare-Object ($sourceTools | Sort-Object) ($executableTools | Sort-Object))) "Executable tool list does not match source tool list."
        }

        $checksumPath = "$resolvedExecutable.sha256"
        Assert-Condition (Test-Path -LiteralPath $checksumPath) "Missing executable checksum: $checksumPath"
        $expectedHash = (Get-Content -LiteralPath $checksumPath | Select-Object -First 1).Split()[0]
        $actualHash = (Get-FileHash -LiteralPath $resolvedExecutable -Algorithm SHA256).Hash
        Assert-Condition ($actualHash -eq $expectedHash) "Executable checksum does not match."

        $licenseBundlePath = Join-Path (Split-Path -Parent $resolvedExecutable) "configurationdesk-mcp-third-party-licenses.zip"
        Assert-Condition (Test-Path -LiteralPath $licenseBundlePath) "Missing third-party license bundle: $licenseBundlePath"
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $licenseBundle = [System.IO.Compression.ZipFile]::OpenRead($licenseBundlePath)
        try {
            $licenseIndexEntry = $licenseBundle.GetEntry("THIRD-PARTY-LICENSES/index.json")
            Assert-Condition ($null -ne $licenseIndexEntry) "Third-party license bundle has no package index."
            $licenseIndexReader = [System.IO.StreamReader]::new($licenseIndexEntry.Open())
            try {
                $licenseIndex = $licenseIndexReader.ReadToEnd() | ConvertFrom-Json
            } finally {
                $licenseIndexReader.Dispose()
            }
            Assert-Condition ($licenseIndex.packages.name -contains "pyinstaller") "Third-party license bundle lacks PyInstaller license material."
        } finally {
            $licenseBundle.Dispose()
        }

    }

    Write-Host "Release validation passed for version $ExpectedVersion." -ForegroundColor Green
} finally {
    Pop-Location
}
