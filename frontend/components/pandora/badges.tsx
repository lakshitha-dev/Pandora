"use client"

import { cn } from "@/lib/utils"
import { EVIDENCE_META, type EvidenceQuality } from "./data"

const toneMap = {
  green: { text: "text-secondary", border: "border-secondary/40", bg: "bg-secondary/10", glow: "text-glow-green" },
  amber: { text: "text-warning", border: "border-warning/40", bg: "bg-warning/10", glow: "" },
  red: { text: "text-critical", border: "border-critical/40", bg: "bg-critical/10", glow: "" },
  blue: { text: "text-primary", border: "border-primary/40", bg: "bg-primary/10", glow: "text-glow-cyan" },
  gray: { text: "text-muted-foreground", border: "border-border", bg: "bg-surface-2", glow: "" },
} as const

export function EvidenceBadge({ quality, className }: { quality: EvidenceQuality; className?: string }) {
  const meta = EVIDENCE_META[quality]
  const tone = toneMap[meta.tone]
  return (
    <span className={cn("group relative inline-flex", className)}>
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
          tone.text, tone.border, tone.bg,
        )}
      >
        <span aria-hidden className={cn("font-display font-bold leading-none", tone.glow)}>
          {meta.symbol}
        </span>
        {meta.label}
      </span>
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-30 mb-2 w-56 -translate-x-1/2 rounded-lg border border-border-glow bg-surface-2 p-2.5 text-xs leading-relaxed text-muted-foreground opacity-0 shadow-xl transition-opacity duration-200 group-hover:opacity-100"
      >
        <span className={cn("mb-0.5 block font-medium", tone.text)}>{meta.label}</span>
        {meta.tip}
      </span>
    </span>
  )
}

export function Tag({ children, tone = "cyan" }: { children: React.ReactNode; tone?: "cyan" | "purple" | "green" | "teal" }) {
  const map = {
    cyan: "border-primary/30 text-primary bg-primary/5",
    purple: "border-accent/40 text-accent bg-accent/10",
    green: "border-secondary/30 text-secondary bg-secondary/5",
    teal: "border-teal/30 text-teal bg-teal/5",
  } as const
  return (
    <span className={cn("inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium", map[tone])}>
      {children}
    </span>
  )
}

export function CitationChip({ id, onClick }: { id: string; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      title={`View source: ${id}`}
      className="inline-flex cursor-pointer items-center rounded border border-primary/40 bg-primary/10 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-primary transition-all hover:border-primary hover:bg-primary/20 hover:glow-cyan"
    >
      {id}
    </button>
  )
}

export function AgentBadge({ emoji, name, color }: { emoji: string; name: string; color: "cyan" | "teal" | "violet" }) {
  const styles = {
    cyan: "border-primary/40 bg-primary/10 text-primary",
    teal: "border-teal/40 bg-teal/10 text-teal",
    violet: "border-accent/40 bg-accent/10 text-accent",
  }
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium", styles[color])}>
      <span>{emoji}</span>
      <span>{name}</span>
    </span>
  )
}

export function TriageBadge({ level }: { level: "W1" | "W2" | "W3" | "W4" | "CRITICAL" }) {
  const styles: Record<string, string> = {
    W1: "border-border text-muted-foreground bg-surface-2",
    W2: "border-warning/60 text-warning bg-warning/10 glow-amber",
    W3: "border-[#fb923c]/60 text-[#fb923c] bg-[#fb923c]/10",
    W4: "border-critical/60 text-critical bg-critical/10 glow-red",
    CRITICAL: "border-critical text-critical bg-critical/15 glow-red animate-pulse-border",
  }
  const shapes: Record<string, string> = { W1: "●", W2: "▲", W3: "⬡", W4: "⬡", CRITICAL: "⬡" }
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-bold", styles[level])}>
      <span aria-hidden>{shapes[level]}</span>
      {level === "CRITICAL" ? "CRITICAL" : level}
    </span>
  )
}
