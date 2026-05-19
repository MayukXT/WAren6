[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$Python = "python",
    [Parameter(Mandatory = $false)]
    [string]$Wheels = "wheels"
)

$root = Split-Path -Parent $PSScriptRoot
$wheelDir = Join-Path $root $Wheels
$requirements = Join-Path $root "requirements-lock.txt"

if (-not (Test-Path -LiteralPath $wheelDir -PathType Container)) {
    Write-Error "Wheel directory not found: $wheelDir"
    exit 1
}
if (-not (Test-Path -LiteralPath $requirements -PathType Leaf)) {
    Write-Error "Requirements file not found: $requirements"
    exit 1
}

& $Python -m pip install --no-index --find-links $wheelDir -r $requirements
exit $LASTEXITCODE
