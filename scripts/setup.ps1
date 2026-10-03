[CmdletBinding()]
param(
    [string]$BasePython,
    [string]$ManimPython,
    [string]$TtsPython,
    [string]$ModelDirectory,
    [string]$RuntimePath,
    [string]$FFmpeg,
    [string]$TexBin,
    [string]$Font = 'Microsoft YaHei',
    [ValidatePattern('^z[fm]_\d{3}$')][string]$Voice = 'zm_010',
    [ValidateRange(0.6, 1.4)][double]$Speed = 0.95,
    [switch]$Reconfigure
)

$ErrorActionPreference = 'Stop'
$skillRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)

function Invoke-Python {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Python 步骤失败，退出码：$LASTEXITCODE" }
}

function Find-BasePython {
    $probe = 'import sys; sys.exit(1) if not ((3,11) <= sys.version_info[:2] <= (3,12)) else print(sys.executable)'
    $candidateCommands = @()
    if ($BasePython) { $candidateCommands += ,@($BasePython) }
    else {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            $candidateCommands += ,@('py', '-3.12')
            $candidateCommands += ,@('py', '-3.11')
        }
        if (Get-Command python -ErrorAction SilentlyContinue) { $candidateCommands += ,@('python') }
    }
    $savedPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        foreach ($candidate in $candidateCommands) {
            $command = $candidate[0]
            $prefix = @($candidate | Select-Object -Skip 1)
            $result = @(& $command @prefix -c $probe 2>$null)
            if ($LASTEXITCODE -eq 0 -and $result.Count -eq 1 -and (Test-Path -LiteralPath $result[0] -PathType Leaf)) {
                return [string]$result[0]
            }
        }
    }
    finally { $ErrorActionPreference = $savedPreference }
    throw '需要 Python 3.11 或 3.12。安装后重试，或用 -BasePython 指定它的 python.exe 路径。'
}

if (-not $RuntimePath) {
    $RuntimePath = if ($env:EXPLAINER_RUNTIME) { $env:EXPLAINER_RUNTIME } else { Join-Path $skillRoot 'runtime.local.json' }
}
$RuntimePath = [IO.Path]::GetFullPath($RuntimePath)

if ((Test-Path -LiteralPath $RuntimePath -PathType Leaf) -and -not $Reconfigure) {
    # 先读取并验证已有配置；不更换环境，不重装依赖，不重新下载模型。
    $existing = Get-Content -LiteralPath $RuntimePath -Raw -Encoding UTF8 | ConvertFrom-Json
    $checker = [string]$existing.python
    if (-not [IO.Path]::IsPathRooted($checker)) { $checker = Join-Path (Split-Path -Parent $RuntimePath) $checker }
    if (-not (Test-Path -LiteralPath $checker -PathType Leaf)) {
        throw '已有配置中的 Python 路径失效。恢复环境路径，或添加 -Reconfigure 重新配置。'
    }
    Invoke-Python -Executable $checker -Arguments @((Join-Path $PSScriptRoot 'init_project.py'), '--runtime', $RuntimePath, '--check')
    Write-Output '已有环境与模型路径可用；无需重新安装。'
    return
}

foreach ($providedPython in @($ManimPython, $TtsPython)) {
    if ($providedPython -and -not (Test-Path -LiteralPath $providedPython -PathType Leaf)) {
        throw "指定的 Python 不存在：$providedPython"
    }
}

$base = if (-not $ManimPython -or -not $TtsPython) { Find-BasePython } else { $ManimPython }

if (-not $ManimPython) {
    $environment = Join-Path $skillRoot '.venv-manim'
    $ManimPython = Join-Path $environment 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $ManimPython -PathType Leaf)) {
        Invoke-Python -Executable $base -Arguments @('-m', 'venv', $environment)
    }
    Invoke-Python -Executable $ManimPython -Arguments @('-m', 'pip', 'install', '-r', (Join-Path $skillRoot 'requirements-manim.txt'))
}

if (-not $TtsPython) {
    $environment = Join-Path $skillRoot '.venv-kokoro'
    $TtsPython = Join-Path $environment 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $TtsPython -PathType Leaf)) {
        Invoke-Python -Executable $base -Arguments @('-m', 'venv', $environment)
    }
    Invoke-Python -Executable $TtsPython -Arguments @('-m', 'pip', 'install', '--upgrade', 'pip')
    Invoke-Python -Executable $TtsPython -Arguments @('-m', 'pip', 'install', 'torch==2.10.0', '--index-url', 'https://download.pytorch.org/whl/cpu')
    Invoke-Python -Executable $TtsPython -Arguments @('-m', 'pip', 'install', '-r', (Join-Path $skillRoot 'requirements-kokoro.txt'))
}

if (-not $ModelDirectory) { $ModelDirectory = Join-Path $skillRoot 'models\kokoro-zh' }
Write-Output '检查中文模型和两个音色。首次下载约 328 MB；有效文件会直接复用。'
& (Join-Path $PSScriptRoot 'download_kokoro.ps1') -ModelDirectory $ModelDirectory

$arguments = @(
    (Join-Path $PSScriptRoot 'configure_runtime.py'),
    '--manim-python', $ManimPython, '--tts-python', $TtsPython,
    '--model-directory', $ModelDirectory, '--output', $RuntimePath,
    '--font', $Font, '--voice', $Voice, '--speed', $Speed.ToString([Globalization.CultureInfo]::InvariantCulture)
)
if ($FFmpeg) { $arguments += @('--ffmpeg', $FFmpeg) }
if ($TexBin) { $arguments += @('--tex-bin', $TexBin) }
if ($Reconfigure) { $arguments += '--force' }
Invoke-Python -Executable $base -Arguments $arguments

$latex = if ($TexBin) { Test-Path -LiteralPath (Join-Path $TexBin 'latex.exe') -PathType Leaf } else { [bool](Get-Command latex -ErrorAction SilentlyContinue) }
$dvisvgm = if ($TexBin) { Test-Path -LiteralPath (Join-Path $TexBin 'dvisvgm.exe') -PathType Leaf } else { [bool](Get-Command dvisvgm -ErrorAction SilentlyContinue) }
if (-not $latex -or -not $dvisvgm) {
    Write-Warning '配音与动画环境已配置。附带导数示例还需要 TeX；可让 Codex 改用 Text 和几何图形。此脚本不安装 TeX。'
}
Write-Output '初始化完成。以后可以直接在 Codex 中调用 $explainer-video 制作视频。'
