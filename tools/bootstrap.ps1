param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ScriptArgs
)

$ErrorActionPreference = "Stop"

$tempDir = Join-Path $env:TEMP "WAren6-$(Get-Random)"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

try {
    Write-Host "Downloading WAren6..." -ForegroundColor Cyan
    $zipPath = Join-Path $tempDir "waren6.zip"
    Invoke-WebRequest -Uri "https://github.com/MayukXT/WAren6/archive/refs/heads/main.zip" -OutFile $zipPath -UseBasicParsing

    Write-Host "Extracting WAren6..." -ForegroundColor Cyan
    Expand-Archive -Path $zipPath -DestinationPath $tempDir

    $scriptPath = Join-Path $tempDir "WAren6-main\waren6.ps1"
    
    if (Test-Path $scriptPath) {
        Write-Host "Running WAren6..." -ForegroundColor Cyan
        $ErrorActionPreference = "Continue"
        & $scriptPath @ScriptArgs
    } else {
        Write-Error "Could not find waren6.ps1 in the extracted archive."
    }
}
finally {
    if (Test-Path $tempDir) {
        Write-Host "Cleaning up temporary files..." -ForegroundColor Gray
        # Note: BouncyCastle.Cryptography.dll gets locked in the PowerShell process after Add-Type,
        # so it cannot be deleted until this PowerShell session exits. We ignore access errors.
        Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
