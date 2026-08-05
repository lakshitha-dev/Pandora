"use client"

import { useEffect, useRef, useState } from "react"
import {
  ArrowUp, Mic, Network, TriangleAlert, ChevronDown,
  CircleCheck, Loader2, ShieldQuestion, Shield, Microscope, Users,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { EvidenceBadge, CitationChip, AgentBadge } from "./badges"
import { EMERGENCY_META, ROLE_INTRO, SUGGESTED_QUESTIONS, ROLES, type Answer, type Role } from "./data"

const STEPS = [
  { label: "Searching knowledge base...", icon: "🔍" },
  { label: "Retrieving relevant chunks...", icon: "📄" },
  { label: "Generating grounded answer...", icon: "🧠" },
]

/* ---- Triage Banner ---- */
function TriageBanner({ emergency }: { emergency: Answer["emergency"] }) {
  const meta = EMERGENCY_META[emergency]
  const colorMap = {
    gray: "border-border/60 bg-surface-2 text-muted-foreground",
    amber: "border-warning/60 bg-warning/10 text-warning glow-amber",
    orange: "border-[#fb923c]/60 bg-[#fb923c]/10 text-[#fb923c]",
    red: "border-critical/60 bg-critical/10 text-critical glow-red",
  }
  const pulseMap = { gray: "", amber: "", orange: "", red: "animate-pulse-border" }
  return (
    <div className={cn("rounded-xl border px-4 py-3 animate-section-fill", colorMap[meta.tone], pulseMap[meta.tone])}>
      <div className="flex items-center gap-3">
        <span className="font-display text-lg font-bold leading-none">{meta.shape}</span>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="font-display text-sm font-bold tracking-wide">{meta.label}</span>
          </div>
          <p className="mt-0.5 text-xs leading-relaxed opacity-90">{meta.desc}</p>
        </div>
        <CitationChip id={meta.citation.split(",")[0]} />
      </div>
    </div>
  )
}

/* ---- Welcome State ---- */
function WelcomeState({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-6 py-10 text-center">
      <span className="mb-6 flex h-20 w-20 items-center justify-center rounded-full border border-primary/40 bg-primary/10 text-primary glow-cyan">
        <Network className="h-9 w-9" />
      </span>
      <h2 className="font-display text-2xl font-bold tracking-wide text-foreground text-glow-cyan">
        Ask the Living Network
      </h2>
      <p className="mt-3 max-w-md text-balance text-sm leading-relaxed text-muted-foreground">
        Query Pandora&apos;s environmental knowledge base. Every answer is grounded in retrieved documents.
      </p>
      <div className="mt-7 grid w-full max-w-lg grid-cols-1 gap-2.5 sm:grid-cols-2">
        {SUGGESTED_QUESTIONS.map((q) => (
          <button
            key={q}
            onClick={() => onPick(q)}
            className="rounded-xl border border-border bg-surface-2 px-4 py-3 text-left text-xs leading-relaxed text-muted-foreground transition-all hover:scale-[1.03] hover:border-primary/60 hover:text-foreground hover:glow-cyan"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}

/* ---- Processing Steps ---- */
function ProcessingSteps({ step, showBanner, emergency }: { step: number; showBanner?: boolean; emergency?: Answer["emergency"] }) {
  return (
    <div className="flex flex-col gap-3">
      {showBanner && emergency && (
        <TriageBanner emergency={emergency} />
      )}
      <div className="rounded-2xl border border-border bg-surface p-5">
        <div className="mb-4 flex items-center gap-2 text-xs font-medium uppercase tracking-widest text-primary">
          <Loader2 className="h-4 w-4 animate-spin" />
          Assembling situation report
        </div>
        <ol className="flex flex-col gap-3">
          {STEPS.map(({ label, icon }, i) => {
            const done = i < step
            const current = i === step
            return (
              <li key={label} className="flex items-center gap-3 text-sm">
                <span className={cn(
                  "flex h-7 w-7 items-center justify-center rounded-full border text-base transition-all",
                  done && "border-secondary bg-secondary/15 text-secondary glow-green",
                  current && "border-primary bg-primary/15 text-primary glow-cyan",
                  !done && !current && "border-border text-muted-foreground",
                )}>
                  {done ? <CircleCheck className="h-3.5 w-3.5" /> : current ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <span className="text-[10px]">{icon}</span>}
                </span>
                <span className={cn(done ? "text-foreground" : current ? "text-primary" : "text-muted-foreground")}>{label}</span>
              </li>
            )
          })}
        </ol>
        <div className="mt-4 flex items-center gap-2">
          {["🐋 Marine-Life Protector", "🌊 Incident Investigator", "🚨 Emergency Responder"].map((a, i) => (
            <span key={a} className={cn(
              "rounded-full border px-2.5 py-1 text-[10px] font-medium transition-all",
              step >= i
                ? "border-primary/50 bg-primary/10 text-primary animate-pulse-dot"
                : "border-border/50 text-muted-foreground/50"
            )}>
              {a.split(" ")[0]}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

/* ---- Three-way Conflict Panel ---- */
function ConflictPanel({ conflict }: { conflict: NonNullable<Answer["conflict"]> }) {
  const [open, setOpen] = useState(true)
  const sides = [conflict.a, conflict.b, conflict.c]
  return (
    <div className="overflow-hidden rounded-xl border border-warning/50 bg-warning/10 animate-section-fill">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-2.5 px-4 py-3 text-left">
        <TriangleAlert className="h-4 w-4 shrink-0 text-warning" />
        <span className="flex-1 text-sm font-semibold text-warning">Conflicting Evidence Detected</span>
        <span className="text-xs text-warning/70">3 records disagree</span>
        <ChevronDown className={cn("h-4 w-4 text-warning transition-transform", open && "rotate-180")} />
      </button>
      <p className="px-4 pb-3 text-xs leading-relaxed text-warning/90">{conflict.summary}</p>
      {open && (
        <div className="grid grid-cols-1 gap-2 border-t border-warning/30 p-3 md:grid-cols-3">
          {sides.map((c) => (
            <div key={c.label} className="rounded-lg border border-border bg-surface-2 p-3">
              <p className="mb-1 text-[11px] font-semibold text-primary">{c.label}</p>
              <p className="mb-2 text-xs leading-relaxed text-muted-foreground">{c.text}</p>
              {c.limitation && (
                <p className="rounded bg-critical/10 px-2 py-1 text-[10px] text-critical">
                  ⚠ {c.limitation}
                </p>
              )}
              <div className="mt-2">
                <EvidenceBadge quality={c.quality} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* ---- SITREP Section Wrapper ---- */
function SitrepSection({
  emoji, agentName, agentColor, title, children,
}: {
  emoji: string; agentName: string; agentColor: "cyan" | "teal" | "violet"
  title: string; children: React.ReactNode
}) {
  const borderColor = { cyan: "border-l-primary", teal: "border-l-teal", violet: "border-l-accent" }
  const glowColor = { cyan: "glow-cyan", teal: "glow-teal", violet: "glow-purple" }
  return (
    <div className={cn("rounded-2xl border border-border bg-surface p-4 border-l-2 animate-section-fill", borderColor[agentColor], glowColor[agentColor])}>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <AgentBadge emoji={emoji} name={agentName} color={agentColor} />
        <span className="text-xs font-semibold text-foreground">{title}</span>
      </div>
      {children}
    </div>
  )
}

/* ---- Full SITREP Report ---- */
function SitrepReport({ answer, role }: { answer: Answer; role: Role }) {
  return (
    <div className="flex flex-col gap-3">
      {/* Section 1: Priority Banner */}
      <TriageBanner emergency={answer.emergency} />

      {/* Role intro */}
      <p className="rounded-lg border border-border/50 bg-surface-2 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
        {ROLE_INTRO[role]}
      </p>

      {/* Section 2: Affected Species */}
      <SitrepSection emoji="🐋" agentName="Marine-Life Protector" agentColor="teal" title="Affected Species">
        <div className="flex flex-col gap-2">
          {answer.affectedSpecies.map((sp) => (
            <div key={sp.id} className="rounded-lg border border-border bg-surface-2 p-3">
              <div className="mb-1 flex items-center gap-2">
                <CitationChip id={sp.id} />
                <span className="text-sm font-semibold text-foreground">{sp.name}</span>
                <span className="text-[11px] text-muted-foreground">{sp.habitat}</span>
              </div>
              <p className="text-xs leading-relaxed text-muted-foreground">
                <span className="text-warning">⚠ Pressure:</span> {sp.pressure}
              </p>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                <span className="text-primary">Protection:</span> {sp.protection}
              </p>
            </div>
          ))}
        </div>
      </SitrepSection>

      {/* Section 3: Likely Causes */}
      <SitrepSection emoji="🌊" agentName="Incident Investigator" agentColor="cyan" title="Likely Causes">
        <ul className="mb-3 flex flex-col gap-2.5">
          {answer.causes.map((c, i) => (
            <li key={i} className="flex gap-2.5 text-sm leading-relaxed text-muted-foreground">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary glow-cyan" />
              <span>
                <strong className="text-foreground">{c.term}.</strong>{" "}
                {c.detail}
                {c.recordId && <> <CitationChip id={c.recordId} /></>}
              </span>
            </li>
          ))}
        </ul>
        <div className="rounded-lg border border-primary/20 bg-primary/5 px-3 py-2 text-xs text-primary/80">
          Cause not established. These are hypotheses only — no confirmed cause. <CitationChip id="§15.2" />
        </div>
        {answer.conflict && (
          <div className="mt-3">
            <ConflictPanel conflict={answer.conflict} />
          </div>
        )}
      </SitrepSection>

      {/* Section 4: Recommended Actions */}
      <SitrepSection emoji="🚨" agentName="Emergency Responder" agentColor="violet" title="Recommended Actions">
        <ol className="flex flex-col gap-2">
          {answer.recommendedActions.map((a) => (
            <li key={a.step} className="flex items-start gap-3 text-sm">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-accent/50 bg-accent/10 font-display text-[11px] font-bold text-accent">
                {a.step}
              </span>
              <span className="flex-1 leading-relaxed text-muted-foreground">
                {a.action}
                {a.citation && <> <CitationChip id={a.citation} /></>}
              </span>
            </li>
          ))}
        </ol>
        {/* Public comms template */}
        <div className="mt-3 rounded-lg border border-accent/30 bg-accent/5 p-3">
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-widest text-accent">
            Public Communication Template <CitationChip id="KC-01" />
          </p>
          <p className="text-xs leading-relaxed text-muted-foreground">{answer.publicComms}</p>
        </div>
      </SitrepSection>

      {/* Evidence Quality */}
      <div className="flex flex-wrap items-center gap-2 px-1">
        <EvidenceBadge quality={answer.quality} />
        <span className="text-xs text-muted-foreground">·</span>
        <span className="text-xs text-muted-foreground">{answer.confidenceReason}</span>
      </div>
    </div>
  )
}

/* ---- Main Center Panel ---- */
export function CenterPanel({
  role, query, answer, processing, step, input, setInput, onSubmit, onPick, onRoleChange,
}: {
  role: Role
  query: string | null
  answer: Answer | null
  processing: boolean
  step: number
  input: string
  setInput: (v: string) => void
  onSubmit: () => void
  onPick: (q: string) => void
  onRoleChange: (r: Role) => void
}) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [sent, setSent] = useState(false)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
  }, [query, processing, step, answer])

  const handleSend = () => {
    if (!input.trim()) return
    setSent(true)
    setTimeout(() => setSent(false), 600)
    onSubmit()
  }

  const roleIcons: Record<Role, typeof Shield> = { guardian: Shield, researcher: Microscope, citizen: Users }
  const roleStyles: Record<Role, string> = {
    guardian: "border-primary/50 bg-primary/10 text-primary",
    researcher: "border-accent/50 bg-accent/10 text-accent",
    citizen: "border-secondary/50 bg-secondary/10 text-secondary",
  }

  return (
    <div className="flex h-full flex-col">
      {/* Top bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-5 py-2.5">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="capitalize text-primary">{role}</span>
          <span className="text-border-glow">/</span>
          <span>Ecosystem Intelligence Interface</span>
        </div>
        {/* Role toggle in report header */}
        <div className="flex items-center gap-1">
          {ROLES.map(({ id, label }) => {
            const Icon = roleIcons[id]
            const active = role === id
            return (
              <button
                key={id}
                onClick={() => onRoleChange(id)}
                title={label}
                className={cn(
                  "flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-all",
                  active ? roleStyles[id] : "border-border text-muted-foreground hover:border-border-glow hover:text-foreground"
                )}
              >
                <Icon className="h-3 w-3" />
                <span className="hidden sm:inline">{label}</span>
              </button>
            )
          })}
        </div>
        <div className="flex items-center gap-2 rounded-full border border-secondary/30 bg-secondary/5 px-3 py-1 text-[11px] text-secondary">
          <span className="h-1.5 w-1.5 rounded-full bg-secondary glow-green" />
          Knowledge Base: Active · 268 chunks · 130 records
        </div>
      </div>

      {/* Processing progress bar */}
      {processing && <div className="relative h-0.5 w-full overflow-hidden bg-primary/10 progress-shimmer" />}

      {/* Conversation */}
      <div ref={scrollRef} className="flex flex-1 flex-col gap-5 overflow-y-auto px-5 py-6 thin-scroll">
        {!query && !processing && <WelcomeState onPick={onPick} />}

        {query && (
          <div className="flex justify-end">
            <div className="max-w-lg rounded-2xl rounded-tr-sm border-l-2 border-primary/60 bg-surface-2 px-4 py-3 text-sm leading-relaxed text-foreground">
              {query}
            </div>
          </div>
        )}

        {processing && (
          <div className="flex justify-start">
            <div className="w-full max-w-2xl">
              <ProcessingSteps step={step} showBanner={step >= 1} emergency="W2" />
            </div>
          </div>
        )}

        {!processing && answer && (
          <div className="flex justify-start">
            <div className="w-full max-w-2xl">
              <SitrepReport answer={answer} role={role} />
            </div>
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="border-t border-border bg-surface/60 px-5 py-4 backdrop-blur-md">
        <div className="flex items-center gap-2 rounded-2xl border border-border bg-surface-2 px-3 py-2 transition-all focus-within:border-primary/60 focus-within:glow-cyan">
          <button className="rounded-lg p-2 text-muted-foreground transition-colors hover:text-primary" aria-label="Voice input">
            <Mic className="h-4 w-4" />
          </button>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.nativeEvent.isComposing) { e.preventDefault(); handleSend() }
            }}
            placeholder="Describe the situation — Pandora's knowledge base will retrieve the evidence..."
            className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground/70 focus:outline-none"
          />
          <button
            onClick={handleSend}
            aria-label="Send"
            className={cn(
              "flex h-9 w-9 items-center justify-center rounded-xl border border-primary bg-primary/15 text-primary transition-all hover:glow-cyan-strong",
              sent && "animate-send-pulse",
            )}
          >
            <ArrowUp className="h-4 w-4" />
          </button>
        </div>
        <p className="mt-2 flex items-center gap-1.5 px-1 text-[11px] text-muted-foreground">
          <ShieldQuestion className="h-3.5 w-3.5" />
          Every answer is grounded in retrieved records only · Sources and confidence shown for each response
        </p>
      </div>
    </div>
  )
}
