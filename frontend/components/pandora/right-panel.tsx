"use client"

import { Database, Gauge, Siren } from "lucide-react"
import { cn } from "@/lib/utils"
import { EvidenceBadge, Tag } from "./badges"
import { EMERGENCY_META, type Answer, type EmergencyLevel } from "./data"

function relevanceColor(v: number) {
  if (v >= 85) return "#39ff8f"
  if (v >= 70) return "#f59e0b"
  return "#ef4444"
}

function SourceCardView({
  source,
}: {
  source: Answer["sources"][number]
}) {
  const color = relevanceColor(source.relevance)
  return (
    <article className="group rounded-xl border border-border bg-surface-2 p-3 transition-all hover:-translate-y-0.5 hover:border-primary/50 hover:glow-cyan">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-semibold text-primary">{source.doc}</p>
      </div>
      <p className="mt-0.5 text-[11px] text-muted-foreground">{source.ref}</p>

      {/* relevance bar */}
      <div className="mt-2.5">
        <div className="mb-1 flex items-center justify-between text-[10px] text-muted-foreground">
          <span>Relevance</span>
          <span style={{ color }}>{source.relevance}%</span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-background">
          <div
            className="h-full rounded-full"
            style={{
              width: `${source.relevance}%`,
              background: color,
              boxShadow: `0 0 8px ${color}`,
            }}
          />
        </div>
      </div>

      <p className="mt-2.5 line-clamp-3 text-xs leading-relaxed text-muted-foreground">{source.excerpt}</p>

      <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
        {source.region && <Tag tone="cyan">{source.region}</Tag>}
        {source.category && <Tag tone="purple">{source.category}</Tag>}
      </div>
      <div className="mt-2.5">
        <EvidenceBadge quality={source.quality} />
      </div>
    </article>
  )
}

function ConfidenceGauge({ value, reason }: { value: number; reason: string }) {
  const color = value >= 75 ? "#00e5ff" : value >= 50 ? "#f59e0b" : "#ef4444"
  const r = 40
  const circ = 2 * Math.PI * r
  const offset = circ - (value / 100) * circ
  return (
    <div className="flex flex-col items-center rounded-xl border border-border bg-surface-2 p-4">
      <div className="mb-1 flex items-center gap-2 self-start text-xs font-medium uppercase tracking-widest text-muted-foreground">
        <Gauge className="h-4 w-4 text-primary" />
        Answer Confidence
      </div>
      <div className="relative my-2 h-28 w-28">
        <svg className="h-full w-full -rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r={r} fill="none" stroke="#0d2040" strokeWidth="8" />
          <circle
            cx="50"
            cy="50"
            r={r}
            fill="none"
            stroke={color}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circ}
            strokeDashoffset={offset}
            style={{ filter: `drop-shadow(0 0 6px ${color})`, transition: "stroke-dashoffset 0.8s ease" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-display text-2xl font-bold" style={{ color }}>
            {value}%
          </span>
        </div>
      </div>
      <p className="text-center text-[11px] leading-relaxed text-muted-foreground">{reason}</p>
    </div>
  )
}

const levelToneClass: Record<string, string> = {
  gray: "border-border text-muted-foreground",
  amber: "border-warning/50 text-warning glow-amber",
  orange: "border-[#fb923c]/60 text-[#fb923c]",
  red: "border-critical/60 text-critical glow-red",
}

function EmergencyClassifier({ active }: { active: EmergencyLevel }) {
  const levels = Object.keys(EMERGENCY_META) as (keyof typeof EMERGENCY_META)[]
  return (
    <div className="rounded-xl border border-border bg-surface-2 p-4">
      <div className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-widest text-muted-foreground">
        <Siren className="h-4 w-4 text-warning" />
        Emergency Level
      </div>
      <div className="flex flex-col gap-1.5">
        {levels.map((lvl) => {
          const meta = EMERGENCY_META[lvl]
          const isActive = active === lvl
          const critical = lvl === "CRITICAL"
          return (
            <div
              key={lvl}
              className={cn(
                "flex items-center gap-2.5 rounded-lg border px-3 py-2 text-xs font-medium transition-all",
                isActive ? levelToneClass[meta.tone] : "border-border/50 text-muted-foreground/50",
                isActive && "bg-background/60",
                isActive && critical && "animate-pulse-border",
              )}
            >
              <span
                className={cn("h-2 w-2 shrink-0 rounded-full", isActive ? "opacity-100" : "opacity-40")}
                style={{
                  background:
                    meta.tone === "gray"
                      ? "#7faec7"
                      : meta.tone === "amber"
                        ? "#f59e0b"
                        : meta.tone === "orange"
                          ? "#fb923c"
                          : "#ef4444",
                  boxShadow: isActive ? `0 0 8px currentColor` : "none",
                }}
              />
              <span className="flex-1">{meta.label}</span>
            </div>
          )
        })}
      </div>
      <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
        {active === "none" ? "No active incident detected." : EMERGENCY_META[active].desc}
      </p>
    </div>
  )
}

export function RightPanel({ answer }: { answer: Answer | null }) {
  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-4 thin-scroll">
      <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
        <Database className="h-4 w-4 text-primary" />
        Retrieved Sources
      </div>

      {answer ? (
        <>
          <div className="flex flex-col gap-3">
            {answer.sources.map((s, i) => (
              <div key={s.id}>
                <SourceCardView source={s} />
                {i < answer.sources.length - 1 && (
                  <div className="mx-auto mt-3 h-px w-full bg-gradient-to-r from-transparent via-primary/40 to-transparent" />
                )}
              </div>
            ))}
          </div>

          <ConfidenceGauge value={answer.confidence} reason={answer.confidenceReason} />
          <EmergencyClassifier active={answer.emergency} />
        </>
      ) : (
        <div className="rounded-xl border border-dashed border-border p-6 text-center text-xs leading-relaxed text-muted-foreground">
          Sources will appear here once you query the knowledge base. Every answer is grounded in retrieved records.
        </div>
      )}
    </div>
  )
}
