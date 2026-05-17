"""Role-aware query planning for fast research mode."""

from typing import Optional

from engine.extractor import normalize_target_category


ROLE_QUERY_TERMS = {
    "frontend": [
        "frontend developer intern",
        "front end developer intern",
        "frontend developer internship",
        "react developer intern",
        "next.js developer intern",
        "vue developer intern",
    ],
    "backend": [
        "backend developer intern",
        "back end developer intern",
        "backend developer internship",
        "golang backend intern",
        "node.js backend intern",
        "python backend intern",
    ],
    "fullstack": [
        "fullstack developer intern",
        "full stack developer intern",
        "fullstack developer internship",
        "web developer intern",
        "software developer intern",
    ],
    "software_engineering": [
        "software engineer intern",
        "software engineering intern",
        "software developer intern",
        "programmer intern",
        "it developer intern",
    ],
    "mobile": [
        "mobile developer intern",
        "mobile developer internship",
        "flutter developer intern",
        "android developer intern",
        "react native developer intern",
        "kotlin mobile intern",
    ],
    "data_analyst": [
        "data analyst intern",
        "data analyst internship",
        "business intelligence intern",
        "dashboard intern",
        "reporting intern",
    ],
    "ai_ml": [
        "machine learning intern",
        "ai engineer intern",
        "data scientist intern",
        "computer vision intern",
        "nlp intern",
    ],
    "actuarial": [
        "actuarial internship",
        "actuarial intern",
        "actuary internship",
        "actuary intern",
        "magang aktuaria",
        "pricing valuation internship",
        "reserving intern",
        "reinsurance internship",
        "insurance pricing intern",
        "IFRS 17 intern",
        "PSAK 117 intern",
    ],
}

CATEGORY_ROLES = {
    "tech": ["frontend", "backend", "fullstack", "software_engineering", "mobile"],
    "data": ["data_analyst", "ai_ml"],
    "actuarial": ["actuarial"],
}

SITE_TEMPLATES = [
    'site:dealls.com/loker "{term}" "{location}"',
    'site:glints.com/id/opportunities/jobs "{term}" "{location}"',
    'site:glints.com/id/en/opportunities/jobs "{term}" "{location}"',
    'site:kalibrr.id "{term}" "{location}"',
    'site:jobstreet.co.id/id "{term}" "{location}"',
    'site:prosple.com "{term}" "{location}"',
    'site:suitmedia.com/careers "{term}" "{location}"',
    'site:jobs.sea.deloitte.com "{term}" "{location}"',
]

PLATFORM_TEMPLATES = [
    'site:dealls.com/loker "{term}" "Lamar Cepat"',
    'site:glints.com/id/opportunities/jobs "{term}" "{location}"',
    'site:kalibrr.id "{term}" "internship"',
    'site:jobstreet.co.id/id "{term}" "internship"',
    'site:id.prosple.com "{term}" "{location}"',
    'site:suitmedia.com/careers "{term}" "intern"',
    'site:jobs.sea.deloitte.com "{term}" "internship"',
]


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    output = []
    for item in items:
        key = item.lower().strip()
        if key and key not in seen:
            seen.add(key)
            output.append(item)
    return output


def terms_for_target(target_category: Optional[str], query: Optional[str] = None) -> list[str]:
    """Generate role-aware terms from a target category/role and optional raw query."""
    terms = [query.strip()] if query and query.strip() else []
    target = normalize_target_category(target_category)
    if not target:
        return _dedupe(terms)

    role_keys = CATEGORY_ROLES.get(target, [target])
    for role_key in role_keys:
        terms.extend(ROLE_QUERY_TERMS.get(role_key, []))
    return _dedupe(terms)


def plan_research_queries(
    query: Optional[str] = None,
    location: str = "Indonesia",
    target_category: Optional[str] = None,
    query_count: int = 24,
) -> list[str]:
    """Build site-specific and general search queries for fast research."""
    terms = terms_for_target(target_category, query=query)
    if not terms and query:
        terms = [query]

    planned = []
    has_user_query = bool(query and query.strip())
    if has_user_query:
        planned.append(f'"{query.strip()}" "{location}"')

        # Fast profiles only run a small number of queries, so first spread
        # role-aware terms across platforms instead of spending all slots on
        # one broad user query.
        role_terms = terms[1:8] if len(terms) > 1 else terms
        for idx, template in enumerate(PLATFORM_TEMPLATES):
            term = role_terms[idx % len(role_terms)]
            planned.append(template.format(term=term, location=location))

        for term in role_terms[:3]:
            for template in SITE_TEMPLATES[:4]:
                planned.append(template.format(term=term, location=location))

    for term in terms:
        planned.append(f'"{term}" "{location}"')

    site_terms = terms[4:] if has_user_query else terms[:4]
    for term in site_terms:
        for template in SITE_TEMPLATES:
            planned.append(template.format(term=term, location=location))
    for term in terms:
        planned.extend([
            f'{term} internship "{location}"',
            f'{term} intern "{location}"',
            f'magang {term} "{location}"',
        ])

    return _dedupe(planned)[:query_count]
