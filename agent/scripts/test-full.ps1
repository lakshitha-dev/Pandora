<#
.SYNOPSIS
    Full end-to-end verification for the Pandora agent service.

.DESCRIPTION
    Covers every endpoint, Layer 1 through Layer 5:

      1. Health          — service up, corpus indexed
      2. Auth gate       — internal key enforced
      3. Upload          — POST /rag/ingest with a real generated document
      4. Layer 1 RAG     — plain grounded answer, the 10 gate questions
      5. Kill shot       — the turquoise-water conflict, 6 criteria (corpus p.48)
      6. Refusal         — out-of-corpus question declines instead of inventing
      7. Layer 5 agentic — POST /agent/sitrep, three specialists, W1-W4 triage

    Exits non-zero if any check fails.

.PARAMETER Quick
    Skip the 10-question retrieval sweep (the slow part). ~3 min instead of ~12.

.PARAMETER SkipAgentic
    Skip section 7 if the orchestrator is not wired yet.

.EXAMPLE
    .\scripts\test-full.ps1
    .\scripts\test-full.ps1 -Quick
#>

[CmdletBinding()]
param(
    [string]$BaseUrl = 'http://127.0.0.1:8000',
    [string]$Key,
    [switch]$Quick,
    [switch]$SkipAgentic,
    [int]$TimeoutSec = 300
)

$ErrorActionPreference = 'Stop'
$script:Failures = 0
$script:Checks = 0

function Write-Head([string]$Text) {
    Write-Host ''
    Write-Host ('=' * 78) -ForegroundColor DarkCyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host ('=' * 78) -ForegroundColor DarkCyan
}
function Write-Pass([string]$Text) {
    Write-Host "  [PASS] $Text" -ForegroundColor Green; $script:Checks++
}
function Write-Fail([string]$Text) {
    Write-Host "  [FAIL] $Text" -ForegroundColor Red; $script:Failures++; $script:Checks++
}
function Write-Info([string]$Text) { Write-Host "         $Text" -ForegroundColor DarkGray }

function Get-EnvKey {
    $p = Join-Path $PSScriptRoot '..\.env'
    if (-not (Test-Path $p)) { return $null }
    foreach ($line in Get-Content $p) {
        if ($line -match '^\s*AGENT_SERVICE_KEY\s*=\s*(.+?)\s*$') { return $Matches[1] }
    }
    return $null
}

function Invoke-Agent {
    param([string]$Path, [hashtable]$Body, [int]$Timeout = 0)
    if ($Timeout -eq 0) { $Timeout = $TimeoutSec }
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $resp = Invoke-RestMethod -Uri "$BaseUrl$Path" -Method Post `
        -Headers @{ 'X-Internal-Key' = $Key } `
        -ContentType 'application/json' `
        -Body ($Body | ConvertTo-Json -Depth 8 -Compress) `
        -TimeoutSec $Timeout
    $sw.Stop()
    return [pscustomobject]@{ R = $resp; S = [math]::Round($sw.Elapsed.TotalSeconds, 1) }
}

if (-not $Key) { $Key = Get-EnvKey }
if (-not $Key) { Write-Host 'ERROR: no AGENT_SERVICE_KEY' -ForegroundColor Red; exit 2 }

$started = Get-Date
Write-Host ''
Write-Host 'Pandora Knowledge Guardian - full verification' -ForegroundColor White
Write-Host "target: $BaseUrl" -ForegroundColor DarkGray

# ── 1. health ────────────────────────────────────────────────────────────
Write-Head '1 - HEALTH'
try { $h = Invoke-RestMethod -Uri "$BaseUrl/health" -TimeoutSec 60 }
catch { Write-Fail "unreachable at $BaseUrl - is uvicorn running?"; exit 1 }

if ($h.search_index_reachable) { Write-Pass 'Azure AI Search reachable' } else { Write-Fail 'Search unreachable' }
if ($h.llm_reachable) { Write-Pass 'Azure OpenAI reachable' } else { Write-Fail 'LLM unreachable' }
if ($h.corpus_indexed) { Write-Pass "corpus indexed - $($h.corpus_chunk_count) chunks, $($h.corpus_record_count) records" }
else { Write-Fail 'corpus NOT indexed - run scripts/seed_corpus.py'; exit 1 }

