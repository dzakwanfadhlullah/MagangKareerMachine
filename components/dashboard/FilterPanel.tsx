const sections = [
  { title: "Role", items: ["Frontend", "Backend", "Fullstack", "Mobile", "Data", "AI/ML", "Aktuaria"] },
  { title: "Lokasi", items: ["Jakarta", "Bandung", "Surabaya", "Yogyakarta", "Remote", "Indonesia"] },
  { title: "Sistem Kerja", items: ["Remote", "Hybrid", "Onsite"] },
  { title: "Platform", items: ["Glints", "Jobstreet", "LinkedIn", "Dealls", "Kalibrr"] },
  { title: "Kualitas Data", items: ["Detail Lengkap", "Data Terbatas", "Sumber Publik"] },
  { title: "Gaji", items: ["Ada info gaji", "Tidak dicantumkan"] },
  { title: "Status Lamaran", items: ["Belum disimpan", "Tersimpan", "Sudah Apply", "Interview"] },
];

export function FilterPanel({ onReset }: { onReset?: () => void }) {
  return (
    <aside className="filter-panel">
      <div className="filter-head">
        <h2>Filter</h2>
        <button className="ghost-button compact" type="button" onClick={onReset}>
          Reset Semua
        </button>
      </div>

      {sections.map((section) => (
        <details key={section.title} className="filter-section" open={["Role", "Lokasi", "Sistem Kerja"].includes(section.title)}>
          <summary>{section.title}</summary>
          <div className="filter-options">
            {section.items.map((item) => (
              <label key={item} className="filter-option">
                <input type="checkbox" />
                <span>{item}</span>
              </label>
            ))}
          </div>
        </details>
      ))}
    </aside>
  );
}
