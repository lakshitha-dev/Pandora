"use client"

import { useState } from "react"
import { Network, UploadCloud, FileText, X, Shield, Microscope, Users } from "lucide-react"
import { cn } from "@/lib/utils"
import { DOCUMENTS, REGIONS, ROLES, type Role, type RegionId } from "./data"

const roleStyles: Record<Role, { active: string; icon: typeof Shield }> = {
  guardian: { active: "border-primary bg-primary/15 text-primary glow-cyan", icon: Shield },
  researcher: { active: "border-accent bg-accent/15 text-accent glow-purple", icon: Microscope },
  citizen: { active: "border-secondary bg-secondary/15 text-secondary glow-green", icon: Users },
}

/* ---- Pandora SVG Map ---- */
const REGION_PATHS: Record<RegionId, string> = {
  "REG-01": "M 30 20 L 70 20 L 80 35 L 65 45 L 40 40 L 25 30 Z",
  "REG-02": "M 65 45 L 80 35 L 95 45 L 90 62 L 72 60 Z",
  "REG-03": "M 72 60 L 90 62 L 88 80 L 75 85 L 65 72 Z",
  "REG-04": "M 40 40 L 65 45 L 72 60 L 65 72 L 45 70 L 35 58 Z",
  "REG-05": "M 10 35 L 25 30 L 40 40 L 35 58 L 20 65 L 8 50 Z",
  "REG-06": "M 20 65 L 35 58 L 45 70 L 38 86 L 22 88 L 12 78 Z",
  "REG-07": "M 45 70 L 65 72 L 75 85 L 60 95 L 38 92 L 38 86 Z",
  "REG-08": "M 8 50 L 20 65 L 12 78 L 2 70 L 4 55 Z",
  "REG-09": "M 12 78 L 22 88 L 18 100 L 6 98 L 2 82 Z",
  "REG-10": "M 75 85 L 88 80 L 95 90 L 85 100 L 60 95 Z",
}

const TRIAGE_COLORS: Record<string, string> = {
  W1: "#8FAFB8",
  W2: "#F0A93E",
  W3: "#fb923c",
  W4: "#F0644E",
  CRITICAL: "#F0644E",
  none: "transparent",
}

