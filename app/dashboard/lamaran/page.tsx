import { ApplicationKanban } from "@/components/dashboard/ApplicationKanban";
import { applications } from "@/lib/dashboard/mock-data";

export default function LamaranPage() {
  return (
    <div className="page-wrap lamaran-page">
      <header className="page-header split">
        <div>
          <h1>Lamaran Saya</h1>
          <p>Pantau setiap tahap lamaranmu dengan mudah.</p>
        </div>
        <div className="page-actions">
          <div className="view-toggle" aria-label="Tampilan">
            <button className="active" type="button">
              Kanban
            </button>
            <button type="button">Daftar</button>
          </div>
          <button className="primary-button" type="button">
            Tambah Manual
          </button>
        </div>
      </header>

      <ApplicationKanban applications={applications} />
    </div>
  );
}
