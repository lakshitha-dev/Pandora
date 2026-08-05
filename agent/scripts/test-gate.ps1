<#
.SYNOPSIS
    Layer 1 verification gate for the Pandora agent service.

.DESCRIPTION
    Runs the checks that decide whether Layer 1 can be tagged `v1-core-rag`:

      1. Health          — service up, corpus indexed
      2. Auth gate       — /rag/query rejects a missing internal key
      3. Retrieval gate  — the 7 brief questions + the corpus's own 3 (§15.1)
                           each cite the record they should
      4. Kill shot       — the turquoise-water conflict, scored against the
                           six criteria the corpus states on page 48
      5. Refusal         — an out-of-corpus question must decline, not invent

    Prints each result as it completes. Exits non-zero if the gate fails, so
    it can be wired into CI later.

.PARAMETER BaseUrl
    Agent service base URL. Default http://127.0.0.1:8000

.PARAMETER Key
    X-Internal-Key value. Defaults to AGENT_SERVICE_KEY from agent/.env

.PARAMETER Quick
    Run only the kill shot and the refusal test (~2 minutes instead of ~7).

.PARAMETER TimeoutSec
    Per-request timeout. Default 180.

.EXAMPLE
    .\scripts\test-gate.ps1
    .\scripts\test-gate.ps1 -Quick
    .\scripts\test-gate.ps1 -BaseUrl https://pandora-agent.azurewebsites.net
#>

[CmdletBinding()]
param(
    [string]$BaseUrl = 'http://127.0.0.1:8000',
    [string]$Key,
    [switch]$Quick,
    [int]$TimeoutSec = 180
)

$ErrorActionPreference = 'Stop'
$script:Failures = 0

# ── helpers ──────────────────────────────────────────────────────────────

function Write-Head([string]$Text) {
    Write-Host ''
    Write-Host ('=' * 78) -ForegroundColor DarkCyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host ('=' * 78) -ForegroundColor DarkCyan
}

function Write-Pass([string]$Text) { Write-Host "  [PASS] $Text" -ForegroundColor Green }
function Write-Fail([string]$Text) {
    Write-Host "  [FAIL] $Text" -ForegroundColor Red
    $script:Failures++
}
function Write-Info([string]$Text) { Write-Host "         $Text" -ForegroundColor DarkGray }

function Get-EnvKey {
    $envPath = Join-Path $PSScriptRoot '..\.env'
    if (-not (Test-Path $envPath)) { return $null }
    foreach ($line in Get-Content $envPath) {
        if ($line -match '^\s*AGENT_SERVICE_KEY\s*=\s*(.+?)\s*$') { return $Matches[1] }
    }
    return $null
}

function Invoke-Query {
    param([string]$Question, [string]$SectionType)

    $payload = @{ question = $Question }
    if ($SectionType) { $payload.section_type = $SectionType }

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $resp = Invoke-RestMethod -Uri "$BaseUrl/rag/query" -Method Post `
        -Headers @{ 'X-Internal-Key' = $Key } `
        -ContentType 'application/json' `
        -Body ($payload | ConvertTo-Json -Depth 5 -Compress) `
        -TimeoutSec $TimeoutSec
    $sw.Stop()

    return [pscustomobject]@{
        Response = $resp
        Seconds  = [math]::Round($sw.Elapsed.TotalSeconds, 1)
    }
}

# ── resolve key ──────────────────────────────────────────────────────────

if (-not $Key) { $Key = Get-EnvKey }
if (-not $Key) {
    Write-Host 'ERROR: no key. Pass -Key or set AGENT_SERVICE_KEY in agent/.env' -ForegroundColor Red
    exit 2
}

$started = Get-Date
Write-Host ''
Write-Host 'Pandora Knowledge Guardian — Layer 1 verification gate' -ForegroundColor White
Write-Host "target: $BaseUrl" -ForegroundColor DarkGray

# ── 1. health ────────────────────────────────────────────────────────────

Write-Head '1 - HEALTH'
try {
    $h = Invoke-RestMethod -Uri "$BaseUrl/health" -TimeoutSec 60
} catch {
    Write-Fail "service unreachable at $BaseUrl - is uvicorn running?"
    Write-Info $_.Exception.Message
    exit 1
}

