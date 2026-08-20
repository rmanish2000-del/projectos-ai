@echo off
REM ============================================================================
REM  FOUNDER-RUN ONLY (REMOVE-THE-GO). Registering these tasks is the one-time
REM  enablement act the assignment reserves for the founder. No seat runs this.
REM  Run it from an ELEVATED prompt: tasks created in another context cannot be
REM  modified later without the account password.
REM
REM  CADENCE: ONE task per seat, repeating every 20 minutes across the working
REM  day 09:00-19:00, staggered 3 minutes apart so two seats never touch Drive
REM  on the same minute (PROJECTOS-P0-WAKE-CADENCE). The old twice-daily
REM  cadence left assignments sitting untouched for hours.
REM
REM  ONE TASK PER SEAT, NOT TWO. The previous -AM/-PM pairs made sense only
REM  while each fired once. With a 20-minute repeat a surviving pair would
REM  double every seat's session count, so the obsolete names are deleted
REM  first, below. Deleting them is part of this act, not a side effect.
REM
REM  OVERLAP PROTECTION IS REQUIRED AT THIS CADENCE and lives in wake.ps1: a
REM  per-seat lock recording the owner's pid AND that process's start time.
REM  A second wake arriving while the seat is still working exits 0 quietly -
REM  no WAKE-FAILURE, no Drive report - and the running session is never
REM  interrupted. Staleness is decided by proving the owner is dead, never by
REM  a timeout that could expire under a long legitimate gate run.
REM
REM  COST WARNING, measured 2026-08-20: this cadence multiplies engine sessions
REM  roughly 15x per seat (2/day -> ~30/day). On the day it was written BOTH
REM  engines were already exhausted - claude "out of usage credits", codex
REM  "hit your usage limit". Idle wakes are cheap but not free. Ratify the
REM  spend before enabling, and watch AGENT-REPORTS\FLEET-USAGE.md.
REM
REM  HIDDEN WINDOWS (PROJECTOS-HIDDEN-TASKS-02). Every action launches through
REM  scripts\run-hidden.vbs instead of powershell.exe directly, so no console
REM  flashes over the founder's screen. The shim keeps the SAME interactive
REM  user, so the mapped G: drive and the k1 keyring under %USERPROFILE% both
REM  still resolve, and it passes the child's exit code straight through - a
REM  failing wake still writes its WAKE-FAILURE file and still shows a nonzero
REM  Last Result. Do NOT "simplify" this to -WindowStyle Hidden (the console is
REM  allocated before it is hidden, so it flashes) or to run-whether-logged-on
REM  / SYSTEM (session 0 has no G: and no user profile, which breaks reading
REM  the INBOX and the key).
REM
REM  CHAT-AUTO-RESTOCK runs the deterministic Python restocker, not a model
REM  session, so its passes are far cheaper than a seat wake. It holds NO
REM  founder authority - anything needing judgment lands in
REM  AGENT-REPORTS\FOUNDER-QUEUE.md. It stays DISABLED until CODEX's
REM  SAFE-TO-ENABLE verdict changes; registering it does not enable it.
REM
REM  PRECONDITIONS: wake-prompt.md + scripts\wake.ps1 exist in each repo below
REM  (PROJECTOS's are committed; other seats commit their own copies from the
REM  template in the REMOVE-THE-GO report), the founder has ratified the
REM  cadence and its cost, and INBOX-AUTH is enforcing so an unattended seat
REM  refuses unsigned instructions.
REM ============================================================================

