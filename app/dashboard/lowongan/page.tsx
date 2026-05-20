"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { EmptyState } from "@/components/dashboard/EmptyState";
import { FilterPanel } from "@/components/dashboard/FilterPanel";
import { JobCard } from "@/components/dashboard/JobCard";
import { JobDetailDrawer } from "@/components/dashboard/JobDetailDrawer";
import { RoleChips } from "@/components/dashboard/RoleChips";
import { filterOpportunities } from "@/lib/dashboard/filters";
import type { ApplicationStatus, Opportunity } from "@/lib/dashboard/types";

type EngineStatus = {
  running: boolean;
  phase: "idle" | "engine" | "export" | "success" | "failed";
  message: string;
  startedAt: string | null;
  finishedAt: string | null;
  stdoutTail: string[];
  stderrTail: string[];
};

type OpportunitiesResponse = {
  opportunities: Opportunity[];
  metadata: {
    generated_at?: string;
    result_count?: number;
    accepted_by_platform?: Record<string, number>;
  };
  source: "exports/dashboard" | "latest-export" | "empty";
  sourcePath: string | null;
  updatedAt: string | null;
};

function readSavedIds() {
  if (typeof window === "undefined") return new Set<string>();
  try {
    const stored = window.localStorage.getItem("magangkareer_saved_ids");
    return new Set(stored ? (JSON.parse(stored) as string[]) : []);
  } catch {
    return new Set<string>();
  }
}

export default function LowonganPage() {
  const [activeRole, setActiveRole] = useState("Semua");
  const [query, setQuery] = useState("");
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [snapshot, setSnapshot] = useState<OpportunitiesResponse | null>(null);
  const [engineStatus, setEngineStatus] = useState<EngineStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedIds, setSavedIds] = useState<Set<string>>(readSavedIds);
  const [selected, setSelected] = useState<Opportunity | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [status, setStatus] = useState<ApplicationStatus>("saved");

  const filtered = useMemo(() => filterOpportunities(opportunities, activeRole, query), [opportunities, activeRole, query]);

  const loadDashboardData = useCallback(async () => {
    try {
      const [opportunitiesResponse, statusResponse] = await Promise.all([
        fetch("/api/opportunities", { cache: "no-store" }),
        fetch("/api/engine/status", { cache: "no-store" }),
      ]);
      if (!opportunitiesResponse.ok || !statusResponse.ok) {
        throw new Error("Gagal membaca data engine.");
      }
      const nextSnapshot = (await opportunitiesResponse.json()) as OpportunitiesResponse;
      const nextStatus = (await statusResponse.json()) as EngineStatus;
      setSnapshot(nextSnapshot);
      setEngineStatus(nextStatus);
      setOpportunities(nextSnapshot.opportunities);
      setSelected((current) => current ?? nextSnapshot.opportunities[0] ?? null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal membaca data engine.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const firstLoad = window.setTimeout(() => {
      void loadDashboardData();
    }, 0);
    const interval = window.setInterval(() => {
      void loadDashboardData();
    }, engineStatus?.running ? 3000 : 10000);
    return () => {
      window.clearTimeout(firstLoad);
      window.clearInterval(interval);
    };
  }, [engineStatus?.running, loadDashboardData]);

  function toggleSaved(id: string) {
    setSavedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      window.localStorage.setItem("magangkareer_saved_ids", JSON.stringify([...next]));
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

  async function runEngine() {
    setSyncing(true);
    try {
      const response = await fetch("/api/engine/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: "crawl-sources", profile: "quick", minScore: 40 }),
      });
      const nextStatus = (await response.json()) as EngineStatus;
      setEngineStatus(nextStatus);
      if (!response.ok && !nextStatus.running) {
        setError(nextStatus.message);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menjalankan engine.");
    } finally {
      setSyncing(false);
      void loadDashboardData();
    }
  }

  const lastRunLabel =
    snapshot?.updatedAt || snapshot?.metadata.generated_at
      ? new Intl.DateTimeFormat("id-ID", {
          dateStyle: "medium",
          timeStyle: "short",
        }).format(new Date(snapshot.updatedAt ?? snapshot.metadata.generated_at ?? ""))
      : "Belum ada export";

  return (
    <div className="page-wrap lowongan-page">
      <header className="page-header split">
        <div>
          <h1>Cari Lowongan</h1>
          <p>
            {engineStatus?.running ? engineStatus.message : "Data dibaca langsung dari export engine lokal."}
          </p>
        </div>
        <div className="page-actions">
          <button className="secondary-button" type="button" onClick={runEngine} disabled={syncing || engineStatus?.running}>
            {engineStatus?.running ? "Engine Berjalan" : syncing ? "Menyalakan..." : "Jalankan Engine"}
          </button>
          <div className="page-search">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Cari judul, perusahaan, peran..."
              aria-label="Cari lowongan"
            />
          </div>
        </div>
      </header>

      <section className="panel-card">
        <div className="section-head">
          <div>
            <h2>Status Engine</h2>
            <p>
              {snapshot?.sourcePath ? `${snapshot.sourcePath} • ${lastRunLabel}` : lastRunLabel}
            </p>
          </div>
          <span className={`badge ${engineStatus?.phase === "failed" ? "badge-amber" : engineStatus?.running ? "badge-blue" : "badge-green"}`}>
            {engineStatus?.running ? "Live update" : engineStatus?.phase === "failed" ? "Perlu dicek" : "Siap"}
          </span>
        </div>
        {error ? <p className="job-summary">{error}</p> : null}
      </section>

      <RoleChips active={activeRole} onSelect={setActiveRole} />

      <section className="lowongan-layout">
        <FilterPanel onReset={resetFilters} />

        <div className="results-area">
          <div className="results-head">
            <div>
              <h2>{loading ? "Memuat peluang..." : `${filtered.length} peluang ditemukan`}</h2>
              <p>
                {snapshot?.metadata.accepted_by_platform
                  ? `Sumber: ${Object.entries(snapshot.metadata.accepted_by_platform)
                      .map(([platform, count]) => `${platform} ${count}`)
                      .join(", ")}.`
                  : "Apply tetap dilakukan di platform asli."}
              </p>
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
              title={loading ? "Menghubungkan ke engine..." : "Belum ada hasil yang cocok."}
              description={loading ? "Dashboard sedang membaca export engine lokal." : "Coba ubah keyword, lokasi, atau jalankan engine."}
              actionLabel={loading ? "Memuat" : "Atur Ulang Filter"}
              onAction={loading ? undefined : resetFilters}
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
