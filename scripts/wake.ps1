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
    [string]$PromptFile = "wake-prompt.md"
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

$prompt = Join-Path $RepoRoot $PromptFile
if (-not (Test-Path $prompt)) { Write-WakeFailure "$PromptFile missing"; exit 2 }
$cli = Get-Command claude -ErrorAction SilentlyContinue
if ($null -eq $cli) { Write-WakeFailure "claude CLI not on PATH"; exit 2 }

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

claude -p (Get-Content $prompt -Raw)
$claudeExit = $LASTEXITCODE

$reportsAfter = @(Get-ChildItem $ReportsDir -File -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty Name)
$new = @($reportsAfter | Where-Object { $reportsBefore -notcontains $_ })
$newClaims = @($new | Where-Object { $_ -match "_${Seat}_CLAIM_" })
$newOutcomes = @($new | Where-Object {
        $_ -notmatch "_CLAIM_" -and
        ($_ -match "_${Seat}_" -or $_ -match "HEARTBEAT|PARTIAL|BLOCKED|AUTH-REFUSAL|WAKE-FAILURE")
    })

# Backgrounded work left alive is the other half of the same defect: a
# process outliving the session is work with no owner and no report.
$orphans = @(Get-Process python*, py*, pytest* -ErrorAction SilentlyContinue |
    Where-Object { $_.StartTime -gt $wakeStart })
if ($orphans.Count -gt 0) {
    $names = ($orphans | ForEach-Object { "$($_.ProcessName):$($_.Id)" }) -join ", "
    $orphans | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-WakeFailure "wake left running processes ($names) - backgrounded work has no owner after exit; stopped"
    exit 1
}
if ($newClaims.Count -gt 0 -and $newOutcomes.Count -eq 0) {
    Write-WakeFailure "v4 report-contract breach: wake claimed ($($newClaims -join ', ')) and exited with NO report on Drive"
    exit 1
}
if ($claudeExit -ne 0) { Write-WakeFailure "claude exited $claudeExit"; exit 1 }
exit 0
