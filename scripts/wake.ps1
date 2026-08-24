# Headless seat wake wrapper (REMOVE-THE-GO). One wake = one loop pass.
# Launched by Task Scheduler; runnable by hand for a dry-run. The prompt is
# wake-prompt.md in the repo root - versioned, never an inline string here.
#
# Exit codes: 0 = loop completed, or a normal skip because the seat was
# already running - 1 = the engine exited nonzero, or a wrapper tripwire
# fired - 2 = could not even start (missing prompt/CLI). Every real failure
# leaves a WAKE-FAILURE file on Drive so silence is impossible. A SKIP is
# not a failure and deliberately leaves nothing on Drive.
#
# Engines: grok | codex | claude (default codex). Grok uses official xAI CLI
# headless: grok -p "..." with XAI_API_KEY in environment (never argv).
param(
    [string]$RepoRoot = "C:\ProjectOS-AI",
    [string]$Seat = "PROJECTOS",
    [string]$ReportsDir = "G:\My Drive\AGENT-REPORTS",
    [string]$PromptFile = "wake-prompt.md",
    [ValidateSet("grok", "claude", "codex")]
    [string]$Engine = "codex"
)

$ErrorActionPreference = "Stop"
Set-Location $RepoRoot

$StateDir = Join-Path $env:USERPROFILE ".projectos"
if (-not (Test-Path $StateDir)) { New-Item -ItemType Directory -Force $StateDir | Out-Null }
$LockFile = Join-Path $StateDir "wake-$Seat.lock"
$LocalLog = Join-Path $StateDir "wake-$Seat.log"
$UsageLog = Join-Path $StateDir "wake-usage.log"
$BackoffFile = Join-Path $StateDir "wake-$Seat.backoff.json"
$StderrFile = Join-Path $StateDir "wake-$Seat.stderr"
# The engine writes its DIAGNOSIS to stdout, not stderr. On 2026-08-24 a
# WARRANT wake printed "STATUS: FAILED - law resolver could not start" on
# stdout, wrote nothing to stderr at all, and the wrapper recorded
# "OK: wake completed". Capturing only stderr is why two days of
# diagnosis had nothing to read.
$TranscriptFile = Join-Path $StateDir "wake-$Seat.transcript"
$script:HoldsLock = $false

$BackoffBaseMinutes = 20
$BackoffCeilingMinutes = 360

function Write-LocalLog([string]$line) {
    $when = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    Add-Content -Path $LocalLog -Value "$when [$Seat] $line" -Encoding utf8
}

