import type { AccessClass, Retrieved, Role, VectorIndex } from "@/lib/types";
import { retrievalPrior } from "@/lib/corpus/classify";
import { bm25Score, tokenize, type LexicalIndex } from "./bm25";
import { cosine, embedOne } from "./embeddings";

/**
 * Hybrid retrieval: BM25 ∪ dense vectors, fused with Reciprocal Rank Fusion,
 * de-duplicated, diversified with Maximal Marginal Relevance, and filtered by
 * the asking role's access class.
 *
 * RRF is used rather than a weighted score blend because BM25 scores and cosine
 * similarities live on incomparable scales; fusing *ranks* avoids inventing a
 * normalisation constant that would need retuning for every query shape.
 */

/** RRF damping. 60 is the value from the original Cormack et al. formulation. */
const RRF_K = 60;
/** MMR trade-off: 0.72 favours relevance while still breaking up near-duplicates. */
const MMR_LAMBDA = 0.72;
/** Candidates pulled from each arm before fusion. */
const CANDIDATES = 40;
/** Cosine above which two chunks are treated as the same content. */
const NEAR_DUPLICATE = 0.94;

/** What each role is cleared to read, per Chapter 11 and POL-005. */
const ROLE_ACCESS: Record<Role, AccessClass[]> = {
  guardian: ["public", "community-limited", "guardian-limited"],
  healer: ["public", "community-limited", "healer-limited"],
  researcher: ["public", "community-limited", "guardian-limited"],
  citizen: ["public"],
};

/**
 * Query expansion mapped onto the corpus's own vocabulary. A guardian types
 * "the water went weird"; the corpus says "unusual color", "turbidity",
 * "harmful bloom". Bridging that gap lexically costs nothing at query time and
 * lifts recall noticeably on colloquial phrasing.
 */
const SYNONYMS: Record<string, string[]> = {
  water: ["turbidity", "salinity", "dissolved oxygen", "drinking water"],
  colour: ["color", "turquoise", "discolouration"],
  color: ["turquoise", "green tint", "yellow plume"],
  sick: ["symptoms", "illness", "clinical", "red flags"],
  ill: ["symptoms", "illness", "clinical"],
  fish: ["marine", "species", "fauna", "grazer"],
  dying: ["mortality", "dead", "distress"],
  coral: ["reef", "bleaching", "recruitment"],
  storm: ["cyclone", "deep current", "evacuation"],
  emergency: ["incident", "response", "immediate actions", "exclusion boundary"],
  rules: ["policy", "core rule"],
  tradition: ["community", "cultural practices", "oral knowledge"],
  volcano: ["volcanic", "vent", "geothermal", "ashfall"],
  volcanic: ["vent", "plume", "obsidian reach"],
  contamination: ["contaminated", "pollution", "exclusion zone"],
  urgent: ["critical", "emergency", "priority"],
};

/** Queries that are asking "what do we deal with first?" */
const TRIAGE_INTENT =
  /\b(first|priority|prioriti[sz]e|urgent|most critical|immediate attention|triage|worst)\b/i;

/** Queries asking for an explicit comparison between two things. */
const COMPARISON_INTENT =
  /\b(compare|comparison|versus|vs\.?|difference between|differences between|contrast)\b/i;

/**
 * Split a comparison question into its aspects.
 *
 * "Compare the recommended responses for water contamination and an underwater
 * volcanic event" retrieved well for the volcanic half and lost the
 * contamination half entirely: one embedding cannot sit near both poles at once.
 * Splitting on the coordinating conjunction and retrieving each side separately
 * guarantees both records reach the context window — which is what the
 * multi-document comparison use case actually requires.
 */
export function decomposeQuery(question: string): string[] {
  if (!COMPARISON_INTENT.test(question)) return [];

  const stripped = question
    .replace(COMPARISON_INTENT, "")
    .replace(/^[\s,:-]+/, "")
    .replace(/\?+$/, "")
    .trim();

  const parts = stripped
    .split(/\s+(?:and|versus|vs\.?|with|against|or)\s+/i)
    .map((p) => p.trim())
    .filter((p) => p.split(/\s+/).length >= 2);

  if (parts.length < 2) return [];

  // The lead-in ("the recommended responses for") belongs to both aspects, so
  // re-attach it to every part after the first.
  const lead = parts[0];
  const leadWords = lead.split(/\s+/);
  const carrier =
    leadWords.length > 4 ? leadWords.slice(0, leadWords.length - 2).join(" ") : "";

  return parts.map((p, i) => (i === 0 || !carrier ? p : `${carrier} ${p}`));
}

