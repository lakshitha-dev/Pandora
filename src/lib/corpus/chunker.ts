import type { Chunk, ChunkMeta, RecordType } from "@/lib/types";
import type { PageText } from "./pdf";
import {
  detectAccessClass,
  detectEvidenceQuality,
  detectRegion,
  detectSeverity,
  isNavigational,
  recordTypeFor,
} from "./classify";

/**
 * Structure-aware chunking.
 *
 * A fixed-size sliding window would be the wrong tool for this corpus. The
 * source is a register of self-contained records — "FAU-003 — Deepbell Singer"
 * runs about 220 words and answers a question on its own — so we cut on record
 * and section boundaries instead. Each chunk then has a real citable identity
 * (record ID + page) rather than an arbitrary offset.
 */

const RECORD_HEADING =
  /^((?:REG|STL|FAU|FLR|MED|INC|POL|ACC|KC)-\d{2,3})\s*[—–-]\s*(.+)$/;
const KNOWLEDGE_CARD = /^Knowledge Card\s+(KC-\d{2})\s*$/i;
const CHAPTER = /^(\d{1,2})\.\s+([A-Z][^.]{3,})$/;
const SECTION = /^(\d{1,2}\.\d{1,2})\s+(.{3,})$/;
const APPENDIX = /^Appendix\s+([A-Z])\s*[—–-]?\s*(.*)$/i;
const APPENDIX_SECTION = /^([A-Z]\.\d)\s+(.{3,})$/;
const NAMED_SECTION =
  /^(Document Map and Retrieval Metadata|Document Control|PURPOSE|IMPORTANT NOTICE)\s*:?\s*$/i;
/** Field and laboratory notes live inside §14.3 but must be separable. */
const FIELD_NOTE = /(Field Note|Laboratory Note)\s+((?:FN|LAB)-[A-Z])\b/g;

/** Chunks longer than this are split on sentence boundaries with overlap. */
const MAX_CHARS = 1500;
const OVERLAP_CHARS = 180;
/** A sentence repeated in at least this many records is treated as boilerplate. */
const BOILERPLATE_THRESHOLD = 3;

interface Segment {
  recordId: string | null;
  title: string;
  type: RecordType;
  chapter: number | null;
  chapterTitle: string | null;
  section: string | null;
  page: number;
  lines: string[];
}

interface Line {
  text: string;
  page: number;
}

function flatten(pages: PageText[]): Line[] {
  const out: Line[] = [];
  for (const p of pages) {
    for (const raw of p.text.split(/\r?\n/)) {
      out.push({ text: raw.trim(), page: p.num });
    }
  }
  return out;
}

/**
 * Reflow visually-wrapped PDF lines back into sentences. PDF text extraction
 * breaks at the end of every rendered line, so joining first and splitting on
 * sentence terminators recovers the author's units far more reliably than
 * trusting blank lines to mark paragraphs.
 */
function toSentences(lines: string[]): string[] {
  const joined = lines
    .join(" ")
    // Repair words hyphenated across a line break ("drinking- water").
    .replace(/(\w)-\s+(\w)/g, "$1$2")
    .replace(/\s{2,}/g, " ")
    .trim();
  if (!joined) return [];
  const parts = joined.match(/[^.!?]+[.!?]+(?:\s|$)|[^.!?]+$/g);
  return (parts ?? [joined]).map((s) => s.trim()).filter(Boolean);
}

function normalizeSentence(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9 ]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

