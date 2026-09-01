# Retime the four seat tasks this seat could not touch. FOUNDER ACT, elevated.
# CHEAP-AND-VISIBLE-FLEET, 2026-09-01.
#
# Eight of the twelve seat tasks were retimed to a 3-hour interval from an
# ordinary session. These four returned "Access is denied" because they were
# created under a different principal, which is the same wall this seat hit on
# 2026-08-20 trying to change founder-created tasks. That is an ACL doing its
# job; nothing here works around it, it just needs to run elevated.
#
# The four slots below are the gaps deliberately left free by the eight that
# succeeded, so afterwards all twelve sit on an even 15-minute stagger:
#
#   09:00 AIW      09:15 CHAT-RESTOCK   09:30 CHIEF    09:45 EDUOS
#   10:00 LEOS     10:15 LSN            10:30 PROJECTOS 10:45 TRADEOS
#   11:00 URJAOPS  11:15 WARRANT        11:30 WEB      11:45 WMCP
#
# EVERY TASK IS LEFT DISABLED, including these. Enabling the fleet is your
# call after reading the report - this script only changes when they would
# fire if you do.
#
# AUTO-SIGN is deliberately absent from this script. It is cheap, it starts no
# engine, and it must stay responsive.

$ErrorActionPreference = "Stop"

$slots = @{
    "WAKE-CHAT-RESTOCK" = "09:15"
    "WAKE-EDUOS"        = "09:45"
    "WAKE-LEOS"         = "10:00"
    "WAKE-URJAOPS"      = "11:00"
}

foreach ($name in ($slots.Keys | Sort-Object)) {
    $at = Get-Date $slots[$name]
    $trigger = New-ScheduledTaskTrigger -Daily -At $at
    $trigger.Repetition = (New-ScheduledTaskTrigger -Once -At $at `
        -RepetitionInterval (New-TimeSpan -Hours 3) `
        -RepetitionDuration (New-TimeSpan -Hours 10)).Repetition

    Set-ScheduledTask -TaskPath "\FLEET\" -TaskName $name -Trigger $trigger | Out-Null
    Write-Output ("retimed {0,-20} -> {1} every 3h" -f $name, $slots[$name])
}

# Leave them Disabled, and prove it rather than assuming it.
foreach ($name in $slots.Keys) {
    $task = Get-ScheduledTask -TaskPath "\FLEET\" -TaskName $name
    if ($task.State -ne "Disabled") {
        Disable-ScheduledTask -TaskPath "\FLEET\" -TaskName $name | Out-Null
    }
}

Write-Output ""
Write-Output "--- all twelve seat tasks, after ---"
Get-ScheduledTask -TaskPath "\FLEET\" |
    Where-Object { $_.TaskName -like "WAKE-*" } |
    Sort-Object TaskName |
    ForEach-Object {
        $t = $_.Triggers[0]
        "{0,-20} start={1} interval={2,-5} state={3}" -f $_.TaskName,
            ($t.StartBoundary -replace '.*T', '' -replace '\+.*', '' -replace ':00$', ''),
            $t.Repetition.Interval, $_.State
    }
