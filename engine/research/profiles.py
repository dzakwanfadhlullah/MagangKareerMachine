"""Research mode profile presets."""

RESEARCH_PROFILES = {
    "fast": {
        "query_count": 12,
        "max_fetch": 20,
        "workers": 8,
        "timeout": 8,
        "results_per_query": 8,
    },
    "normal": {
        "query_count": 24,
        "max_fetch": 40,
        "workers": 8,
        "timeout": 10,
        "results_per_query": 10,
    },
    "deep": {
        "query_count": 50,
        "max_fetch": 100,
        "workers": 10,
        "timeout": 12,
        "results_per_query": 12,
    },
}


def get_research_profile(profile: str) -> dict:
    """Return a named research profile."""
    if profile not in RESEARCH_PROFILES:
        available = ", ".join(sorted(RESEARCH_PROFILES))
        raise ValueError(f"Unknown research profile '{profile}'. Available: {available}")
    return dict(RESEARCH_PROFILES[profile])
