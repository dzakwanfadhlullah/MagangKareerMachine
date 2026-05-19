import { EmptyState } from "@/components/dashboard/EmptyState";
import { WatchlistCard } from "@/components/dashboard/WatchlistCard";
import { watchlists } from "@/lib/dashboard/mock-data";

export default function WatchlistPage() {
  return (
    <div className="page-wrap">
      <header className="page-header split">
        <div>
          <h1>Watchlist</h1>
          <p>Pantau keyword magang yang paling penting untukmu.</p>
        </div>
        <button className="primary-button" type="button">
          Buat Watchlist Baru
        </button>
      </header>

      {watchlists.length ? (
        <div className="watchlist-grid">
          {watchlists.map((watchlist) => (
            <WatchlistCard key={watchlist.id} watchlist={watchlist} />
          ))}
        </div>
      ) : (
        <EmptyState
          title="Belum ada watchlist."
          description="Buat pencarian seperti 'Frontend Intern Jakarta' atau 'Aktuaria Internship' agar peluang baru lebih mudah dipantau."
          actionLabel="Buat Watchlist"
        />
      )}
    </div>
  );
}
