# One-time registration of the FLEET applier. FOUNDER ACT, elevated.
# NO-LAPTOP-PRIVILEGED-APPLIER, 2026-08-21. NOT RUN by the seat that wrote it:
# installing a privileged component is founder-only, and a seat that installs
# its own privilege has defeated the point of having a privilege boundary.
#
# WHAT THIS REGISTERS. A task that runs the applier's DRY RUN on a schedule.
# It decides and reports; it does not apply. Applying is a deliberate second
# step you take after reading a dry run you agree with. Registering the
# decision half first means the fence can be watched in production for as long
# as you like before anything is ever allowed to act on its verdicts.
#
# WHY THE APPLIER IS SAFE TO RUN AT ALL. A manifest may only NAME a task and an
# operation. Every executable, argument, path, principal and trigger comes from
# docs/fleet_tasks.json, which changes only through a reviewed commit. A
# manifest carrying an `execute`, `user`, `runlevel` or `trigger` field is
# REFUSED outright rather than having the field ignored - the applier will not
# quietly honour part of an instruction it will not honour in full.
#
# BATTERY FLAGS ARE NOT OPTIONAL - see docs/wake/register-new-seats.ps1. A task
# registered without them starts, aborts and reports LastTaskResult 0 on
# battery: a success code, no log line, nothing to notice.
#
# KILL SWITCH (instant, no privileges):
#     New-Item -ItemType File "$env:USERPROFILE\.projectos\fleet-applier.OFF"
# While that file exists the applier applies nothing and KEEPS REPORTING that
# it is stopped, so a stopped applier is visibly stopped rather than silent.

$ErrorActionPreference = "Stop"

$repo = "C:\ProjectOS-AI"
$shim = "$repo\scripts\run-hidden.vbs"
$manifestDir = "G:\My Drive\AGENT-REPORTS\FLEET-MANIFESTS"
$statusDir = "G:\My Drive\AGENT-REPORTS"

foreach ($required in @($shim, "$repo\docs\fleet_tasks.json")) {
    if (-not (Test-Path -LiteralPath $required)) { throw "missing prerequisite: $required" }
}
if (-not (Test-Path -LiteralPath $manifestDir)) {
    New-Item -ItemType Directory -Path $manifestDir -Force | Out-Null
}

# The applier sweep: dry-run whatever manifest is waiting, write status, exit.
# Deliberately NOT elevated - the decision half needs no privilege, and keeping
# it unprivileged is what lets the whole fence be tested without any.
$inner = "cd /d $repo && py -3.11 -m projectos.infrastructure.fleet_applier " +
         "`"$manifestDir\pending.json`" --status `"$statusDir`""
$arg = "//B //Nologo $shim cmd /c `"$inner`""

$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument $arg
$trigger = New-ScheduledTaskTrigger -Once -At "09:19" `
    -RepetitionInterval (New-TimeSpan -Minutes 20) `
    -RepetitionDuration (New-TimeSpan -Hours 10)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName "FLEET-APPLIER" -TaskPath "\FLEET\" `
    -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

# 09:19 is the last free minute of the 20-minute cycle: seats hold 0,3,6,9,12,
# 15,16,17,18. Chosen so the applier never sweeps while a seat is starting.

Write-Output "registered FLEET-APPLIER (dry-run sweep, 09:19, every 20 min)"

# Prove it rather than trusting it.
$t = Get-ScheduledTask -TaskPath "\FLEET\" -TaskName "FLEET-APPLIER"
Write-Output ("state={0} battery_ok={1}" -f $t.State, (-not $t.Settings.DisallowStartIfOnBatteries))
Write-Output "NOTE: this task only DECIDES. Nothing applies until you run the"
Write-Output "elevated apply step by hand against a dry run you have read."
