import "server-only";

import { promises as fs } from "fs";
import path from "path";
import type { Opportunity } from "./types";

export type DashboardMetadata = {
  generated_at?: string;
  result_count?: number;
  accepted_by_platform?: Record<string, number>;
  accepted_by_dashboard_quality?: Record<string, number>;
  accepted_by_extraction_depth?: Record<string, number>;
  accepted_full_detail_by_platform?: Record<string, number>;
  accepted_partial_by_platform?: Record<string, number>;
  source_diversity_warning?: boolean;
  full_detail_source_diversity_warning?: boolean;
};

export type DashboardSnapshot = {
  opportunities: Opportunity[];
  metadata: DashboardMetadata;
  source: "exports/dashboard" | "latest-export" | "empty";
  sourcePath: string | null;
  updatedAt: string | null;
};

const DASHBOARD_DIR = path.join(process.cwd(), "exports", "dashboard");

function exportDirFromEnv() {
  return process.env.DASHBOARD_EXPORT_DIR
    ? path.resolve(process.cwd(), process.env.DASHBOARD_EXPORT_DIR)
    : DASHBOARD_DIR;
}

async function fileExists(filePath: string) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function findLatestDashboardExport() {
  const exportsRoot = path.join(process.cwd(), "exports");
  let entries: string[] = [];
  try {
    entries = await fs.readdir(exportsRoot);
  } catch {
    return null;
  }

  const candidates = await Promise.all(
    entries.map(async (entry) => {
      const dashboardDir = path.join(exportsRoot, entry, "dashboard");
      const opportunitiesPath = path.join(dashboardDir, "opportunities.json");
      if (!(await fileExists(opportunitiesPath))) return null;
      const stats = await fs.stat(opportunitiesPath);
      return { dashboardDir, mtimeMs: stats.mtimeMs };
    }),
  );

  return candidates
    .filter((candidate): candidate is { dashboardDir: string; mtimeMs: number } => Boolean(candidate))
    .sort((a, b) => b.mtimeMs - a.mtimeMs)[0]?.dashboardDir ?? null;
}

function normalizeOpportunity(row: Record<string, unknown>): Opportunity {
  return {
    id: String(row.id ?? ""),
    title: String(row.title ?? "Lowongan tanpa judul"),
    company: String(row.company ?? "Perusahaan belum tersedia"),
    role: String(row.role ?? "Role belum tersedia"),
    role_specialization: typeof row.role_specialization === "string" ? row.role_specialization : undefined,
    category: String(row.category ?? "unknown"),
    location: typeof row.location === "string" ? row.location : null,
    location_area: typeof row.location_area === "string" ? row.location_area : null,
    work_mode: row.work_mode === "remote" || row.work_mode === "hybrid" || row.work_mode === "onsite" ? row.work_mode : null,
    duration: typeof row.duration === "string" ? row.duration : null,
    salary_display: typeof row.salary_display === "string" ? row.salary_display : null,
    deadline: typeof row.deadline === "string" ? row.deadline : null,
    source_platform: String(row.source_platform ?? "generic"),
    source_url: String(row.apply_url ?? row.source_url ?? "#"),
    score: Number(row.score ?? 0),
    dashboard_quality: row.dashboard_quality === "high" || row.dashboard_quality === "low" ? row.dashboard_quality : "medium",
    extraction_depth:
      row.extraction_depth === "listing_card" || row.extraction_depth === "search_snippet"
        ? row.extraction_depth
        : "full_detail",
    verification_level:
      row.verification_level === "verified_detail" ||
      row.verification_level === "listed_only" ||
      row.verification_level === "search_index_only"
        ? row.verification_level
        : "unknown",
    active_status:
      row.active_status === "active" ||
      row.active_status === "listed" ||
      row.active_status === "closed" ||
      row.active_status === "unknown"
        ? row.active_status
        : "unknown",
    summary_short: String(row.summary_short ?? "Ringkasan belum tersedia. Cek detail di platform asli."),
    first_seen: typeof row.first_seen === "string" ? row.first_seen : undefined,
    last_verified_at: typeof row.last_verified_at === "string" ? row.last_verified_at : undefined,
  };
}

async function readJson<T>(filePath: string, fallback: T): Promise<T> {
  try {
    return JSON.parse(await fs.readFile(filePath, "utf-8")) as T;
  } catch {
    return fallback;
  }
}

export async function readDashboardSnapshot(): Promise<DashboardSnapshot> {
  const configuredDir = exportDirFromEnv();
  const configuredOpportunities = path.join(configuredDir, "opportunities.json");
  const dashboardDir = (await fileExists(configuredOpportunities)) ? configuredDir : await findLatestDashboardExport();

  if (!dashboardDir) {
    return {
      opportunities: [],
      metadata: { result_count: 0 },
      source: "empty",
      sourcePath: null,
      updatedAt: null,
    };
  }

  const opportunitiesPath = path.join(dashboardDir, "opportunities.json");
  const metadataPath = path.join(dashboardDir, "metadata.json");
  const rawRows = await readJson<Record<string, unknown>[]>(opportunitiesPath, []);
  const stats = await fs.stat(opportunitiesPath);

  return {
    opportunities: rawRows.map(normalizeOpportunity),
    metadata: await readJson<DashboardMetadata>(metadataPath, { result_count: rawRows.length }),
    source: dashboardDir === configuredDir ? "exports/dashboard" : "latest-export",
    sourcePath: path.relative(process.cwd(), opportunitiesPath),
    updatedAt: stats.mtime.toISOString(),
  };
}
