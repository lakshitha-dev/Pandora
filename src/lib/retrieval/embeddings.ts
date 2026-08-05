/**
 * Local sentence embeddings.
 *
 * Runs all-MiniLM-L6-v2 on-device through onnxruntime, so retrieval needs no
 * API key and makes no network call at demo time (the model is fetched once and
 * cached under node_modules/.cache). If the runtime is unavailable we fall back
 * to a deterministic hashed lexical projection rather than failing the query —
 * degraded but still functional, and the active embedder is reported in the UI
 * so the distinction is never hidden.
 */

const MODEL = "Xenova/all-MiniLM-L6-v2";
export const FALLBACK_DIM = 384;

type Extractor = (
  input: string[],
  opts: { pooling: "mean"; normalize: boolean },
) => Promise<{ tolist: () => number[][] }>;

let extractorPromise: Promise<Extractor | null> | null = null;
let activeEmbedder = "hashed-lexical-384 (fallback)";

export function embedderName(): string {
  return activeEmbedder;
}

async function loadExtractor(): Promise<Extractor | null> {
  try {
    const mod = await import("@huggingface/transformers");
    mod.env.allowLocalModels = false;
    const pipe = await mod.pipeline("feature-extraction", MODEL, {
      dtype: "q8",
    });
    activeEmbedder = `${MODEL} (local, q8)`;
    return pipe as unknown as Extractor;
  } catch (err) {
    console.warn(
      `[embeddings] ${MODEL} unavailable, using hashed lexical fallback:`,
      err instanceof Error ? err.message : err,
    );
    return null;
  }
}

function getExtractor(): Promise<Extractor | null> {
  extractorPromise ??= loadExtractor();
  return extractorPromise;
}

/* ------------------------------------------------------------------ *
 * Fallback embedder: hashed bag-of-bigrams, L2-normalised.
 * Not semantic, but deterministic, dependency-free and never throws.
 * ------------------------------------------------------------------ */

function hash(str: string): number {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function fallbackEmbed(text: string): number[] {
  const vec = new Array<number>(FALLBACK_DIM).fill(0);
  const tokens = text
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, " ")
    .split(/\s+/)
    .filter((t) => t.length > 1);
  const grams: string[] = [...tokens];
  for (let i = 0; i < tokens.length - 1; i++) {
    grams.push(`${tokens[i]}_${tokens[i + 1]}`);
  }
  for (const g of grams) {
    vec[hash(g) % FALLBACK_DIM] += 1;
  }
  // Sublinear scaling keeps frequent filler from dominating the direction.
  for (let i = 0; i < vec.length; i++) {
    if (vec[i] > 0) vec[i] = 1 + Math.log(vec[i]);
  }
  return normalize(vec);
}

export function normalize(vec: number[]): number[] {
  let sum = 0;
  for (const v of vec) sum += v * v;
  const norm = Math.sqrt(sum) || 1;
  return vec.map((v) => v / norm);
}

export function cosine(a: number[], b: number[]): number {
  // Both sides are stored normalised, so the dot product is the cosine.
  let dot = 0;
  const n = Math.min(a.length, b.length);
  for (let i = 0; i < n; i++) dot += a[i] * b[i];
  return dot;
}

/** Embed a batch of texts. Order of results matches order of input. */
export async function embed(texts: string[]): Promise<number[][]> {
  if (!texts.length) return [];
  const extractor = await getExtractor();
  if (!extractor) return texts.map(fallbackEmbed);

  const BATCH = 32;
  const out: number[][] = [];
  for (let i = 0; i < texts.length; i += BATCH) {
    const batch = texts.slice(i, i + BATCH).map((t) => t.slice(0, 2000));
    try {
      const result = await extractor(batch, { pooling: "mean", normalize: true });
      out.push(...result.tolist());
    } catch (err) {
      console.warn("[embeddings] batch failed, falling back:", err);
      out.push(...batch.map(fallbackEmbed));
    }
  }
  return out;
}

export async function embedOne(text: string): Promise<number[]> {
  const [v] = await embed([text]);
  return v ?? fallbackEmbed(text);
}