/** Segment the linear line stream on structural headings. */
function segment(lines: Line[], docTitle: string): Segment[] {
  const segments: Segment[] = [];
  let chapter: number | null = null;
  let chapterTitle: string | null = null;
  let current: Segment | null = null;

  const open = (s: Omit<Segment, "lines">) => {
    if (current && current.lines.join("").trim()) segments.push(current);
    else if (current) segments.push(current);
    current = { ...s, lines: [] };
  };

  // Everything before the first heading belongs to a front-matter segment.
  current = {
    recordId: null,
    title: `${docTitle} — front matter`,
    type: "chapter",
    chapter: null,
    chapterTitle: null,
    section: null,
    page: lines[0]?.page ?? 1,
    lines: [],
  };

  for (const line of lines) {
    const t = line.text;
    if (!t) {
      current?.lines.push("");
      continue;
    }

    const record = RECORD_HEADING.exec(t);
    if (record) {
      const id = record[1].toUpperCase();
      open({
        recordId: id,
        title: record[2].trim(),
        type: recordTypeFor(id) ?? "section",
        chapter,
        chapterTitle,
        section: null,
        page: line.page,
      });
      continue;
    }

    const card = KNOWLEDGE_CARD.exec(t);
    if (card) {
      const id = card[1].toUpperCase();
      open({
        recordId: id,
        title: `Knowledge Card ${id}`,
        type: "knowledge-card",
        chapter,
        chapterTitle,
        section: null,
        page: line.page,
      });
      continue;
    }

    const sec = SECTION.exec(t);
    if (sec) {
      open({
        recordId: null,
        title: sec[2].trim(),
        type: "section",
        chapter,
        chapterTitle,
        section: sec[1],
        page: line.page,
      });
      continue;
    }

    const chap = CHAPTER.exec(t);
    if (chap && Number(chap[1]) >= 1 && Number(chap[1]) <= 20) {
      chapter = Number(chap[1]);
      chapterTitle = chap[2].trim();
      open({
        recordId: null,
        title: chapterTitle,
        type: "chapter",
        chapter,
        chapterTitle,
        section: String(chapter),
        page: line.page,
      });
      continue;
    }

    const appSec = APPENDIX_SECTION.exec(t);
    if (appSec) {
      open({
        recordId: null,
        title: appSec[2].trim(),
        type: "appendix",
        chapter,
        chapterTitle,
        section: appSec[1],
        page: line.page,
      });
      continue;
    }

    const app = APPENDIX.exec(t);
    if (app) {
      open({
        recordId: null,
        title: `Appendix ${app[1].toUpperCase()}${app[2] ? ` — ${app[2].trim()}` : ""}`,
        type: "appendix",
        chapter,
        chapterTitle,
        section: `Appendix ${app[1].toUpperCase()}`,
        page: line.page,
      });
      continue;
    }

    if (NAMED_SECTION.test(t)) {
      open({
        recordId: null,
        title: t.replace(/:$/, "").trim(),
        type: "section",
        chapter,
        chapterTitle,
        section: null,
        page: line.page,
      });
      continue;
    }

    current?.lines.push(t);
  }

  if (current) segments.push(current);
  return segments.filter((s) => s.lines.join(" ").trim().length > 40);
}

/**
 * Split §14.3-style segments that contain several independently-citable notes
 * into one segment per note, so a contradiction can name FN-A vs FN-B vs LAB-C.
 */
function splitFieldNotes(segments: Segment[]): Segment[] {
  const out: Segment[] = [];
  for (const seg of segments) {
    const body = seg.lines.join(" ");
    const ids = [...body.matchAll(FIELD_NOTE)];
    if (ids.length < 2) {
      out.push(seg);
      continue;
    }
    // Keep the parent segment for its framing sentences, then add each note.
    const firstAt = ids[0].index ?? 0;
    const preamble = body.slice(0, firstAt).trim();
    if (preamble.length > 60) {
      out.push({ ...seg, lines: [preamble] });
    }
    ids.forEach((m, i) => {
      const start = m.index ?? 0;
      const end = i + 1 < ids.length ? (ids[i + 1].index ?? body.length) : body.length;
      const text = body.slice(start, end).trim();
      if (text.length < 40) return;
      out.push({
        ...seg,
        recordId: m[2].toUpperCase(),
        title: `${m[1]} ${m[2].toUpperCase()}`,
        type: "field-note",
        lines: [text],
      });
    });
  }
  return out;
}

interface Deduped {
  segments: Array<Segment & { sentences: string[] }>;
  sharedProtocols: Array<{
    type: RecordType;
    label: string;
    sentences: string[];
    appliesTo: string[];
  }>;
  removedSentences: number;
}

/**
 * Hoist repeated boilerplate out of individual records.
 *
 * This corpus repeats large blocks verbatim: all ten regions share the same
 * "Recommended baseline assessment" and "Restoration priorities" paragraphs,
 * all ten settlements share the same four-safety-zones text, all thirty fauna
 * profiles share the same secondary-pressures and monitoring paragraphs, and
 * the twenty Knowledge Cards are near-identical.
 *
 * Left in place, a top-k search for "restoration priorities" returns ten
 * indistinguishable neighbours and crowds out the one record that actually
 * answers the question. So we store each shared block once as a
 * `shared-protocol` chunk and strip it from the records, which leaves every
 * record chunk carrying only what makes it distinct. Retrieval precision rises
 * sharply and the shared protocol is still citable in its own right.
 */