REM --- retire the obsolete twice-daily pairs before creating the new tasks ---
schtasks /delete /tn "FLEET\WAKE-TRADEOS-AM"   /f 2>nul
schtasks /delete /tn "FLEET\WAKE-TRADEOS-PM"   /f 2>nul
schtasks /delete /tn "FLEET\WAKE-AIW-AM"       /f 2>nul
schtasks /delete /tn "FLEET\WAKE-AIW-PM"       /f 2>nul
schtasks /delete /tn "FLEET\WAKE-WEB-AM"       /f 2>nul
schtasks /delete /tn "FLEET\WAKE-WEB-PM"       /f 2>nul
schtasks /delete /tn "FLEET\WAKE-PROJECTOS-AM" /f 2>nul
schtasks /delete /tn "FLEET\WAKE-PROJECTOS-PM" /f 2>nul
schtasks /delete /tn "FLEET\WAKE-WARRANT-AM"   /f 2>nul
schtasks /delete /tn "FLEET\WAKE-WARRANT-PM"   /f 2>nul

REM --- one repeating, window-less task per seat ---
schtasks /create /tn "FLEET\WAKE-TRADEOS"   /tr "wscript.exe //B //Nologo C:\ProjectOS-AI\scripts\run-hidden.vbs powershell -NoProfile -ExecutionPolicy Bypass -File C:\dev\TradeOS-AI\scripts\wake.ps1 -RepoRoot C:\dev\TradeOS-AI -Seat TRADEOS" /sc daily /st 09:00 /ri 20 /du 10:00 /f
schtasks /create /tn "FLEET\WAKE-AIW"       /tr "wscript.exe //B //Nologo C:\ProjectOS-AI\scripts\run-hidden.vbs powershell -NoProfile -ExecutionPolicy Bypass -File C:\AI-Workspace\scripts\wake.ps1 -RepoRoot C:\AI-Workspace -Seat AIW" /sc daily /st 09:03 /ri 20 /du 10:00 /f
schtasks /create /tn "FLEET\WAKE-WEB"       /tr "wscript.exe //B //Nologo C:\ProjectOS-AI\scripts\run-hidden.vbs powershell -NoProfile -ExecutionPolicy Bypass -File C:\Push-to-Prod-2026\aiworkspace-hq-web\scripts\wake.ps1 -RepoRoot C:\Push-to-Prod-2026\aiworkspace-hq-web -Seat WEB" /sc daily /st 09:06 /ri 20 /du 10:00 /f
schtasks /create /tn "FLEET\WAKE-PROJECTOS" /tr "wscript.exe //B //Nologo C:\ProjectOS-AI\scripts\run-hidden.vbs powershell -NoProfile -ExecutionPolicy Bypass -File C:\ProjectOS-AI\scripts\wake.ps1" /sc daily /st 09:09 /ri 20 /du 10:00 /f
schtasks /create /tn "FLEET\WAKE-WARRANT"   /tr "wscript.exe //B //Nologo C:\ProjectOS-AI\scripts\run-hidden.vbs powershell -NoProfile -ExecutionPolicy Bypass -File C:\Push-to-Prod-2026\warrant\scripts\wake.ps1 -RepoRoot C:\Push-to-Prod-2026\warrant -Seat WARRANT" /sc daily /st 09:12 /ri 20 /du 10:00 /f
schtasks /create /tn "FLEET\WAKE-CHAT-RESTOCK" /tr "wscript.exe //B //Nologo C:\ProjectOS-AI\scripts\run-hidden.vbs powershell -NoProfile -ExecutionPolicy Bypass -File C:\ProjectOS-AI\scripts\wake.ps1 -Seat CHAT-AUTO-RESTOCK -PromptFile wake-prompt-chat.md" /sc daily /st 09:15 /ri 20 /du 10:00 /f
schtasks /change /tn "FLEET\WAKE-CHAT-RESTOCK" /disable

REM --- the two-minute signer, also window-less ---
schtasks /create /tn "FLEET\AUTO-SIGN" /tr "wscript.exe //B //Nologo C:\ProjectOS-AI\scripts\run-hidden.vbs powershell -NoProfile -ExecutionPolicy Bypass -File C:\ProjectOS-AI\scripts\auto-sign.ps1" /sc daily /st 00:00 /ri 2 /du 24:00 /f

echo Done. Verify with: schtasks /query /tn "FLEET\" /fo LIST
echo Every action should read wscript.exe, and every WAKE task /ri 20.
