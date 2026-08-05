/**
 * Core domain types for the Pandora Knowledge Guardian.
 *
 * The corpus is not free-form prose: it is a register of identified records
 * (REG-01, FAU-003, INC-005, POL-002 ...). Modelling that structure explicitly
 * is what lets us chunk on record boundaries, cite exact record IDs, filter by
 * access class, and detect when two records contradict one another.
 */

/** Record families present in the Pandora corpus, keyed by their ID prefix. */
export type RecordType =
  | "region" // REG-xx
  | "settlement" // STL-xxx
  | "fauna" // FAU-xxx
  | "flora" // FLR-xxx
  | "medical" // MED-xxx
  | "incident" // INC-xxx
  | "policy" // POL-xxx
  | "accommodation" // ACC-xxx
  | "knowledge-card" // KC-xx
  | "water-station" // WS-xx
  | "survey" // SV-xxx
  | "field-note" // FN-A, LAB-C
  | "section" // numbered prose section, e.g. 4.5
  | "chapter" // chapter preamble
  | "appendix"
  | "shared-protocol"; // de-duplicated boilerplate, hoisted out of records

/**
 * Evidence quality labels. Chapter 1 states these are part of the corpus and
 * that "RAG applications should preserve these labels", so they are first-class
 * metadata rather than something we infer at answer time.
 */
export type EvidenceQuality =
  | "verified-observation"
  | "community-tradition"
  | "provisional-interpretation"
  | "modeled-estimate"
  | "disputed-report"
  | "documented-protocol";

/**
 * Access classification from Chapter 11 and POL-005. Drives the role lens:
 * a Citizen must not receive healer-limited clinical detail verbatim.
 */
export type AccessClass =
  | "public"
  | "community-limited"
  | "healer-limited"
  | "guardian-limited";

/** Who is asking. Changes both retrieval filtering and answer register. */
export type Role = "guardian" | "researcher" | "healer" | "citizen";

/** Severity vocabulary the corpus itself uses for incidents (INC-xxx). */
export type Severity = "critical" | "high" | "medium" | "low" | "none";

/** Water incident classes from §4.5. */
export type WaterClass = "W1" | "W2" | "W3" | "W4";

export interface ChunkMeta {
  docId: string;
  docName: string;
  /** 1-based page in the source PDF, used for "p. 42" style citation. */
  page: number;
  chapter: number | null;
  chapterTitle: string | null;
  /** Dotted section number where applicable, e.g. "4.5". */
  section: string | null;
  /** Canonical record identifier, e.g. "INC-005". Null for prose sections. */
  recordId: string | null;
  recordType: RecordType;
  /** Human title, e.g. "Vent Plume Release". */
  title: string;
  /** Region name or ID this chunk is scoped to, when determinable. */
  region: string | null;
  accessClass: AccessClass;
  evidenceQuality: EvidenceQuality;
  severity: Severity;
  /**
   * True when this chunk's body was assembled from boilerplate shared across
   * many records. Kept once as a shared-protocol chunk instead of N times.
   */
  isSharedProtocol: boolean;
  /** Record IDs that referenced the shared protocol we hoisted. */
  appliesTo?: string[];
  /**
   * True for sections describing the corpus itself (contents, glossary, the
   * suggested test questions). Retrievable, but with a low prior.
   */
  navigational: boolean;
}

export interface Chunk {
  id: string;
  text: string;
  /** Token count approximation, for context budgeting. */
  tokens: number;
  meta: ChunkMeta;
}

/** A chunk plus its embedding, as persisted in the index. */
export interface IndexedChunk extends Chunk {
  vector: number[];
}

export interface VectorIndex {
  version: number;
  createdAt: string;
  embedder: string;
  dim: number;
  chunks: IndexedChunk[];
  /** Inverse document frequency table for the lexical half of hybrid search. */
  idf: Record<string, number>;
  avgLength: number;
  docs: Array<{ docId: string; docName: string; pages: number; chunks: number }>;
}

/** One retrieved chunk with the scoring breakdown we show in the UI. */
export interface Retrieved {
  chunk: Chunk;
  /** Fused final score after RRF + MMR + rerank. */
  score: number;
  lexicalRank: number | null;
  denseRank: number | null;
  lexicalScore: number;
  denseScore: number;
  /** Which retrieval arms found it — surfaced as a tag in the source card. */
  matchedBy: Array<"lexical" | "dense" | "metadata">;
  /** Query terms present in this chunk, for excerpt highlighting. */
  highlights: string[];
}

/** A single assertion in the generated brief, bound to its supporting sources. */
export interface Claim {
  text: string;
  /** 1-based indices into the retrieved source list. */
  citations: number[];
  /** Documented protocol vs model inference — required by §15.2. */
  kind: "protocol" | "inference";
  evidenceQuality: EvidenceQuality | null;
}

export interface Contradiction {
  topic: string;
  positions: Array<{
    sourceIndex: number;
    recordId: string | null;
    claim: string;
    reliability: string;
  }>;
  /** Why this cannot be resolved from the corpus alone. */
  limitation: string;
  recommendation: string;
}

export type AnswerStatus = "grounded" | "partial" | "insufficient";

export interface GuardianAnswer {
  status: AnswerStatus;
  /** Short imperative headline for the action callout, when one is warranted. */
  headline: string | null;
  summary: string;
  claims: Claim[];
  /** Explicit statement of what the corpus does not cover. */
  gaps: string[];
  contradictions: Contradiction[];
  severity: Severity;
  waterClass: WaterClass | null;
  /** 0..1 groundedness confidence, derived from retrieval + citation coverage. */
  confidence: number;
  /** Set when status === "insufficient". */
  refusal: string | null;
}

export interface PipelineStage {
  name: string;
  detail: string;
  ms: number;
}

export interface QueryResponse {
  question: string;
  role: Role;
  answer: GuardianAnswer;
  sources: Retrieved[];
  stages: PipelineStage[];
  /** Rewritten query variants actually used for retrieval. */
  variants: string[];
  llm: { provider: string; model: string; grounded: boolean };
  totalMs: number;
}
