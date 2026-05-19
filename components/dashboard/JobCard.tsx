"use client";

import { formatLocation, formatSalary, formatWorkMode, getRoleBadgeStyle } from "@/lib/dashboard/formatters";
import type { Opportunity } from "@/lib/dashboard/types";
import { BookmarkIcon, ExternalLinkIcon, MapPinIcon, WorkModeIcon } from "./icons";
import { QualityBadge } from "./QualityBadge";
import { SourceBadge } from "./SourceBadge";

export function JobCard({
  opportunity,
  saved,
  onToggleSaved,
  onOpen,
}: {
  opportunity: Opportunity;
  saved: boolean;
  onToggleSaved: (id: string) => void;
  onOpen: (opportunity: Opportunity) => void;
}) {
  return (
    <article className="job-card" onClick={() => onOpen(opportunity)}>
      <div className="job-card-top">
        <div className="badge-row">
          <span className={getRoleBadgeStyle(opportunity.role)}>{opportunity.role}</span>
          <SourceBadge platform={opportunity.source_platform} />
          <QualityBadge opportunity={opportunity} />
        </div>
        <span className="score-pill">Skor {opportunity.score}</span>
      </div>

      <h3>{opportunity.title}</h3>
      <p className="company">{opportunity.company}</p>

      <div className="metadata-row">
        <span>
          <MapPinIcon />
          {formatLocation(opportunity.location)}
        </span>
        <span>
          <WorkModeIcon />
          {formatWorkMode(opportunity.work_mode)}
        </span>
        <span>{formatSalary(opportunity.salary_display)}</span>
      </div>

      <p className="job-summary">{opportunity.summary_short}</p>

      <div className="job-actions">
        <button
          className={`secondary-button ${saved ? "saved" : ""}`}
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onToggleSaved(opportunity.id);
          }}
        >
          <BookmarkIcon />
          {saved ? "Tersimpan" : "Simpan"}
        </button>
        <a
          className="primary-button"
          href={opportunity.source_url}
          target="_blank"
          rel="noreferrer"
          onClick={(event) => event.stopPropagation()}
        >
          Buka Lowongan
          <ExternalLinkIcon />
        </a>
      </div>
    </article>
  );
}
