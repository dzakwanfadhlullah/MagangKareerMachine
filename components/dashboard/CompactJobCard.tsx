import { formatLocation, formatSalary, getRoleBadgeStyle } from "@/lib/dashboard/formatters";
import type { Opportunity } from "@/lib/dashboard/types";
import { QualityBadge } from "./QualityBadge";
import { SourceBadge } from "./SourceBadge";

export function CompactJobCard({ opportunity }: { opportunity: Opportunity }) {
  return (
    <article className="compact-job-card">
      <div className="compact-job-head">
        <div>
          <h3>{opportunity.title}</h3>
          <p>{opportunity.company}</p>
        </div>
        <span className="score-pill">Skor {opportunity.score}</span>
      </div>
      <div className="badge-row">
        <span className={getRoleBadgeStyle(opportunity.role)}>{opportunity.role}</span>
        <SourceBadge platform={opportunity.source_platform} />
        <QualityBadge opportunity={opportunity} />
      </div>
      <div className="metadata-row">
        <span>{formatLocation(opportunity.location)}</span>
        <span>{formatSalary(opportunity.salary_display)}</span>
      </div>
    </article>
  );
}
