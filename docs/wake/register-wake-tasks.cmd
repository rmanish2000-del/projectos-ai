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
REM  CHAT-AUTO-RESTOCK is budgeted SEPARATELY from that ceiling: every 20
REM  minutes 09:00-19:00 IST = 31 passes/day, but a pass is verify/restock
REM  or a heartbeat - no build work, no test gates, typically far shorter
REM  than a seat wake. Worst day: 31 short sessions + 10 seat sessions.
REM  The restocker prompt is wake-prompt-chat.md (its own contract, v4
REM  rules inherited); it holds NO founder authority - anything needing
REM  judgment lands in AGENT-REPORTS\FOUNDER-QUEUE.md.
REM
REM  HIDDEN WINDOWS (PROJECTOS-HIDDEN-TASKS-02). Every action below launches
REM  through scripts\run-hidden.vbs instead of powershell.exe directly, so no
REM  console flashes over the founder's screen. The shim keeps the SAME
REM  interactive user, so the mapped G: drive and the k1 keyring under
REM  %USERPROFILE% both still resolve, and it passes the child's exit code
REM  straight through - a failing wake still writes its WAKE-FAILURE file and
REM  still shows a nonzero Last Result. Do NOT "simplify" this to
REM  -WindowStyle Hidden (the console is allocated before it is hidden, so it
REM  flashes) or to run-whether-logged-on / SYSTEM (session 0 has no G: and
REM  no user profile, which breaks reading the INBOX and the key).
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
schtasks /create /tn "FLEET\WAKE-CHAT-RESTOCK" /tr "powershell -NoProfile -ExecutionPolicy Bypass -File C:\ProjectOS-AI\scripts\wake.ps1 -Seat CHAT-AUTO-RESTOCK -PromptFile wake-prompt-chat.md" /sc daily /st 09:00 /ri 20 /du 10:00 /f
schtasks /create /tn "FLEET\WAKE-PROJECTOS-AM" /tr "powershell -NoProfile -ExecutionPolicy Bypass -File C:\ProjectOS-AI\scripts\wake.ps1" /sc daily /st 10:20 /f
schtasks /create /tn "FLEET\WAKE-PROJECTOS-PM" /tr "powershell -NoProfile -ExecutionPolicy Bypass -File C:\ProjectOS-AI\scripts\wake.ps1" /sc daily /st 18:20 /f
schtasks /create /tn "FLEET\WAKE-WARRANT-AM"   /tr "powershell -NoProfile -ExecutionPolicy Bypass -File C:\Push-to-Prod-2026\warrant\scripts\wake.ps1 -RepoRoot C:\Push-to-Prod-2026\warrant -Seat WARRANT" /sc daily /st 10:30 /f
schtasks /create /tn "FLEET\WAKE-WARRANT-PM"   /tr "powershell -NoProfile -ExecutionPolicy Bypass -File C:\Push-to-Prod-2026\warrant\scripts\wake.ps1 -RepoRoot C:\Push-to-Prod-2026\warrant -Seat WARRANT" /sc daily /st 18:30 /f

echo Done. Verify with: schtasks /query /tn "FLEET\" /fo LIST
