# Headless seat wake wrapper (REMOVE-THE-GO). One wake = one loop pass.
# Launched by Task Scheduler; runnable by hand for a dry-run. The prompt is
# wake-prompt.md in the repo root - versioned, never an inline string here.
#
# Exit codes: 0 = loop completed (work or heartbeat) - 1 = claude exited
# nonzero - 2 = could not even start (missing prompt/CLI); both failure
# paths leave a WAKE-FAILURE file on Drive so silence is impossible.
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

function Write-WakeFailure([string]$why) {
    # Fleet-clock stamp when python is reachable; raw UTC marked ASSUMED when
    # it is not - a failure record with a suspect stamp beats no record.
    try { $stamp = py -3.11 -m projectos.infrastructure.fleet_clock }
    catch { $stamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd_HHmm") + "-UTC-ASSUMED" }
    $target = Join-Path $ReportsDir "${stamp}_${Seat}_WAKE-FAILURE.md"
    "WAKE FAILURE ($Seat): $why" | Out-File -FilePath $target -Encoding utf8
    # Telegram escalation rides the existing TradeOS alert rail; wiring it is
    # a TRADEOS-seat integration (flagged in the REMOVE-THE-GO report), so
    # this wrapper's guaranteed signal is the Drive file above.
}

# CHAT-AUTO-RESTOCK is a deterministic program, not an agent session.
# This branch is deliberately before prompt/CLI discovery: untrusted report
# text can never enter the same context as instructions, and the restocker has
# no model tools with which to merge, ratify, edit a repo, or self-issue.
if ($Seat -eq "CHAT-AUTO-RESTOCK") {
    $config = Join-Path $RepoRoot "docs\wake\chat-restock-config.json"
    if (-not (Test-Path $config)) {
        Write-WakeFailure "chat-restock-config.json missing"
        exit 2
    }
    try {
        py -3.11 -m projectos.infrastructure.chat_auto_restock --reports-dir $ReportsDir --config $config
        $restockExit = $LASTEXITCODE
    } catch {
        Write-WakeFailure "deterministic restocker could not start"
        exit 2
    }
    if ($restockExit -ne 0) {
        Write-WakeFailure "deterministic restocker exited $restockExit"
        exit 1
    }
    exit 0
}

$prompt = Join-Path $RepoRoot $PromptFile
if (-not (Test-Path $prompt)) { Write-WakeFailure "$PromptFile missing"; exit 2 }
$cliName = if ($Engine -eq "codex") { "codex" } else { "claude" }
$cli = Get-Command $cliName -ErrorAction SilentlyContinue
if ($null -eq $cli) { Write-WakeFailure "$cliName CLI not on PATH"; exit 2 }

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
    exit 1
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
    exit 1
}
if ($claudeExit -ne 0) { Write-WakeFailure "claude exited $claudeExit"; exit 1 }
exit 0

