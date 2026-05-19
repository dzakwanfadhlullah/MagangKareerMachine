import { getQualityBadgeStyle, getQualityLabel } from "@/lib/dashboard/formatters";
import type { Opportunity } from "@/lib/dashboard/types";

export function QualityBadge({ opportunity }: { opportunity: Opportunity }) {
  return <span className={getQualityBadgeStyle(opportunity)}>{getQualityLabel(opportunity)}</span>;
}
