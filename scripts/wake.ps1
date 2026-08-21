# Headless seat wake wrapper (REMOVE-THE-GO). One wake = one loop pass.
# Launched by Task Scheduler; runnable by hand for a dry-run. The prompt is
# wake-prompt.md in the repo root - versioned, never an inline string here.
#
# Exit codes: 0 = loop completed, or a normal skip because the seat was
# already running - 1 = the engine exited nonzero, or a wrapper tripwire
# fired - 2 = could not even start (missing prompt/CLI). Every real failure
# leaves a WAKE-FAILURE file on Drive so silence is impossible. A SKIP is
# not a failure and deliberately leaves nothing on Drive.
#
# WAKE-LOOP-STOP-THE-BLEED (2026-08-21): stderr tail on engine failures;
# per-seat exponential backoff after consecutive identical failures; default
# engine is codex (GROK/CODEX preferred, Claude fallback) per founder decision.
param(
    [string]$RepoRoot = "C:\ProjectOS-AI",
    [string]$Seat = "PROJECTOS",
    [string]$ReportsDir = "G:\My Drive\AGENT-REPORTS",
    [string]$PromptFile = "wake-prompt.md",
    [ValidateSet("claude", "codex")]
    [string]$Engine = "codex"
)

$ErrorActionPreference = "Stop"
Set-Location $RepoRoot

$StateDir = Join-Path $env:USERPROFILE ".projectos"
if (-not (Test-Path $StateDir)) { New-Item -ItemType Directory -Force $StateDir | Out-Null }
$LockFile = Join-Path $StateDir "wake-$Seat.lock"
$LocalLog = Join-Path $StateDir "wake-$Seat.log"
$UsageLog = Join-Path $StateDir "wake-usage.log"
$BackoffFile = Join-Path $StateDir "wake-$Seat.backoff.json"
$StderrFile = Join-Path $StateDir "wake-$Seat.stderr"
$script:HoldsLock = $false

$BackoffBaseMinutes = 20
$BackoffCeilingMinutes = 360

function Write-LocalLog([string]$line) {
    $when = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    Add-Content -Path $LocalLog -Value "$when [$Seat] $line" -Encoding utf8
}

