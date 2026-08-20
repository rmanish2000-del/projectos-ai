# Headless seat wake wrapper (REMOVE-THE-GO). One wake = one loop pass.
# Launched by Task Scheduler; runnable by hand for a dry-run. The prompt is
# wake-prompt.md in the repo root - versioned, never an inline string here.
#
# Exit codes: 0 = loop completed, or a normal skip because the seat was
# already running - 1 = the engine exited nonzero, or a wrapper tripwire
# fired - 2 = could not even start (missing prompt/CLI). Every real failure
# leaves a WAKE-FAILURE file on Drive so silence is impossible. A SKIP is
# not a failure and deliberately leaves nothing on Drive.
param(
    [string]$RepoRoot = "C:\ProjectOS-AI",
    [string]$Seat = "PROJECTOS",
    [string]$ReportsDir = "G:\My Drive\AGENT-REPORTS",
    # CHAT-AUTO-RESTOCK passes wake-prompt-chat.md; seat wakes use the default.
    [string]$PromptFile = "wake-prompt.md",
    # ENGINE-AGNOSTIC-WAKE: how the session starts is a detail; what the seat
    # owes (claim, report contract, AUTH, tripwires) is engine-independent.
    # ValidateSet fails closed on unknown engines. Default = claude, byte-
    # identical behaviour when unspecified.
    [ValidateSet("claude", "codex")]
    [string]$Engine = "claude"
)

$ErrorActionPreference = "Stop"
Set-Location $RepoRoot

# Machine-local state, beside the keyring: never on Drive, so a 20-minute
# cadence cannot flood the report channel with its own bookkeeping.
$StateDir = Join-Path $env:USERPROFILE ".projectos"
if (-not (Test-Path $StateDir)) { New-Item -ItemType Directory -Force $StateDir | Out-Null }
$LockFile = Join-Path $StateDir "wake-$Seat.lock"
$LocalLog = Join-Path $StateDir "wake-$Seat.log"
$UsageLog = Join-Path $StateDir "wake-usage.log"
$script:HoldsLock = $false

function Write-LocalLog([string]$line) {
    $when = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    Add-Content -Path $LocalLog -Value "$when [$Seat] $line" -Encoding utf8
}

