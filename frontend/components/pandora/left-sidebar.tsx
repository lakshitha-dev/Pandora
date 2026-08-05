"use client"

import { useState } from "react"
import { Network, UploadCloud, FileText, X, Shield, Microscope, Users } from "lucide-react"
import { cn } from "@/lib/utils"
import { DOCUMENTS, REGIONS, ROLES, type Role } from "./data"

const roleStyles: Record<Role, { active: string; icon: typeof Shield }> = {
  guardian: {
    active: "border-primary bg-primary/15 text-primary glow-cyan",
    icon: Shield,
  },
  researcher: {
    active: "border-accent bg-accent/15 text-accent glow-purple",
    icon: Microscope,
  },
  citizen: {
    active: "border-secondary bg-secondary/15 text-secondary glow-green",
    icon: Users,
  },
}

export function LeftSidebar({
  role,
  onRoleChange,
}: {
  role: Role
  onRoleChange: (r: Role) => void
}) {
  const [dragOver, setDragOver] = useState(false)
  const [activeRegions, setActiveRegions] = useState<Set<string>>(new Set(["Luminous Shelf"]))

  const toggleRegion = (r: string) => {
    setActiveRegions((prev) => {
      const next = new Set(prev)
      next.has(r) ? next.delete(r) : next.add(r)
      return next
    })
  }

  return (
    <div className="flex h-full flex-col gap-6 overflow-y-auto p-4 thin-scroll">
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

      {/* Document library */}
      <section>
        <p className="mb-2 text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
          Document Library
        </p>
        <label
          onDragOver={(e) => {
            e.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragOver(false)
          }}
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

      {/* Active regions */}
      <section className="mt-auto">
        <p className="mb-2 text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Active Regions</p>
        <div className="flex flex-wrap gap-1.5">
          {REGIONS.map((r) => {
            const active = activeRegions.has(r)
            return (
              <button
                key={r}
                onClick={() => toggleRegion(r)}
                className={cn(
                  "rounded-full border px-2.5 py-1 text-[10px] font-medium transition-all",
                  active
                    ? "border-primary bg-primary/15 text-primary glow-cyan"
                    : "border-border text-muted-foreground hover:border-border-glow hover:text-foreground",
                )}
              >
                {r}
              </button>
            )
          })}
        </div>
      </section>
    </div>
  )
}
