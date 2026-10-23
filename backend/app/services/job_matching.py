import json
import re
from app.models.resume import Resume

ROLE_TERMS = {
    "it support": ["it support", "service desk", "help desk", "desktop support", "technical support", "system support"],
    "junior system administrator": ["system administrator", "systems administrator", "sysadmin", "windows server", "linux administrator", "administrator"],
    "junior devops": ["devops", "docker", "kubernetes", "ci/cd", "jenkins", "terraform", "cloud engineer"],
    "junior cybersecurity analyst": ["cybersecurity", "security analyst", "soc analyst", "siem", "threat detection", "network security"],
}

def _terms(text: str) -> set[str]:
    return {re.sub(r"\s+", " ", x.strip().casefold()) for x in re.split(r"[,;|\n]", text or "") if x.strip()}

def score_job(job: dict, resume: Resume | None, roles: list[str], keywords: list[str]) -> tuple[float, list[str]]:
    title = (job.get("title") or "").casefold()
    text = " ".join([title, job.get("description") or "", job.get("company") or "", job.get("location") or "", " ".join(job.get("tags") or [])]).casefold()
    reasons: list[str] = []
    score = 0.0
    role_hits = []
    for role in roles:
        key = role.casefold()
        candidates = ROLE_TERMS.get(key, [key])
        if any(term in title for term in candidates):
            role_hits.append(role)
    if role_hits:
        score += min(30, 18 + 4 * (len(role_hits) - 1))
        reasons.append("Zgodność z kierunkiem stanowiska: " + ", ".join(role_hits[:3]))
    elif roles:
        reasons.append("Tytuł nie wskazuje bezpośrednio wybranego stanowiska")

    resume_skills: list[str] = []
    if resume:
        try:
            profile = json.loads(resume.profile_json or "{}")
            resume_skills = profile.get("skills_detected", [])
        except (ValueError, AttributeError):
            pass
    skills = list(dict.fromkeys([str(s) for s in resume_skills + keywords if s]))
    matched = [skill for skill in skills if skill.casefold() in text]
    if skills:
        score += min(55, 55 * len(matched) / min(8, len(skills)))
        if matched:
            reasons.append("Wspólne słowa kluczowe: " + ", ".join(matched[:6]))
        else:
            reasons.append("Nie znaleziono wspólnych słów kluczowych z profilem")
    if job.get("remote"):
        score += 8
        reasons.append("Oferta zdalna")
    if job.get("location") and any(city in job["location"].casefold() for city in ["kraków", "krakow", "poland", "polska"]):
        score += 7
        reasons.append("Lokalizacja zgodna z Polską/Krakowem")
    return round(min(100.0, score), 1), reasons
