[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$ModelDirectory)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$modelRoot = [IO.Path]::GetFullPath($ModelDirectory)
$null = New-Item -ItemType Directory -Path $modelRoot -Force
$revision = '01e7505bd6a7a2ac4975463114c3a7650a9f7218'
$files = @(
    @{ name = 'config.json'; size = 3228; sha = 'bc333efa5ce4ceff433c8c8e5d027a1eca0166001e4e4a62bea2d26ff7a46890' },
    @{ name = 'kokoro-v1_1-zh.pth'; size = 327247856; sha = 'b1d8410fa44dfb5c15471fd6c4225ea6b4e9ac7fa03c98e8bea47a9928476e2b' },
    @{ name = 'voices/zf_001.pt'; size = 523331; sha = '9bdc9a87e13e9bb1ea3e7803259c2ecbfebaeeb2ff80b5d0c76df1a464c1c962' },
    @{ name = 'voices/zm_010.pt'; size = 523331; sha = 'd2eeba86192eee269f600ca6821038034abd017532a1fe68ff7b0e86c2983b2a' }
)
foreach ($asset in $files) {
    $path = Join-Path $modelRoot $asset.name
    $null = New-Item -ItemType Directory -Path (Split-Path $path -Parent) -Force
    $valid = (Test-Path -LiteralPath $path -PathType Leaf) -and ((Get-Item -LiteralPath $path).Length -eq $asset.size)
    if ($valid -and $asset.sha) { $valid = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -eq $asset.sha }
    if (-not $valid) {
        Write-Output "Downloading $($asset.name) ($([Math]::Round($asset.size / 1MB, 1)) MiB)"
        $temporary = "$path.part"
        $url = "https://huggingface.co/hexgrad/Kokoro-82M-v1.1-zh/resolve/$revision/$($asset.name)"
        Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $temporary -TimeoutSec 600
        if ((Get-Item -LiteralPath $temporary).Length -ne $asset.size) { throw "Incomplete download: $($asset.name)" }
        if ($asset.sha -and (Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash -ne $asset.sha) { throw "Hash mismatch: $($asset.name)" }
        Move-Item -LiteralPath $temporary -Destination $path -Force
    }
}
$manifest = @{ model = 'hexgrad/Kokoro-82M-v1.1-zh'; revision = $revision; files = $files }
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $modelRoot 'download-manifest.json') -Encoding utf8
Write-Output 'Kokoro Chinese weights and two voices ready.'
