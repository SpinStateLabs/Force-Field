<#
.SYNOPSIS
    FIELD Skill Installer for Windows — Spin State Labs

.DESCRIPTION
    Idempotent installer for the FIELD Claude Code skill + /field command.
    Skill and command files are refreshed on every run (so updates apply).
    The state file (~/.claude/state/field.json) is CREATE-ONLY — your toggles
    and last-audit timestamp are never overwritten.

.PARAMETER Level
    Install scope:
      'user'    (default) -> %USERPROFILE%\.claude\
      'project'           -> .\.claude\

.EXAMPLE
    .\install.ps1
    Installs at user level (all projects).

.EXAMPLE
    .\install.ps1 -Level project
    Installs into the current directory's .claude\.

.NOTES
    Requires PowerShell 5.1+ (ships with Windows 10/11).
    If execution policy blocks the script:
        Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
    or:
        powershell -ExecutionPolicy Bypass -File .\install.ps1
#>

[CmdletBinding()]
param(
    [Parameter(Position=0)]
    [ValidateSet('user','project')]
    [string]$Level = 'user'
)

$ErrorActionPreference = 'Stop'

# Resolve the plugin directory (this script's location)
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Definition
$SkillSrc   = Join-Path $ScriptDir 'skills\field'
$CommandSrc = Join-Path $ScriptDir 'commands\field.md'

# Determine target root
if ($Level -eq 'user') {
    $Root = Join-Path $env:USERPROFILE '.claude'
} else {
    $Root = Join-Path (Get-Location).Path '.claude'
}

$SkillDir   = Join-Path $Root 'skills\field'
$CmdDir     = Join-Path $Root 'commands'
$StateDir   = Join-Path $Root 'state'
$StateFile  = Join-Path $StateDir 'field.json'

Write-Host ''
Write-Host 'FIELD Skill Installer (Windows)' -ForegroundColor Cyan
Write-Host "  Source: $ScriptDir"
Write-Host "  Target: $Root"
Write-Host ''

New-Item -ItemType Directory -Force -Path $SkillDir              | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $SkillDir 'templates') | Out-Null
New-Item -ItemType Directory -Force -Path $CmdDir               | Out-Null
New-Item -ItemType Directory -Force -Path $StateDir            | Out-Null

# Refresh skill files (overwrite so updates apply)
function Copy-Refresh {
    param([string]$Source, [string]$Destination)
    if (-not (Test-Path -Path $Source)) {
        Write-Host "  [warn] source missing: $Source" -ForegroundColor Yellow
        return
    }
    Copy-Item -Path $Source -Destination $Destination -Force
    Write-Host "  [ok]   $Destination" -ForegroundColor Green
}

Copy-Refresh -Source (Join-Path $SkillSrc 'SKILL.md')             -Destination (Join-Path $SkillDir 'SKILL.md')
Copy-Refresh -Source (Join-Path $SkillSrc 'framework.md')         -Destination (Join-Path $SkillDir 'framework.md')
Copy-Refresh -Source (Join-Path $SkillSrc 'manifest-schema.json') -Destination (Join-Path $SkillDir 'manifest-schema.json')
Copy-Refresh -Source (Join-Path $SkillSrc 'field-defaults.json')  -Destination (Join-Path $SkillDir 'field-defaults.json')

Get-ChildItem -Path (Join-Path $SkillSrc 'templates') -Filter '*.yaml' | ForEach-Object {
    Copy-Refresh -Source $_.FullName -Destination (Join-Path $SkillDir "templates\$($_.Name)")
}

# Install the /field command at the discoverable user/project command path
Copy-Refresh -Source $CommandSrc -Destination (Join-Path $CmdDir 'field.md')

# Seed state — CREATE ONLY, never overwrite
if (Test-Path -Path $StateFile) {
    Write-Host "  [skip] $StateFile already exists (state preserved)"
} else {
    Copy-Item -Path (Join-Path $SkillSrc 'field-defaults.json') -Destination $StateFile -Force
    Write-Host "  [ok]   $StateFile (seeded from defaults)" -ForegroundColor Green
}

Write-Host ''
Write-Host 'Done.' -ForegroundColor Green
Write-Host 'Test with:  /field'
Write-Host 'Bootstrap a manifest:  /field init financial-agent'
Write-Host ''