function PandoraMap({
  affectedRegions,
  triageLevel,
}: {
  affectedRegions: RegionId[]
  triageLevel: string
}) {
  const [hoveredRegion, setHoveredRegion] = useState<RegionId | null>(null)
  const alertColor = TRIAGE_COLORS[triageLevel] ?? "#3EE8D0"

  return (
    <div className="relative overflow-hidden rounded-xl border border-primary/20 bg-background">
      <p className="absolute left-2 top-2 z-10 text-[9px] font-semibold uppercase tracking-widest text-primary/60">
        Pandora Ecosystem Map
      </p>
      <svg
        viewBox="0 0 100 100"
        className="w-full"
        style={{ aspectRatio: "1 / 1" }}
      >
        {/* Ocean background */}
        <rect width="100" height="100" fill="#04121C" rx="8" />
        <ellipse cx="50" cy="50" rx="48" ry="46" fill="#071a2a" />

        {/* Grid lines */}
        {[20, 40, 60, 80].map((v) => (
          <line key={`h${v}`} x1="0" y1={v} x2="100" y2={v} stroke="#0d2a40" strokeWidth="0.3" />
        ))}
        {[20, 40, 60, 80].map((v) => (
          <line key={`v${v}`} x1={v} y1="0" x2={v} y2="100" stroke="#0d2a40" strokeWidth="0.3" />
        ))}

        {/* Region zones */}
        {REGIONS.map(({ id }) => {
          const path = REGION_PATHS[id]
          const isAffected = affectedRegions.includes(id)
          const isHovered = hoveredRegion === id
          return (
            <g key={id}>
              <path
                d={path}
                fill={isAffected ? `${alertColor}22` : "#0A223388"}
                stroke={isAffected ? alertColor : isHovered ? "#3EE8D0" : "#1a4a6e"}
                strokeWidth={isAffected ? 0.8 : 0.4}
                style={{
                  filter: isAffected ? `drop-shadow(0 0 3px ${alertColor})` : "none",
                  transition: "all 0.3s",
                  cursor: "pointer",
                }}
                onMouseEnter={() => setHoveredRegion(id)}
                onMouseLeave={() => setHoveredRegion(null)}
              />
              {isAffected && (
                <path
                  d={path}
                  fill="none"
                  stroke={alertColor}
                  strokeWidth={1.2}
                  opacity={0.6}
                  style={{ animation: "pulse-border 1.6s ease-in-out infinite" }}
                />
              )}
            </g>
          )
        })}

        {/* Region labels */}
        {[
          { id: "REG-01" as RegionId, cx: 52, cy: 31 },
          { id: "REG-02" as RegionId, cx: 83, cy: 50 },
          { id: "REG-03" as RegionId, cx: 79, cy: 73 },
          { id: "REG-04" as RegionId, cx: 52, cy: 57 },
          { id: "REG-05" as RegionId, cx: 22, cy: 47 },
          { id: "REG-06" as RegionId, cx: 28, cy: 74 },
          { id: "REG-07" as RegionId, cx: 54, cy: 82 },
          { id: "REG-08" as RegionId, cx: 8, cy: 63 },
          { id: "REG-09" as RegionId, cx: 12, cy: 88 },
          { id: "REG-10" as RegionId, cx: 82, cy: 91 },
        ].map(({ id, cx, cy }) => {
          const isAffected = affectedRegions.includes(id)
          return (
            <text
              key={id}
              x={cx}
              y={cy}
              textAnchor="middle"
              fill={isAffected ? alertColor : "#8FAFB8"}
              fontSize="3.5"
              fontFamily="monospace"
              fontWeight={isAffected ? "bold" : "normal"}
              opacity={isAffected ? 1 : 0.7}
            >
              {id}
            </text>
          )
        })}
      </svg>

      {/* Tooltip */}
      {hoveredRegion && (
        <div className="absolute bottom-2 left-1/2 -translate-x-1/2 rounded-lg border border-primary/30 bg-surface px-2 py-1 text-[10px] text-primary whitespace-nowrap">
          {REGIONS.find((r) => r.id === hoveredRegion)?.name}
        </div>
      )}
    </div>
  )
}

