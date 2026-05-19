import { formatPlatformLabel, getSourceBadgeStyle } from "@/lib/dashboard/formatters";

export function SourceBadge({ platform }: { platform: string }) {
  return <span className={getSourceBadgeStyle(platform)}>{formatPlatformLabel(platform)}</span>;
}