function Write-WakeFailure([string]$why) {
    # Fleet-clock stamp when python is reachable; raw UTC marked ASSUMED when
    # it is not - a failure record with a suspect stamp beats no record.
    try { $stamp = py -3.11 -m projectos.infrastructure.fleet_clock }
    catch { $stamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd_HHmm") + "-UTC-ASSUMED" }
    $target = Join-Path $ReportsDir "${stamp}_${Seat}_WAKE-FAILURE.md"
    "WAKE FAILURE ($Seat): $why" | Out-File -FilePath $target -Encoding utf8
    Write-LocalLog "WAKE-FAILURE: $why"
    # Telegram escalation rides the existing TradeOS alert rail; wiring it is
    # a TRADEOS-seat integration (flagged in the REMOVE-THE-GO report), so
    # this wrapper's guaranteed signal is the Drive file above.
}

function Release-SeatLock {
    # Only ever release a lock this process actually owns. A wake that skipped
    # because another session held the lock must never delete that lock.
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

function Write-UsageLine {
    # Phone-readable usage, appended (never rewritten, so seats waking
    # concurrently cannot race). Date, seat, engine and this seat's session
    # count for today - all measured. Provider token counts are NOT available
    # to this wrapper and are deliberately never estimated.
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

# ---------------------------------------------------------------------------
# PER-SEAT LOCK (20-minute cadence). Two sessions of one seat overlapping can
# double-claim an assignment and corrupt Drive state, so a seat is serialized.
#
# Staleness is decided by PROVING THE OWNER IS DEAD, not by a timeout: the
# lock records the owner's pid AND that process's exact start time, so a
# recycled pid cannot masquerade as a live owner, and a legitimately long
# session is never displaced no matter how long it runs. A blind timeout was
# rejected for exactly that reason - it would kill a slow gate mid-run.
# ---------------------------------------------------------------------------
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
        # Same pid AND same start time = genuinely the process that took the
        # lock. Same pid, different start time = the pid was recycled and the
        # real owner is long gone.
        try { $ownerIsLive = ($owner.StartTime.Ticks.ToString() -eq $ownerTicks) }
        catch { $ownerIsLive = $true }  # cannot read it: assume live, never displace
    }
    if ($ownerIsLive) {
        # Normal skip. Not a failure: no WAKE-FAILURE, no Drive report, and
        # the running session is left completely alone to finish and report.
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

# Usage visibility: one appended line per session. Session counts and engines
# are real; provider token counts are NOT available to this wrapper and are
# deliberately never estimated.
$today = (Get-Date).ToString("yyyy-MM-dd")
Add-Content -Path $UsageLog -Value "$today|$Seat|$Engine" -Encoding utf8

# CHAT-AUTO-RESTOCK is a deterministic program, not an agent session.
# This branch is deliberately before prompt/CLI discovery: untrusted report
# text can never enter the same context as instructions, and the restocker has
# no model tools with which to merge, ratify, edit a repo, or self-issue.
if ($Seat -eq "CHAT-AUTO-RESTOCK") {
    $config = Join-Path $RepoRoot "docs\wake\chat-restock-config.json"
    if (-not (Test-Path $config)) {
        Write-WakeFailure "chat-restock-config.json missing"
        Exit-Wake 2
    }
    try {
        py -3.11 -m projectos.infrastructure.chat_auto_restock --reports-dir $ReportsDir --config $config
        $restockExit = $LASTEXITCODE
    } catch {
        Write-WakeFailure "deterministic restocker could not start"
        Exit-Wake 2
    }
    if ($restockExit -ne 0) {
        Write-WakeFailure "deterministic restocker exited $restockExit"
        Exit-Wake 1
    }
    Exit-Wake 0
}

$prompt = Join-Path $RepoRoot $PromptFile
if (-not (Test-Path $prompt)) { Write-WakeFailure "$PromptFile missing"; Exit-Wake 2 }
$cliName = if ($Engine -eq "codex") { "codex" } else { "claude" }
$cli = Get-Command $cliName -ErrorAction SilentlyContinue
if ($null -eq $cli) { Write-WakeFailure "$cliName CLI not on PATH"; Exit-Wake 2 }

# No --dangerously-skip-permissions: the repo's tracked .claude/settings.json
# allowlist governs the session (RATIFICATION-WAKE-CADENCE hardening). Print
# mode cannot answer permission prompts, so anything outside the allowlist is
# DENIED - the seat fails closed and reports BLOCKED instead of acting. The
# fence is that allowlist + the wake prompt's guardrails + INBOX-AUTH + tiers.

# STRUCTURAL v4 enforcement (V4-BREACH-DIAGNOSIS-AND-FIX). The 2026-08-18
# dry-run proved prose alone does not hold: the wake loaded v4 (verified from
# this file's default) and still backgrounded the suite, exited 0, stranded
# its claim. So the WRAPPER now audits the report contract mechanically -
# the seat cannot exit 0 with a claim and no report, whatever it narrates.
$wakeStart = Get-Date
$reportsBefore = @(Get-ChildItem $ReportsDir -File -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty Name)

# Prompt goes via STDIN for EVERY engine, never as an argument: PS 5.1
# native-call quoting mangles embedded double quotes, and the tripwire proof
# caught a prompt truncating at its first inner quote (WAKE-TRIPWIRE-PROVEN,
# test 2). The real wake prompts contain quotes, so the argument path is a
# live-fire bug. Codex runs sandboxed (workspace-write + the reports dir as
# an extra writable root) - the nearest equivalent of the Claude allowlist;
# the differences are audited in the ENGINE-AGNOSTIC-WAKE report.
if ($Engine -eq "codex") {
    Get-Content $prompt -Raw | codex exec - -s workspace-write --add-dir $ReportsDir --skip-git-repo-check --color never
} else {
    Get-Content $prompt -Raw | claude -p
}
$claudeExit = $LASTEXITCODE

# Usage is recorded HERE, immediately after the engine returns, and NOT on
# the success path only: a wake that reached the engine consumed a session
# whether or not it then succeeded. Counting only successes would hide
# exactly the days worth watching - the ones where sessions are being burned
# on failures.
Write-UsageLine

$reportsAfter = @(Get-ChildItem $ReportsDir -File -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty Name)
$new = @($reportsAfter | Where-Object { $reportsBefore -notcontains $_ })
$newClaims = @($new | Where-Object { $_ -match "_${Seat}_CLAIM_" })
$newOutcomes = @($new | Where-Object {
        $_ -notmatch "_CLAIM_" -and
        ($_ -match "_${Seat}_" -or $_ -match "HEARTBEAT|PARTIAL|BLOCKED|AUTH-REFUSAL|WAKE-FAILURE")
    })

# The claim check runs FIRST: a stranded claim is the defect class this
# wrapper exists for, and the first tripwire proof showed the orphan check
# masking it when both fire (WAKE-TRIPWIRE-PROVEN, test 1).
if ($newClaims.Count -gt 0 -and $newOutcomes.Count -eq 0) {
    Write-WakeFailure "v4 report-contract breach: wake claimed ($($newClaims -join ', ')) and exited with NO report on Drive"
    Exit-Wake 1
}

# QUIET IDLE WAKES. At 20-minute cadence an idle heartbeat per wake would be
# ~30 files per seat per day, which buries the reports channel it exists to
# make readable. An idle wake is one that claimed nothing and produced only a
# heartbeat: the heartbeat is removed from Drive and recorded locally instead.
# Enforced here rather than in the prompt so the seat's instructions are
# untouched - and so an agent that forgets cannot flood the channel anyway.
if ($newClaims.Count -eq 0) {
    $idleOnly = @($newOutcomes | Where-Object { $_ -match "HEARTBEAT" })
    if ($idleOnly.Count -gt 0 -and $idleOnly.Count -eq $newOutcomes.Count) {
        foreach ($name in $idleOnly) {
            Remove-Item -LiteralPath (Join-Path $ReportsDir $name) -Force -ErrorAction SilentlyContinue
        }
        Write-LocalLog "IDLE: nothing claimable; suppressed Drive heartbeat ($($idleOnly -join ', '))"
    }
}

# Backgrounded work left alive is the other half of the same defect: a
# process outliving the session is work with no owner and no report. The
# settling pause exists because the same proof run caught TRANSIENT
# interpreter children of the just-exited session (a race, not an orphan);
# only a process still alive after the pause counts.
Start-Sleep -Seconds 5
$orphans = @(Get-Process python*, py*, pytest* -ErrorAction SilentlyContinue |
    Where-Object { $_.StartTime -gt $wakeStart })
if ($orphans.Count -gt 0) {
    $names = ($orphans | ForEach-Object { "$($_.ProcessName):$($_.Id)" }) -join ", "
    $orphans | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-WakeFailure "wake left running processes ($names) - backgrounded work has no owner after exit; stopped"
    Exit-Wake 1
}
if ($claudeExit -ne 0) { Write-WakeFailure "engine exited $claudeExit"; Exit-Wake 1 }

Write-LocalLog "OK: wake completed (engine=$Engine)"
Exit-Wake 0
