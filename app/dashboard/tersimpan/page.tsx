"use client";

import { useEffect, useMemo, useState } from "react";
import { EmptyState } from "@/components/dashboard/EmptyState";
import { JobCard } from "@/components/dashboard/JobCard";
import type { Opportunity } from "@/lib/dashboard/types";

function readSavedIds() {
  if (typeof window === "undefined") return new Set<string>();
  try {
    const stored = window.localStorage.getItem("magangkareer_saved_ids");
    return new Set(stored ? (JSON.parse(stored) as string[]) : []);
  } catch {
    return new Set<string>();
  }
}

export default function TersimpanPage() {
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [savedIds, setSavedIds] = useState<Set<string>>(readSavedIds);
  const [selected, setSelected] = useState<Opportunity | null>(null);
  const saved = useMemo(
    () => opportunities.filter((opportunity) => savedIds.has(opportunity.id)),
    [opportunities, savedIds],
  );

  useEffect(() => {
    async function load() {
      const response = await fetch("/api/opportunities", { cache: "no-store" });
      if (!response.ok) return;
      const payload = (await response.json()) as { opportunities: Opportunity[] };
      setOpportunities(payload.opportunities);
    }

    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  function toggleSaved(id: string) {
    setSavedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      window.localStorage.setItem("magangkareer_saved_ids", JSON.stringify([...next]));
      return next;
    });
  }

  return (
    <div className="page-wrap">
      <header className="page-header split">
        <div>
          <h1>Tersimpan</h1>
          <p>Peluang yang kamu simpan untuk dipertimbangkan lagi.</p>
        </div>
        <div className="saved-filter-row">
          <button className="secondary-button" type="button">Peran</button>
          <button className="secondary-button" type="button">Platform</button>
          <button className="secondary-button" type="button">Status</button>
          <button className="secondary-button" type="button">Kualitas Data</button>
        </div>
      </header>

      {saved.length ? (
        <div className="saved-grid">
          {saved.map((opportunity) => (
            <JobCard
              key={opportunity.id}
              opportunity={opportunity}
              saved={savedIds.has(opportunity.id)}
              onToggleSaved={toggleSaved}
              onOpen={setSelected}
            />
          ))}
        </div>
      ) : (
        <EmptyState
          title="Belum ada lowongan tersimpan."
          description="Simpan peluang yang menarik agar kamu bisa membandingkan dan melacaknya nanti."
          actionLabel="Cari Lowongan"
          href="/dashboard/lowongan"
        />
      )}

      <div className="sr-only" aria-live="polite">
        {selected ? `Lowongan dipilih: ${selected.title}` : ""}
      </div>
    </div>
  );
}
