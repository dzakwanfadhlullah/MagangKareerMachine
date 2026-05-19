import { getApplicationStatusLabel, formatPlatformLabel } from "@/lib/dashboard/formatters";
import type { ApplicationCard, ApplicationStatus } from "@/lib/dashboard/types";

const columns: ApplicationStatus[] = ["saved", "applied", "screening", "interview", "technical_test", "offer", "accepted", "rejected"];

export function ApplicationKanban({ applications }: { applications: ApplicationCard[] }) {
  return (
    <div className="kanban-board">
      {columns.map((status) => {
        const items = applications.filter((application) => application.status === status);
        return (
          <section className="kanban-column" key={status}>
            <div className="kanban-column-head">
              <h2>{getApplicationStatusLabel(status)}</h2>
              <span>{items.length}</span>
            </div>
            <div className="kanban-cards">
              {items.map((application) => (
                <article className="kanban-card" key={application.id}>
                  <div>
                    <h3>{application.opportunity.title}</h3>
                    <p>{application.opportunity.company}</p>
                  </div>
                  <div className="kanban-card-meta">
                    <span>{formatPlatformLabel(application.opportunity.source_platform)}</span>
                    <span>Skor {application.opportunity.score}</span>
                  </div>
                  <time>{application.applied_at ? `Apply: ${application.applied_at}` : application.updated_at}</time>
                </article>
              ))}
              <button className="kanban-add" type="button">
                + Tambah kartu
              </button>
            </div>
          </section>
        );
      })}
    </div>
  );
}
