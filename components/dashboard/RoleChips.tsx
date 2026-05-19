"use client";

import { roleChips } from "@/lib/dashboard/filters";

export function RoleChips({
  active,
  onSelect,
}: {
  active: string;
  onSelect: (role: string) => void;
}) {
  return (
    <div className="role-chips" aria-label="Filter role cepat">
      {roleChips.map((role) => (
        <button key={role} className={`role-chip ${active === role ? "active" : ""}`} onClick={() => onSelect(role)} type="button">
          {role}
        </button>
      ))}
    </div>
  );
}