function dedupeBoilerplate(segments: Segment[]): Deduped {
  const withSentences = segments.map((s) => ({
    ...s,
    sentences: toSentences(s.lines),
  }));

  const occurrences = new Map<string, number[]>();
  withSentences.forEach((seg, i) => {
    const seen = new Set<string>();
    for (const sentence of seg.sentences) {
      const key = normalizeSentence(sentence);
      // Very short sentences are headings or fragments, not boilerplate.
      if (key.length < 45 || seen.has(key)) continue;
      seen.add(key);
      const list = occurrences.get(key) ?? [];
      list.push(i);
      occurrences.set(key, list);
    }
  });

  const repeated = new Set<string>();
  for (const [key, list] of occurrences) {
    if (list.length >= BOILERPLATE_THRESHOLD) repeated.add(key);
  }

  // Group the repeated sentences by the record family they belong to, keeping
  // first-appearance order so the hoisted protocol still reads naturally.
  const groups = new Map<
    RecordType,
    { sentences: string[]; seen: Set<string>; appliesTo: Set<string> }
  >();
  let removedSentences = 0;

  const cleaned = withSentences.map((seg) => {
    const kept: string[] = [];
    seg.sentences.forEach((sentence, idx) => {
      const key = normalizeSentence(sentence);
      // Always keep the opening sentence: it carries the record's identity.
      if (idx === 0 || !repeated.has(key)) {
        kept.push(sentence);
        return;
      }
      removedSentences++;
      const group =
        groups.get(seg.type) ??
        { sentences: [], seen: new Set<string>(), appliesTo: new Set<string>() };
      if (!group.seen.has(key)) {
        group.seen.add(key);
        group.sentences.push(sentence);
      }
      if (seg.recordId) group.appliesTo.add(seg.recordId);
      groups.set(seg.type, group);
    });
    return { ...seg, sentences: kept };
  });

  const sharedProtocols = [...groups.entries()]
    .filter(([, g]) => g.sentences.length > 0)
    .map(([type, g]) => ({
      type,
      label: `Shared protocol — ${type.replace(/-/g, " ")} records`,
      sentences: g.sentences,
      appliesTo: [...g.appliesTo].sort(),
    }));

  return { segments: cleaned, sharedProtocols, removedSentences };
}

/** Split an over-long body on sentence boundaries, with a little overlap. */
function packSentences(sentences: string[]): string[] {
  const bodies: string[] = [];
  let buf = "";
  for (const s of sentences) {
    if (buf.length + s.length + 1 > MAX_CHARS && buf) {
      bodies.push(buf.trim());
      const tail = buf.slice(-OVERLAP_CHARS);
      const pivot = tail.indexOf(" ");
      buf = pivot === -1 ? "" : tail.slice(pivot + 1) + " ";
    }
    buf += s + " ";
  }
  if (buf.trim()) bodies.push(buf.trim());
  return bodies;
}

export interface ChunkResult {
  chunks: Chunk[];
  stats: {
    segments: number;
    chunks: number;
    sharedProtocols: number;
    boilerplateSentencesHoisted: number;
  };
}

export function chunkDocument(
  pages: PageText[],
  docId: string,
  docName: string,
): ChunkResult {
  const lines = flatten(pages);
  const rawSegments = splitFieldNotes(segment(lines, docName));
  const { segments, sharedProtocols, removedSentences } =
    dedupeBoilerplate(rawSegments);

  const chunks: Chunk[] = [];
  let seq = 0;

  const push = (text: string, meta: ChunkMeta) => {
    chunks.push({
      id: `${docId}#${seq++}`,
      text,
      tokens: Math.ceil(text.length / 4),
      meta,
    });
  };

  for (const seg of segments) {
    if (!seg.sentences.length) continue;
    const full = seg.sentences.join(" ");
    if (full.trim().length < 40) continue;

    const type = seg.type;
    const region = detectRegion(`${seg.title} ${full}`);
    const bodies = packSentences(seg.sentences);

    bodies.forEach((body, part) => {
      // Prefix the heading so an isolated chunk still states what it describes.
      const heading = seg.recordId
        ? `${seg.recordId} — ${seg.title}`
        : seg.section
          ? `${seg.section} ${seg.title}`
          : seg.title;
      const text =
        bodies.length > 1
          ? `${heading} (part ${part + 1} of ${bodies.length})\n${body}`
          : `${heading}\n${body}`;

      push(text, {
        docId,
        docName,
        page: seg.page,
        chapter: seg.chapter,
        chapterTitle: seg.chapterTitle,
        section: seg.section,
        recordId: seg.recordId,
        recordType: type,
        title: seg.title,
        region,
        accessClass: detectAccessClass(type, full),
        evidenceQuality: detectEvidenceQuality(type, full),
        severity: detectSeverity(type, full),
        isSharedProtocol: false,
        navigational: isNavigational(seg.title, seg.section),
      });
    });
  }

  for (const proto of sharedProtocols) {
    const body = proto.sentences.join(" ");
    const text = `${proto.label}\nThis protocol text is shared verbatim across ${proto.appliesTo.length || "multiple"} records (${proto.appliesTo.slice(0, 6).join(", ")}${proto.appliesTo.length > 6 ? ", …" : ""}). It is stored once to keep individual records distinctive.\n${body}`;
    push(text, {
      docId,
      docName,
      page: 1,
      chapter: null,
      chapterTitle: null,
      section: null,
      recordId: null,
      recordType: "shared-protocol",
      title: proto.label,
      region: null,
      accessClass: "public",
      evidenceQuality: "documented-protocol",
      severity: "none",
      isSharedProtocol: true,
      appliesTo: proto.appliesTo,
      navigational: false,
    });
  }

  return {
    chunks,
    stats: {
      segments: segments.length,
      chunks: chunks.length,
      sharedProtocols: sharedProtocols.length,
      boilerplateSentencesHoisted: removedSentences,
    },
  };
}
