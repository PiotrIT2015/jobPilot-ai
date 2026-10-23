"""Small public job-board adapters. Source terms and links are retained for transparency."""
import html
import re
from typing import Any
import httpx

TIMEOUT = httpx.Timeout(15.0, connect=5.0)
USER_AGENT = "JobPilotAI/0.3 (personal job-search prototype)"


def _plain(value: Any, limit: int = 12000) -> str:
    text = str(value or "")
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()[:limit]

async def fetch_arbeitnow(query: str = "", location: str = "", remote_only: bool = False, limit: int = 60) -> list[dict]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    items: list[dict] = []
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers, follow_redirects=True) as client:
        # API is paginated; fetch at most three pages per sync.
        for page in range(1, 4):
            response = await client.get("https://www.arbeitnow.com/api/job-board-api", params={"page": page})
            response.raise_for_status()
            payload = response.json()
            rows = payload.get("data", []) if isinstance(payload, dict) else []
            if not rows:
                break
            for row in rows:
                title = _plain(row.get("title"), 500)
                company = _plain(row.get("company_name"), 255) or "Unknown"
                loc = _plain(row.get("location"), 255)
                tags = row.get("tags") if isinstance(row.get("tags"), list) else []
                desc = _plain(row.get("description"))
                remote = bool(row.get("remote")) or "remote" in (loc + " " + title).lower()
                haystack = f"{title} {company} {loc} {' '.join(map(str, tags))} {desc}".casefold()
                if query and not any(term.casefold() in haystack for term in query.split() if len(term) > 2):
                    continue
                if location and location.casefold() not in loc.casefold() and not remote:
                    continue
                if remote_only and not remote:
                    continue
                items.append({"source":"arbeitnow", "source_job_id":str(row.get("slug") or row.get("url") or f"{company}:{title}"), "title":title, "company":company, "location":loc, "remote":remote, "job_type":_plain(row.get("job_types") or "",100), "description":desc, "url":str(row.get("url") or ""), "tags":[_plain(t,100) for t in tags], "published_at":str(row.get("created_at") or "")})
                if len(items) >= limit:
                    return items
    return items

async def fetch_remotive(query: str = "", location: str = "", remote_only: bool = False, limit: int = 60) -> list[dict]:
    # Remotive is a remote-only source. API recommends not polling more frequently than every 5 minutes.
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    params: dict[str, Any] = {"limit": min(limit, 100)}
    if query:
        params["search"] = query[:100]
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers, follow_redirects=True) as client:
        response = await client.get("https://remotive.com/api/remote-jobs", params=params)
        response.raise_for_status()
        payload = response.json()
    rows = payload.get("jobs", []) if isinstance(payload, dict) else []
    results = []
    for row in rows:
        title = _plain(row.get("title"), 500)
        company = _plain(row.get("company_name"), 255) or "Unknown"
        loc = _plain(row.get("candidate_required_location") or "Remote", 255)
        tags = row.get("tags") if isinstance(row.get("tags"), list) else []
        desc = _plain(row.get("description"))
        if location and location.casefold() not in loc.casefold() and "worldwide" not in loc.casefold() and "anywhere" not in loc.casefold() and "europe" not in loc.casefold():
            # Remote role may still be available from Poland; keep broad remote listings unless the location is restrictive.
            if any(word in loc.casefold() for word in ["united states", "usa", "canada", "india", "australia"]):
                continue
        results.append({"source":"remotive", "source_job_id":str(row.get("id")), "title":title, "company":company, "location":loc, "remote":True, "job_type":_plain(row.get("job_type") or "",100), "description":desc, "url":str(row.get("url") or ""), "tags":[_plain(t,100) for t in tags], "published_at":str(row.get("publication_date") or "")})
        if len(results) >= limit:
            break
    return results

async def fetch_jobs(source: str, query: str = "", location: str = "", remote_only: bool = False, limit: int = 60) -> list[dict]:
    if source == "arbeitnow":
        return await fetch_arbeitnow(query, location, remote_only, limit)
    if source == "remotive":
        return await fetch_remotive(query, location, remote_only, limit)
    if source == "all":
        # Keep source calls independent so one upstream outage does not hide the other source.
        results = []
        errors = []
        for name in ("arbeitnow", "remotive"):
            try:
                results.extend(await fetch_jobs(name, query, location, remote_only, limit))
            except Exception as exc:
                errors.append(f"{name}: {type(exc).__name__}")
        if not results and errors:
            raise RuntimeError("Nie udało się pobrać ofert z żadnego źródła (" + ", ".join(errors) + ").")
        return results
    raise ValueError("Nieznane źródło. Dozwolone: all, arbeitnow, remotive.")
