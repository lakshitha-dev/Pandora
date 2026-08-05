export type Role = "guardian" | "researcher" | "citizen"

export type EvidenceQuality = "verified" | "provisional" | "disputed" | "tradition" | "modeled"

export type EmergencyLevel = "none" | "W1" | "W2" | "W3" | "W4" | "CRITICAL"

export type SectionType = "priority" | "affected_species" | "likely_causes" | "recommended_actions"

export type AgentId = "marine_life" | "investigator" | "emergency"

export type OrbStatus = "dormant" | "active" | "complete" | "timeout"

export const ROLES: { id: Role; label: string; color: string }[] = [
  { id: "guardian", label: "Guardian", color: "cyan" },
  { id: "researcher", label: "Researcher", color: "purple" },
  { id: "citizen", label: "Citizen", color: "green" },
]

export const REGIONS = [
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
] as const

export type RegionId = (typeof REGIONS)[number]["id"]

export interface DocumentItem {
  id: string
  title: string
  pages: number
  chunks: number
  status: string
}

export const DOCUMENTS: DocumentItem[] = [
  { id: "corpus", title: "Pandora Knowledge Corpus", pages: 56, chunks: 220, status: "Loaded" },
  { id: "field", title: "Environmental Field Reports", pages: 24, chunks: 48, status: "Loaded" },
]

export const EVIDENCE_META: Record<
  EvidenceQuality,
  { label: string; symbol: string; tone: "green" | "amber" | "red" | "blue" | "gray"; tip: string }
> = {
  verified: {
    label: "Verified Observation",
    symbol: "✓",
    tone: "green",
    tip: "Supported by direct measurement or repeatable evidence.",
  },
  provisional: {
    label: "Provisional Interpretation",
    symbol: "~",
    tone: "amber",
    tip: "A plausible explanation not yet confirmed by documented evidence.",
  },
  disputed: {
    label: "Disputed Report",
    symbol: "!",
    tone: "red",
    tip: "Challenged by another source or weakened by poor evidence quality.",
  },
  tradition: {
    label: "Community Tradition",
    symbol: "◈",
    tone: "blue",
    tip: "Transmitted local or ancestral knowledge held by the community.",
  },
  modeled: {
    label: "Modeled Estimate",
    symbol: "≈",
    tone: "gray",
    tip: "Derived from models, not direct observation. Subject to assumptions.",
  },
}

export const EMERGENCY_META: Record<
  Exclude<EmergencyLevel, "none">,
  { label: string; shape: string; tone: "gray" | "amber" | "orange" | "red"; desc: string; citation: string }
> = {
  W1: {
    label: "W1 · Observation",
    shape: "●",
    tone: "gray",
    desc: "Logged for monitoring. Record, sample, compare upstream/downstream.",
    citation: "§4.5 Water Incident Classification, p.12",
  },
  W2: {
    label: "W2 · Advisory",
    shape: "▲",
    tone: "amber",
    desc: "Restrict sensitive use, provide alternate drinking water, investigate source.",
    citation: "§4.5 Water Incident Classification, p.12",
  },
  W3: {
    label: "W3 · Emergency",
    shape: "⬡",
    tone: "orange",
    desc: "Close access, activate medical and ecological teams, isolate inflow.",
    citation: "§4.5 Water Incident Classification, p.12",
  },
  W4: {
    label: "W4 · Regional Crisis",
    shape: "⬡",
    tone: "red",
    desc: "Regional command, public warning, external laboratories, long-term restoration.",
    citation: "§4.5 Water Incident Classification, p.12",
  },
  CRITICAL: {
    label: "CRITICAL",
    shape: "⬡",
    tone: "red",
    desc: "Life-safety threat. Immediate evacuation posture. All responders activated.",
    citation: "§12 Environmental Threats and Emergency Response",
  },
}

export interface GroundingCheck {
  rule: number
  name: string
  passed: boolean
  detail?: string
}

