"""Explainable job analysis and application-material drafting.

The deterministic mode is the default. An OpenAI-compatible chat-completions
endpoint can be enabled with LLM_API_KEY, LLM_BASE_URL and LLM_MODEL.
Generated text is always a draft and must be verified by the candidate.
"""
import json
import re
from typing import Any

import httpx
from app.core.config import settings
from app.models.job import Job
from app.models.resume import Resume

SKILL_TERMS = [
    "Python", "Java", "JavaScript", "TypeScript", "PHP", "SQL", "MySQL",
    "PostgreSQL", "Windows", "Linux", "Docker", "Kubernetes", "Git",
    "CI/CD", "Jenkins", "GitHub Actions", "FastAPI", "React", "AWS",
    "Azure", "TCP/IP", "DNS", "DHCP", "Active Directory", "Bash",
    "PowerShell", "LAMP", "Nmap", "CCNA", "IT Support", "troubleshooting",
    "networking", "monitoring", "backup", "virtualization", "communication",
    "ticketing", "Service Desk", "Linux administration", "Windows Server",
]


def _contains(text: str, term: str) -> bool:
    return term.casefold() in text.casefold()


def analyze_job(job: Job, resume: Resume) -> dict[str, Any]:
    cv_text = resume.extracted_text or ""
    description = f"{job.title}\n{job.description}\n{' '.join(json.loads(job.tags_json or '[]'))}"
    detected = json.loads(resume.profile_json or "{}").get("skills_detected", [])
    # Detect skills from the actual CV text and include the parser's known list.
    cv_skills = sorted({s for s in SKILL_TERMS if _contains(cv_text, s)} | set(detected), key=str.casefold)
    required = sorted({s for s in SKILL_TERMS if _contains(description, s)}, key=str.casefold)
    matched = [s for s in required if any(s.casefold() == c.casefold() for c in cv_skills)]
    missing = [s for s in required if s not in matched]
    cv_lower = cv_text.casefold()
    evidence = []
    for skill in matched:
        snippets = [line.strip(" •\t-") for line in cv_text.splitlines() if skill.casefold() in line.casefold()]
        evidence.append({"skill": skill, "evidence": snippets[:2] or ["Słowo kluczowe wykryte w tekście CV."]})
    recommendations = []
    if missing:
        recommendations.append("Zweryfikuj wymagania: " + ", ".join(missing[:8]) + ". Nie dodawaj ich do CV, jeśli nie masz rzeczywistego doświadczenia.")
    if not required:
        recommendations.append("Opis nie zawiera słów kluczowych z listy kontrolnej. Przejrzyj wymagania ręcznie.")
    if len(cv_text.strip()) < 300:
        recommendations.append("CV zawiera mało odczytanego tekstu; sprawdź ekstrakcję i uzupełnij opis doświadczenia.")
    if matched:
        recommendations.append("W CV są potencjalne dowody dla: " + ", ".join(matched[:8]) + ". Podkreśl je tylko wtedy, gdy odpowiadają rzeczywistym zadaniom.")
    score = round(100 * len(matched) / len(required)) if required else 0
    return {
        "job_id": job.id, "resume_id": resume.id, "job_title": job.title,
        "company": job.company, "score": score, "required_skills": required,
        "matched_skills": matched, "missing_skills": missing,
        "evidence": evidence, "recommendations": recommendations,
        "method": "rule_based", "disclaimer": "Analiza słów kluczowych nie ocenia poziomu biegłości i może pomijać synonimy. Sprawdź wnioski ręcznie.",
    }


def _cover_letter(job: Job, resume: Resume, language: str, analysis: dict[str, Any], applicant_name: str) -> str:
    skills = analysis["matched_skills"][:5]
    title = job.title or "to stanowisko"
    company = job.company or "Państwa firma"
    cv = resume.extracted_text or ""
    # Reuse only a few existing CV lines as factual anchors; never invent achievements.
    lines = [line.strip(" •\t-") for line in cv.splitlines() if line.strip()]
    evidence_lines = [line for line in lines if any(s.casefold() in line.casefold() for s in skills)][:2]
    if language == "en":
        paragraphs = [
            f"Dear Hiring Team at {company},",
            f"I am writing to express my interest in the {title} position. I would welcome the opportunity to discuss how my background and practical learning could support your team.",
        ]
        if skills:
            paragraphs.append("The CV I provided contains references to " + ", ".join(skills) + ". I would be happy to explain the context and extent of this experience during an interview.")
        if evidence_lines:
            paragraphs.append("Relevant CV details to discuss:\n" + "\n".join(f"- {line[:220]}" for line in evidence_lines))
        paragraphs.extend(["Thank you for considering my application. I would appreciate the opportunity to discuss the role and your team's needs.", "Kind regards,\n" + (applicant_name.strip() or "[Your name]")])
    else:
        paragraphs = [
            f"Szanowni Państwo,",
            f"z zainteresowaniem aplikuję na stanowisko {title} w firmie {company}. Chętnie porozmawiam o tym, w jaki sposób moje dotychczasowe doświadczenie i rozwijane umiejętności mogą wesprzeć Państwa zespół.",
        ]
        if skills:
            paragraphs.append("W przekazanym CV znajdują się odniesienia do: " + ", ".join(skills) + ". Podczas rozmowy chętnie wyjaśnię zakres i kontekst tych umiejętności.")
        if evidence_lines:
            paragraphs.append("Fragmenty CV, które warto omówić:\n" + "\n".join(f"- {line[:220]}" for line in evidence_lines))
        paragraphs.extend(["Dziękuję za rozpatrzenie mojej kandydatury. Będę wdzięczny za możliwość rozmowy o stanowisku i potrzebach zespołu.", "Z poważaniem,\n" + (applicant_name.strip() or "[Imię i nazwisko]")])
    return "\n\n".join(paragraphs)


