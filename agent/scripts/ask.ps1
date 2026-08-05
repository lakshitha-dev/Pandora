<#
.SYNOPSIS
    Ask the Pandora Knowledge Guardian a question and read the Situation Report.

.DESCRIPTION
    The everyday driver for the agent service. Give it a question in plain
    language and it runs the whole pipeline, then prints the assembled report
    the way a guardian would read it.

    Two paths, because the service has two:

      (default)  POST /agent/sitrep  - Layer 5. The orchestrator classifies and
                 triages the question, then three specialists fill their own
                 sections concurrently. Slower (~60-90s on gpt-5-mini) and it
                 is what the demo shows.

      -Fast      POST /rag/query     - Layer 1. One grounded, cited answer over
                 unfiltered retrieval, ~20-30s. This is also what the
                 orchestrator degrades to, so it is worth seeing on its own.

    Exit code is 0 when the corpus could answer, 1 when it refused or errored,
    so this composes into a larger script.

    NOTE: ASCII only, deliberately. Windows PowerShell 5.1 reads .ps1 files as
    ANSI, so a stray em-dash or box-drawing character is a parse error on a
    teammate's machine even though it looks fine here.

.PARAMETER Question
    The question. Positional - quotes only needed if it contains characters
    PowerShell would otherwise eat.

.EXAMPLE
    .\scripts\ask.ps1 "The water near Awa Reef has turned turquoise and the fish are leaving."

.EXAMPLE
    .\scripts\ask.ps1 "Which species are vulnerable to water contamination?" -Fast

.EXAMPLE
    .\scripts\ask.ps1 "What is the W3 classification?" -Full -Json
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]] $Question,

    # Layer 1 single grounded answer instead of the orchestrated report.
    [switch] $Fast,

    # Print every section in full rather than truncating to a preview.
    [switch] $Full,

    # Dump the raw JSON response after the readable report.
    [switch] $Json,

    # Force a routing mode; only meaningful without -Fast.
    [ValidateSet('sitrep', 'focused', 'compare')]
    [string] $Mode,

    [string] $BaseUrl = 'http://127.0.0.1:8000',

    [int] $TimeoutSec = 280
)

$ErrorActionPreference = 'Stop'

# --- question ---------------------------------------------------------------
$q = ($Question -join ' ').Trim()
if (-not $q) { $q = (Read-Host 'Question').Trim() }
if (-not $q) { Write-Host 'No question given.' -ForegroundColor Red; exit 1 }

# --- key: read the same .env the service reads, so they cannot drift ---------
$key = 'dev-internal-key-change-me'
$envFile = Join-Path $PSScriptRoot '..\.env'
if (Test-Path $envFile) {
    $line = Select-String -Path $envFile -Pattern '^\s*AGENT_SERVICE_KEY\s*=' -ErrorAction SilentlyContinue |
            Select-Object -First 1
    if ($line) { $key = ($line.Line -split '=', 2)[1].Trim() }
}
$headers = @{ 'X-Internal-Key' = $key; 'Content-Type' = 'application/json' }

function Write-Rule([string] $Text) {
    Write-Host ''
    Write-Host ('=' * 78) -ForegroundColor DarkCyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host ('=' * 78) -ForegroundColor DarkCyan
}

function Write-Field([string] $Label, $Value, [string] $Colour = 'Gray') {
    Write-Host ("  {0,-12}" -f $Label) -NoNewline -ForegroundColor DarkGray
    Write-Host $Value -ForegroundColor $Colour
}

# --- is the service even up? a clear message beats a raw connection error ----
try {
    $health = Invoke-RestMethod -Uri "$BaseUrl/health" -TimeoutSec 20
} catch {
    Write-Host ''
    Write-Host "Cannot reach the agent service at $BaseUrl" -ForegroundColor Red
    Write-Host 'Start it with:' -ForegroundColor DarkGray
    Write-Host ("  cd {0}" -f (Split-Path $PSScriptRoot -Parent))
    Write-Host '  python -m uvicorn app.main:app --port 8000'
    Write-Host ''
    exit 1
}
if (-not $health.corpus_indexed) {
    Write-Host ''
    Write-Host 'The corpus is not indexed. Seed it first:' -ForegroundColor Red
    Write-Host '  python -m scripts.seed_corpus'
    Write-Host ''
    exit 1
}

$endpoint = if ($Fast) { '/rag/query' } else { '/agent/sitrep' }
$layer    = if ($Fast) { 'Layer 1 - grounded answer' } else { 'Layer 5 - orchestrated Situation Report' }

