/**
 * Backend gateway client (docs/API_CONTRACT.md Part 1).
 *
 * Everything goes through the backend — never the agent service directly. One
 * origin, one auth surface, one CORS config.
 */

import type {
  AffectedSpecies,
  Answer,
  EmergencyLevel,
  EvidenceQuality,
  RegionId,
  SourceCard,
} from "@/components/pandora/data"

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:5000"

// --- wire types, hand-mirrored from docs/API_CONTRACT.md §1.1 ---------------

export interface ApiCitation {
  marker: number
  document_id: string
  document_name: string
  chunk_id: string | null
  record_id: string
  record_type: string
  title: string
  chapter: string
  section: string | null
  page: number | null
  region_id: string | null
  excerpt: string
  relevance_score: number
  rerank_score: number | null
  evidence_quality: string
  risk_level: string | null
  record_date: string | null
}

export interface ApiSection {
  section_type: "affected_species" | "likely_causes" | "recommended_actions"
  owning_agent: string
  status: "filled" | "empty" | "timed_out" | "not_applicable"
  empty_reason: string | null
  content: string
  claim_count: number
  supported_claim_count: number
  duration_ms: number
  display_order: number
}

export interface ApiConflictPosition {
  record_id: string
  claim: string
  evidence_quality: string
  reliability_limitation: string
}

export interface ApiSituationReport {
  priority: {
    class: "W1" | "W2" | "W3" | "W4" | "informational"
    label: string
    reason: string
    citation: string | null
    page: number | null
  }
  affected_region_ids: string[]
  assembly_mode: string
  sections: ApiSection[]
  confidence: {
    level: "high" | "moderate" | "low" | "insufficient"
    reason: string
    groundedness: number
  }
  conflicts: {
    record_ids: string[]
    conflict_nature: string
    positions: ApiConflictPosition[]
    resolution_recommendation: string
  }[]
  was_partial: boolean
}

export interface ApiInsufficientEvidence {
  banner: string
  message: string
  searched_scope: string
  closest_matches: { record_id: string; title: string; relevance_score: number; page: number | null }[]
  what_would_resolve: string
}

export interface AskResponse {
  answer_id: string
  conversation_id: string
  situation_report: ApiSituationReport
  insufficient_evidence: ApiInsufficientEvidence | null
  citations: ApiCitation[]
  has_sufficient_evidence: boolean
  llm_call_count: number
  latency_ms: number
}

export interface ApiError {
  error: { code: string; message: string; details?: unknown }
}

// --- calls ------------------------------------------------------------------

