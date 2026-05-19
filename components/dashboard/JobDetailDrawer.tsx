"use client";

import {
  formatDeadline,
  formatDuration,
  formatLocation,
  formatPlatformLabel,
  formatSalary,
  formatWorkMode,
  getQualityLabel,
  getRoleBadgeStyle,
} from "@/lib/dashboard/formatters";
import type { ApplicationStatus, Opportunity } from "@/lib/dashboard/types";
import { ExternalLinkIcon, XIcon } from "./icons";
import { QualityBadge } from "./QualityBadge";
import { SourceBadge } from "./SourceBadge";

const statuses: { value: ApplicationStatus; label: string }[] = [
  { value: "saved", label: "Tersimpan" },
  { value: "applied", label: "Sudah Apply" },
  { value: "screening", label: "Screening" },
  { value: "interview", label: "Interview" },
  { value: "technical_test", label: "Technical Test" },
  { value: "offer", label: "Offer" },
  { value: "accepted", label: "Accepted" },
  { value: "rejected", label: "Rejected" },
  { value: "withdrawn", label: "Withdrawn" },
];

export function JobDetailDrawer({
  opportunity,
  open,
  saved,
  status,
  onClose,
  onSave,
  onStatusChange,
}: {
  opportunity: Opportunity | null;
  open: boolean;
  saved: boolean;
  status: ApplicationStatus;
  onClose: () => void;
  onSave: () => void;
  onStatusChange: (status: ApplicationStatus) => void;
}) {
  if (!opportunity) return null;

  const listedOnly = opportunity.extraction_depth === "listing_card";

  return (
    <div className={`drawer-backdrop ${open ? "open" : ""}`} aria-hidden={!open}>
      <aside className="detail-drawer" aria-label="Detail lowongan">
        <div className="drawer-head">
          <h2>Detail Lowongan</h2>
          <button className="icon-button" type="button" aria-label="Tutup detail" onClick={onClose}>
            <XIcon />
          </button>
        </div>

        <div className="drawer-title-row">
          <div>
            <h3>{opportunity.title}</h3>
            <p>{opportunity.company}</p>
          </div>
          <span className="score-pill">Skor {opportunity.score}</span>
        </div>

        <div className="badge-row drawer-badges">
          <span className={getRoleBadgeStyle(opportunity.role)}>{opportunity.role}</span>
          <SourceBadge platform={opportunity.source_platform} />
          <QualityBadge opportunity={opportunity} />
        </div>

        <section className="drawer-section">
          <h4>Ringkasan</h4>
          <p>{opportunity.summary_short}</p>
        </section>

        <section className="drawer-section">
          <h4>Detail Lowongan</h4>
          <dl className="detail-list">
            <div>
              <dt>Lokasi</dt>
              <dd>{formatLocation(opportunity.location)}</dd>
            </div>
            <div>
              <dt>Sistem Kerja</dt>
              <dd>{formatWorkMode(opportunity.work_mode)}</dd>
            </div>
            <div>
              <dt>Gaji</dt>
              <dd>{formatSalary(opportunity.salary_display)}</dd>
            </div>
            <div>
              <dt>Durasi</dt>
              <dd>{formatDuration(opportunity.duration)}</dd>
            </div>
            <div>
              <dt>Deadline</dt>
              <dd>{formatDeadline(opportunity.deadline)}</dd>
            </div>
            <div>
              <dt>Platform</dt>
              <dd>{formatPlatformLabel(opportunity.source_platform)}</dd>
            </div>
            <div>
              <dt>Terakhir dicek</dt>
              <dd>{opportunity.last_verified_at || "Terakhir dicek hari ini"}</dd>
            </div>
          </dl>
        </section>

        <section className="drawer-section">
          <h4>Kualitas Data</h4>
          <ul className="quality-list">
            <li>{getQualityLabel(opportunity)}</li>
            <li>Sumber: {formatPlatformLabel(opportunity.source_platform)}</li>
            <li>{listedOnly ? "Data sebagian dari listing" : "URL sudah diverifikasi"}</li>
            {listedOnly ? <li>Cek detail di platform asli</li> : null}
          </ul>
        </section>

        <section className="drawer-section">
          <h4>Catatan Pribadi</h4>
          <textarea placeholder="Tulis catatan atau hal penting tentang lowongan ini..." maxLength={500} />
          <span className="textarea-count">0/500</span>
        </section>

        <section className="drawer-section">
          <h4>Status Lamaran</h4>
          <select value={status} onChange={(event) => onStatusChange(event.target.value as ApplicationStatus)}>
            {statuses.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </section>

        <div className="drawer-actions">
          <a className="primary-button full" href={opportunity.source_url} target="_blank" rel="noreferrer">
            Apply di Platform Asli
            <ExternalLinkIcon />
          </a>
          <div className="split-actions">
            <button className="secondary-button" type="button" onClick={onSave}>
              {saved ? "Tersimpan" : "Simpan"}
            </button>
            <button className="secondary-button" type="button" onClick={() => onStatusChange("applied")}>
              Tandai Sudah Apply
            </button>
          </div>
        </div>

        <div className="info-box">
          MagangKareer tidak mengirim lamaran otomatis. Kamu akan diarahkan ke platform asli untuk apply.
        </div>
      </aside>
    </div>
  );
}
