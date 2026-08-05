import { PDFParse } from "pdf-parse";

export interface PageText {
  num: number;
  text: string;
}

/**
 * Running headers and footers repeat on all 56 pages of the corpus. Left in
 * place they would pollute every chunk and inflate lexical scores for the words
 * "Pandora", "corpus", and "knowledge" — which appear in almost every query.
 */
const NOISE = [
  /^PANDORA BUILDERTHON \d{4}\s*\|\s*RAG KNOWLEDGE CORPUS$/i,
  /^Pandora Knowledge Guardian Dataset\s*[•·]\s*Page\s*\d+$/i,
  /^Page\s+\d+$/i,
];

function stripRunningHeaders(text: string): string {
  return text
    .split(/\r?\n/)
    .filter((line) => {
      const t = line.trim();
      if (!t) return true;
      return !NOISE.some((re) => re.test(t));
    })
    .join("\n");
}

/** Extract per-page text so every chunk can carry a real page locator. */
export async function extractPages(data: Uint8Array): Promise<PageText[]> {
  const parser = new PDFParse({ data });
  try {
    const result = await parser.getText();
    return result.pages.map((p) => ({
      num: p.num,
      text: stripRunningHeaders(p.text ?? ""),
    }));
  } finally {
    await parser.destroy();
  }
}

/** Plain-text and markdown uploads arrive as a single synthetic page. */
export function pagesFromPlainText(text: string): PageText[] {
  const CHARS_PER_PAGE = 3000;
  const paragraphs = text.split(/\n{2,}/);
  const pages: PageText[] = [];
  let buf = "";
  let num = 1;
  for (const p of paragraphs) {
    if (buf.length + p.length > CHARS_PER_PAGE && buf.length > 0) {
      pages.push({ num: num++, text: buf.trim() });
      buf = "";
    }
    buf += p + "\n\n";
  }
  if (buf.trim()) pages.push({ num, text: buf.trim() });
  return pages.length ? pages : [{ num: 1, text }];
}

/**
 * CSV becomes one row per record so each row is independently retrievable,
 * with the header line prepended to give the values meaning in isolation.
 */
export function pagesFromCsv(text: string): PageText[] {
  const lines = text.split(/\r?\n/).filter((l) => l.trim());
  if (lines.length < 2) return [{ num: 1, text }];
  const header = lines[0];
  const cols = splitCsvLine(header);
  const rows = lines.slice(1).map((line, i) => {
    const cells = splitCsvLine(line);
    const pairs = cols.map((c, j) => `${c}: ${cells[j] ?? ""}`).join("; ");
    return `Row ${i + 1} — ${pairs}`;
  });
  const PER_PAGE = 25;
  const pages: PageText[] = [];
  for (let i = 0; i < rows.length; i += PER_PAGE) {
    pages.push({
      num: pages.length + 1,
      text: rows.slice(i, i + PER_PAGE).join("\n\n"),
    });
  }
  return pages;
}

function splitCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = "";
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (quoted) {
      if (ch === '"') {
        if (line[i + 1] === '"') {
          cur += '"';
          i++;
        } else quoted = false;
      } else cur += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") {
      out.push(cur.trim());
      cur = "";
    } else cur += ch;
  }
  out.push(cur.trim());
  return out;
}
