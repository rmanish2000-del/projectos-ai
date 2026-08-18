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
    [string]$ReportsDir = "G:\My Drive\AGENT-REPORTS"
)

$ErrorActionPreference = "Stop"
Set-Location $RepoRoot

function Write-WakeFailure([string]$why) {
    # Fleet-clock stamp when python is reachable; raw UTC marked ASSUMED when
    # it is not - a failure record with a suspect stamp beats no record.
    try { $stamp = py -3.11 -c "from projectos.infrastructure.fleet_clock import stamp_for_filename; print(stamp_for_filename())" }
    catch { $stamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd_HHmm") + "-UTC-ASSUMED" }
    $target = Join-Path $ReportsDir "${stamp}_${Seat}_WAKE-FAILURE.md"
    "WAKE FAILURE ($Seat): $why" | Out-File -FilePath $target -Encoding utf8
    # Telegram escalation rides the existing TradeOS alert rail; wiring it is
    # a TRADEOS-seat integration (flagged in the REMOVE-THE-GO report), so
    # this wrapper's guaranteed signal is the Drive file above.
}

$prompt = Join-Path $RepoRoot "wake-prompt.md"
if (-not (Test-Path $prompt)) { Write-WakeFailure "wake-prompt.md missing"; exit 2 }
$cli = Get-Command claude -ErrorAction SilentlyContinue
if ($null -eq $cli) { Write-WakeFailure "claude CLI not on PATH"; exit 2 }

# --dangerously-skip-permissions is required for an unattended run (print
# mode cannot answer permission prompts). The fence for a headless seat is
# therefore the wake prompt's guardrails + INBOX-AUTH + the tiers module,
# and the report to the founder says exactly that. Hardening to a
# .claude/settings.json allowlist is proposed in the same report.
claude -p (Get-Content $prompt -Raw) --dangerously-skip-permissions
if ($LASTEXITCODE -ne 0) { Write-WakeFailure "claude exited $LASTEXITCODE"; exit 1 }
exit 0
