import { CompactJobCard } from "@/components/dashboard/CompactJobCard";
import { StatCard } from "@/components/dashboard/StatCard";
import { readDashboardSnapshot } from "@/lib/dashboard/server-data";

export const dynamic = "force-dynamic";

const activities = [
  { title: "Kamu menyimpan lowongan Frontend Developer Intern", time: "2 jam yang lalu" },
  { title: "Kamu mengubah status lamaran Data Analyst Intern ke Screening", time: "5 jam yang lalu" },
  { title: "Kamu melamar lowongan UI/UX Design Intern", time: "Kemarin, 18.30" },
  { title: "Kamu menyimpan lowongan Backend Developer Intern", time: "Kemarin, 14.12" },
];

export default async function DashboardPage() {
  const { opportunities, metadata, updatedAt } = await readDashboardSnapshot();
  const highQuality = metadata.accepted_by_dashboard_quality?.high ?? 0;
  const fullDetail = metadata.accepted_by_extraction_depth?.full_detail ?? 0;
  const lastRun = updatedAt
    ? new Intl.DateTimeFormat("id-ID", { dateStyle: "medium", timeStyle: "short" }).format(new Date(updatedAt))
    : "Belum ada export";

  return (
    <div className="page-wrap overview-page">
      <header className="page-header">
        <h1>Selamat datang kembali, Jakk.</h1>
        <p>Dashboard membaca peluang terbaru dari export engine lokal. Terakhir sync: {lastRun}.</p>
      </header>

      <section className="stats-grid">
        <StatCard title="Peluang Engine" value={String(opportunities.length)} helper="Data dari engine lokal" delta="auto-refresh di lowongan" />
        <StatCard title="Kualitas Tinggi" value={String(highQuality)} helper="Dashboard quality high" delta="siap diprioritaskan" />
        <StatCard title="Detail Lengkap" value={String(fullDetail)} helper="Full-detail extraction" delta="trust paling kuat" />
        <StatCard title="Platform" value={String(Object.keys(metadata.accepted_by_platform ?? {}).length)} helper="Sumber terdeteksi" delta="diversity check" />
      </section>

      <section className="overview-grid">
        <div className="panel-card">
          <div className="section-head">
            <div>
              <h2>Rekomendasi terbaik dari engine</h2>
              <p>Dipilih berdasarkan skor, role, dan kualitas data lowongan.</p>
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
