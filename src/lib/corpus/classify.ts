import type {
  AccessClass,
  EvidenceQuality,
  RecordType,
  Severity,
} from "@/lib/types";

/** ID prefix → record family. */
const PREFIX_TO_TYPE: Record<string, RecordType> = {
  REG: "region",
  STL: "settlement",
  FAU: "fauna",
  FLR: "flora",
  MED: "medical",
  INC: "incident",
  POL: "policy",
  ACC: "accommodation",
  KC: "knowledge-card",
  WS: "water-station",
  SV: "survey",
  FN: "field-note",
  LAB: "field-note",
};

export function recordTypeFor(recordId: string | null): RecordType | null {
  if (!recordId) return null;
  const prefix = recordId.split("-")[0]?.toUpperCase();
  return PREFIX_TO_TYPE[prefix] ?? null;
}

/**
 * The ten named regions. Used both to tag chunks with a region and to power
 * metadata-filtered retrieval ("what happened in the Obsidian Reach?").
 */
export const REGIONS: Array<{ id: string; name: string }> = [
  { id: "REG-01", name: "Luminous Shelf" },
  { id: "REG-02", name: "Emerald Canopy" },
  { id: "REG-03", name: "Cloudspine Highlands" },
  { id: "REG-04", name: "Silverreed Wetlands" },
  { id: "REG-05", name: "Obsidian Reach" },
  { id: "REG-06", name: "Whispering Dunes" },
  { id: "REG-07", name: "Deep Current Expanse" },
  { id: "REG-08", name: "Mistroot Basin" },
  { id: "REG-09", name: "Aurora Mangroves" },
  { id: "REG-10", name: "Sunfall Archipelago" },
];

/**
 * Region detection is deliberately name-based and longest-match-first.
 *
 * §15.2 warns: "Do not merge details from two species, villages, plants, or
 * incidents merely because their names or habitats are similar." The corpus
 * contains Silverreed Wetlands (REG-04), the Silverreed Stalker (FAU-008) and
 * Silver Reed (FLR-011) — three unrelated records. Matching the full region
 * name rather than the token "silverreed" keeps them apart.
 */
export function detectRegion(text: string): string | null {
  const haystack = text.toLowerCase();
  let best: { name: string; at: number } | null = null;
  for (const r of REGIONS) {
    const at = haystack.indexOf(r.name.toLowerCase());
    if (at === -1) continue;
    if (!best || at < best.at) best = { name: r.name, at };
  }
  return best?.name ?? null;
}

/**
 * Access classification per Chapter 11 and POL-005.
 *
 * Clinical protocols are healer-limited; live incident records are
 * guardian-limited; anything touching sacred or restricted knowledge is
 * community-limited. Everything else is public.
 */
export function detectAccessClass(
  type: RecordType,
  text: string,
): AccessClass {
  const t = text.toLowerCase();
  if (
    t.includes("sacred") ||
    t.includes("restricted knowledge") ||
    t.includes("without consent")
  ) {
    return "community-limited";
  }
  if (type === "medical") return "healer-limited";
  if (type === "flora" && /healer|dose|infusion|toxic|medicinal/.test(t)) {
    return "healer-limited";
  }
  if (type === "incident") return "guardian-limited";
  return "public";
}

/**
 * Evidence quality, using the vocabulary the corpus defines in Chapter 1 and
 * the glossary. Order matters: the strongest disqualifying signal wins, so a
 * record with an incomplete chain of custody is never labelled "verified".
 */