# ── 2. auth ──────────────────────────────────────────────────────────────
Write-Head '2 - AUTH GATE'
try {
    Invoke-RestMethod -Uri "$BaseUrl/rag/query" -Method Post -ContentType 'application/json' `
        -Body '{"question":"test"}' -TimeoutSec 30 | Out-Null
    Write-Fail 'accepted a request with no internal key'
} catch {
    if ($_.Exception.Response.StatusCode.value__ -eq 401) { Write-Pass 'unauthenticated request rejected (401)' }
    else { Write-Fail "expected 401, got $($_.Exception.Response.StatusCode.value__)" }
}

# ── 3. upload ────────────────────────────────────────────────────────────
Write-Head '3 - UPLOAD PATH (/rag/ingest)'
Write-Info 'a required brief item - PDF/DOCX/CSV/TXT ingestion'

$sample = @"
# Obsidian Reach Field Survey - June 2026

## Vent Activity
Survey teams recorded elevated sulfur readings along the Vitra vent edge on
2026-06-14. Shellfish beds within 200 m of the vent showed mortality.

## Water Column
Dissolved oxygen fell to 3.8 mg/L at the vent edge, well below the seasonal
baseline of 5.9 mg/L recorded in May.

## Recommendations
Close seafood harvest pending laboratory confirmation. Monitor gas readings
twice daily until values return to the normal vent range.
"@
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($sample))
$docId = [guid]::NewGuid().ToString()

try {
    $u = Invoke-Agent -Path '/rag/ingest' -Timeout 180 -Body @{
        document_id    = $docId
        file_name      = 'obsidian-reach-survey-june.txt'
        content_type   = 'text/plain'
        content_base64 = $b64
    }
    $ing = $u.R
    if ($ing.status -eq 'indexed') {
        Write-Pass "ingested in $($u.S)s - $($ing.chunk_count) chunks, mode=$($ing.chunking_mode)"
    } else {
        Write-Fail "ingest failed: $($ing.error_message)"
    }
} catch { Write-Fail "ingest threw: $($_.Exception.Message)" }

# ── 4. retrieval gate ────────────────────────────────────────────────────
if (-not $Quick) {
    Write-Head '4 - LAYER 1 RETRIEVAL GATE'
    Write-Info '7 brief questions + 3 from corpus 15.1 - each must cite its record'
    Write-Host ''

    $gate = @(
        @{ Q = "What are the possible causes of unusual changes in Pandora's ocean water?";                   E = 'INC-001' }
        @{ Q = 'Which marine species are most vulnerable to water contamination?';                            E = 'FAU-'    }
        @{ Q = 'What immediate actions should guardians take after detecting coral damage?';                  E = 'INC-002' }
        @{ Q = 'Compare the recommended responses for water contamination and an underwater volcanic event.'; E = 'INC-00'  }
        @{ Q = 'What traditional community practices can support marine conservation?';                       E = 'POL-'    }
        @{ Q = 'Summarize the major environmental threats mentioned across the reports.';                     E = 'INC-'    }
        @{ Q = 'Which areas should receive emergency attention first, based on the available evidence?';      E = 'INC-'    }
        @{ Q = 'What are the immediate steps when water changes color near Awa Reef?';                        E = 'INC-001' }
        @{ Q = 'Compare Reef Cut Infection and Marine Sting Reaction, including red flags.';                  E = 'MED-'    }
        @{ Q = 'Which accommodations are safest for a traveler with limited mobility during storm season?';   E = 'ACC-'    }
    )

    $hits = 0; $i = 0; $times = @()
    foreach ($g in $gate) {
        $i++
        Write-Host ("  {0,2}. {1}" -f $i, $g.Q.Substring(0, [Math]::Min(60, $g.Q.Length))) -ForegroundColor Gray
        try {
            $r = Invoke-Agent -Path '/rag/query' -Body @{ question = $g.Q }
            $d = $r.R; $times += $r.S
            $cited = @($d.citations | ForEach-Object { $_.record_id })
            $hit = $false
            foreach ($c in $cited) { if ($c -and $c.StartsWith($g.E)) { $hit = $true } }
            if ($hit) { $hits++ }
            $nr = @($d.grounding.rules | Where-Object { $_.passed }).Count
            $col = if ($hit) { 'Green' } else { 'Yellow' }
            Write-Host ("      {0}  {1,5}s  grounded={2,3}%  rules={3}/8" -f `
                $(if ($hit) { 'HIT ' } else { 'MISS' }), $r.S, $d.grounding.groundedness, $nr) -ForegroundColor $col
            Write-Info ("expect {0}  cited: {1}" -f $g.E, ($cited -join ', '))
        } catch { Write-Host ''; Write-Fail "failed: $($_.Exception.Message)" }
    }
    Write-Host ''
    if ($times.Count) {
        $s = $times | Sort-Object
        Write-Info ("latency p50={0}s max={1}s" -f $s[[int]($s.Count/2)], $s[-1])
    }
    if ($hits -ge 8) { Write-Pass "retrieval gate: $hits/10" } else { Write-Fail "retrieval gate: $hits/10 (need 8+)" }
}

