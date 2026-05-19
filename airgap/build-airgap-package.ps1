[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$Output = "dist\airgap",
    [Parameter(Mandatory = $false)]
    [string]$Name,
    [Parameter(Mandatory = $false)]
    [switch]$IncludeReader,
    [Parameter(Mandatory = $false)]
    [switch]$Json
)

$root = Split-Path -Parent $PSScriptRoot
$argsList = @(
    (Join-Path $PSScriptRoot "build_airgap_package.py"),
    "--root", $root,
    "--output", (Join-Path $root $Output)
)
if ($Name) {
    $argsList += @("--name", $Name)
}
if ($IncludeReader) {
    $argsList += "--include-reader"
}
if ($Json) {
    $argsList += "--json"
}

python @argsList
exit $LASTEXITCODE