if ($h.search_index_reachable) { Write-Pass 'Azure AI Search reachable' } else { Write-Fail 'Azure AI Search unreachable' }
if ($h.llm_reachable)          { Write-Pass 'Azure OpenAI reachable' }    else { Write-Fail 'Azure OpenAI unreachable' }
if ($h.corpus_indexed)         { Write-Pass "corpus indexed - $($h.corpus_chunk_count) chunks, $($h.corpus_record_count) records" }
else                           { Write-Fail 'corpus NOT indexed - run scripts/seed_corpus.py'; exit 1 }
Write-Info "rerank_mode=$($h.rerank_mode)  version=$($h.version)"

# ── 2. auth gate ─────────────────────────────────────────────────────────

Write-Head '2 - AUTH GATE'
try {
    Invoke-RestMethod -Uri "$BaseUrl/rag/query" -Method Post `
        -ContentType 'application/json' -Body '{"question":"test"}' -TimeoutSec 30 | Out-Null
    Write-Fail '/rag/query accepted a request with NO internal key'
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    if ($code -eq 401) { Write-Pass 'unauthenticated request correctly rejected (401)' }
    else { Write-Fail "expected 401 without a key, got $code" }
}

# ── 3. retrieval gate ────────────────────────────────────────────────────

if (-not $Quick) {
    Write-Head '3 - RETRIEVAL GATE (7 brief questions + 3 from corpus 15.1)'
    Write-Info 'each question must cite the record it should - roughly 30-40s each'
    Write-Host ''

    $gate = @(
        @{ Q = "What are the possible causes of unusual changes in Pandora's ocean water?";                    Expect = 'INC-001' }
        @{ Q = 'Which marine species are most vulnerable to water contamination?';                             Expect = 'FAU-'    }
        @{ Q = 'What immediate actions should guardians take after detecting coral damage?';                   Expect = 'INC-002' }
        @{ Q = 'Compare the recommended responses for water contamination and an underwater volcanic event.';  Expect = 'INC-00'  }
        @{ Q = 'What traditional community practices can support marine conservation?';                        Expect = 'POL-'    }
        @{ Q = 'Summarize the major environmental threats mentioned across the reports.';                      Expect = 'INC-'    }
        @{ Q = 'Which areas should receive emergency attention first, based on the available evidence?';       Expect = 'INC-'    }
        @{ Q = 'What are the immediate steps when water changes color near Awa Reef?';                         Expect = 'INC-001' }
        @{ Q = 'Compare Reef Cut Infection and Marine Sting Reaction, including red flags.';                   Expect = 'MED-'    }
        @{ Q = 'Which accommodations are safest for a traveler with limited mobility during storm season?';    Expect = 'ACC-'    }
    )

    $hits = 0
    $times = @()
    $i = 0

    foreach ($item in $gate) {
        $i++
        Write-Host ("  {0,2}. {1}" -f $i, $item.Q.Substring(0, [Math]::Min(62, $item.Q.Length))) -ForegroundColor Gray -NoNewline

        try {
            $r = Invoke-Query -Question $item.Q
            $d = $r.Response
            $times += $r.Seconds

            $cited = @($d.citations | ForEach-Object { $_.record_id })
            $hit = $false
            foreach ($c in $cited) { if ($c -and $c.StartsWith($item.Expect)) { $hit = $true } }
            if ($hit) { $hits++ }

            $rulesPassed = @($d.grounding.rules | Where-Object { $_.passed }).Count
            $mark  = if ($hit) { 'HIT ' } else { 'MISS' }
            $color = if ($hit) { 'Green' } else { 'Yellow' }

            Write-Host ''
            Write-Host ("      {0}  {1,4}s  grounded={2,3}%  rules={3}/8  sufficient={4}" -f `
                $mark, $r.Seconds, $d.grounding.groundedness, $rulesPassed, $d.has_sufficient_evidence) -ForegroundColor $color
            Write-Info ("expect {0}  cited: {1}" -f $item.Expect, ($cited -join ', '))
        } catch {
            Write-Host ''
            Write-Fail "request failed: $($_.Exception.Message)"
        }
    }

    Write-Host ''
    if ($times.Count -gt 0) {
        $sorted = $times | Sort-Object
        $p50 = $sorted[[int]($sorted.Count / 2)]
        Write-Info ("latency p50={0}s  max={1}s" -f $p50, ($sorted[-1]))
    }
    if ($hits -ge 8) { Write-Pass "retrieval gate: $hits/10 expected records cited" }
    else { Write-Fail "retrieval gate: only $hits/10 expected records cited (need 8+)" }
}

