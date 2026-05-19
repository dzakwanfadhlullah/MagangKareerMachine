"use client";

import { useMemo, useState } from "react";
import { EmptyState } from "@/components/dashboard/EmptyState";
import { FilterPanel } from "@/components/dashboard/FilterPanel";
import { JobCard } from "@/components/dashboard/JobCard";
import { JobDetailDrawer } from "@/components/dashboard/JobDetailDrawer";
import { RoleChips } from "@/components/dashboard/RoleChips";
import { filterOpportunities } from "@/lib/dashboard/filters";
import { applications, opportunities } from "@/lib/dashboard/mock-data";
import type { ApplicationStatus, Opportunity } from "@/lib/dashboard/types";

export default function LowonganPage() {
  const [activeRole, setActiveRole] = useState("Semua");
  const [query, setQuery] = useState("");
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set(applications.map((item) => item.opportunity.id)));
  const [selected, setSelected] = useState<Opportunity | null>(opportunities[0]);
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [status, setStatus] = useState<ApplicationStatus>("saved");

  const filtered = useMemo(() => filterOpportunities(opportunities, activeRole, query), [activeRole, query]);

  function toggleSaved(id: string) {
    setSavedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function openDrawer(opportunity: Opportunity) {
    setSelected(opportunity);
    setDrawerOpen(true);
  }

  function resetFilters() {
    setActiveRole("Semua");
    setQuery("");
  }

  return (
    <div className="page-wrap lowongan-page">
      <header className="page-header split">
        <div>
          <h1>Cari Lowongan</h1>
          <p>Temukan peluang magang dari berbagai platform dan simpan yang paling relevan.</p>
        </div>
        <div className="page-search">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Cari judul, perusahaan, peran..."
            aria-label="Cari lowongan"
          />
        </div>
      </header>

      <RoleChips active={activeRole} onSelect={setActiveRole} />

      <section className="lowongan-layout">
        <FilterPanel onReset={resetFilters} />

        <div className="results-area">
          <div className="results-head">
            <div>
              <h2>{filtered.length} peluang ditemukan</h2>
              <p>Dari Glints, Jobstreet, dan LinkedIn. Apply tetap dilakukan di platform asli.</p>
            </div>
            <select aria-label="Urutkan lowongan" defaultValue="rekomendasi">
              <option value="rekomendasi">Urutkan: Rekomendasi</option>
              <option value="cocok">Paling cocok</option>
              <option value="terbaru">Terbaru</option>
              <option value="skor">Skor tertinggi</option>
              <option value="dicek">Terakhir dicek</option>
              <option value="gaji">Ada info gaji</option>
            </select>
          </div>

          {filtered.length ? (
            <div className="job-grid">
              {filtered.map((opportunity) => (
                <JobCard
                  key={opportunity.id}
                  opportunity={opportunity}
                  saved={savedIds.has(opportunity.id)}
                  onToggleSaved={toggleSaved}
                  onOpen={openDrawer}
                />
              ))}
            </div>
          ) : (
            <EmptyState
              title="Belum ada hasil yang cocok."
              description="Coba ubah keyword, lokasi, atau filter pencarian."
              actionLabel="Atur Ulang Filter"
              onAction={resetFilters}
            />
          )}
        </div>
      </section>

      <JobDetailDrawer
        opportunity={selected}
        open={drawerOpen}
        saved={selected ? savedIds.has(selected.id) : false}
        status={status}
        onClose={() => setDrawerOpen(false)}
        onSave={() => selected && toggleSaved(selected.id)}
        onStatusChange={setStatus}
      />
    </div>
  );
}
