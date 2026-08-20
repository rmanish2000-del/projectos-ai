' Hidden launcher for the fleet's scheduled tasks (PROJECTOS-HIDDEN-TASKS-02).
'
' Why this exists: every FLEET task launched powershell.exe directly, and
' powershell always allocates a console, so each wake and every two-minute
' auto-sign sweep flashed a window over whatever the founder was doing.
'
' Why a WSH shim rather than the alternatives, in one line each:
'   -WindowStyle Hidden      still allocates the console first; it flashes.
'   Run-whether-logged-on-or-not runs in session 0 - which loses the mapped
'                            G: drive the whole fleet reads and writes.
'   SYSTEM                   loses the user profile, so the k1 keyring at
'                            %USERPROFILE%\.projectos\ disappears - and the
'                            assignment forbids it anyway.
' wscript.exe //B is itself windowless, and WshShell.Run with window style 0
' starts the child with no console at all, INSIDE the same interactive user
' session - so identity, the G: mapping and the keyring are all unchanged.
'
' Failure stays visible: Run(..., True) waits for the child and returns its
' exit code, which is passed straight to Task Scheduler's Last Result. A
' failing wake still writes its WAKE-FAILURE file to Drive exactly as before;
' this shim changes where the window goes, never what the wake does.
'
' Usage (as a task action):
'   wscript.exe //B //Nologo C:\ProjectOS-AI\scripts\run-hidden.vbs ^
'       powershell -NoProfile -ExecutionPolicy Bypass -File <script> [args]

Option Explicit

Dim shell, i, part, commandLine, exitCode
Set shell = CreateObject("WScript.Shell")

If WScript.Arguments.Count = 0 Then
    ' Nothing to run is a configuration error, not a silent success.
    WScript.Quit 2
End If

commandLine = ""
For i = 0 To WScript.Arguments.Count - 1
    part = WScript.Arguments(i)
    ' Re-quote any argument containing spaces; WSH strips the original quotes.
    If InStr(part, " ") > 0 And Left(part, 1) <> """" Then
        part = """" & part & """"
    End If
    If i = 0 Then
        commandLine = part
    Else
        commandLine = commandLine & " " & part
    End If
Next

' 0 = hidden window, True = wait, so the exit code is the child's own.
exitCode = shell.Run(commandLine, 0, True)
WScript.Quit exitCode
