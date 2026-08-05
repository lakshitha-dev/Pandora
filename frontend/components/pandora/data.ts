export type Role = "guardian" | "researcher" | "citizen"

export type EvidenceQuality = "verified" | "provisional" | "disputed"

export type EmergencyLevel = "none" | "W1" | "W2" | "W3" | "W4" | "CRITICAL"

export const ROLES: { id: Role; label: string; color: string }[] = [
  { id: "guardian", label: "Guardian", color: "cyan" },
  { id: "researcher", label: "Researcher", color: "purple" },
  { id: "citizen", label: "Citizen", color: "green" },
]

export const REGIONS = [
  "Luminous Shelf",
  "Emerald Canopy",
  "Cloudspine Highlands",
  "Silverreed Wetlands",
  "Obsidian Reach",
  "Whispering Dunes",
  "Deep Current Expanse",
  "Mistroot Basin",
  "Aurora Mangroves",
  "Sunfall Archipelago",
] as const

export interface DocumentItem {
  id: string
  title: string
  pages: number
  status: string
}

export const DOCUMENTS: DocumentItem[] = [
  { id: "corpus", title: "Pandora Knowledge Corpus", pages: 56, status: "Loaded" },
  { id: "field", title: "Environmental Field Reports", pages: 24, status: "Loaded" },
]

export const EVIDENCE_META: Record<
  EvidenceQuality,
  { label: string; symbol: string; tone: "green" | "amber" | "red"; tip: string }
> = {
  verified: {
    label: "Verified Observation",
    symbol: "✓",
    tone: "green",
    tip: "Directly documented and independently confirmed in the corpus.",
  },
  provisional: {
    label: "Provisional Interpretation",
    symbol: "~",
    tone: "amber",
    tip: "An informed inference from available records — not yet confirmed.",
  },
  disputed: {
    label: "Disputed Report",
    symbol: "!",
    tone: "red",
    tip: "Sources disagree or the chain of evidence is incomplete.",
  },
}

export const EMERGENCY_META: Record<
  Exclude<EmergencyLevel, "none">,
  { label: string; tone: "gray" | "amber" | "orange" | "red"; desc: string }
> = {
  W1: { label: "W1 · Observation", tone: "gray", desc: "Logged for monitoring. No action required yet." },
  W2: { label: "W2 · Advisory", tone: "amber", desc: "Heightened watch. Precautionary guidance issued." },
  W3: { label: "W3 · Emergency", tone: "orange", desc: "Active incident. Response protocol engaged." },
  W4: { label: "W4 · Regional Crisis", tone: "red", desc: "Multi-region escalation. Command activated." },
  CRITICAL: { label: "CRITICAL", tone: "red", desc: "Life-safety threat. Immediate evacuation posture." },
}

export interface SourceCard {
  id: string
  doc: string
  ref: string
  relevance: number
  excerpt: string
  region?: string
  category?: string
  quality: EvidenceQuality
}

export interface Answer {
  question: string
  causes: { term: string; detail: string }[]
  quality: EvidenceQuality
  emergency: Exclude<EmergencyLevel, "none">
  conflict?: {
    summary: string
    a: { label: string; text: string }
    b: { label: string; text: string }
  }
  sources: SourceCard[]
  confidence: number
  confidenceReason: string
}

// Role-specific opening line for the same underlying evidence.
export const ROLE_INTRO: Record<Role, string> = {
  guardian:
    "Field directive for on-site guardians. Prioritize containment and documented sampling before assigning any cause.",
  researcher:
    "Analytical summary for researchers. Note the unresolved three-way conflict and the incomplete chain of custody below.",
  citizen:
    "Public advisory. The water discoloration near Awa Reef is under investigation. There is no confirmed hazard — follow official updates.",
}

export const SAMPLE_ANSWER: Answer = {
  question:
    "What are the possible causes of the turquoise water color near Awa Reef, and what should guardians do first?",
  causes: [
    {
      term: "Mineral sediment plume",
      detail:
        "Suspended silicate sediment stirred from the shelf floor can scatter light toward turquoise. Consistent with recent current shifts.",
    },
    {
      term: "Plankton bloom",
      detail:
        "A rapid bloom of bioluminescent phytoplankton can tint shallows. Field Note FN-A favors this natural explanation.",
    },
    {
      term: "Chemical / pigment release",
      detail:
        "Upstream pigment workshop damage could discharge coloring compounds. Field Note FN-B raises this possibility.",
    },
    {
      term: "Light reflection artifact",
      detail:
        "Angle-of-incidence effects over pale carbonate sand can exaggerate perceived color and should be ruled out first.",
    },
  ],
  quality: "provisional",
  emergency: "W2",
  conflict: {
    summary:
      "Field Note FN-A suggests a natural plankton bloom. Field Note FN-B notes upstream pigment workshop damage. Cause is unconfirmed.",
    a: {
      label: "Field Note FN-A · 2026-06-02",
      text: "Observed rapid greenish sheen consistent with seasonal phytoplankton bloom. No industrial odor detected. Recommend routine monitoring.",
    },
    b: {
      label: "Field Note FN-B · 2026-06-03",
      text: "Reported structural damage at the upstream pigment workshop. Possible dye discharge into the tributary feeding Awa Reef. Chain of custody incomplete.",
    },
  },
  sources: [
    {
      id: "s1",
      doc: "Pandora Knowledge Corpus",
      ref: "Chapter 12 · Page 40",
      relevance: 94,
      excerpt:
        "Environmental incident protocol for anomalous water coloration on the Luminous Shelf: isolate, sample per checklist A.1, and refrain from declaring a cause before chain-of-custody confirmation.",
      region: "Luminous Shelf",
      category: "Environmental Incident",
      quality: "verified",
    },
    {
      id: "s2",
      doc: "Field Note FN-A · 2026-06-02",
      ref: "Field Log · Entry 14",
      relevance: 87,
      excerpt:
        "Greenish sheen near Awa Reef consistent with seasonal phytoplankton bloom. No industrial odor. Recommend routine monitoring rather than escalation.",
      region: "Luminous Shelf",
      category: "Observation",
      quality: "provisional",
    },
    {
      id: "s3",
      doc: "Field Note FN-B · 2026-06-03",
      ref: "Field Log · Entry 15",
      relevance: 81,
      excerpt:
        "Upstream pigment workshop damaged; possible dye discharge into tributary. Sample not sealed on collection — chain of custody incomplete.",
      region: "Luminous Shelf",
      category: "Disputed Report",
      quality: "disputed",
    },
  ],
  confidence: 68,
  confidenceReason: "Moderate — 3 sources, 1 unresolved conflict, chain-of-custody incomplete.",
}

export const SUGGESTED_QUESTIONS = [
  "What causes unusual water color near Awa Reef?",
  "Which marine species are most vulnerable to contamination?",
  "Emergency steps after detecting coral damage?",
  "Compare water contamination vs. volcanic event responses",
]
