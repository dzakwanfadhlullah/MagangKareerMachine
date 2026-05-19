export default function PengaturanPage() {
  return (
    <div className="page-wrap settings-page">
      <header className="page-header">
        <h1>Pengaturan</h1>
        <p>Atur profil, preferensi pencarian, notifikasi, dan paket MagangKareer.</p>
      </header>

      <div className="settings-grid">
        <section className="settings-card">
          <h2>Profil</h2>
          <div className="settings-row">
            <span>Nama</span>
            <strong>Jakk</strong>
          </div>
          <div className="settings-row">
            <span>Peran</span>
            <strong>Mahasiswa</strong>
          </div>
        </section>

        <section className="settings-card">
          <h2>Preferensi Pencarian</h2>
          <div className="badge-row">
            {["Frontend", "Backend", "Fullstack", "Mobile", "Data"].map((item) => (
              <span className="badge badge-role" key={item}>{item}</span>
            ))}
          </div>
        </section>

        <section className="settings-card">
          <h2>Notifikasi</h2>
          <label className="toggle-row">
            <span>Notifikasi email</span>
            <input type="checkbox" defaultChecked />
          </label>
          <label className="toggle-row">
            <span>Notifikasi watchlist</span>
            <input type="checkbox" defaultChecked />
          </label>
        </section>

        <section className="settings-card plan-card">
          <h2>Paket</h2>
          <p>Paket saat ini: Gratis</p>
          <p>Pemakaian: 12 pencarian tersisa</p>
          <button className="primary-button" type="button">Upgrade ke Premium</button>
        </section>
      </div>
    </div>
  );
}
