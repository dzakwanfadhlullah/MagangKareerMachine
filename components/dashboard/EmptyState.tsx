import Link from "next/link";

export function EmptyState({
  title,
  description,
  actionLabel,
  href,
  onAction,
}: {
  title: string;
  description: string;
  actionLabel?: string;
  href?: string;
  onAction?: () => void;
}) {
  const action = actionLabel ? (
    href ? (
      <Link className="primary-button" href={href}>
        {actionLabel}
      </Link>
    ) : (
      <button className="primary-button" type="button" onClick={onAction}>
        {actionLabel}
      </button>
    )
  ) : null;

  return (
    <div className="empty-state">
      <h2>{title}</h2>
      <p>{description}</p>
      {action}
    </div>
  );
}
