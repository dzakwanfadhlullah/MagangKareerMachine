import type { ApplicationStatus, Opportunity, WorkMode } from "./types";

export function formatWorkMode(mode?: WorkMode | null) {
  if (!mode) return "Sistem kerja belum tersedia";
  const labels: Record<WorkMode, string> = {
    remote: "Remote",
    hybrid: "Hybrid",
    onsite: "Onsite",
  };
  return labels[mode];
}

export function formatSalary(value?: string | null) {
  return value || "Gaji tidak dicantumkan";
}

export function formatLocation(value?: string | null) {
  return value || "Lokasi belum tersedia";
}

export function formatDuration(value?: string | null) {
  return value || "Durasi tidak dicantumkan";
}

export function formatDeadline(value?: string | null) {
  return value || "Deadline tidak dicantumkan";
}

export function formatPlatformLabel(platform: string) {
  const labels: Record<string, string> = {
    glints: "Glints",
    jobstreet: "Jobstreet",
    linkedin: "LinkedIn",
    dealls: "Dealls",
    kalibrr: "Kalibrr",
    generic: "Sumber Umum",
  };
  return labels[platform] || platform;
}

export function getQualityLabel(opp: Opportunity) {
  if (opp.dashboard_quality === "high" && opp.extraction_depth === "full_detail" && opp.verification_level === "verified_detail") {
    return "Detail Lengkap";
  }
  if (opp.extraction_depth === "listing_card" || opp.verification_level === "listed_only") {
    return "Data Terbatas";
  }
  if (opp.extraction_depth === "search_snippet") {
    return "Sumber Publik";
  }
  if (opp.dashboard_quality === "low") {
    return "Perlu Dicek";
  }
  return "Data Cukup";
}

export function getQualityBadgeStyle(opp: Opportunity) {
  const label = getQualityLabel(opp);
  if (label === "Detail Lengkap") return "badge badge-green";
  if (label === "Data Terbatas") return "badge badge-amber";
  if (label === "Sumber Publik") return "badge badge-blue";
  return "badge badge-gray";
}

export function getSourceBadgeStyle(platform: string) {
  const normalized = platform.toLowerCase();
  if (normalized === "glints") return "badge badge-cream";
  if (normalized === "jobstreet") return "badge badge-purple";
  if (normalized === "linkedin") return "badge badge-blue";
  if (normalized === "dealls") return "badge badge-violet";
  if (normalized === "kalibrr") return "badge badge-sky";
  return "badge badge-gray";
}

export function getRoleBadgeStyle(role: string) {
  const lowered = role.toLowerCase();
  if (lowered.includes("data")) return "badge badge-blue";
  if (lowered.includes("product")) return "badge badge-violet";
  if (lowered.includes("mobile")) return "badge badge-green";
  if (lowered.includes("backend")) return "badge badge-purple";
  return "badge badge-role";
}

export function getApplicationStatusLabel(status: ApplicationStatus) {
  const labels: Record<ApplicationStatus, string> = {
    saved: "Tersimpan",
    applied: "Sudah Apply",
    screening: "Screening",
    interview: "Interview",
    technical_test: "Technical Test",
    offer: "Offer",
    accepted: "Accepted",
    rejected: "Rejected",
    withdrawn: "Withdrawn",
  };
  return labels[status];
}
