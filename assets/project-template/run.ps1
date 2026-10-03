[CmdletBinding()]
param([switch]$Draft, [switch]$AudioOnly, [string]$AudioManifest)
$ErrorActionPreference = 'Stop'
$tools = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'tools.json') -Encoding UTF8 -Raw | ConvertFrom-Json
$python = [string]$tools.python
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'Manim Python 路径失效，请恢复 tools.json 中的环境路径。'
}
$env:PYTHONIOENCODING = 'utf-8'
$arguments = @((Join-Path $PSScriptRoot 'run.py'))
if ($Draft) { $arguments += '--draft' }
if ($AudioOnly) { $arguments += '--audio-only' }
if ($AudioManifest) { $arguments += @('--audio-manifest', $AudioManifest) }
& $python @arguments
if ($LASTEXITCODE -ne 0) { throw "视频制作失败，退出码：$LASTEXITCODE" }