# ── 4. kill shot ─────────────────────────────────────────────────────────

Write-Head '4 - KILL SHOT: the turquoise-water conflict'
Write-Info 'corpus p.48 states the expected answer - all six criteria must pass'
Write-Host ''

try {
    $r = Invoke-Query -Question 'The water near Awa Reef has turned turquoise and the fish are leaving.' -SectionType 'likely_causes'
    $d = $r.Response
    $text = ($d.sections | ForEach-Object { $_.content }) -join "`n"
    $lower = $text.ToLower()

    Write-Host '  ---------- answer ----------' -ForegroundColor DarkGray
    Write-Host ($text.Substring(0, [Math]::Min(900, $text.Length))) -ForegroundColor White
    Write-Host '  ----------------------------' -ForegroundColor DarkGray
    Write-Host ''

    $criteria = @(
        @{ Name = 'presents FN-A';                     Ok = $lower.Contains('fn-a') }
        @{ Name = 'presents FN-B';                     Ok = $lower.Contains('fn-b') }
        @{ Name = 'presents LAB-C';                    Ok = $lower.Contains('lab-c') }
        @{ Name = 'flags incomplete chain of custody'; Ok = ($lower.Contains('chain of custody') -or $lower.Contains('chain-of-custody')) }
        @{ Name = 'declares no confirmed cause';       Ok = ($lower.Contains('not confirmed') -or $lower.Contains('no confirmed') -or $lower.Contains('cannot be confirmed') -or $lower.Contains('remain possible') -or $lower.Contains('not established')) }
        @{ Name = 'recommends further sampling';       Ok = $lower.Contains('sampl') }
    )

    $met = 0
    foreach ($c in $criteria) {
        if ($c.Ok) { Write-Pass $c.Name; $met++ } else { Write-Fail $c.Name }
    }

    Write-Host ''
    Write-Info ("{0}/6 criteria  |  {1}s  |  grounded={2}%  |  conflicts={3}" -f `
        $met, $r.Seconds, $d.grounding.groundedness, @($d.conflicts).Count)

    foreach ($cf in $d.conflicts) {
        Write-Info ("conflict {0} :: {1}" -f ($cf.record_ids -join ', '), $cf.reliability_limitation)
    }
} catch {
    Write-Fail "kill shot failed: $($_.Exception.Message)"
}

# ── 5. refusal ───────────────────────────────────────────────────────────

Write-Head '5 - HONEST REFUSAL (out-of-corpus question)'
try {
    $r = Invoke-Query -Question 'What is the current stock price of Microsoft and should I buy shares?'
    $d = $r.Response
    $text = ($d.sections | ForEach-Object { $_.content }) -join "`n"

    Write-Info ("{0}s  sufficient={1}  citations={2}" -f $r.Seconds, $d.has_sufficient_evidence, @($d.citations).Count)
    Write-Host ''
    Write-Host ('  ' + $text.Substring(0, [Math]::Min(320, $text.Length))) -ForegroundColor White
    Write-Host ''

    if (-not $d.has_sufficient_evidence) { Write-Pass 'declined instead of inventing' }
    else { Write-Fail 'answered a question the corpus cannot support' }

    if ($text -match 'does not contain sufficient evidence') { Write-Pass "used the brief's mandated wording" }
    else { Write-Fail "did not use the brief's mandated insufficient-evidence sentence" }
} catch {
    Write-Fail "refusal test failed: $($_.Exception.Message)"
}

# ── summary ──────────────────────────────────────────────────────────────

$elapsed = [math]::Round(((Get-Date) - $started).TotalSeconds, 0)
Write-Head 'SUMMARY'
Write-Host "  elapsed: ${elapsed}s" -ForegroundColor DarkGray

if ($script:Failures -eq 0) {
    Write-Host ''
    Write-Host '  GATE PASSED - Layer 1 is ready to tag v1-core-rag' -ForegroundColor Green
    Write-Host ''
    exit 0
} else {
    Write-Host ''
    Write-Host "  GATE FAILED - $($script:Failures) check(s) failed" -ForegroundColor Red
    Write-Host ''
    exit 1
}