export async function askQuestion(
  question: string,
  conversationId?: string | null,
): Promise<AskResponse> {
  const response = await fetch(`${BASE_URL}/api/v1/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      conversation_id: conversationId ?? null,
      document_ids: null,
      role_lens: "guardian",
    }),
  })

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiError | null
    throw new Error(body?.error?.message ?? `Request failed (${response.status})`)
  }
  return (await response.json()) as AskResponse
}

/** SSE trace. Returns an unsubscribe function. */
export function streamQuestion(
  question: string,
  onEvent: (stepType: string, payload: unknown) => void,
  onDone: (final: AskResponse) => void,
  onError: (message: string) => void,
): () => void {
  const url = `${BASE_URL}/api/v1/ask/stream?question=${encodeURIComponent(question)}`
  const source = new EventSource(url)

  const handle = (event: MessageEvent) => {
    let parsed: { step_type?: string; payload?: unknown }
    try {
      parsed = JSON.parse(event.data)
    } catch {
      return
    }
    const stepType = parsed.step_type ?? "message"
    if (stepType === "answer.completed") {
      onDone(parsed.payload as AskResponse)
      source.close()
      return
    }
    if (stepType === "error") {
      const payload = parsed.payload as { message?: string } | undefined
      onError(payload?.message ?? "The trace stream failed.")
      source.close()
      return
    }
    onEvent(stepType, parsed.payload)
  }

  source.onmessage = handle
  // Named events arrive on their own listeners, not onmessage.
  for (const name of [
    "query.received", "query.classified", "priority.classified", "map.zone_lit",
    "route.decided", "retrieval.started", "retrieval.completed", "agent.thinking",
    "section.filling", "section.completed", "section.unavailable", "agent.completed",
    "agent.timed_out", "conflict.detected", "validation.running", "validation.result",
    "synthesis.started", "answer.streaming", "answer.completed", "error",
  ]) {
    source.addEventListener(name, handle as EventListener)
  }
  source.onerror = () => {
    onError("Lost the connection to the trace stream.")
    source.close()
  }

  return () => source.close()
}

// --- adapter: wire shape -> the shape the UI already renders ----------------

const QUALITY_MAP: Record<string, EvidenceQuality> = {
  verified_observation: "verified",
  community_tradition: "tradition",
  provisional_interpretation: "provisional",
  modeled_estimate: "modeled",
  disputed_report: "disputed",
}

function toQuality(raw: string): EvidenceQuality {
  return QUALITY_MAP[raw] ?? "provisional"
}

function sectionContent(report: ApiSituationReport, type: ApiSection["section_type"]): ApiSection | undefined {
  return report.sections.find((s) => s.section_type === type)
}

/** Pull `**NAME**` lead-ins out of the species markdown into cards. */
function parseSpecies(section: ApiSection | undefined): AffectedSpecies[] {
  if (!section?.content) return []
  const out: AffectedSpecies[] = []
  const pattern = /\*\*([A-Z]{2,4}-[A-Z0-9]+)\s*([^*]*)\*\*\s*[—-]?\s*([^*]*)/g
  let match: RegExpExecArray | null
  while ((match = pattern.exec(section.content)) !== null) {
    out.push({
      id: match[1],
      name: match[2].trim() || match[1],
      habitat: "",
      pressure: match[3].trim().slice(0, 220),
      protection: "",
    })
  }
  return out
}

function parseActions(section: ApiSection | undefined): Answer["recommendedActions"] {
  if (!section?.content) return []
  return section.content
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => /^\d+\./.test(line))
    .map((line, index) => {
      const citation = line.match(/\[([^\]]+)\]/)?.[1]
      return {
        step: index + 1,
        action: line.replace(/^\d+\.\s*/, "").replace(/\s*\[[^\]]+\]/g, "").trim(),
        citation,
      }
    })
}

function parseCauses(section: ApiSection | undefined): Answer["causes"] {
  if (!section?.content) return []
  return section.content
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean)
    .slice(0, 6)
    .map((block) => {
      const recordId = block.match(/\[([A-Z]{2,4}-[A-Z0-9]+)/)?.[1]
      const term = block.match(/\*\*([^*]+)\*\*/)?.[1] ?? "Finding"
      return {
        term: term.replace(/[.:]$/, ""),
        detail: block.replace(/\*\*/g, "").replace(/\s*\[[^\]]+\]/g, "").trim(),
        recordId,
      }
    })
}

export function toAnswer(response: AskResponse, question: string): Answer {
  const report = response.situation_report
  const speciesSection = sectionContent(report, "affected_species")
  const causesSection = sectionContent(report, "likely_causes")
  const actionsSection = sectionContent(report, "recommended_actions")

  const sources: SourceCard[] = response.citations.map((c) => ({
    id: c.record_id || `#${c.marker}`,
    doc: c.document_name,
    ref: [c.chapter, c.page ? `p.${c.page}` : null].filter(Boolean).join(" · "),
    relevance: Math.round((c.relevance_score ?? 0) * 100),
    excerpt: c.excerpt,
    region: (c.region_id ?? undefined) as RegionId | undefined,
    category: c.record_type,
    quality: toQuality(c.evidence_quality),
  }))

  const conflict = report.conflicts[0]
  const position = (index: number) => {
    const p = conflict?.positions[index]
    return {
      label: p?.record_id ?? "—",
      text: p?.claim ?? "",
      quality: toQuality(p?.evidence_quality ?? ""),
      limitation: p?.reliability_limitation,
    }
  }

  // `informational` has no W-class badge; the UI's EmergencyLevel has no
  // equivalent, so it renders as the lowest band.
  const emergency = (
    report.priority.class === "informational" ? "W1" : report.priority.class
  ) as Exclude<EmergencyLevel, "none">

  return {
    question,
    emergency,
    priorityReason: report.priority.reason,
    priorityCitation: [report.priority.citation, report.priority.page ? `p.${report.priority.page}` : null]
      .filter(Boolean)
      .join(", "),
    affectedRegions: report.affected_region_ids as RegionId[],
    affectedSpecies: parseSpecies(speciesSection),
    causes: parseCauses(causesSection),
    quality: toQuality(response.citations[0]?.evidence_quality ?? ""),
    conflict: conflict
      ? {
          summary: conflict.conflict_nature,
          a: position(0),
          b: position(1),
          c: position(2),
        }
      : undefined,
    recommendedActions: parseActions(actionsSection),
    publicComms:
      response.insufficient_evidence?.message ??
      actionsSection?.content.split("\n").slice(-1)[0] ??
      "",
    sources,
    confidence: report.confidence.groundedness,
    confidenceLevel: report.confidence.level,
    confidenceReason: report.confidence.reason,
  }
}
