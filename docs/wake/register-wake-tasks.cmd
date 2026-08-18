@echo off
REM ============================================================================
REM  FOUNDER-RUN ONLY (REMOVE-THE-GO). Registering these tasks is the one-time
REM  enablement act the assignment reserves for the founder. No seat runs this.
REM
REM  Each seat wakes staggered so Drive is never touched by two seats at once.
REM  Cadence below is the PROPOSAL awaiting ratification:
REM    TRADEOS   08:40 + 15:50  (market open prep + post-close; 2/day)
REM    AIW       10:00 + 18:00  (2/day)
REM    WEB       10:10 + 18:10  (2/day)
REM    PROJECTOS 10:20 + 18:20  (2/day)
REM    WARRANT   10:30 + 18:30  (2/day)
REM  Each wake is one claude -p session (one assignment or a heartbeat), so
REM  the ceiling is 10 headless sessions/day fleet-wide plus TradeOS's two.
REM
REM  PRECONDITIONS before running: wake-prompt.md + scripts\wake.ps1 exist in
REM  each repo below (PROJECTOS's are committed; other seats commit their own
REM  copies from the template in the REMOVE-THE-GO report), and the founder
REM  has ratified the cadence. INBOX-AUTH enforcing is strongly recommended
REM  first: an unattended seat should refuse unsigned instructions.
REM ============================================================================

schtasks /create /tn "FLEET\WAKE-TRADEOS-AM"   /tr "powershell -NoProfile -ExecutionPolicy Bypass -File C:\dev\TradeOS-AI\scripts\wake.ps1 -RepoRoot C:\dev\TradeOS-AI -Seat TRADEOS" /sc daily /st 08:40 /f
schtasks /create /tn "FLEET\WAKE-TRADEOS-PM"   /tr "powershell -NoProfile -ExecutionPolicy Bypass -File C:\dev\TradeOS-AI\scripts\wake.ps1 -RepoRoot C:\dev\TradeOS-AI -Seat TRADEOS" /sc daily /st 15:50 /f
schtasks /create /tn "FLEET\WAKE-AIW-AM"       /tr "powershell -NoProfile -ExecutionPolicy Bypass -File C:\AI-Workspace\scripts\wake.ps1 -RepoRoot C:\AI-Workspace -Seat AIW" /sc daily /st 10:00 /f
schtasks /create /tn "FLEET\WAKE-AIW-PM"       /tr "powershell -NoProfile -ExecutionPolicy Bypass -File C:\AI-Workspace\scripts\wake.ps1 -RepoRoot C:\AI-Workspace -Seat AIW" /sc daily /st 18:00 /f
schtasks /create /tn "FLEET\WAKE-WEB-AM"       /tr "powershell -NoProfile -ExecutionPolicy Bypass -File C:\Push-to-Prod-2026\aiworkspace-hq-web\scripts\wake.ps1 -RepoRoot C:\Push-to-Prod-2026\aiworkspace-hq-web -Seat WEB" /sc daily /st 10:10 /f
schtasks /create /tn "FLEET\WAKE-WEB-PM"       /tr "powershell -NoProfile -ExecutionPolicy Bypass -File C:\Push-to-Prod-2026\aiworkspace-hq-web\scripts\wake.ps1 -RepoRoot C:\Push-to-Prod-2026\aiworkspace-hq-web -Seat WEB" /sc daily /st 18:10 /f
schtasks /create /tn "FLEET\WAKE-PROJECTOS-AM" /tr "powershell -NoProfile -ExecutionPolicy Bypass -File C:\ProjectOS-AI\scripts\wake.ps1" /sc daily /st 10:20 /f
schtasks /create /tn "FLEET\WAKE-PROJECTOS-PM" /tr "powershell -NoProfile -ExecutionPolicy Bypass -File C:\ProjectOS-AI\scripts\wake.ps1" /sc daily /st 18:20 /f
schtasks /create /tn "FLEET\WAKE-WARRANT-AM"   /tr "powershell -NoProfile -ExecutionPolicy Bypass -File C:\Push-to-Prod-2026\warrant\scripts\wake.ps1 -RepoRoot C:\Push-to-Prod-2026\warrant -Seat WARRANT" /sc daily /st 10:30 /f
schtasks /create /tn "FLEET\WAKE-WARRANT-PM"   /tr "powershell -NoProfile -ExecutionPolicy Bypass -File C:\Push-to-Prod-2026\warrant\scripts\wake.ps1 -RepoRoot C:\Push-to-Prod-2026\warrant -Seat WARRANT" /sc daily /st 18:30 /f

echo Done. Verify with: schtasks /query /tn "FLEET\" /fo LIST
