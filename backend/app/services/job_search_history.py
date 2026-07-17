import hashlib
import json

from app.models.user_profile import UserProfile


def _normalized_list(values: list[str]) -> list[str]:
    return sorted({" ".join(value.casefold().split()) for value in values if value.strip()})


def build_search_signature(
    profile: UserProfile,
    *,
    keyword: str,
    city: str,
    target_roles: list[str] | None,
    blocked_keywords: list[str],
) -> str:
    payload = {
        "keyword": " ".join(keyword.casefold().split()),
        "city": " ".join(city.casefold().split()),
        "target_roles": _normalized_list(target_roles or profile.target_roles),
        "salary_min": profile.salary_min,
        "salary_max": profile.salary_max,
        "degree": " ".join(profile.degree.casefold().split()),
        "experience_level": " ".join(profile.experience_level.casefold().split()),
        "company_sizes": _normalized_list(profile.company_sizes),
        "blocked_keywords": _normalized_list(blocked_keywords),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