Write-Host ''
Write-Host '  PANDORA KNOWLEDGE GUARDIAN' -ForegroundColor Cyan
Write-Host "  $layer" -ForegroundColor DarkGray
Write-Host ''
Write-Host '  Q: ' -NoNewline -ForegroundColor DarkGray
Write-Host $q -ForegroundColor White
Write-Host ''
Write-Host '  working' -NoNewline -ForegroundColor DarkGray

$payload = @{ question = $q }
if ($Mode -and -not $Fast) { $payload.mode = $Mode }
$body = $payload | ConvertTo-Json

# Keep a heartbeat on screen - a 90s silent wait looks like a hang.
$job = Start-Job -ScriptBlock {
    param($u, $h, $b, $t)
    try {
        $r = Invoke-RestMethod -Uri $u -Method Post -Headers $h -Body $b -TimeoutSec $t
        @{ ok = $true; data = $r }
    } catch {
        @{ ok = $false; error = $_.Exception.Message }
    }
} -ArgumentList "$BaseUrl$endpoint", $headers, $body, $TimeoutSec

$sw = [Diagnostics.Stopwatch]::StartNew()
while ($job.State -eq 'Running') {
    Start-Sleep -Milliseconds 1000
    Write-Host '.' -NoNewline -ForegroundColor DarkGray
    if ($sw.Elapsed.TotalSeconds -gt ($TimeoutSec + 15)) { break }
}
$result = Receive-Job $job -Wait -AutoRemoveJob
$sw.Stop()
Write-Host ''

if (-not $result.ok) {
    Write-Host ''
    Write-Host "  Request failed: $($result.error)" -ForegroundColor Red
    Write-Host ''
    exit 1
}
$r = $result.data

# --- normalise the two response shapes into one -----------------------------
if ($Fast) {
    $report = $null
    $sections = $r.sections
} else {
    $report = $r.situation_report
    $sections = $report.sections
}
$grounding  = $r.grounding
$sufficient = $r.has_sufficient_evidence
$citations  = $r.citations
$conflicts  = $r.conflicts

# --- the honest refusal is an outcome, not an error -------------------------
if (-not $sufficient) {
    Write-Rule 'NO SUFFICIENT EVIDENCE'
    $msg = $r.insufficient_evidence
    if (-not $msg) {
        $withText = $sections | Where-Object { $_.content } | Select-Object -First 1
        if ($withText) { $msg = $withText.content }
    }
    Write-Host ''
    Write-Host "  $msg" -ForegroundColor Yellow
    Write-Host ''
    Write-Field 'Latency' ("{0:N1}s" -f $sw.Elapsed.TotalSeconds)
    Write-Host ''
    Write-Host '  This is correct behaviour for a question the corpus does not cover.' -ForegroundColor DarkGray
    Write-Host ''
    if ($Json) { $r | ConvertTo-Json -Depth 12 }
    exit 1
}

# --- header -----------------------------------------------------------------
Write-Rule 'SITUATION REPORT'
Write-Host ''
if ($report) {
    $priColour = switch -Regex ($report.priority_class) {
        'W4'    { 'Red' }
        'W3'    { 'Magenta' }
        'W2'    { 'Yellow' }
        default { 'Green' }
    }
    Write-Field 'Priority' ("{0} - {1}" -f $report.priority_class, $report.priority_label) $priColour
    if ($report.priority_reason) {
        Write-Host ("  {0,-12}{1}" -f '', $report.priority_reason) -ForegroundColor DarkGray
    }
    if ($report.priority_citation) { Write-Field 'Cited to' $report.priority_citation DarkGray }
    if ($report.affected_region_ids) { Write-Field 'Regions' ($report.affected_region_ids -join ', ') }
    Write-Field 'Assembly' $report.assembly_mode DarkGray
    Write-Field 'Confidence' ("{0} - {1}" -f $report.confidence_level, $report.confidence_reason)
} else {
    # QueryResponse carries no confidence field - confidence is assembled by the
    # orchestrator, so the Layer 1 path reports its retrieval facts instead.
    Write-Field 'Retrieved' ("{0} chunks (rerank: {1})" -f $r.retrieved_chunk_count, $r.rerank_mode)
}

$rulesOk  = @($grounding.rules | Where-Object { $_.passed }).Count
$rulesAll = @($grounding.rules).Count
$gColour  = if ($grounding.groundedness -ge 90) { 'Green' }
            elseif ($grounding.groundedness -ge 70) { 'Yellow' }
            else { 'Red' }