export const GROUNDING_CHECKS: GroundingCheck[] = [
  { rule: 1, name: "Cite record IDs for specific claims", passed: true, detail: "All 6 factual claims carry ≥1 valid marker" },
  { rule: 2, name: "Present multiple causes as hypotheses", passed: true, detail: "4 hypotheses listed, none asserted as confirmed" },
  { rule: 3, name: "No cross-record merging", passed: true, detail: "Each cited fact traces to its originating record only" },
  { rule: 4, name: "Preserve time and location", passed: true, detail: "WS-01 reading cited as Awa Reef North, 2026-06-02" },
  { rule: 5, name: "Health: red flags + fictional disclaimer", passed: true, detail: "No MED-* records retrieved — rule not triggered" },
  { rule: 6, name: "State when information is absent", passed: true, detail: "Cause not established — documented in Likely Causes section" },
  { rule: 7, name: "Surface conflicts, show reliability limits", passed: true, detail: "FN-A / FN-B / LAB-C conflict panel populated" },
  { rule: 8, name: "Separate documented protocol from inference", passed: true, detail: "All normative statements carry citations" },
]

export interface TraceStep {
  label: string
  detail: string
  elapsed: number
  done: boolean
}

export const SAMPLE_TRACE: TraceStep[] = [
  { label: "Query received", detail: "Turquoise water + fish movement near Awa Reef", elapsed: 0, done: true },
  { label: "Query rewritten", detail: "2 variants · Awa Reef · INC-001 ID extracted", elapsed: 120, done: true },
  { label: "Classified W2 Advisory", detail: "Fish avoidance + water discoloration → §4.5", elapsed: 280, done: true },
  { label: "Routing: sitrep mode", detail: "Incident indicators → 3 specialists dispatched in parallel", elapsed: 310, done: true },
  { label: "Retrieval: BM25 + vector", detail: "k=30 each leg · filter: Luminous Shelf", elapsed: 490, done: true },
  { label: "Reranked → top 6 retrieved", detail: "38 candidates → best score 3.71 / 4.0", elapsed: 680, done: true },
  { label: "3 specialists running", detail: "🐋 🌊 🚨 dispatched concurrently", elapsed: 710, done: true },
  { label: "GroundingGate: 8/8 passed", detail: "Groundedness 96% · conflict detected", elapsed: 2380, done: true },
  { label: "SITREP assembled", detail: "4.1 s · 6 LLM calls · 6 sources cited", elapsed: 4100, done: true },
]

export interface AgentOrbData {
  id: AgentId
  emoji: string
  name: string
  section: string
  color: "cyan" | "teal" | "violet"
  claimCount: number
  sourceCount: number
  durationMs: number
}

export const AGENT_ORBS: AgentOrbData[] = [
  { id: "marine_life", emoji: "🐋", name: "Marine-Life Protector", section: "Affected Species", color: "teal", claimCount: 3, sourceCount: 3, durationMs: 2600 },
  { id: "investigator", emoji: "🌊", name: "Incident Investigator", section: "Likely Causes", color: "cyan", claimCount: 5, sourceCount: 4, durationMs: 2900 },
  { id: "emergency", emoji: "🚨", name: "Emergency Responder", section: "Recommended Actions", color: "violet", claimCount: 6, sourceCount: 5, durationMs: 2400 },
]

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

export interface AffectedSpecies {
  id: string
  name: string
  habitat: string
  pressure: string
  protection: string
}

export interface Answer {
  question: string
  emergency: Exclude<EmergencyLevel, "none">
  priorityReason: string
  priorityCitation: string
  affectedRegions: RegionId[]
  affectedSpecies: AffectedSpecies[]
  causes: { term: string; detail: string; recordId?: string }[]
  quality: EvidenceQuality
  conflict?: {
    summary: string
    a: { label: string; text: string; quality: EvidenceQuality; limitation?: string }
    b: { label: string; text: string; quality: EvidenceQuality; limitation?: string }
    c: { label: string; text: string; quality: EvidenceQuality; limitation?: string }
  }
  recommendedActions: { step: number; action: string; citation?: string }[]
  publicComms: string
  sources: SourceCard[]
  confidence: number
  confidenceLevel: "high" | "moderate" | "low" | "insufficient"
  confidenceReason: string
}

