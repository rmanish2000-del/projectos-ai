# Register the three new seats (EDUOS, URJAOPS, LEOS) as FLEET wake tasks.
# Founder act: run this from an ELEVATED PowerShell. THREE-NEW-SEATS, 2026-08-20.
#
# WHY THIS IS A .ps1 AND NOT schtasks. The LEOS repo lives at a path containing
# spaces, en-dashes, parentheses and a full stop. Both schtasks forms fail on it,
# tested rather than assumed:
#   * quoting the path breaks the /tr parser -> "Invalid argument/option - 'Case'"
#   * the 8.3 short path fits the parser but the whole action then exceeds the
#     hard 261-character limit on /tr
# Register-ScheduledTask takes the action as a real argument rather than a
# re-parsed string, so the quotes and the en-dashes survive intact. Verified:
# the stored action read back byte-identical and the LEOS wake ran from it.
#
# WHY THE BATTERY FLAGS ARE NOT OPTIONAL. A task registered without them
# defaults to DisallowStartIfOnBatteries, and on battery it STARTS, ABORTS
# IMMEDIATELY AND REPORTS LastTaskResult 0 - a success code, no log line, no
# artifact, nothing to notice. This laptop was on battery tonight and that alone
# produced three consecutive silent no-ops that looked exactly like a broken
# path. The existing five FLEET tasks already carry these flags; the new three
# must match or they will be dark every time the charger is out.
#
# STAGGER. Existing seats hold minute offsets 0,3,6,9,12,15 of a 20-minute
# repeat, so the only free window is 16-19. These three take 16, 17 and 18 and
# leave 19 spare. One minute apart is tighter than the existing three, which is
# a consequence of fitting nine seats into a 20-minute cycle - see the report's
# note on the cleaner alternative.

$ErrorActionPreference = "Stop"

$shim = "C:\ProjectOS-AI\scripts\run-hidden.vbs"
if (-not (Test-Path -LiteralPath $shim)) { throw "shim missing: $shim" }

$seats = @(
    @{ Seat = "EDUOS";   Root = "C:\EduOS";   Start = "09:16" },
    @{ Seat = "URJAOPS"; Root = "C:\UrjaOps"; Start = "09:17" },
    @{ Seat = "LEOS";    Root = "C:\Urjadata Case - Dobhi Deori - Sagar (M.P.) - 470226\LEOS"; Start = "09:18" }
)
# NOTE: the LEOS Root above uses plain hyphens for safe transport in this file.
# The real folder uses EN-DASHES, so it is resolved from disk rather than
# transcribed - a transcription slip would register a task pointing at a folder
# that does not exist, the precise failure this assignment was written to avoid.
#
# Resolve by EVIDENCE, not by name prefix. C:\ has TWO folders matching
# "Urjadata*" and the shorter one is a decoy: a -Filter "Urjadata*" plus
# Select-Object -First 1 picks "C:\Urjadata Case" and silently produces a task
# aimed at nothing. The identifying artifact is the wake script itself, and an
# ambiguous match is refused rather than guessed.
$leosCandidates = @(Get-ChildItem "C:\" -Directory -Filter "Urjadata*" |
    Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "LEOS\scripts\wake.ps1") })
if ($leosCandidates.Count -ne 1) {
    throw "LEOS matter folder: expected exactly one candidate holding LEOS\scripts\wake.ps1, found $($leosCandidates.Count)"
}
$seats[2].Root = Join-Path $leosCandidates[0].FullName "LEOS"

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1)

foreach ($s in $seats) {
    $wake = Join-Path $s.Root "scripts\wake.ps1"
    if (-not (Test-Path -LiteralPath $wake)) { throw "wake.ps1 missing for $($s.Seat): $wake" }

    $arg = "//B //Nologo $shim powershell -NoProfile -ExecutionPolicy Bypass " +
           "-File `"$wake`" -RepoRoot `"$($s.Root)`" -Seat $($s.Seat)"

    $action  = New-ScheduledTaskAction -Execute "wscript.exe" -Argument $arg
    $trigger = New-ScheduledTaskTrigger -Daily -At $s.Start
    $trigger.Repetition = (New-ScheduledTaskTrigger -Once -At $s.Start `
        -RepetitionInterval (New-TimeSpan -Minutes 20) `
        -RepetitionDuration (New-TimeSpan -Hours 10)).Repetition

    Register-ScheduledTask -TaskName "WAKE-$($s.Seat)" -TaskPath "\FLEET\" `
        -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

    Write-Output "registered WAKE-$($s.Seat) at $($s.Start), target $wake"
}

# Prove the registration rather than trusting it: read every action back and
# confirm the file it points at exists. Ready means the trigger is armed, not
# that the action can execute.
Write-Output ""
Write-Output "--- verification ---"
foreach ($s in $seats) {
    $t = Get-ScheduledTask -TaskPath "\FLEET\" -TaskName "WAKE-$($s.Seat)"
    $m = [regex]::Match($t.Actions[0].Arguments, '-File\s+"([^"]+)"')
    $ok = $m.Success -and (Test-Path -LiteralPath $m.Groups[1].Value)
    Write-Output ("WAKE-{0,-8} state={1} targetExists={2}" -f $s.Seat, $t.State, $ok)
}
