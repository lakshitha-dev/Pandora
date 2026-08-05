/**
 * BM25 lexical retrieval — the keyword half of hybrid search.
 *
 * Dense vectors alone are weak on this corpus because so much of it is
 * addressed by exact identifiers and proper nouns: "INC-005", "WS-03",
 * "POL-002", "Awa Reef". An embedding blurs those; BM25 nails them. Running
 * both and fusing the ranks is what makes identifier lookup and paraphrased
 * questions work in the same box.
 */

const STOPWORDS = new Set([
  "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "can",
  "could", "did", "do", "does", "for", "from", "had", "has", "have", "how",
  "i", "if", "in", "into", "is", "it", "its", "may", "might", "must", "of",
  "on", "or", "our", "should", "so", "than", "that", "the", "their", "them",
  "then", "there", "these", "they", "this", "to", "was", "we", "were", "what",
  "when", "where", "which", "who", "why", "will", "with", "would", "you",
  "your",
]);

const K1 = 1.5;
const B = 0.75;

/**
 * Tokenise while preserving record identifiers.
 *
 * "INC-005" is emitted as the whole token *and* as "inc" + "005", so a query
 * for the bare ID scores strongly while a query for "incident 5" still lands.
 */
export function tokenize(text: string): string[] {
  const out: string[] = [];
  const raw = text
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, " ")
    .split(/\s+/)
    .filter(Boolean);

  for (const token of raw) {
    if (/^[a-z]{2,3}-\d{2,3}$/.test(token)) {
      out.push(token);
      const [prefix, num] = token.split("-");
      out.push(prefix, num, String(Number(num)));
      continue;
    }
    const parts = token.split("-").filter(Boolean);
    for (const p of parts) {
      if (p.length < 2 || STOPWORDS.has(p)) continue;
      out.push(p);
      // Cheap suffix folding: plural and gerund forms collapse to the stem so
      // "species"/"specie", "blooms"/"bloom", "sampling"/"sample" co-index.
      if (p.length > 4 && p.endsWith("s") && !p.endsWith("ss")) {
        out.push(p.slice(0, -1));
      }
      if (p.length > 5 && p.endsWith("ing")) out.push(p.slice(0, -3));
    }
  }
  return out;
}

export interface LexicalIndex {
  idf: Record<string, number>;
  avgLength: number;
}

/** Build the IDF table once at ingest time. */
export function buildLexicalIndex(docs: string[]): LexicalIndex {
  const df = new Map<string, number>();
  let totalLength = 0;

  for (const doc of docs) {
    const tokens = tokenize(doc);
    totalLength += tokens.length;
    for (const t of new Set(tokens)) {
      df.set(t, (df.get(t) ?? 0) + 1);
    }
  }

  const N = docs.length || 1;
  const idf: Record<string, number> = {};
  for (const [term, freq] of df) {
    // Standard BM25 IDF with the +1 guard so common terms stay non-negative.
    idf[term] = Math.log(1 + (N - freq + 0.5) / (freq + 0.5));
  }
  return { idf, avgLength: totalLength / N };
}

/** Score one document against query tokens. */
export function bm25Score(
  queryTokens: string[],
  docTokens: string[],
  index: LexicalIndex,
): { score: number; matched: string[] } {
  const tf = new Map<string, number>();
  for (const t of docTokens) tf.set(t, (tf.get(t) ?? 0) + 1);

  const len = docTokens.length || 1;
  let score = 0;
  const matched: string[] = [];

  for (const term of new Set(queryTokens)) {
    const freq = tf.get(term);
    if (!freq) continue;
    const idf = index.idf[term] ?? Math.log(1 + 1 / 0.5);
    const numerator = freq * (K1 + 1);
    const denominator = freq + K1 * (1 - B + B * (len / index.avgLength));
    score += idf * (numerator / denominator);
    matched.push(term);
  }
  return { score, matched };
}
