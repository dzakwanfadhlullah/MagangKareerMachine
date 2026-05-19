import type { Watchlist } from "@/lib/dashboard/types";

export function WatchlistCard({ watchlist }: { watchlist: Watchlist }) {
  return (
    <article className="watchlist-card">
      <div>
        <h3>{watchlist.title}</h3>
        <p>{watchlist.lastRun}</p>
      </div>
      <div className="badge-row">
        {watchlist.roles.map((role) => (
          <span className="badge badge-role" key={role}>
            {role}
          </span>
        ))}
        {watchlist.locations.map((location) => (
          <span className="badge badge-gray" key={location}>
            {location}
          </span>
        ))}
      </div>
      <strong>{watchlist.newCount} peluang baru</strong>
      <button className="secondary-button" type="button">
        Lihat Hasil
      </button>
    </article>
  );
}