function Write-WakeFailure([string]$why) {
    try { $stamp = py -3.11 -m projectos.infrastructure.fleet_clock }
    catch { $stamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd_HHmm") + "-UTC-ASSUMED" }
    $target = Join-Path $ReportsDir "${stamp}_${Seat}_WAKE-FAILURE.md"
    "WAKE FAILURE ($Seat): $why" | Out-File -FilePath $target -Encoding utf8
    Write-LocalLog "WAKE-FAILURE: $why"
}

function Release-SeatLock {
    if (-not $script:HoldsLock) { return }
    if (Test-Path $LockFile) {
        $raw = Get-Content $LockFile -Raw -ErrorAction SilentlyContinue
        if ($raw -match "pid=$PID(\D|$)") { Remove-Item $LockFile -Force -ErrorAction SilentlyContinue }
    }
    $script:HoldsLock = $false
}

function Exit-Wake([int]$code) {
    Release-SeatLock
    exit $code
}

function Get-BackoffState {
    if (-not (Test-Path $BackoffFile)) {
        return @{ consecutive = 0; last_class = ""; next_eligible = $null }
    }
    try {
        $j = Get-Content $BackoffFile -Raw | ConvertFrom-Json
        return @{
            consecutive = [int]$j.consecutive
            last_class = [string]$j.last_class
            next_eligible = $j.next_eligible
        }
    } catch {
        return @{ consecutive = 0; last_class = ""; next_eligible = $null }
    }
}

function Save-BackoffState($state) {
    ($state | ConvertTo-Json -Compress) | Set-Content -Path $BackoffFile -Encoding utf8
}

function Record-FailureClass([string]$class) {
    $s = Get-BackoffState
    if ($s.last_class -eq $class -and $class -ne "") {
        $s.consecutive = [int]$s.consecutive + 1
    } else {
        $s.consecutive = 1
        $s.last_class = $class
    }
    if ($s.consecutive -ge 2) {
        $exp = [Math]::Min($s.consecutive - 1, 5)
        $delay = [Math]::Min($BackoffBaseMinutes * [Math]::Pow(2, $exp), $BackoffCeilingMinutes)
        $s.next_eligible = (Get-Date).AddMinutes($delay).ToString("o")
        Write-LocalLog "BACKOFF: class=$class consecutive=$($s.consecutive) next_eligible=$($s.next_eligible) delay_min=$delay"
    }
    Save-BackoffState $s
}

function Record-Success {
    Save-BackoffState @{ consecutive = 0; last_class = ""; next_eligible = $null }
    Write-LocalLog "BACKOFF reset on success"
}

function Write-UsageLine {
    try {
        $day = (Get-Date).ToString("yyyy-MM-dd")
        $todaysSessions = @(Get-Content $UsageLog -ErrorAction SilentlyContinue |
            Where-Object { $_ -like "$day|$Seat|*" }).Count
        $usageDrive = Join-Path $ReportsDir "FLEET-USAGE.md"
        if (-not (Test-Path $usageDrive)) {
            Set-Content -Path $usageDrive -Encoding utf8 -Value @(
                "# FLEET USAGE - one line per wake session that reached an engine",
                "",
                "Session counts and engines are measured. Provider token counts are NOT",
                "available to the wrapper and are never estimated here. A failed session",
                "still counts: it consumed quota.",
                ""
            )
        }
        Add-Content -Path $usageDrive -Encoding utf8 `
            -Value "$day | $Seat | engine=$Engine | session #$todaysSessions today"
    } catch {
        Write-LocalLog "usage line could not be written: $($_.Exception.Message)"
    }
}

$bo = Get-BackoffState
if ($bo.next_eligible) {
    try {
        $eligible = [DateTime]::Parse($bo.next_eligible)
        if ((Get-Date) -lt $eligible) {
            Write-LocalLog "SKIP: backoff active until $($bo.next_eligible) (class=$($bo.last_class) consecutive=$($bo.consecutive))"
            exit 0
        }
    } catch { }
}

if (Test-Path $LockFile) {
    $raw = Get-Content $LockFile -Raw -ErrorAction SilentlyContinue
    $ownerPid = 0
    $ownerTicks = ""
    if ($raw -match "pid=(\d+)") { $ownerPid = [int]$Matches[1] }
    if ($raw -match "startticks=(\d+)") { $ownerTicks = $Matches[1] }
    $owner = $null
    if ($ownerPid -gt 0) { $owner = Get-Process -Id $ownerPid -ErrorAction SilentlyContinue }
    $ownerIsLive = $false
    if ($null -ne $owner) {
        try { $ownerIsLive = ($owner.StartTime.Ticks.ToString() -eq $ownerTicks) }
        catch { $ownerIsLive = $true }
    }
    if ($ownerIsLive) {
        Write-LocalLog "SKIP: seat already running (owner pid $ownerPid); this wake exits without claiming"
        exit 0
    }
    Write-LocalLog "STALE LOCK cleared: owner pid $ownerPid is not alive (recorded start $ownerTicks)"
    Remove-Item $LockFile -Force -ErrorAction SilentlyContinue
}

$self = Get-Process -Id $PID
@(
    "pid=$PID",
    "startticks=$($self.StartTime.Ticks)",
    "seat=$Seat",
    "engine=$Engine",
    "since=$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))"
) | Set-Content -Path $LockFile -Encoding utf8
$script:HoldsLock = $true

$today = (Get-Date).ToString("yyyy-MM-dd")
Add-Content -Path $UsageLog -Value "$today|$Seat|$Engine" -Encoding utf8

if ($Seat -eq "CHAT-AUTO-RESTOCK") {
    $config = Join-Path $RepoRoot "docs\wake\chat-restock-config.json"
    if (-not (Test-Path $config)) {
        Write-WakeFailure "chat-restock-config.json missing"
        Record-FailureClass "missing-restock-config"
        Exit-Wake 2
    }
    try {
        py -3.11 -m projectos.infrastructure.chat_auto_restock --reports-dir $ReportsDir --config $config
        $restockExit = $LASTEXITCODE
    } catch {
        Write-WakeFailure "deterministic restocker could not start"
        Record-FailureClass "restock-start"
        Exit-Wake 2
    }
    if ($restockExit -ne 0) {
        Write-WakeFailure "deterministic restocker exited $restockExit"
        Record-FailureClass "restock-exit-$restockExit"
        Exit-Wake 1
    }
    Record-Success
    Exit-Wake 0
}

$prompt = Join-Path $RepoRoot $PromptFile
if (-not (Test-Path $prompt)) {
    Write-WakeFailure "$PromptFile missing at $prompt (RepoRoot=$RepoRoot). Seat-specific tasks must pass -RepoRoot to that seat's local path where the prompt lives."
    Record-FailureClass "missing-prompt"
    Exit-Wake 2
}
$cliName = if ($Engine -eq "codex") { "codex" } else { "claude" }
$cli = Get-Command $cliName -ErrorAction SilentlyContinue
if ($null -eq $cli) {
    Write-WakeFailure "$cliName CLI not on PATH (Engine=$Engine)"
    Record-FailureClass "missing-cli-$cliName"
    Exit-Wake 2
}

$wakeStart = Get-Date
$reportsBefore = @(Get-ChildItem $ReportsDir -File -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty Name)

if (Test-Path $StderrFile) { Remove-Item $StderrFile -Force -ErrorAction SilentlyContinue }
if ($Engine -eq "codex") {
    Get-Content $prompt -Raw | & codex exec - -s workspace-write --add-dir $ReportsDir --skip-git-repo-check --color never 2>$StderrFile
} else {
    Get-Content $prompt -Raw | & claude -p 2>$StderrFile
}
$claudeExit = $LASTEXITCODE

Write-UsageLine

$reportsAfter = @(Get-ChildItem $ReportsDir -File -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty Name)
$new = @($reportsAfter | Where-Object { $reportsBefore -notcontains $_ })
$newClaims = @($new | Where-Object { $_ -match "_${Seat}_CLAIM_" })
$newOutcomes = @($new | Where-Object {
        $_ -notmatch "_CLAIM_" -and
        ($_ -match "_${Seat}_" -or $_ -match "HEARTBEAT|PARTIAL|BLOCKED|AUTH-REFUSAL|WAKE-FAILURE")
    })

if ($newClaims.Count -gt 0 -and $newOutcomes.Count -eq 0) {
    Write-WakeFailure "v4 report-contract breach: wake claimed ($($newClaims -join ', ')) and exited with NO report on Drive"
    Record-FailureClass "report-contract-breach"
    Exit-Wake 1
}

if ($newClaims.Count -eq 0) {
    $idleOnly = @($newOutcomes | Where-Object { $_ -match "HEARTBEAT" })
    if ($idleOnly.Count -gt 0 -and $idleOnly.Count -eq $newOutcomes.Count) {
        foreach ($name in $idleOnly) {
            Remove-Item -LiteralPath (Join-Path $ReportsDir $name) -Force -ErrorAction SilentlyContinue
        }
        Write-LocalLog "IDLE: nothing claimable; suppressed Drive heartbeat ($($idleOnly -join ', '))"
    }
}

Start-Sleep -Seconds 5
$orphans = @(Get-Process python*, py*, pytest* -ErrorAction SilentlyContinue |
    Where-Object { $_.StartTime -gt $wakeStart })
if ($orphans.Count -gt 0) {
    $names = ($orphans | ForEach-Object { "$($_.ProcessName):$($_.Id)" }) -join ", "
    $orphans | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-WakeFailure "wake left running processes ($names) - backgrounded work has no owner after exit; stopped"
    Record-FailureClass "orphan-process"
    Exit-Wake 1
}
if ($claudeExit -ne 0) {
    $tail = ""
    if (Test-Path $StderrFile) {
        $tail = (Get-Content $StderrFile -Tail 40 -ErrorAction SilentlyContinue | Out-String)
    }
    if ([string]::IsNullOrWhiteSpace($tail)) { $tail = "(no stderr captured)" }
    Write-WakeFailure "engine exited $claudeExit`nstderr tail:`n$tail"
    Record-FailureClass "engine-exit-$claudeExit"
    Exit-Wake 1
}

Write-LocalLog "OK: wake completed (engine=$Engine)"
Record-Success
Exit-Wake 0
