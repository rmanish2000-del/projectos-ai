# Auto-signer sweep (AUTO-SIGNER). One synchronous pass over the Drive INBOX:
# sign newly-arrived unsigned assignments with k1 so work the founder directs
# from his phone stops silently stalling.
#
# Every bound lives in the Python (projectos.infrastructure.inbox_auth
# auto_sign_once) where it is unit-tested: this directory only, assignment-
# named files only, never a second stamp, never a repair of a tampered one,
# and a per-sweep cap. This wrapper only schedules and reports.
#
# KILL SWITCH (instant, no privileges):
#     New-Item -ItemType File "$env:USERPROFILE\.projectos\auto-sign.OFF"
# Delete that file to resume.
#
# Exit codes: 0 clean sweep - 1 a tampered stamp was found (an incident,
# left refused and logged) - 2 could not run at all.
param(
    [string]$RepoRoot = "C:\ProjectOS-AI",
    [string]$InboxDir = "G:\My Drive\AGENT-REPORTS\INBOX"
)

$ErrorActionPreference = "Stop"
Set-Location $RepoRoot

if (-not (Test-Path $InboxDir)) {
    # Drive not mounted yet (reboot, sync starting). Say so; do not sign.
    Write-Output "auto-sign: INBOX not reachable at $InboxDir - skipped this sweep"
    exit 2
}

py -3.11 -m projectos.infrastructure.inbox_auth auto-sign $InboxDir
exit $LASTEXITCODE
