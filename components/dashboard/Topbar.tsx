import { BellIcon, SearchIcon } from "./icons";

export function Topbar() {
  return (
    <header className="topbar">
      <form className="topbar-search">
        <SearchIcon />
        <input aria-label="Cari magang" placeholder="Cari magang frontend, data, aktuaria..." />
        <button className="primary-button" type="submit">
          Cari
        </button>
      </form>

      <div className="topbar-actions">
        <span className="usage-pill">12 pencarian tersisa</span>
        <button className="icon-button" aria-label="Notifikasi">
          <BellIcon />
        </button>
        <div className="user-menu" aria-label="Profil pengguna">
          <span className="avatar">J</span>
          <span>
            <strong>Jakk</strong>
            <span>Mahasiswa</span>
          </span>
        </div>
      </div>
    </header>
  );
}
