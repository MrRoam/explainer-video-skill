[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$LessonPath,
    [Parameter(Mandatory = $true)][string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Add-Type -AssemblyName System.Speech
$lesson = Get-Content -LiteralPath $LessonPath -Encoding UTF8 -Raw | ConvertFrom-Json
$null = New-Item -ItemType Directory -Path $OutputDirectory -Force
$speech = New-Object System.Speech.Synthesis.SpeechSynthesizer
$sha = [System.Security.Cryptography.SHA256]::Create()
$rows = [System.Collections.Generic.List[object]]::new()
try {
    $speech.SelectVoice([string]$lesson.voice)
    $speech.Rate = [int]$lesson.speech_rate
    $format = [System.Speech.AudioFormat.SpeechAudioFormatInfo]::new(
        24000,
        [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
        [System.Speech.AudioFormat.AudioChannel]::Mono
    )
    foreach ($beat in $lesson.beats) {
        if ([string]$beat.id -notmatch '^[a-z][a-z0-9_]*$') {
            throw "Invalid beat id: $($beat.id)"
        }
        $cacheKey = "$($speech.Voice.Name)|$($speech.Rate)|24000|$($beat.text)"
        $hash = [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($cacheKey))).Replace('-', '').Substring(0, 12)
        $audioPath = Join-Path $OutputDirectory "$($beat.id)-$hash.wav"
        if (-not (Test-Path -LiteralPath $audioPath)) {
            $speech.SetOutputToWaveFile($audioPath, $format)
            $speech.Speak([string]$beat.text)
            $speech.SetOutputToNull()
        }
        $rows.Add([pscustomobject]@{id = $beat.id; path = $audioPath; voice = $speech.Voice.Name})
    }
    $json = ConvertTo-Json -InputObject @($rows.ToArray()) -Depth 5
    [IO.File]::WriteAllText((Join-Path $OutputDirectory 'narration.json'), $json, [Text.UTF8Encoding]::new($false))
    Write-Output "Chinese narration ready: $($rows.Count) segments, $($speech.Voice.Name)"
}
finally {
    $sha.Dispose()
    $speech.Dispose()
}