export function rewriteQuery(question: string): string[] {
  const variants = [question];
  const lower = question.toLowerCase();

  const expansions = new Set<string>();
  for (const [term, syns] of Object.entries(SYNONYMS)) {
    if (lower.includes(term)) syns.forEach((s) => expansions.add(s));
  }
  if (expansions.size) variants.push(`${question} ${[...expansions].join(" ")}`);

  // Identifier-only probe: if the user named a record, search for it in
  // isolation so the exact record outranks anything merely topical.
  const ids = question
    .toUpperCase()
    .match(/\b(?:REG|STL|FAU|FLR|MED|INC|POL|ACC|KC|WS|SV|FN|LAB)-[0-9A-Z]{1,3}\b/g);
  if (ids?.length) variants.push(ids.join(" "));

  return variants;
}

interface Scored {
  i: number;
  rrf: number;
  lexicalRank: number | null;
  denseRank: number | null;
  lexicalScore: number;
  denseScore: number;
  matched: Set<string>;
}

function blank(i: number): Scored {
  return {
    i,
    rrf: 0,
    lexicalRank: null,
    denseRank: null,
    lexicalScore: 0,
    denseScore: 0,
    matched: new Set<string>(),
  };
}

/** Run both retrieval arms for one query string and fuse their ranks. */
async function fuseOne(
  index: VectorIndex,
  query: string,
  lexical: LexicalIndex,
  into: Map<number, Scored>,
): Promise<void> {
  const queryTokens = tokenize(query);
  const queryVector = await embedOne(query);

  const lexicalScores: Array<{ i: number; score: number; matched: string[] }> = [];
  const denseScores: Array<{ i: number; score: number }> = [];

  index.chunks.forEach((chunk, i) => {
    const { score, matched } = bm25Score(queryTokens, tokenize(chunk.text), lexical);
    if (score > 0) lexicalScores.push({ i, score, matched });
    denseScores.push({ i, score: cosine(queryVector, chunk.vector) });
  });

  lexicalScores.sort((a, b) => b.score - a.score);
  denseScores.sort((a, b) => b.score - a.score);

  lexicalScores.slice(0, CANDIDATES).forEach((e, rank) => {
    const cur = into.get(e.i) ?? blank(e.i);
    cur.rrf += 1 / (RRF_K + rank + 1);
    cur.lexicalRank =
      cur.lexicalRank === null ? rank + 1 : Math.min(cur.lexicalRank, rank + 1);
    cur.lexicalScore = Math.max(cur.lexicalScore, e.score);
    e.matched.forEach((m) => cur.matched.add(m));
    into.set(e.i, cur);
  });

  denseScores.slice(0, CANDIDATES).forEach((e, rank) => {
    const cur = into.get(e.i) ?? blank(e.i);
    cur.rrf += 1 / (RRF_K + rank + 1);
    cur.denseRank =
      cur.denseRank === null ? rank + 1 : Math.min(cur.denseRank, rank + 1);
    cur.denseScore = Math.max(cur.denseScore, e.score);
    into.set(e.i, cur);
  });
}

export interface RetrieveOptions {
  role: Role;
  types?: string[];
  region?: string | null;
  topK?: number;
}

export interface RetrieveResult {
  results: Retrieved[];
  variants: string[];
  aspects: string[];
  restrictedCount: number;
  poolSize: number;
  /** Best raw fused score, before normalisation — drives the refusal threshold. */
  topScore: number;
  duplicatesDropped: number;
  clusterAdded: string[];
}

