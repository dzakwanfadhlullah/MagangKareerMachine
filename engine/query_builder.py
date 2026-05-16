"""Query Builder — ekspansi keyword menjadi search queries."""

from pathlib import Path
from typing import Optional

import yaml


CONFIG_PATH = Path("config/keywords.yml")

TARGET_QUERY_EXPANSIONS = {
    "actuarial": [
        "actuarial internship",
        "actuarial intern",
        "actuary internship",
        "actuary intern",
        "magang aktuaria",
        "pricing valuation internship",
        "pricing and valuation intern",
        "valuation intern",
        "reserving intern",
        "reinsurance internship",
        "insurance pricing intern",
        "product pricing intern",
        "technical reserve intern",
        "IFRS 17 intern",
        "PSAK 117 intern",
    ],
}


def load_keywords(config_path: Optional[Path] = None) -> dict:
    """Load keyword config dari YAML."""
    path = config_path or CONFIG_PATH
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_queries(role: str, location: str, config_path: Optional[Path] = None) -> list[str]:
    """
    Ekspansi role + location menjadi beberapa search query.

    Contoh: role="frontend", location="Indonesia"
    Output:
        "frontend intern" "Indonesia"
        "frontend internship" "Indonesia"
        "magang frontend" "Indonesia"
        "react intern" "Indonesia"
        ...
    """
    config = load_keywords(config_path)
    internship_terms = config.get("internship_terms", ["intern", "internship", "magang"])
    role_keywords = config.get("role_keywords", {})

    # Kumpulkan semua sinonim untuk role yang diberikan
    role_lower = role.lower().strip()
    synonyms = [role_lower]

    # Cari di role_keywords config
    for category, keywords in role_keywords.items():
        if role_lower in [k.lower() for k in keywords] or role_lower == category.lower():
            synonyms.extend([k.lower() for k in keywords])
            break

    # Hapus duplikat, pertahankan urutan
    seen = set()
    unique_synonyms = []
    for s in synonyms:
        if s not in seen:
            seen.add(s)
            unique_synonyms.append(s)

    # Generate query combinations
    queries = []
    for synonym in unique_synonyms:
        for term in internship_terms:
            # Format: "frontend intern" "Indonesia"
            q = f'"{synonym} {term}" "{location}"'
            if q not in queries:
                queries.append(q)

            # Format bahasa Indonesia: "magang frontend"
            if term == "magang":
                q_id = f'"magang {synonym}" "{location}"'
                if q_id not in queries:
                    queries.append(q_id)

    return queries


def build_queries_from_raw(query: str, location: str, target_category: Optional[str] = None) -> list[str]:
    """
    Build queries dari raw query string tanpa ekspansi role.
    Untuk query yang sudah spesifik dari user.
    """
    normalized_target = (target_category or "").strip().lower().replace("-", "_").replace(" ", "_")
    raw_queries = [query]
    raw_queries.extend(TARGET_QUERY_EXPANSIONS.get(normalized_target, []))

    seen_raw = set()
    unique_raw = []
    for raw in raw_queries:
        key = raw.lower().strip()
        if key and key not in seen_raw:
            seen_raw.add(key)
            unique_raw.append(raw)

    queries = []
    if normalized_target:
        for raw in unique_raw:
            queries.append(f'"{raw}" "{location}"')
        for raw in unique_raw:
            queries.extend([
                f'site:glints.com/id/opportunities/jobs "{raw}" "{location}"',
                f'site:dealls.com/loker "{raw}" "{location}"',
                f'site:jobstreet.co.id "{raw}" "{location}"',
                f'site:prosple.com "{raw}" "{location}"',
            ])
        for raw in unique_raw:
            queries.extend([
                f'{raw} intern "{location}"',
                f'{raw} internship "{location}"',
                f'magang {raw} "{location}"',
            ])
    else:
        for raw in unique_raw:
            queries.extend([
                f'"{raw}" "{location}"',
                f'{raw} intern "{location}"',
                f'{raw} internship "{location}"',
                f'magang {raw} "{location}"',
            ])

    deduped = []
    seen = set()
    for q in queries:
        if q not in seen:
            seen.add(q)
            deduped.append(q)
    return deduped
