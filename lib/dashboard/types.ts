export type WorkMode = "remote" | "hybrid" | "onsite";
export type DashboardQuality = "high" | "medium" | "low";
export type ExtractionDepth = "full_detail" | "listing_card" | "search_snippet";
export type VerificationLevel = "verified_detail" | "listed_only" | "search_index_only" | "unknown";
export type ActiveStatus = "active" | "listed" | "unknown" | "closed";

export type Opportunity = {
  id: string;
  title: string;
  company: string;
  role: string;
  role_specialization?: string;
  category: string;
  location?: string | null;
  location_area?: string | null;
  work_mode?: WorkMode | null;
  duration?: string | null;
  salary_display?: string | null;
  deadline?: string | null;
  source_platform: "glints" | "jobstreet" | "linkedin" | "dealls" | "kalibrr" | string;
  source_url: string;
  score: number;
  dashboard_quality: DashboardQuality;
  extraction_depth: ExtractionDepth;
  verification_level: VerificationLevel;
  active_status: ActiveStatus;
  summary_short: string;
  first_seen?: string;
  last_verified_at?: string;
};

export type ApplicationStatus =
  | "saved"
  | "applied"
  | "screening"
  | "interview"
  | "technical_test"
  | "offer"
  | "accepted"
  | "rejected"
  | "withdrawn";

export type ApplicationCard = {
  id: string;
  opportunity: Opportunity;
  status: ApplicationStatus;
  updated_at: string;
  applied_at?: string;
};

export type Watchlist = {
  id: string;
  title: string;
  roles: string[];
  locations: string[];
  newCount: number;
  lastRun: string;
};