export function detectEvidenceQuality(
  type: RecordType,
  text: string,
): EvidenceQuality {
  const t = text.toLowerCase();

  // Chapter 1 and the glossary *define* the label "disputed report", so a bare
  // keyword match would mislabel the very sections that explain the vocabulary.
  // Only concrete custody or corroboration failures count.
  const isDefinitional =
    type === "chapter" || type === "section" || type === "appendix";
  if (
    !isDefinitional &&
    (t.includes("chain-of-custody form was incomplete") ||
      t.includes("chain of custody was incomplete") ||
      t.includes("did not confirm that material entered") ||
      t.includes("but did not confirm"))
  ) {
    return "disputed-report";
  }
  if (
    t.includes("these are hypotheses, not confirmed findings") ||
    t.includes("plausible causes") ||
    t.includes("may change as evidence is collected") ||
    t.includes("suggests")
  ) {
    return "provisional-interpretation";
  }
  if (
    t.includes("traditional") ||
    t.includes("oral knowledge") ||
    t.includes("community tradition") ||
    t.includes("elders")
  ) {
    return "community-tradition";
  }
  if (type === "water-station" || type === "survey") {
    // Measurement tables are verified observations, but a survey whose own
    // comment undermines comparability is not.
    if (/poor visibility|not directly comparable|blocked access/.test(t)) {
      return "disputed-report";
    }
    return "verified-observation";
  }
  if (type === "policy" || type === "knowledge-card") return "documented-protocol";
  if (t.includes("modeled") || t.includes("estimate")) return "modeled-estimate";
  if (type === "medical" || type === "shared-protocol") return "documented-protocol";
  return "verified-observation";
}

/** Incident records state their own risk level; we lift it verbatim. */
export function detectSeverity(type: RecordType, text: string): Severity {
  const m = /initial risk level:\s*(CRITICAL|HIGH|MEDIUM|LOW)/i.exec(text);
  if (m) return m[1].toLowerCase() as Severity;
  if (type === "incident") return "medium";
  const t = text.toLowerCase();
  if (/\bw4\b|regional crisis/.test(t)) return "critical";
  if (/\bw3\b|emergency/.test(t) && type !== "accommodation") return "high";
  return "none";
}

/**
 * Sections that describe the corpus rather than Pandora.
 *
 * The table of contents, the glossary, the list of suggested test questions and
 * the retrieval-grounding rules are all highly "relevant" to any question about
 * Pandora — they name every topic in the book — which made them surface
 * constantly while displacing actual records. They stay in the index (a
 * definitional query should still find the glossary) but carry a low prior.
 */
const NAVIGATIONAL_TITLES =
  /document map|document control|recommended test questions|retrieval grounding rules|glossary|front matter|purpose|important notice/i;

export function isNavigational(title: string, section: string | null): boolean {
  if (NAVIGATIONAL_TITLES.test(title)) return true;
  // §15.1–15.3 are the evaluation-harness sections, not Pandora knowledge.
  return section !== null && /^15\.[123]$/.test(section);
}

/**
 * Retrieval prior per record family: how specific and informative a chunk of
 * this kind tends to be. Applied multiplicatively to the fused rank score.
 *
 * Knowledge cards are penalised because all twenty are near-identical
 * templates, and shared protocols because they are generic by construction —
 * both are still retrievable, they just no longer outrank the specific record
 * that actually answers the question.
 */
export function retrievalPrior(
  type: RecordType,
  navigational: boolean,
): number {
  if (navigational) return 0.3;
  if (type === "shared-protocol") return 0.62;
  if (type === "knowledge-card") return 0.5;
  if (type === "chapter") return 0.85;
  return 1;
}

/** Friendly label for a record family, used in the source cards. */
export function recordTypeLabel(type: RecordType): string {
  const labels: Record<RecordType, string> = {
    region: "Region",
    settlement: "Settlement",
    fauna: "Species",
    flora: "Flora",
    medical: "Clinical",
    incident: "Incident",
    policy: "Policy",
    accommodation: "Accommodation",
    "knowledge-card": "Knowledge card",
    "water-station": "Monitoring",
    survey: "Survey",
    "field-note": "Field note",
    section: "Section",
    chapter: "Chapter",
    appendix: "Appendix",
    "shared-protocol": "Shared protocol",
  };
  return labels[type];
}

export const EVIDENCE_LABEL: Record<EvidenceQuality, string> = {
  "verified-observation": "Verified observation",
  "community-tradition": "Community tradition",
  "provisional-interpretation": "Provisional interpretation",
  "modeled-estimate": "Modeled estimate",
  "disputed-report": "Disputed report",
  "documented-protocol": "Documented protocol",
};

export const ACCESS_LABEL: Record<AccessClass, string> = {
  public: "Public",
  "community-limited": "Community-limited",
  "healer-limited": "Healer-limited",
  "guardian-limited": "Guardian-limited",
};
