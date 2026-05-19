"use client";

import { useState } from "react";
import { EmptyState } from "@/components/dashboard/EmptyState";
import { JobCard } from "@/components/dashboard/JobCard";
import { opportunities } from "@/lib/dashboard/mock-data";
import type { Opportunity } from "@/lib/dashboard/types";

export default function TersimpanPage() {
  const initialSaved = opportunities.slice(0, 6);
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set(initialSaved.map((item) => item.id)));
  const [selected, setSelected] = useState<Opportunity | null>(null);
  const saved = opportunities.filter((opportunity) => savedIds.has(opportunity.id));

  function toggleSaved(id: string) {
    setSavedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
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
          <button className="secondary-button" type="button">Role</button>
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