export function LeftSidebar({
  role,
  onRoleChange,
  affectedRegions,
  triageLevel,
}: {
  role: Role
  onRoleChange: (r: Role) => void
  affectedRegions?: RegionId[]
  triageLevel?: string
}) {
  const [dragOver, setDragOver] = useState(false)
  const [activeRegions, setActiveRegions] = useState<Set<RegionId>>(new Set(["REG-01"]))

  const toggleRegion = (id: RegionId) => {
    setActiveRegions((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  return (
    <div className="flex h-full flex-col gap-5 overflow-y-auto p-4 thin-scroll">
      {/* Logo */}
      <div className="flex items-center gap-3 px-1">
        <span className="flex h-11 w-11 items-center justify-center rounded-xl border border-primary/40 bg-primary/10 text-primary glow-cyan">
          <Network className="h-5 w-5" />
        </span>
        <div className="leading-tight">
          <p className="font-display text-lg font-bold tracking-widest text-primary text-glow-cyan">PANDORA</p>
          <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Knowledge Guardian</p>
        </div>
      </div>

      {/* Role selector */}
      <section>
        <p className="mb-2 text-[11px] font-medium uppercase tracking-widest text-muted-foreground">I am a...</p>
        <div className="flex flex-col gap-2">
          {ROLES.map(({ id, label }) => {
            const Icon = roleStyles[id].icon
            const active = role === id
            return (
              <button
                key={id}
                onClick={() => onRoleChange(id)}
                className={cn(
                  "flex items-center gap-2.5 rounded-full border px-3.5 py-2 text-sm font-medium transition-all",
                  active
                    ? roleStyles[id].active
                    : "border-border text-muted-foreground hover:border-border-glow hover:text-foreground",
                )}
              >
                <Icon className="h-4 w-4" />
                {label}
              </button>
            )
          })}
        </div>
      </section>

      {/* Pandora SVG Map */}
      <section>
        <p className="mb-2 text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Ecosystem Map</p>
        <PandoraMap
          affectedRegions={affectedRegions ?? []}
          triageLevel={triageLevel ?? "none"}
        />
        <div className="mt-2 flex flex-wrap gap-1.5">
          {affectedRegions && affectedRegions.length > 0 ? (
            affectedRegions.map((id) => (
              <span key={id} className="rounded border border-warning/50 bg-warning/10 px-1.5 py-0.5 text-[10px] text-warning">
                {id} · {REGIONS.find((r) => r.id === id)?.name}
              </span>
            ))
          ) : (
            <span className="text-[10px] text-muted-foreground">No active incident zones</span>
          )}
        </div>
      </section>

      {/* Corpus stats */}
      <section>
        <p className="mb-2 text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Knowledge Base</p>
        <div className="rounded-xl border border-primary/20 bg-primary/5 px-3 py-2.5">
          <div className="grid grid-cols-3 gap-2 text-center">
            {[["268", "Chunks"], ["130", "Records"], ["15", "Chapters"]].map(([val, lbl]) => (
              <div key={lbl}>
                <p className="font-display text-base font-bold text-primary">{val}</p>
                <p className="text-[10px] text-muted-foreground">{lbl}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Document library */}
      <section>
        <p className="mb-2 text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
          Document Library
        </p>
        <label
          onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => { e.preventDefault(); setDragOver(false) }}
          className={cn(
            "flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed p-5 text-center transition-all",
            dragOver
              ? "border-primary bg-primary/10 glow-cyan"
              : "border-primary/30 hover:border-primary/60 hover:bg-primary/5",
          )}
        >
          <UploadCloud className={cn("h-6 w-6 transition-colors", dragOver ? "text-primary" : "text-primary/70")} />
          <span className="text-xs font-medium text-foreground">Drop knowledge documents here</span>
          <span className="text-[10px] text-muted-foreground">PDF, TXT, DOCX supported</span>
          <input type="file" className="hidden" />
        </label>

        <ul className="mt-3 flex flex-col gap-2">
          {DOCUMENTS.map((doc) => (
            <li
              key={doc.id}
              className="group flex items-center gap-3 rounded-lg border border-border bg-surface-2 p-2.5 transition-colors hover:border-border-glow"
            >
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-primary/30 bg-primary/10 text-primary glow-cyan">
                <FileText className="h-4 w-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-medium text-foreground">{doc.title}</p>
                <p className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
                  <span className="inline-block h-1.5 w-1.5 rounded-full bg-secondary glow-green" />
                  {doc.pages} pages · {doc.status}
                </p>
              </div>
              <button
                aria-label={`Remove ${doc.title}`}
                className="rounded p-1 text-muted-foreground opacity-0 transition-opacity hover:text-critical group-hover:opacity-100"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
      </section>

      {/* Region filter */}
      <section className="pb-4">
        <p className="mb-2 text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Region Filter</p>
        <div className="flex flex-wrap gap-1.5">
          {REGIONS.map((r) => {
            const active = activeRegions.has(r.id)
            return (
              <button
                key={r.id}
                onClick={() => toggleRegion(r.id)}
                className={cn(
                  "rounded-full border px-2.5 py-1 text-[10px] font-medium transition-all",
                  active
                    ? "border-primary bg-primary/15 text-primary glow-cyan"
                    : "border-border text-muted-foreground hover:border-border-glow hover:text-foreground",
                )}
              >
                {r.id}
              </button>
            )
          })}
        </div>
      </section>
    </div>
  )
}
