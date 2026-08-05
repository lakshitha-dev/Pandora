"use client"

import { useState } from "react"
import { CircleCheck, Clock, XCircle, Database, Activity, GitMerge } from "lucide-react"
import { cn } from "@/lib/utils"
import { EvidenceBadge, CitationChip } from "./badges"
import {
  AGENT_ORBS, GROUNDING_CHECKS, SAMPLE_TRACE, type Answer, type OrbStatus,
} from "./data"

/* ---- Confidence Gauge ---- */
function ConfidenceGauge({ value, level }: { value: number; level: Answer["confidenceLevel"] }) {
  const colorClass = {
    high: "stroke-primary",
    moderate: "stroke-warning",
    low: "stroke-critical",
    insufficient: "stroke-muted-foreground",
  }[level]
  const glowColor = {
    high: "#3EE8D0",
    moderate: "#F0A93E",
    low: "#F0644E",
    insufficient: "#8FAFB8",
  }[level]
  const r = 42
  const circ = 2 * Math.PI * r
  const dash = (value / 100) * circ
  return (
    <div className="flex flex-col items-center gap-2 py-4">
      <div className="relative">
        <svg width={104} height={104} viewBox="0 0 104 104">
          <circle cx={52} cy={52} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={8} />
          <circle
            cx={52} cy={52} r={r} fill="none"
            strokeWidth={8} strokeLinecap="round"
            strokeDasharray={`${dash} ${circ}`}
            strokeDashoffset={circ / 4}
            className={cn("transition-all duration-1000", colorClass)}
            style={{ filter: `drop-shadow(0 0 6px ${glowColor})` }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-display text-2xl font-bold text-foreground">{value}</span>
          <span className="text-[11px] text-muted-foreground">%</span>
        </div>
      </div>
      <p className="text-xs font-medium capitalize text-muted-foreground">
        Answer Confidence · <span className="capitalize text-foreground">{level}</span>
      </p>
    </div>
  )
}

/* ---- Agent Orb ---- */
function AgentOrb({ orb, status }: { orb: typeof AGENT_ORBS[number]; status: OrbStatus }) {
  const breatheClass = {
    teal: "animate-orb-breathe-teal",
    cyan: "animate-orb-breathe",
    violet: "animate-orb-breathe-violet",
  }[orb.color]

  const borderClass = { teal: "border-teal/50", cyan: "border-primary/50", violet: "border-accent/50" }
  const bgClass = { teal: "bg-teal/10", cyan: "bg-primary/10", violet: "bg-accent/10" }
  const textClass = { teal: "text-teal", cyan: "text-primary", violet: "text-accent" }

  return (
    <div className="flex items-center gap-3">
      <div className={cn(
        "flex h-12 w-12 shrink-0 items-center justify-center rounded-full border text-2xl transition-all",
        borderClass[orb.color], bgClass[orb.color],
        status === "active" && breatheClass,
        status === "dormant" && "opacity-40",
        status === "timeout" && "border-critical/50 bg-critical/10 opacity-70",
      )}>
        {orb.emoji}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <p className="truncate text-xs font-semibold text-foreground">{orb.name}</p>
          {status === "complete" && <CircleCheck className={cn("h-3 w-3 shrink-0", textClass[orb.color])} />}
          {status === "active" && <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary animate-pulse-dot" />}
          {status === "timeout" && <XCircle className="h-3 w-3 shrink-0 text-critical" />}
        </div>
        <p className="text-[11px] text-muted-foreground">{orb.section}</p>
        {status === "complete" && (
          <p className="text-[10px] text-muted-foreground">
            {orb.claimCount} claims · {orb.sourceCount} sources · {(orb.durationMs / 1000).toFixed(1)}s
          </p>
        )}
        {status === "active" && (
          <p className={cn("animate-pulse-dot text-[10px]", textClass[orb.color])}>Running in parallel…</p>
        )}
      </div>
    </div>
  )
}

/* ---- Grounding Gate ---- */
function GroundingGatePanel() {
  const passed = GROUNDING_CHECKS.filter((c) => c.passed).length
  return (
    <div className="rounded-xl border border-primary/30 bg-primary/5 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-primary">
          <GitMerge className="h-3.5 w-3.5" />
          GroundingGate
        </div>
        <span className="text-xs font-bold text-primary">{passed}/8 passed</span>
      </div>
      <div className="flex flex-col gap-1.5">
        {GROUNDING_CHECKS.map((c) => (
          <div key={c.rule} className="flex items-start gap-2">
            <span className={cn(
              "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] font-bold animate-grounding-tick",
              c.passed ? "bg-primary/20 text-primary" : "bg-critical/20 text-critical",
            )}>
              {c.passed ? "✓" : "✗"}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[11px] leading-tight text-muted-foreground">
                <span className="font-medium text-foreground">R{c.rule}:</span> {c.name}
              </p>
              {c.detail && (
                <p className="mt-0.5 text-[10px] text-muted-foreground/70">{c.detail}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ---- Step Timeline ---- */
function StepTimeline() {
  return (
    <div className="flex flex-col gap-1">
      {SAMPLE_TRACE.map((step, i) => (
        <div key={i} className="flex items-start gap-2.5 py-1">
          <div className="flex flex-col items-center">
            <span className={cn(
              "flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[10px] font-bold",
              step.done ? "border-primary/50 bg-primary/10 text-primary" : "border-border text-muted-foreground",
            )}>
              {step.done ? "✓" : i + 1}
            </span>
            {i < SAMPLE_TRACE.length - 1 && (
              <div className={cn("mt-0.5 h-3 w-px", step.done ? "bg-primary/30" : "bg-border/50")} />
            )}
          </div>
          <div className="min-w-0 flex-1 pb-1">
            <p className={cn("text-[11px] font-medium leading-tight", step.done ? "text-foreground" : "text-muted-foreground")}>
              {step.label}
            </p>
            <p className="text-[10px] text-muted-foreground/70">{step.detail}</p>
            <p className="text-[10px] text-muted-foreground/50">{step.elapsed}ms</p>
          </div>
        </div>
      ))}
    </div>
  )
}

/* ---- Source Card ---- */
function SourceCard({ src, active }: { src: Answer["sources"][number]; active: boolean }) {
  return (
    <div className={cn(
      "rounded-xl border bg-surface-2 p-3 transition-all",
      active ? "border-primary/60 glow-cyan" : "border-border hover:border-primary/40 hover:glow-cyan",
    )}>
      <div className="mb-1 flex items-center justify-between">
        <p className="text-[11px] font-semibold text-primary">{src.doc}</p>
        <span className="text-[10px] font-bold text-secondary">{src.relevance}%</span>
      </div>
      <p className="mb-2 text-[10px] text-muted-foreground/80">{src.ref}</p>
      <div className="mb-2 h-1 w-full overflow-hidden rounded-full bg-border">
        <div
          className="h-full rounded-full bg-primary transition-all duration-700"
          style={{ width: `${src.relevance}%`, opacity: 0.75 }}
        />
      </div>
      <p className="mb-2.5 line-clamp-3 text-[11px] leading-relaxed text-muted-foreground">{src.excerpt}</p>
      <div className="flex flex-wrap gap-1.5">
        {src.region && (
          <span className="rounded border border-teal/30 bg-teal/10 px-1.5 py-0.5 text-[10px] text-teal">{src.region}</span>
        )}
        {src.category && (
          <span className="rounded border border-border bg-surface px-1.5 py-0.5 text-[10px] text-muted-foreground">{src.category}</span>
        )}
        <EvidenceBadge quality={src.quality} />
      </div>
    </div>
  )
}

/* ---- Emergency Pill ---- */
function EmergencyPill({ level }: { level: Answer["emergency"] }) {
  const configs: Record<string, { color: string; shape: string; desc: string }> = {
    W1: { color: "border-border text-muted-foreground", shape: "●", desc: "W1 · Observation" },
    W2: { color: "border-warning/60 text-warning glow-amber", shape: "▲", desc: "W2 · Advisory" },
    W3: { color: "border-[#fb923c]/60 text-[#fb923c]", shape: "⬡", desc: "W3 · Emergency" },
    W4: { color: "border-critical/60 text-critical glow-red", shape: "⬡", desc: "W4 · Regional Crisis" },
    CRITICAL: { color: "border-critical text-critical glow-red animate-pulse-border", shape: "⬡", desc: "CRITICAL" },
  }
  const m = configs[level]
  return (
    <div className={cn("rounded-xl border px-4 py-3 text-sm font-semibold", m.color)}>
      <span className="mr-2">{m.shape}</span>{m.desc}
    </div>
  )
}

type Tab = "orchestration" | "sources"

/* ---- Right Panel ---- */
export function RightPanel({ answer, processing }: { answer: Answer | null; processing: boolean }) {
  const [tab, setTab] = useState<Tab>("orchestration")
  const [activeSource] = useState<string | null>(null)

  const orbStatus = (): OrbStatus => {
    if (!processing && !answer) return "dormant"
    if (processing) return "active"
    return "complete"
  }
  const status = orbStatus()

  return (
    <div className="flex h-full flex-col">
      {/* Tab header */}
      <div className="flex items-center gap-1 border-b border-border px-3 py-2.5">
        {(["orchestration", "sources"] as Tab[]).map((t) => {
          const labels: Record<Tab, string> = { orchestration: "⚙ Orchestration", sources: "📂 Sources" }
          const Icon = t === "orchestration" ? Activity : Database
          return (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                "flex flex-1 items-center justify-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-medium transition-all",
                tab === t ? "bg-primary/15 text-primary glow-cyan" : "text-muted-foreground hover:bg-surface-2 hover:text-foreground",
              )}
            >
              <Icon className="h-3 w-3" />
              {labels[t]}
            </button>
          )
        })}
      </div>

      <div className="flex-1 overflow-y-auto p-3 thin-scroll">
        {tab === "orchestration" && (
          <div className="flex flex-col gap-4">
            {/* Agent orbs */}
            <div className="rounded-xl border border-border bg-surface p-3">
              <p className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                Specialist Agents
              </p>
              <div className="flex flex-col gap-3">
                {AGENT_ORBS.map((orb) => (
                  <AgentOrb key={orb.id} orb={orb} status={status} />
                ))}
              </div>
            </div>

            {/* Trace timeline */}
            {answer && (
              <div className="rounded-xl border border-border bg-surface p-3">
                <div className="mb-3 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                  <Clock className="h-3 w-3" />
                  Trace Timeline
                </div>
                <StepTimeline />
              </div>
            )}

            {/* Grounding gate */}
            {answer && <GroundingGatePanel />}

            {/* Confidence gauge */}
            {answer && (
              <div className="rounded-xl border border-border bg-surface p-3">
                <ConfidenceGauge value={answer.confidence} level={answer.confidenceLevel} />
                <p className="px-1 text-center text-[11px] leading-relaxed text-muted-foreground">
                  {answer.confidenceReason}
                </p>
              </div>
            )}

            {/* Triage level */}
            {answer && (
              <div className="rounded-xl border border-border bg-surface p-3">
                <p className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                  Triage Level
                </p>
                <EmergencyPill level={answer.emergency} />
                <p className="mt-2 text-[11px] text-muted-foreground">
                  Per §4.5 Water Incident Classification · <CitationChip id="§4.5" />
                </p>
              </div>
            )}

            {!answer && !processing && (
              <div className="py-8 text-center text-sm text-muted-foreground">
                Submit a query to activate the orchestration rail.
              </div>
            )}
          </div>
        )}

        {tab === "sources" && (
          <div className="flex flex-col gap-3">
            {answer?.sources.length ? (
              answer.sources.map((src) => (
                <SourceCard key={src.id} src={src} active={activeSource === src.id} />
              ))
            ) : (
              <div className="py-8 text-center text-sm text-muted-foreground">
                Submit a query to load retrieved sources.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