export const ROLE_INTRO: Record<Role, string> = {
  guardian:
    "Field directive for on-site guardians. Prioritize containment and documented sampling before assigning any cause.",
  researcher:
    "Analytical summary for researchers. Note the unresolved three-way conflict (FN-A / FN-B / LAB-C) and the incomplete chain of custody at LAB-C.",
  citizen:
    "Public advisory. Water discoloration near Awa Reef is under active investigation. No confirmed hazard — avoid the area and follow official updates.",
}

export const SAMPLE_ANSWER: Answer = {
  question:
    "What are the possible causes of the turquoise water color near Awa Reef, and what should guardians do first?",
  emergency: "W2",
  priorityReason: "Fish avoidance and unusual water discoloration reported near Awa Reef",
  priorityCitation: "§4.5 Water Incident Classification, p.12",
  affectedRegions: ["REG-01"],
  affectedSpecies: [
    {
      id: "FAU-001",
      name: "Tideglass Grazer",
      habitat: "Seagrass lagoons",
      pressure: "Juveniles vulnerable to turbidity and water-quality decline",
      protection: "Protected during spawning — current status uncertain",
    },
    {
      id: "FAU-002",
      name: "Ribbonfin Skimmer",
      habitat: "Warm reef channels",
      pressure: "Sensitive to oil films and chemical contamination",
      protection: "No harvest during Bloom Tide",
    },
    {
      id: "FAU-004",
      name: "Reef Lantern Crab",
      habitat: "Coral rubble",
      pressure: "Disruption of bioluminescent signaling under turbid or contaminated water",
      protection: "Hand collection prohibited",
    },
  ],
  causes: [
    {
      term: "Mineral sediment plume",
      detail:
        "Suspended silicate sediment stirred from the shelf floor can scatter light toward turquoise. Consistent with recent current shifts.",
      recordId: "INC-001",
    },
    {
      term: "Plankton bloom",
      detail:
        "A rapid bloom of bioluminescent phytoplankton can tint shallows. Field Note FN-A favors this natural explanation — no industrial odor detected.",
      recordId: "FN-A",
    },
    {
      term: "Chemical / pigment release",
      detail:
        "Upstream pigment workshop damage could discharge coloring compounds into the tributary feeding Awa Reef. Field Note FN-B raises this possibility — entry into water unconfirmed.",
      recordId: "FN-B",
    },
    {
      term: "Light reflection artifact",
      detail:
        "Angle-of-incidence effects over pale carbonate sand can exaggerate perceived color. Should be ruled out before escalation.",
      recordId: "INC-001",
    },
  ],
  quality: "provisional",
  conflict: {
    summary:
      "Three records describe the same event and reach incompatible conclusions. No cause is confirmed. See reliability limitations below.",
    a: {
      label: "Field Note FN-A · 2026-06-02",
      text: "Observed rapid greenish sheen consistent with seasonal phytoplankton bloom after three calm hot days. No industrial odor detected. Strongest near the surface.",
      quality: "disputed",
      limitation: "Single observer, no chemical sampling",
    },
    b: {
      label: "Field Note FN-B · 2026-06-03",
      text: "Maintenance work at upstream pigment workshop two days prior. Damaged waste container observed — entry into water not confirmed. Requires follow-up sampling.",
      quality: "disputed",
      limitation: "Material entry into water never confirmed",
    },
    c: {
      label: "Laboratory Note LAB-C · 2026-06-05",
      text: "Detected elevated harmless carbonate particles and moderate plankton density. Both natural and human contributions remain possible.",
      quality: "disputed",
      limitation: "Chain-of-custody form was incomplete — sample integrity cannot be assured",
    },
  },
  recommendedActions: [
    { step: 1, action: "Restrict shellfish harvest and direct drinking from reef area immediately", citation: "INC-001" },
    { step: 2, action: "Sample water at three depths upstream, within the event zone, and downstream", citation: "A.1" },
    { step: 3, action: "Inspect upstream activities — especially the pigment workshop noted in FN-B", citation: "FN-B" },
    { step: 4, action: "Photograph from fixed reference points and record water color with a reference card", citation: "A.1" },
    { step: 5, action: "Complete chain-of-custody forms for all samples before transport to laboratory", citation: "LAB-C" },
    { step: 6, action: "Notify drinking-water, fishery, and clinic operators while exposure risk remains unconfirmed", citation: "POL-010" },
  ],
  publicComms:
    "At 2026-06-02 near Awa Reef, we observed unusual turquoise water discoloration and fish movement offshore. The cause is not yet confirmed. People should avoid direct contact with the water and refrain from harvesting shellfish. Report any symptoms through your village health coordinator. The next update will be issued at 2026-06-06.",
  sources: [
    {
      id: "s1",
      doc: "Pandora Knowledge Corpus",
      ref: "Chapter 12 · Page 40 · INC-001",
      relevance: 94,
      excerpt:
        "Plausible causes listed in the incident record: mineral sediment, plankton bloom, chemical release, light reflection. These are hypotheses, not confirmed findings. The response team must avoid selecting the most dramatic explanation without measurements or corroboration.",
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
        "Water color change began after three calm hot days and was strongest near the surface. Author suggests a plankton bloom and notes no chemical odor.",
      region: "Luminous Shelf",
      category: "Field Observation",
      quality: "disputed",
    },
    {
      id: "s3",
      doc: "Field Note FN-B · 2026-06-03",
      ref: "Field Log · Entry 15",
      relevance: 81,
      excerpt:
        "Maintenance work on upstream pigment workshop two days before color change. Author observed damaged waste container but did not confirm that material entered the water.",
      region: "Luminous Shelf",
      category: "Field Observation",
      quality: "disputed",
    },
    {
      id: "s4",
      doc: "Laboratory Note LAB-C · 2026-06-05",
      ref: "Lab Record · Entry 7",
      relevance: 76,
      excerpt:
        "Detected elevated harmless carbonate particles and moderate plankton density. Chain-of-custody form was incomplete. Both natural and human contributions remain possible.",
      region: "Luminous Shelf",
      category: "Laboratory Analysis",
      quality: "disputed",
    },
    {
      id: "s5",
      doc: "Pandora Knowledge Corpus",
      ref: "Chapter 4 · Page 12 · §4.5",
      relevance: 88,
      excerpt:
        "W2 Advisory — Minor symptoms, localized fish avoidance, moderate parameter shift. Restrict sensitive use, provide alternate drinking water, investigate source.",
      region: "Luminous Shelf",
      category: "Water Classification",
      quality: "verified",
    },
    {
      id: "s6",
      doc: "Pandora Knowledge Corpus",
      ref: "Appendix A · Page 49 · A.1",
      relevance: 72,
      excerpt:
        "Take upstream, event-zone, and downstream samples at consistent depths. Use clean labeled containers and complete chain-of-custody forms. Notify drinking-water operators when exposure is plausible.",
      region: "Luminous Shelf",
      category: "Field Checklist",
      quality: "verified",
    },
  ],
  confidence: 68,
  confidenceLevel: "moderate",
  confidenceReason: "Moderate — 3 sources in direct conflict, chain-of-custody incomplete at LAB-C, cause not established.",
}

export const SUGGESTED_QUESTIONS = [
  "What causes unusual water color near Awa Reef?",
  "Which marine species are most vulnerable to contamination?",
  "Emergency steps after detecting coral damage?",
  "Compare water contamination vs. volcanic event responses",
]
