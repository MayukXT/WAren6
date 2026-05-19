[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$Output = "wheels"
)

$root = Split-Path -Parent $PSScriptRoot
$wheelDir = Join-Path $root $Output
New-Item -ItemType Directory -Force -Path $wheelDir | Out-Null

$requirementsPath = Join-Path $root "requirements-lock.txt"
$requirements = Get-Content $requirementsPath | Where-Object {
    $line = $_.Trim()
    $line -and -not $line.StartsWith("#")
}

foreach ($requirement in $requirements) {
    if ($requirement -eq "ccl_chromium_reader") {
        python -m pip wheel git+https://github.com/cclgroupltd/ccl_chromium_reader.git -w $wheelDir
    } else {
        python -m pip wheel $requirement -w $wheelDir
    }
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

exit 0
