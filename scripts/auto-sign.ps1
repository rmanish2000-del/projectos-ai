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
$signExit = $LASTEXITCODE

# ---------------------------------------------------------------------------
# TASK-TARGET CHECK (WAKE-SCRIPT-DISTRIBUTION item 6). On 2026-08-20 every
# seat but one had a registered, Ready, correctly-triggered wake task whose
# target script DID NOT EXIST - four of five seats could not run for hours
# and Task Scheduler still showed them Ready, because "Ready" means the
# trigger is armed, not that the action can execute.
#
# This runs here because the two-minute signer is the one thing that fires
# reliably. It writes to Drive ONLY when something is wrong, so a healthy
# fleet stays silent and an alert file means exactly one thing.
# ---------------------------------------------------------------------------
try {
    $reportsDir = Split-Path $InboxDir -Parent
    $missing = @()
    foreach ($task in (Get-ScheduledTask -TaskPath "\FLEET\" -ErrorAction SilentlyContinue)) {
        $arguments = $task.Actions[0].Arguments
        # Pull every -File target out of the action, whether it is launched
        # directly or through the hidden shim. The quoted alternative must come
        # first and must not exclude spaces: LEOS lives at a path containing
        # spaces, en-dashes, parentheses and a full stop, and a space-excluding
        # pattern truncates it to "C:\Urjadata" - a path that never exists, so
        # the watchdog would raise a permanent false alert against a healthy
        # seat and teach the fleet to ignore it.
        foreach ($m in [regex]::Matches($arguments, '-File\s+(?:"([^"]+)"|([A-Za-z]:\\[^"\s]+))')) {
            $target = if ($m.Groups[1].Success) { $m.Groups[1].Value } else { $m.Groups[2].Value }
            if (-not (Test-Path -LiteralPath $target)) { $missing += "$($task.TaskName) -> $target" }
        }
        # The shim itself is a target too.
        foreach ($m in [regex]::Matches($arguments, '([A-Za-z]:\\[^"\s]+\.vbs)')) {
            $target = $m.Groups[1].Value
            if (-not (Test-Path $target)) { $missing += "$($task.TaskName) -> $target" }
        }
    }
    $alert = Join-Path $reportsDir "FLEET-TASK-TARGET-ALERT.md"
    if ($missing.Count -gt 0) {
        $lines = @(
            "# ALERT - registered task points at a script that does not exist",
            "",
            "A task can be Ready, correctly triggered and still incapable of running:",
            "Ready means the trigger is armed, not that the action can execute. Each",
            "line below is a task that will fail every time it fires until the file",
            "is placed.",
            ""
        ) + ($missing | Sort-Object -Unique)
        Set-Content -Path $alert -Value $lines -Encoding utf8
    } elseif (Test-Path $alert) {
        # Healthy again: clear the alert rather than leaving a stale scare.
        Remove-Item -LiteralPath $alert -Force -ErrorAction SilentlyContinue
    }
} catch {
    # A check that cannot run must not take the signer down with it.
    Write-Output "auto-sign: task-target check could not run: $($_.Exception.Message)"
}

exit $signExit