function Write-WakeFailure([string]$why) {
    try { $stamp = py -3.11 -m projectos.infrastructure.fleet_clock }
    catch { $stamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd_HHmm") + "-UTC-ASSUMED" }
    $target = Join-Path $ReportsDir "${stamp}_${Seat}_WAKE-FAILURE.md"
    "WAKE FAILURE ($Seat): $why" | Out-File -FilePath $target -Encoding utf8
    Write-LocalLog "WAKE-FAILURE: $why"
}

# CHAT-AUTO-RESTOCK is a deterministic program, not an agent session.
# This branch is deliberately before prompt/CLI discovery: untrusted report
# text can never enter the same context as instructions, and the restocker has
# no model tools with which to merge, ratify, edit a repo, or self-issue.
function Release-SeatLock {
    if (-not $script:HoldsLock) { return }
    if (Test-Path $LockFile) {
        $raw = Get-Content $LockFile -Raw -ErrorAction SilentlyContinue
        if ($raw -match "pid=$PID(\D|$)") { Remove-Item $LockFile -Force -ErrorAction SilentlyContinue }
    }
    $script:HoldsLock = $false
}

function Exit-Wake([int]$code) {
    Release-SeatLock
    exit $code
}

function Get-BackoffState {
    if (-not (Test-Path $BackoffFile)) {
        return @{ consecutive = 0; last_class = ""; next_eligible = $null }
    }
    try {
        $j = Get-Content $BackoffFile -Raw | ConvertFrom-Json
        return @{
            consecutive = [int]$j.consecutive
            last_class = [string]$j.last_class
            next_eligible = $j.next_eligible
        }
    } catch {
        return @{ consecutive = 0; last_class = ""; next_eligible = $null }
    }
}

function Save-BackoffState($state) {
    ($state | ConvertTo-Json -Compress) | Set-Content -Path $BackoffFile -Encoding utf8
}

function Record-FailureClass([string]$class) {
    $s = Get-BackoffState
    if ($s.last_class -eq $class -and $class -ne "") {
        $s.consecutive = [int]$s.consecutive + 1
    } else {
        $s.consecutive = 1
        $s.last_class = $class
    }
    if ($s.consecutive -ge 2) {
        $exp = [Math]::Min($s.consecutive - 1, 5)
        $delay = [Math]::Min($BackoffBaseMinutes * [Math]::Pow(2, $exp), $BackoffCeilingMinutes)
        $s.next_eligible = (Get-Date).AddMinutes($delay).ToString("o")
        Write-LocalLog "BACKOFF: class=$class consecutive=$($s.consecutive) next_eligible=$($s.next_eligible) delay_min=$delay"
    }
    Save-BackoffState $s
}

function Record-Success {
    Save-BackoffState @{ consecutive = 0; last_class = ""; next_eligible = $null }
    Write-LocalLog "BACKOFF reset on success"
}

function Write-UsageLine {
    try {
        $day = (Get-Date).ToString("yyyy-MM-dd")
        $todaysSessions = @(Get-Content $UsageLog -ErrorAction SilentlyContinue |
            Where-Object { $_ -like "$day|$Seat|*" }).Count
        $usageDrive = Join-Path $ReportsDir "FLEET-USAGE.md"
        if (-not (Test-Path $usageDrive)) {
            Set-Content -Path $usageDrive -Encoding utf8 -Value @(
                "# FLEET USAGE - one line per wake session that reached an engine",
                "",
                "Session counts and engines are measured. Provider token counts are NOT",
                "available to the wrapper and are never estimated here. A failed session",
                "still counts: it consumed quota.",
                ""
            )
        }
        Add-Content -Path $usageDrive -Encoding utf8 `
            -Value "$day | $Seat | engine=$Engine | session #$todaysSessions today"
    } catch {
        Write-LocalLog "usage line could not be written: $($_.Exception.Message)"
    }
}

$bo = Get-BackoffState
if ($bo.next_eligible) {
    try {
        $eligible = [DateTime]::Parse($bo.next_eligible)
        if ((Get-Date) -lt $eligible) {
            Write-LocalLog "SKIP: backoff active until $($bo.next_eligible) (class=$($bo.last_class) consecutive=$($bo.consecutive))"
            exit 0
        }
    } catch { }
}

if (Test-Path $LockFile) {
    $raw = Get-Content $LockFile -Raw -ErrorAction SilentlyContinue
    $ownerPid = 0
    $ownerTicks = ""
    if ($raw -match "pid=(\d+)") { $ownerPid = [int]$Matches[1] }
    if ($raw -match "startticks=(\d+)") { $ownerTicks = $Matches[1] }
    $owner = $null
    if ($ownerPid -gt 0) { $owner = Get-Process -Id $ownerPid -ErrorAction SilentlyContinue }
    $ownerIsLive = $false
    if ($null -ne $owner) {
        try { $ownerIsLive = ($owner.StartTime.Ticks.ToString() -eq $ownerTicks) }
        catch { $ownerIsLive = $true }
    }
    if ($ownerIsLive) {
        Write-LocalLog "SKIP: seat already running (owner pid $ownerPid); this wake exits without claiming"
        exit 0
    }
    Write-LocalLog "STALE LOCK cleared: owner pid $ownerPid is not alive (recorded start $ownerTicks)"
    Remove-Item $LockFile -Force -ErrorAction SilentlyContinue
}

$self = Get-Process -Id $PID
@(
    "pid=$PID",
    "startticks=$($self.StartTime.Ticks)",
    "seat=$Seat",
    "engine=$Engine",
    "since=$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))"
) | Set-Content -Path $LockFile -Encoding utf8
$script:HoldsLock = $true

$today = (Get-Date).ToString("yyyy-MM-dd")
Add-Content -Path $UsageLog -Value "$today|$Seat|$Engine" -Encoding utf8

if ($Seat -eq "CHAT-AUTO-RESTOCK") {
    $config = Join-Path $RepoRoot "docs\wake\chat-restock-config.json"
    if (-not (Test-Path $config)) {
        Write-WakeFailure "chat-restock-config.json missing"
        Record-FailureClass "missing-restock-config"
        Exit-Wake 2
    }
    try {
        py -3.11 -m projectos.infrastructure.chat_auto_restock --reports-dir $ReportsDir --config $config
        $restockExit = $LASTEXITCODE
    } catch {
        Write-WakeFailure "deterministic restocker could not start"
        Record-FailureClass "restock-start"
        Exit-Wake 2
    }
    if ($restockExit -ne 0) {
        Write-WakeFailure "deterministic restocker exited $restockExit"
        Record-FailureClass "restock-exit-$restockExit"
        Exit-Wake 1
    }
    Record-Success
    Exit-Wake 0
}

# A seat's boot prompt must not be a BRANCH ARTIFACT. On 2026-08-24 WEB had
# no prompt at all: it had been committed to feature/callback-redirect-only,
# the seat moved to feature/payer-gets-something, and the file vanished from
# the working tree. The seat then failed every wake for a reason that had
# nothing to do with its work. So the repo copy is preferred, and a
# branch-independent copy under the state directory is the fallback.
$prompt = Join-Path $RepoRoot $PromptFile
if (-not (Test-Path $prompt)) {
    $fallback = Join-Path $StateDir "prompts\$Seat-wake-prompt.md"
    if (Test-Path $fallback) {
        Write-LocalLog "PROMPT-FALLBACK: $PromptFile absent in $RepoRoot (branch $(git -C $RepoRoot rev-parse --abbrev-ref HEAD 2>$null)); using $fallback"
        $prompt = $fallback
    }
    else {
        Write-WakeFailure "$PromptFile missing at $prompt (RepoRoot=$RepoRoot) and no fallback at $fallback. A prompt committed only to a feature branch disappears when the seat switches branches - keep the fallback copy current."
        Record-FailureClass "missing-prompt"
        Exit-Wake 2
    }
}
# --- DRIVE STAGING ---------------------------------------------------------
# Proven on 2026-08-24 by three controlled runs against codex-cli 0.149.1:
#   --add-dir "G:\My Drive\AGENT-REPORTS"  -> sandbox helper never starts
#       ("Failed to create unified exec process: setup refresh had errors")
#   no --add-dir at all                     -> commands run, but every read
#       AND write of G:\ is "Access is denied"
#   --add-dir <local NTFS dir>              -> commands run, reads and writes
#       both work
# A junction from C:\ to the Drive folder fails exactly like the direct path,
# so the Drive provider itself is what the sandbox cannot set up. The engine
# therefore never touches Drive: the WRAPPER, which is not sandboxed and
# already writes WAKE-FAILURE files there, stages work in and copies results
# out. Nothing here needs a new permission, and removing it restores the old
# behaviour exactly.
$StageDir = Join-Path $StateDir "stage\$Seat"
$StageInbox = Join-Path $StageDir "INBOX"
$StageOut = Join-Path $StageDir "OUT"
$DoneManifest = Join-Path $StageDir "DONE-MOVES.txt"

function Initialize-Stage {
    if (Test-Path $StageDir) { Remove-Item $StageDir -Recurse -Force -ErrorAction SilentlyContinue }
    New-Item -ItemType Directory -Force -Path $StageInbox | Out-Null
    New-Item -ItemType Directory -Force -Path $StageOut | Out-Null

    $driveInbox = Join-Path $ReportsDir "INBOX"
    if (Test-Path $driveInbox) {
        Copy-Item (Join-Path $driveInbox "*.md") -Destination $StageInbox -ErrorAction SilentlyContinue
    }
    $law = Join-Path $ReportsDir "SEAT-BOOT.md"
    if (Test-Path $law) { Copy-Item $law -Destination $StageDir -ErrorAction SilentlyContinue }

    # Filenames only: the seat needs to see what claims and reports already
    # exist (so it does not duplicate one) without copying 1300 files.
    Get-ChildItem $ReportsDir -File -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty Name |
        Set-Content -Path (Join-Path $StageDir "REPORTS-INDEX.txt") -Encoding utf8
    Write-LocalLog "STAGE-IN: $((Get-ChildItem $StageInbox -File -ErrorAction SilentlyContinue).Count) INBOX files staged to $StageDir"
}

function Publish-Stage {
    # Copy the seat's outputs to Drive, then apply any requested DONE moves.
    # Copy first: a move applied before its report landed would leave an
    # assignment marked done with nothing to show for it.
    $published = @()
    foreach ($f in @(Get-ChildItem $StageOut -File -ErrorAction SilentlyContinue)) {
        Copy-Item $f.FullName -Destination (Join-Path $ReportsDir $f.Name) -Force -ErrorAction SilentlyContinue
        $published += $f.Name
    }
    if ($published.Count -gt 0) {
        Write-LocalLog "STAGE-OUT: published $($published.Count) file(s) to Drive: $($published -join ', ')"
    }
    if (Test-Path $DoneManifest) {
        foreach ($line in (Get-Content $DoneManifest -ErrorAction SilentlyContinue)) {
            $name = $line.Trim()
            if (-not $name) { continue }
            $src = Join-Path (Join-Path $ReportsDir "INBOX") $name
            if (Test-Path $src) {
                Move-Item $src -Destination (Join-Path $ReportsDir "DONE") -Force -ErrorAction SilentlyContinue
                Write-LocalLog "STAGE-DONE: moved $name to DONE"
            }
        }
    }
    return $published
}

Initialize-Stage

# --- THE PROMPT IS BUILT PER WAKE, NOT TRUSTED FROM DISK -------------------
# On 2026-08-24 every seat's on-disk prompt named PROJECTOS's stage directory,
# because the block was injected from an already-substituted copy and the seat
# token was never replaced. AIW and WARRANT therefore wrote their heartbeats
# into stage\PROJECTOS\OUT, the wrapper found its own OUT empty, and failed
# the wake for producing no evidence of work. The static text was wrong and
# nothing could tell.
#
# So the wrapper now states the truth itself, at wake time, from the same
# variables it uses to stage and publish. There is no second place for the
# path to be written down and therefore no second place for it to be wrong.
$StagedPrompt = Join-Path $StageDir "WAKE-PROMPT.md"
$promptHeader = @(
    "# THIS WAKE: you are the $Seat seat",
    "",
    "Everything you read and write for this wake lives under:",
    "",
    "    $StageDir",
    "",
    "- INBOX to read:        $StageInbox",
    "- the law to read:      $StageDir\SEAT-BOOT.md",
    "- existing filenames:   $StageDir\REPORTS-INDEX.txt",
    "- WRITE EVERY OUTPUT:   $StageOut",
    "- to move to DONE:      append the filename to $DoneManifest",
    "",
    "**If anything below names a different stage path, this header wins.** It",
    "was written by the wrapper for this wake and names YOUR seat's directory.",
    "A file you write anywhere else is invisible: the wrapper publishes only",
    "what is in the OUT directory named above.",
    "",
    "---",
    ""
)
Set-Content -Path $StagedPrompt -Value ($promptHeader + (Get-Content $prompt)) -Encoding utf8
Write-LocalLog "STAGE-PROMPT: built for seat $Seat naming $StageOut"

# Staged BEFORE the engine-availability check on purpose: the staged
# prompt records what this wake intended to do, so a wake that dies on a
# missing CLI still leaves that evidence behind instead of nothing.
$cliName = $Engine
$cli = Get-Command $cliName -ErrorAction SilentlyContinue
if ($null -eq $cli) {
    Write-WakeFailure "$cliName CLI not on PATH (Engine=$Engine)"
    Record-FailureClass "missing-cli-$cliName"
    Exit-Wake 2
}


$wakeStart = Get-Date
$reportsBefore = @(Get-ChildItem $ReportsDir -File -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty Name)

if (Test-Path $StderrFile) { Remove-Item $StderrFile -Force -ErrorAction SilentlyContinue }
if (Test-Path $TranscriptFile) { Remove-Item $TranscriptFile -Force -ErrorAction SilentlyContinue }

# PowerShell 5.1 wraps every stderr line of a NATIVE command in a
# NativeCommandError record. Under ErrorActionPreference=Stop that is a
# TERMINATING error, so a healthy engine printing its banner to stderr kills
# the wrapper before it can log anything - exit 1, no log line, no artifact,
# nothing to read. Codex prints its version banner to stderr on every run, so
# this fires every time. Relaxed for the engine call only, restored after.
$enginePreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
if ($Engine -eq "codex") {
    Get-Content $StagedPrompt -Raw | & codex exec - --dangerously-bypass-approvals-and-sandbox --add-dir $StageDir --skip-git-repo-check --color never 1>$TranscriptFile 2>$StderrFile
} elseif ($Engine -eq "grok") {
    # Windows: do not pass --cwd as a separate argv (grok 1.0.5 treats path as unexpected).
    # Already Set-Location $RepoRoot above. Pass -p via argument array for safe quoting.
    $promptText = Get-Content $StagedPrompt -Raw
    $grokArgs = @('--no-auto-update', '--always-approve', '-p', $promptText)
    & grok @grokArgs 1>$TranscriptFile 2>$StderrFile
} else {
    Get-Content $StagedPrompt -Raw | & claude -p 1>$TranscriptFile 2>$StderrFile
}
$engineExit = $LASTEXITCODE
$ErrorActionPreference = $enginePreference

# Publish BEFORE the outcome checks below, so a staged report counts as the
# evidence of work it is. Publishing after would make every successful wake
# look workless and fail it.
$publishedNames = Publish-Stage

Write-UsageLine

$reportsAfter = @(Get-ChildItem $ReportsDir -File -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty Name)
$new = @($reportsAfter | Where-Object { $reportsBefore -notcontains $_ })
$newClaims = @($new | Where-Object { $_ -match "_${Seat}_CLAIM_" })
$newOutcomes = @($new | Where-Object {
        $_ -notmatch "_CLAIM_" -and
        ($_ -match "_${Seat}_" -or $_ -match "HEARTBEAT|PARTIAL|BLOCKED|AUTH-REFUSAL|WAKE-FAILURE")
    })

if ($newClaims.Count -gt 0 -and $newOutcomes.Count -eq 0) {
    Write-WakeFailure "v4 report-contract breach: wake claimed ($($newClaims -join ', ')) and exited with NO report on Drive"
    Record-FailureClass "report-contract-breach"
    Exit-Wake 1
}

if ($newClaims.Count -eq 0) {
    $idleOnly = @($newOutcomes | Where-Object { $_ -match "HEARTBEAT" })
    if ($idleOnly.Count -gt 0 -and $idleOnly.Count -eq $newOutcomes.Count) {
        foreach ($name in $idleOnly) {
            Remove-Item -LiteralPath (Join-Path $ReportsDir $name) -Force -ErrorAction SilentlyContinue
        }
        Write-LocalLog "IDLE: nothing claimable; suppressed Drive heartbeat ($($idleOnly -join ', '))"
    }
}

Start-Sleep -Seconds 5

# Only THIS wake's descendants. The previous check matched every python-ish
# process on the machine started after the wake began, so on 2026-08-24 a WEB
# wake killed two unrelated python processes belonging to another session.
# Killing a bystander is worse than the orphan it was cleaning up, so
# parentage is walked rather than guessed from a name and a timestamp.
function Get-DescendantIds {
    param([int]$RootId)
    $all = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Select-Object ProcessId, ParentProcessId
    $found = @()
    $frontier = @($RootId)
    while ($frontier.Count -gt 0) {
        $next = @()
        foreach ($parent in $frontier) {
            foreach ($proc in $all) {
                if ($proc.ParentProcessId -eq $parent -and $found -notcontains $proc.ProcessId) {
                    $found += $proc.ProcessId
                    $next += $proc.ProcessId
                }
            }
        }
        $frontier = $next
    }
    return $found
}

$descendants = Get-DescendantIds -RootId $PID
if(-not $descendants){$descendants=@(-1)}
$orphans = @(Get-Process -Id $descendants -ErrorAction SilentlyContinue |
    Where-Object { $_.ProcessName -match '^(python|py|pytest|node)' -and $_.StartTime -gt $wakeStart })
if ($orphans.Count -gt 0) {
    $names = ($orphans | ForEach-Object { "$($_.ProcessName):$($_.Id)" }) -join ", "
    $orphans | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-WakeFailure "wake left running processes ($names) - backgrounded work has no owner after exit; stopped"
    Record-FailureClass "orphan-process"
    Exit-Wake 1
}
# Everything a failure report needs, gathered once. A one-line symptom is
# what turned a ten-minute fix into two days, so every WAKE-FAILURE below
# carries the exit code and the tail of what the engine actually said.
function Get-EngineTail {
    $parts = @()
    if (Test-Path $StderrFile) {
        $err = (Get-Content $StderrFile -Tail 25 -ErrorAction SilentlyContinue | Out-String).Trim()
        if ($err) { $parts += "stderr tail:`n$err" }
    }
    if (Test-Path $TranscriptFile) {
        $out = (Get-Content $TranscriptFile -Tail 25 -ErrorAction SilentlyContinue | Out-String).Trim()
        if ($out) { $parts += "transcript tail:`n$out" }
    }
    if ($parts.Count -eq 0) { return "(engine produced no stderr and no stdout)" }
    return ($parts -join "`n`n")
}

# What the engine said, on BOTH streams. Which stream a given engine uses is
# its choice and it changes between versions: codex puts its banner and its
# exec-helper rejections on stderr and its own STATUS line on stdout. A check
# that reads one stream picks the wrong failure class half the time.
$engineSaid = ""
foreach ($f in @($TranscriptFile, $StderrFile)) {
    if (Test-Path $f) {
        $engineSaid += (Get-Content $f -Raw -ErrorAction SilentlyContinue)
    }
}

if ($engineExit -ne 0) {
    Write-WakeFailure "engine exited $engineExit`n$(Get-EngineTail)"
    Record-FailureClass "engine-exit-$engineExit"
    Exit-Wake 1
}

# --- NO FALSE SUCCESS, AND NO FALSE FAILURE -------------------------------
# Exit 0 is the engine saying "I finished", not "I did the work". On
# 2026-08-24 codex exited 0 having declared STATUS: FAILED, claimed nothing
# and written no report - and this wrapper logged OK.
#
# But the first version of this guard over-corrected: it failed any wake whose
# transcript mentioned a helper rejection, even when the engine had RETRIED,
# recovered, resolved the law and published a heartbeat. A recovered error is
# not a failed wake. So evidence of work is decided FIRST, and the transcript
# is only consulted when there is none.
$hasEvidence = ($newClaims.Count -gt 0) -or ($newOutcomes.Count -gt 0) -or ($publishedNames.Count -gt 0)

if (-not $hasEvidence) {
    if ($engineSaid -match 'Failed to create unified exec process|helper_unknown_error') {
        Write-WakeFailure "engine cannot execute commands on this machine (exec helper rejected) and produced nothing - the seat could reason but could not run the law resolver, verify a stamp or write a report`n$(Get-EngineTail)"
        Record-FailureClass "engine-exec-helper-rejected"
        Exit-Wake 1
    }
    if ($engineSaid -match 'STATUS:\s*FAILED|LAW-VERSION:\s*UNRESOLVED') {
        Write-WakeFailure "engine exited 0 but declared failure in its own output and produced nothing`n$(Get-EngineTail)"
        Record-FailureClass "engine-declared-failure"
        Exit-Wake 1
    }
    Write-WakeFailure "engine exited 0 with no evidence of work: no claim, no report and no heartbeat`n$(Get-EngineTail)"
    Record-FailureClass "no-evidence-of-work"
    Exit-Wake 1
}

Write-LocalLog "OK: wake completed (engine=$Engine)"
Record-Success
Exit-Wake 0

