import { getApplicationStatusLabel } from "@/lib/dashboard/formatters";
import type { ApplicationStatus } from "@/lib/dashboard/types";

export function StatusBadge({ status }: { status: ApplicationStatus }) {
  return <span className={`badge status-${status}`}>{getApplicationStatusLabel(status)}</span>;
}