export async function retrieve(
  index: VectorIndex,
  question: string,
  opts: RetrieveOptions,
): Promise<RetrieveResult> {
  const topK = opts.topK ?? 6;
  const lexical: LexicalIndex = { idf: index.idf, avgLength: index.avgLength };
  const aspects = decomposeQuery(question);
  const variants = rewriteQuery(question);

  // For a comparison question, fuse each aspect into its own table so we can
  // guarantee representation from both sides; otherwise use one shared table.
  const tables: Array<Map<number, Scored>> = [];
  if (aspects.length > 1) {
    for (const aspect of aspects) {
      const t = new Map<number, Scored>();
      await fuseOne(index, aspect, lexical, t);
      tables.push(t);
    }
  } else {
    const t = new Map<number, Scored>();
    for (const v of variants) await fuseOne(index, v, lexical, t);
    tables.push(t);
  }

  const allowed = new Set(ROLE_ACCESS[opts.role]);
  const triage = TRIAGE_INTENT.test(question);
  let restrictedCount = 0;

  const prepare = (table: Map<number, Scored>): Scored[] =>
    [...table.values()]
      .filter((s) => {
        const meta = index.chunks[s.i].meta;
        if (!allowed.has(meta.accessClass)) {
          restrictedCount++;
          return false;
        }
        if (opts.types?.length && !opts.types.includes(meta.recordType)) return false;
        if (opts.region && meta.region !== opts.region) return false;
        return true;
      })
      .map((s) => {
        const meta = index.chunks[s.i].meta;
        let weight = retrievalPrior(meta.recordType, meta.navigational);
        // Triage questions want the records that carry a stated risk level.
        if (triage) {
          if (meta.severity === "critical") weight *= 1.5;
          else if (meta.severity === "high") weight *= 1.3;
          else if (meta.severity === "medium") weight *= 1.1;
        }
        return { ...s, rrf: s.rrf * weight };
      })
      .sort((a, b) => b.rrf - a.rrf);

  const prepared = tables.map(prepare);
  const topScore = Math.max(...prepared.map((p) => p[0]?.rrf ?? 0), 0);

  // Interleave aspects round-robin so a comparison cannot be won outright by
  // whichever side happened to score higher.
  let pool: Scored[] = [];
  if (prepared.length > 1) {
    const seen = new Set<number>();
    for (let r = 0; r < CANDIDATES; r++) {
      for (const list of prepared) {
        const cand = list[r];
        if (cand && !seen.has(cand.i)) {
          seen.add(cand.i);
          pool.push(cand);
        }
      }
    }
  } else {
    pool = prepared[0].slice(0, CANDIDATES);
  }

  // Drop near-duplicates before diversifying. The twenty Knowledge Cards are
  // template clones of each other (KC-01 and KC-11 are the same card), and MMR
  // alone was not aggressive enough to stop two of them occupying two slots.
  let duplicatesDropped = 0;
  const deduped: Scored[] = [];
  for (const cand of pool) {
    const clash = deduped.some(
      (kept) =>
        cosine(index.chunks[cand.i].vector, index.chunks[kept.i].vector) >
        NEAR_DUPLICATE,
    );
    if (clash) {
      duplicatesDropped++;
      continue;
    }
    deduped.push(cand);
  }

  // MMR: greedily take the candidate maximising relevance minus redundancy
  // against what is already selected.
  let remaining = [...deduped];
  const selected: Scored[] = [];
  while (selected.length < topK && remaining.length) {
    let bestIdx = 0;
    let bestVal = -Infinity;
    remaining.forEach((cand, idx) => {
      const relevance = cand.rrf / (topScore || 1);
      let maxSim = 0;
      for (const s of selected) {
        maxSim = Math.max(
          maxSim,
          cosine(index.chunks[cand.i].vector, index.chunks[s.i].vector),
        );
      }
      const val = MMR_LAMBDA * relevance - (1 - MMR_LAMBDA) * maxSim;
      if (val > bestVal) {
        bestVal = val;
        bestIdx = idx;
      }
    });
    selected.push(remaining[bestIdx]);
    remaining = remaining.filter((_, idx) => idx !== bestIdx);
  }

  /**
   * Evidence-cluster completion.
   *
   * §14.3 holds three notes about one event — FN-A blames a plankton bloom,
   * FN-B reports an upstream waste container, LAB-C found carbonates but with an
   * incomplete chain of custody. Retrieving FN-A alone would let the system
   * state a confident cause from a single source, which is exactly the failure
   * the corpus is testing for. Whenever one member of such a cluster is
   * selected, we pull in its siblings so the contradiction is unmissable.
   */
  const clusterAdded: string[] = [];
  const selectedIdx = new Set(selected.map((s) => s.i));
  for (const s of [...selected]) {
    const meta = index.chunks[s.i].meta;
    if (meta.recordType !== "field-note") continue;
    index.chunks.forEach((c, i) => {
      if (selectedIdx.has(i)) return;
      if (c.meta.recordType !== "field-note") return;
      if (c.meta.section !== meta.section) return;
      if (!allowed.has(c.meta.accessClass)) return;
      selectedIdx.add(i);
      selected.push({ ...blank(i), rrf: s.rrf * 0.9 });
      if (c.meta.recordId) clusterAdded.push(c.meta.recordId);
    });
  }

  const results: Retrieved[] = selected.map((s) => {
    const chunk = index.chunks[s.i];
    const matchedBy: Retrieved["matchedBy"] = [];
    if (s.lexicalRank !== null) matchedBy.push("lexical");
    if (s.denseRank !== null) matchedBy.push("dense");
    if (opts.region && chunk.meta.region === opts.region) matchedBy.push("metadata");
    return {
      chunk: {
        id: chunk.id,
        text: chunk.text,
        tokens: chunk.tokens,
        meta: chunk.meta,
      },
      score: topScore > 0 ? Math.min(1, s.rrf / topScore) : 0,
      lexicalRank: s.lexicalRank,
      denseRank: s.denseRank,
      lexicalScore: s.lexicalScore,
      denseScore: s.denseScore,
      matchedBy,
      highlights: [...s.matched].slice(0, 12),
    };
  });

  return {
    results,
    variants,
    aspects,
    restrictedCount,
    poolSize: deduped.length,
    topScore,
    duplicatesDropped,
    clusterAdded,
  };
}
