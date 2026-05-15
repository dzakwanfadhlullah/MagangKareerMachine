"""Query Builder — ekspansi keyword menjadi search queries."""

from pathlib import Path
from typing import Optional

import yaml


CONFIG_PATH = Path("config/keywords.yml")


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


def build_queries_from_raw(query: str, location: str) -> list[str]:
    """
    Build queries dari raw query string tanpa ekspansi role.
    Untuk query yang sudah spesifik dari user.
    """
    queries = [
        f'"{query}" "{location}"',
        f'{query} intern "{location}"',
        f'{query} internship "{location}"',
        f'magang {query} "{location}"',
    ]
    return queries
