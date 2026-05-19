import { CompactJobCard } from "@/components/dashboard/CompactJobCard";
import { StatCard } from "@/components/dashboard/StatCard";
import { opportunities } from "@/lib/dashboard/mock-data";

const activities = [
  { title: "Kamu menyimpan lowongan Frontend Developer Intern", time: "2 jam yang lalu" },
  { title: "Kamu mengubah status lamaran Data Analyst Intern ke Screening", time: "5 jam yang lalu" },
  { title: "Kamu melamar lowongan UI/UX Design Intern", time: "Kemarin, 18.30" },
  { title: "Kamu menyimpan lowongan Backend Developer Intern", time: "Kemarin, 14.12" },
];

export default function DashboardPage() {
  return (
    <div className="page-wrap overview-page">
      <header className="page-header">
        <h1>Selamat datang kembali, Jakk.</h1>
        <p>Kelola pencarian magang, simpan peluang terbaik, dan lacak progres lamaranmu dalam satu tempat.</p>
      </header>

      <section className="stats-grid">
        <StatCard title="Tersimpan" value="12" helper="Peluang yang kamu simpan" delta="+3 minggu ini" />
        <StatCard title="Sudah Apply" value="5" helper="Lamaran yang sudah dikirim" delta="+2 minggu ini" />
        <StatCard title="Interview" value="2" helper="Sedang berjalan" delta="+0 minggu ini" />
        <StatCard title="Deadline Terdekat" value="3" helper="Butuh perhatian minggu ini" delta="dalam 7 hari" />
      </section>

      <section className="overview-grid">
        <div className="panel-card">
          <div className="section-head">
            <div>
              <h2>Rekomendasi terbaik hari ini</h2>
              <p>Dipilih berdasarkan minat, role, dan kualitas data lowongan.</p>
            </div>
            <a href="/dashboard/lowongan">Lihat semua</a>
          </div>
          <div className="compact-job-grid">
            {opportunities.slice(0, 3).map((opportunity) => (
              <CompactJobCard key={opportunity.id} opportunity={opportunity} />
            ))}
          </div>
        </div>

        <div className="panel-card activity-panel">
          <div className="section-head">
            <div>
              <h2>Aktivitas Terakhir</h2>
              <p>Ringkasan progres dan perubahan terbaru.</p>
            </div>
            <a href="/dashboard/lamaran">Lihat semua</a>
          </div>
          <div className="activity-list">
            {activities.map((activity) => (
              <article key={activity.title}>
                <span />
                <div>
                  <p>{activity.title}</p>
                  <time>{activity.time}</time>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
