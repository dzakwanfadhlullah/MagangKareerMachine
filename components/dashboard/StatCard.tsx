export function StatCard({
  title,
  value,
  helper,
  delta,
}: {
  title: string;
  value: string;
  helper: string;
  delta: string;
}) {
  return (
    <article className="stat-card">
      <span>{title}</span>
      <strong>{value}</strong>
      <p>{helper}</p>
      <em>{delta}</em>
    </article>
  );
}