Write-Field 'Grounding' ("{0}%  ({1}/{2} corpus rules)" -f $grounding.groundedness, $rulesOk, $rulesAll) $gColour
Write-Field 'Latency' ("{0:N1}s" -f $sw.Elapsed.TotalSeconds)
if ($null -ne $r.llm_call_count) { Write-Field 'LLM calls' $r.llm_call_count DarkGray }

# --- sections ---------------------------------------------------------------
foreach ($s in $sections) {
    # A plain Layer 1 answer is carried in the likely_causes slot because the
    # response shape is fixed at three sections. Calling it "LIKELY CAUSES"
    # would misdescribe it, so the Fast path labels it for what it is.
    $heading = if ($Fast) { 'ANSWER' } else { ($s.section_type -replace '_', ' ').ToUpper() }
    Write-Rule $heading

    if ($s.status -ne 'filled') {
        Write-Host ''
        Write-Host ("  [{0}] {1}" -f $s.status, $s.empty_reason) -ForegroundColor DarkYellow
        if ($s.content) {
            Write-Host ''
            Write-Host "  $($s.content)" -ForegroundColor DarkGray
        }
        continue
    }

    Write-Host ''
    $text = $s.content
    if (-not $Full -and $text.Length -gt 1400) {
        $text = $text.Substring(0, 1400) + "`n  ... (re-run with -Full for the rest)"
    }
    foreach ($line in ($text -split "`n")) { Write-Host "  $line" }

    Write-Host ''
    $meta = "claims $($s.supported_claim_count)/$($s.claim_count) cited"
    if ($s.owning_agent) { $meta += " | $($s.owning_agent)" }
    if ($s.duration_ms)  { $meta += " | $($s.duration_ms)ms" }
    Write-Host "  ($meta)" -ForegroundColor DarkGray
}

# --- conflicts: the thing the corpus cares most about -----------------------
if ($conflicts -and @($conflicts).Count -gt 0) {
    Write-Rule 'CONTESTED EVIDENCE'
    Write-Host ''
    foreach ($c in $conflicts) {
        Write-Host ("  {0}" -f ($c.record_ids -join '  vs  ')) -ForegroundColor Yellow
        Write-Host "    $($c.reliability_limitation)" -ForegroundColor DarkGray
        if ($c.description) { Write-Host "    $($c.description)" -ForegroundColor DarkGray }
    }
    Write-Host ''
    Write-Host '  No cause is declared. The corpus requires these be presented, not resolved.' -ForegroundColor DarkGray
}

# --- sources ----------------------------------------------------------------
if ($citations) {
    Write-Rule 'SOURCES'
    Write-Host ''
    foreach ($c in $citations) {
        $pg = if ($c.page) { " p.$($c.page)" } else { '' }
        Write-Host ("  [{0}]{1}" -f $c.record_id, $pg) -NoNewline -ForegroundColor Cyan
        if ($c.title) { Write-Host "  $($c.title)" -ForegroundColor Gray } else { Write-Host '' }
        if ($c.excerpt) {
            $ex = $c.excerpt
            if ($ex.Length -gt 150) { $ex = $ex.Substring(0, 150) + '...' }
            Write-Host "      $ex" -ForegroundColor DarkGray
        }
    }
}

# --- grounding rules --------------------------------------------------------
Write-Rule 'GROUNDING RULES (corpus 15.2)'
Write-Host ''
foreach ($x in $grounding.rules) {
    $mark = if ($x.passed) { 'PASS' } else { 'FAIL' }
    $col  = if ($x.passed) { 'Green' } else { 'Red' }
    Write-Host ("  [{0}] {1}. {2}" -f $mark, $x.number, $x.name) -ForegroundColor $col
    if ($x.detail) { Write-Host "         $($x.detail)" -ForegroundColor DarkGray }
}

if ($grounding.unsupported_sentences -and @($grounding.unsupported_sentences).Count -gt 0) {
    Write-Host ''
    Write-Host '  Sentences with no resolving citation (dropped as unsupported):' -ForegroundColor DarkYellow
    foreach ($u in $grounding.unsupported_sentences) {
        $t = if ($u.Length -gt 100) { $u.Substring(0, 100) + '...' } else { $u }
        Write-Host "    - $t" -ForegroundColor DarkGray
    }
}

Write-Host ''
if ($Json) {
    Write-Rule 'RAW JSON'
    $r | ConvertTo-Json -Depth 12
}

exit 0