# ── 5. kill shot ─────────────────────────────────────────────────────────
Write-Head '5 - KILL SHOT (Layer 1) - the turquoise-water conflict'
try {
    $r = Invoke-Agent -Path '/rag/query' -Body @{
        question     = 'The water near Awa Reef has turned turquoise and the fish are leaving.'
        section_type = 'likely_causes'
    }
    $d = $r.R
    $t = (($d.sections | ForEach-Object { $_.content }) -join "`n").ToLower()

    $crit = @(
        @{ N = 'presents FN-A';            O = $t.Contains('fn-a') }
        @{ N = 'presents FN-B';            O = $t.Contains('fn-b') }
        @{ N = 'presents LAB-C';           O = $t.Contains('lab-c') }
        @{ N = 'flags chain of custody';   O = ($t.Contains('chain of custody') -or $t.Contains('chain-of-custody')) }
        @{ N = 'no confirmed cause';       O = ($t.Contains('not confirmed') -or $t.Contains('no confirmed') -or $t.Contains('cannot be confirmed') -or $t.Contains('remain possible') -or $t.Contains('not established')) }
        @{ N = 'recommends sampling';      O = $t.Contains('sampl') }
    )
    $met = 0
    foreach ($c in $crit) { if ($c.O) { Write-Pass $c.N; $met++ } else { Write-Fail $c.N } }
    Write-Info ("{0}/6  |  {1}s  |  grounded={2}%  |  conflicts={3}" -f $met, $r.S, $d.grounding.groundedness, @($d.conflicts).Count)
    foreach ($cf in $d.conflicts) { Write-Info ("conflict {0} :: {1}" -f ($cf.record_ids -join ', '), $cf.reliability_limitation) }
} catch { Write-Fail "kill shot failed: $($_.Exception.Message)" }

# ── 6. refusal ───────────────────────────────────────────────────────────
Write-Head '6 - HONEST REFUSAL'
try {
    $r = Invoke-Agent -Path '/rag/query' -Body @{ question = 'What is the current stock price of Microsoft and should I buy shares?' }
    $d = $r.R
    $t = ($d.sections | ForEach-Object { $_.content }) -join "`n"
    Write-Info ("{0}s  sufficient={1}  citations={2}" -f $r.S, $d.has_sufficient_evidence, @($d.citations).Count)
    Write-Host ('  ' + $t.Substring(0, [Math]::Min(280, $t.Length))) -ForegroundColor White
    if (-not $d.has_sufficient_evidence) { Write-Pass 'declined instead of inventing' } else { Write-Fail 'answered an unsupported question' }
    if ($t -match 'does not contain sufficient evidence') { Write-Pass "used the brief's mandated wording" }
    else { Write-Fail 'missing the mandated insufficient-evidence sentence' }
} catch { Write-Fail "refusal test failed: $($_.Exception.Message)" }

# ── 7. agentic ───────────────────────────────────────────────────────────
if (-not $SkipAgentic) {
    Write-Head '7 - LAYER 5 AGENTIC (/agent/sitrep)'
    Write-Info 'three specialists in parallel, W1-W4 triage, assembled report'
    try {
        $r = Invoke-Agent -Path '/agent/sitrep' -Body @{
            question = 'The water near Awa Reef has turned turquoise and the fish are leaving the area.'
        }
        $d = $r.R; $sr = $d.situation_report
        Write-Info ("{0}s  llm_calls={1}  assembly={2}  partial={3}" -f $r.S, $d.llm_call_count, $sr.assembly_mode, $sr.was_partial)
        Write-Info ("priority {0} ({1})  cite={2}" -f $sr.priority_class, $sr.priority_label, $sr.priority_citation)
        Write-Info ("confidence {0} :: {1}" -f $sr.confidence_level, $sr.confidence_reason)
        Write-Host ''
        foreach ($s in $sr.sections) {
            Write-Host ("    [{0,-14}] {1,-20} agent={2,-22} {3}ms" -f $s.status, $s.section_type, $s.owning_agent, $s.duration_ms) -ForegroundColor Gray
        }
        Write-Host ''
        $filled = @($sr.sections | Where-Object { $_.status -eq 'filled' }).Count
        if ($filled -ge 2) { Write-Pass "$filled sections filled" } else { Write-Fail "only $filled section(s) filled" }
        if (@($d.citations).Count -gt 0) { Write-Pass "$(@($d.citations).Count) citations resolved" } else { Write-Fail 'no citations' }
        if ($sr.priority_class) { Write-Pass "triage assigned: $($sr.priority_class)" } else { Write-Fail 'no priority class' }
        if ($d.llm_call_count -le 8) { Write-Pass "LLM call cap respected ($($d.llm_call_count)/8)" } else { Write-Fail "call cap exceeded: $($d.llm_call_count)" }
    } catch { Write-Fail "sitrep failed: $($_.Exception.Message)" }
}

# ── summary ──────────────────────────────────────────────────────────────
$el = [math]::Round(((Get-Date) - $started).TotalSeconds, 0)
Write-Head 'SUMMARY'
Write-Host "  elapsed ${el}s   checks=$($script:Checks)   failures=$($script:Failures)" -ForegroundColor DarkGray
Write-Host ''
if ($script:Failures -eq 0) {
    Write-Host '  ALL CHECKS PASSED' -ForegroundColor Green; Write-Host ''; exit 0
} else {
    Write-Host "  $($script:Failures) CHECK(S) FAILED" -ForegroundColor Red; Write-Host ''; exit 1
}
