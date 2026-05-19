import type { Opportunity } from "./types";

export const roleChips = ["Semua", "Frontend", "Backend", "Fullstack", "Mobile", "Data Analyst", "AI/ML", "Aktuaria", "UI/UX", "Product"];

export function filterOpportunities(opportunities: Opportunity[], role: string, query: string) {
  const normalizedQuery = query.trim().toLowerCase();
  return opportunities.filter((opportunity) => {
    const roleMatch =
      role === "Semua" ||
      opportunity.role.toLowerCase().includes(role.toLowerCase()) ||
      (role === "Aktuaria" && opportunity.category === "actuarial") ||
      (role === "AI/ML" && opportunity.role.toLowerCase().includes("ai"));

    const queryMatch =
      !normalizedQuery ||
      [opportunity.title, opportunity.company, opportunity.role, opportunity.category, opportunity.location || ""]
        .join(" ")
        .toLowerCase()
        .includes(normalizedQuery);

    return roleMatch && queryMatch;
  });
}