def _tailoring_suggestions(job: Job, resume: Resume, analysis: dict[str, Any], language: str) -> dict[str, Any]:
    skills = analysis["matched_skills"]
    missing = analysis["missing_skills"]
    cv_lines = [line.strip(" •\t-") for line in (resume.extracted_text or "").splitlines() if line.strip()]
    relevant_lines = [line for line in cv_lines if any(s.casefold() in line.casefold() for s in skills)][:5]
    if language == "en":
        summary = f"IT professional interested in the {job.title} role, with CV references to {', '.join(skills[:5]) or 'relevant technical skills'}. Adapt this summary only after confirming it accurately reflects your experience."
        actions = [f"Review and prioritise existing CV evidence for {s}." for s in skills[:6]]
        actions += [f"If you have real experience with {s}, add a concrete example; otherwise treat it as a learning gap." for s in missing[:6]]
    else:
        summary = f"Specjalista IT zainteresowany stanowiskiem {job.title}, z odniesieniami w CV do: {', '.join(skills[:5]) or 'umiejętności technicznych'}. Użyj tego podsumowania dopiero po sprawdzeniu, czy wiernie opisuje Twoje doświadczenie."
        actions = [f"Wyeksponuj istniejący w CV przykład dotyczący: {s}." for s in skills[:6]]
        actions += [f"Jeśli masz rzeczywiste doświadczenie z {s}, dodaj konkretny przykład; w przeciwnym razie potraktuj to jako lukę do nauki." for s in missing[:6]]
    return {"summary_draft": summary, "suggested_cv_lines": relevant_lines, "actions": actions, "do_not_claim": missing}


async def generate_materials(job: Job, resume: Resume, language: str, applicant_name: str) -> dict[str, Any]:
    analysis = analyze_job(job, resume)
    materials = {
        "tailoring": _tailoring_suggestions(job, resume, analysis, language),
        "cover_letter": _cover_letter(job, resume, language, analysis, applicant_name),
        "method": "template_fallback",
    }
    # Optional OpenAI-compatible integration. If not configured or unavailable,
    # deterministic materials remain available and no data is sent externally.
    if settings.llm_api_key and settings.llm_base_url:
        prompt = {
            "task": "Improve the draft materials using only facts explicitly present in the CV. Do not invent experience, qualifications, employers, achievements, metrics, or skills. Keep missing skills as gaps. Return JSON with keys summary_draft, actions, cover_letter.",
            "language": language, "job": {"title": job.title, "company": job.company, "description": (job.description or "")[:9000]},
            "cv_text": (resume.extracted_text or "")[:12000], "analysis": analysis,
            "fallback": materials,
        }
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                response = await client.post(
                    settings.llm_base_url.rstrip("/") + "/chat/completions",
                    headers={"Authorization": f"Bearer {settings.llm_api_key}", "Content-Type": "application/json"},
                    json={"model": settings.llm_model, "temperature": 0.2, "messages": [
                        {"role": "system", "content": "You are a careful career assistant. Never fabricate candidate facts. Output only valid JSON."},
                        {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                    ]},
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                parsed = json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.I))
                if isinstance(parsed.get("summary_draft"), str) and isinstance(parsed.get("cover_letter"), str):
                    materials["tailoring"]["summary_draft"] = parsed["summary_draft"][:3000]
                    materials["tailoring"]["actions"] = [str(x)[:500] for x in parsed.get("actions", materials["tailoring"]["actions"])[:15]]
                    materials["cover_letter"] = parsed["cover_letter"][:12000]
                    materials["method"] = "llm"
        except Exception:
            materials["llm_note"] = "Model AI jest niedostępny lub zwrócił nieprawidłowy format; użyto wersji szablonowej."
    return materials
