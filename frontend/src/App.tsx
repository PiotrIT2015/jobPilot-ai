import { ChangeEvent, useCallback, useEffect, useState } from 'react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
type ApiStatus = 'checking' | 'ok' | 'error'
type CandidateProfile = { skills_detected?: string[]; education_hints?: string[]; experience_hints?: string[]; character_count?: number; note?: string }
type Resume = { id: number; filename: string; file_type: string; file_size: number; created_at: string; profile: CandidateProfile }
type ResumeDetail = Resume & { extracted_text: string }
type Preferences = { roles: string[]; location: string; remote_only: boolean; keywords: string[]; preferred_resume_id: number | null }
type Job = { id: number; source: string; title: string; company: string; location: string; remote: boolean; job_type: string; description: string; url: string; tags: string[]; published_at: string; match_score: number; match_reasons: string[]; application_status: string }
type JobAnalysis = { score: number; required_skills: string[]; matched_skills: string[]; missing_skills: string[]; evidence: { skill: string; evidence: string[] }[]; recommendations: string[]; disclaimer: string }
type ApplicationMaterials = { job_id: number; resume_id: number; job_title: string; company: string; method: string; tailoring: { summary_draft: string; suggested_cv_lines: string[]; actions: string[]; do_not_claim: string[] }; cover_letter: string; disclaimer: string; llm_note?: string }
const STATUS_LABELS: Record<string, string> = { saved: 'Zapisana', applied: 'Aplikowano', interview: 'Rozmowa', rejected: 'Odrzucona', offer: 'Oferta', archived: 'Archiwum' }

export default function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>('checking')
  const [dbStatus, setDbStatus] = useState<ApiStatus>('checking')
  const [resumes, setResumes] = useState<Resume[]>([])
  const [selected, setSelected] = useState<ResumeDetail | null>(null)
  const [jobs, setJobs] = useState<Job[]>([])
  const [prefs, setPrefs] = useState<Preferences>({ roles: ['IT Support', 'Junior System Administrator', 'Junior DevOps'], location: 'Kraków, Poland', remote_only: false, keywords: [], preferred_resume_id: null })
  const [roleText, setRoleText] = useState('IT Support, Junior System Administrator, Junior DevOps')
  const [keywordText, setKeywordText] = useState('')
  const [jobQuery, setJobQuery] = useState('')
  const [source, setSource] = useState('all')
  const [filterStatus, setFilterStatus] = useState('')
  const [busy, setBusy] = useState(false)
  const [syncBusy, setSyncBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [analysisByJob, setAnalysisByJob] = useState<Record<number, JobAnalysis>>({})
  const [materialsByJob, setMaterialsByJob] = useState<Record<number, ApplicationMaterials>>({})
  const [materialBusyId, setMaterialBusyId] = useState<number | null>(null)
  const [materialLanguage, setMaterialLanguage] = useState<'pl' | 'en'>('pl')
  const [applicantName, setApplicantName] = useState('')

  const request = async (path: string, init?: RequestInit) => {
    const response = await fetch(`${API_BASE_URL}${path}`, init)
    const result = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(result.detail ?? 'Żądanie nie powiodło się.')
    return result
  }
  const loadResumes = useCallback(async () => { try { const rows = await request('/api/resumes'); setResumes(rows) } catch { /* API status card reports connection issues */ } }, [])
  const loadJobs = useCallback(async () => {
    try {
      const params = new URLSearchParams({ limit: '150' })
      if (filterStatus) params.set('status', filterStatus)
      if (jobQuery.trim()) params.set('q', jobQuery.trim())
      const rows = await request(`/api/jobs?${params}`)
      setJobs(rows)
    } catch { /* surfaced by the user-triggered sync and connection status */ }
  }, [filterStatus, jobQuery])
  const loadPreferences = useCallback(async () => {
    try { const value = await request('/api/jobs/preferences'); setPrefs(value); setRoleText(value.roles.join(', ')); setKeywordText(value.keywords.join(', ')) } catch { /* API may be starting */ }
  }, [])
  useEffect(() => {
    request('/api/health').then(() => setApiStatus('ok')).catch(() => setApiStatus('error'))
    request('/api/health/db').then(() => setDbStatus('ok')).catch(() => setDbStatus('error'))
    void loadResumes(); void loadPreferences()
  }, [loadResumes, loadPreferences])
  useEffect(() => { void loadJobs() }, [loadJobs])

  const uploadResume = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]; event.target.value = ''; if (!file) return
    setMessage(''); setError(''); setSelected(null); setBusy(true)
    const form = new FormData(); form.append('file', file)
    try {
      const result = await request('/api/resumes', { method: 'POST', body: form })
      setMessage(`Dodano CV: ${result.filename}. Wyodrębniono ${result.profile.character_count} znaków tekstu.`)
      await loadResumes(); setSelected({ ...result, extracted_text: '' })
      if (!prefs.preferred_resume_id) { setPrefs((old) => ({ ...old, preferred_resume_id: result.id })) }
    } catch (err) { setError(err instanceof Error ? err.message : 'Wystąpił nieznany błąd.') } finally { setBusy(false) }
  }
  const showResume = async (id: number) => {
    setError(''); setMessage('')
    try { setSelected(await request(`/api/resumes/${id}`)) } catch (err) { setError(err instanceof Error ? err.message : 'Nie udało się pobrać CV.') }
  }
  const savePreferences = async () => {
    setBusy(true); setError(''); setMessage('')
    try {
      const value = await request('/api/jobs/preferences', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...prefs, roles: roleText.split(',').map((x) => x.trim()).filter(Boolean), keywords: keywordText.split(',').map((x) => x.trim()).filter(Boolean) }) })
      setPrefs(value); setRoleText(value.roles.join(', ')); setKeywordText(value.keywords.join(', ')); setMessage('Zapisano preferencje. Dopasowanie ofert zostało przeliczone.'); await loadJobs()
    } catch (err) { setError(err instanceof Error ? err.message : 'Nie udało się zapisać preferencji.') } finally { setBusy(false) }
  }
  const syncJobs = async () => {
    setSyncBusy(true); setError(''); setMessage('')
    try {
      const result = await request('/api/jobs/sync', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ source, query: jobQuery, location: prefs.location, remote_only: prefs.remote_only, limit: 60 }) })
      setMessage(`Synchronizacja zakończona: pobrano ${result.received}, dodano ${result.inserted}, zaktualizowano ${result.updated}. Oferty zapisano w MySQL.`)
      await loadJobs()
    } catch (err) { setError(err instanceof Error ? err.message : 'Nie udało się pobrać ofert.') } finally { setSyncBusy(false) }
  }
  const updateStatus = async (job: Job, status: string) => {
    try { await request(`/api/jobs/${job.id}/status`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status }) }); setMessage(`Zmieniono status oferty „${job.title}”.`); await loadJobs() }
    catch (err) { setError(err instanceof Error ? err.message : 'Nie udało się zmienić statusu.') }
  }
  const prepareMaterials = async (job: Job) => {
    setError(''); setMessage(''); setMaterialBusyId(job.id)
    try {
      const resumeParam = prefs.preferred_resume_id ? `?resume_id=${prefs.preferred_resume_id}` : ''
      const analysis = await request(`/api/analysis/jobs/${job.id}${resumeParam}`) as JobAnalysis
      setAnalysisByJob((old) => ({ ...old, [job.id]: analysis }))
      const materials = await request(`/api/analysis/jobs/${job.id}/materials`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ resume_id: prefs.preferred_resume_id, language: materialLanguage, applicant_name: applicantName }) }) as ApplicationMaterials
      setMaterialsByJob((old) => ({ ...old, [job.id]: materials }))
      setMessage(`Przygotowano analizę i szkice materiałów dla: ${job.title}. Sprawdź je przed użyciem.`)
    } catch (err) { setError(err instanceof Error ? err.message : 'Nie udało się przygotować materiałów.') } finally { setMaterialBusyId(null) }
  }
  const saveMaterials = async (jobId: number) => {
    const draft = materialsByJob[jobId]
    if (!draft) return
    try {
      const result = await request(`/api/analysis/jobs/${jobId}/materials/save`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ resume_id: draft.resume_id, language: materialLanguage, summary_draft: draft.tailoring.summary_draft, actions: draft.tailoring.actions, cover_letter: draft.cover_letter }) })
      setMessage(result.message ?? 'Zapisano szkic materiałów aplikacyjnych.')
    } catch (err) { setError(err instanceof Error ? err.message : 'Nie udało się zapisać szkicu.') }
  }
  const statusLabel = (status: ApiStatus) => ({ checking: 'Sprawdzanie…', ok: 'Połączono', error: 'Brak połączenia' })[status]
  const formatSize = (size: number) => size < 1024 * 1024 ? `${Math.max(1, Math.round(size / 1024))} KB` : `${(size / (1024 * 1024)).toFixed(1)} MB`

  return <div className="app-shell">
    <aside className="sidebar"><div className="brand-mark">JP</div><div className="brand-copy"><strong>JobPilot AI</strong><span>Job search workspace</span></div>
      <nav aria-label="Menu główne"><a className="nav-item active" href="#dashboard">▦ <span>Dashboard</span></a><a className="nav-item" href="#cv">▤ <span>Moje CV</span></a><a className="nav-item" href="#jobs">⌕ <span>Oferty pracy</span></a><a className="nav-item" href="#applications">✓ <span>Aplikacje</span></a><a className="nav-item" href="#settings">⚙ <span>Preferencje</span></a></nav>
      <div className="sidebar-footer">Etap 4 · Asystent aplikowania</div></aside>
    <main className="main-content" id="dashboard"><header className="topbar"><div><p className="eyebrow">WORKSPACE / JOB MATCHING</p><h1>Panel główny</h1></div><div className="avatar" aria-label="Profil użytkownika">U</div></header>
      <section className="welcome-card"><div><span className="pill">WERSJA 0.4.0</span><h2>Znajdź oferty.<br/>Sprawdź dopasowanie.</h2><p>JobPilot zbiera oferty, porównuje je z CV, wskazuje możliwe luki kompetencyjne i przygotowuje szkice materiałów aplikacyjnych do Twojej weryfikacji.</p><a className="primary-button" href="#jobs">Przejdź do ofert <span>↗</span></a></div><div className="welcome-art" aria-hidden="true"><div className="orbit orbit-one"></div><div className="orbit orbit-two"></div><div className="orbit-core">✦</div></div></section>
      <section className="section-heading"><div><h2>Status środowiska</h2><p>Kontrola połączenia z podstawowymi usługami.</p></div></section>
      <section className="status-grid"><article className="status-card"><div className="card-icon purple">⌘</div><div className="card-label">Backend API</div><div className={`status-value ${apiStatus}`}>{statusLabel(apiStatus)}</div><p>FastAPI · {API_BASE_URL}</p></article><article className="status-card"><div className="card-icon green">▤</div><div className="card-label">Baza danych</div><div className={`status-value ${dbStatus}`}>{statusLabel(dbStatus)}</div><p>MySQL · SQLAlchemy</p></article><article className="status-card"><div className="card-icon orange">⌕</div><div className="card-label">Zapisane oferty</div><div className="status-value">{jobs.length}</div><p>Arbeitnow + Remotive · ranking 0–100</p></article></section>
      {message && <div className="notice success" role="status">{message}</div>}{error && <div className="notice error-notice" role="alert">{error}</div>}
      <section className="section-heading next-heading" id="settings"><div><h2>Preferencje wyszukiwania</h2><p>Wybierz kierunki, lokalizację i słowa kluczowe.</p></div></section>
      <section className="preferences-panel"><label>Stanowiska (oddziel przecinkami)<input value={roleText} onChange={(e) => setRoleText(e.target.value)} placeholder="IT Support, Junior DevOps" /></label><div className="preferences-grid"><label>Lokalizacja<input value={prefs.location} onChange={(e) => setPrefs({ ...prefs, location: e.target.value })} placeholder="Kraków, Poland" /></label><label>Słowa kluczowe (oddziel przecinkami)<input value={keywordText} onChange={(e) => setKeywordText(e.target.value)} placeholder="Linux, Docker, Windows, networking" /></label></div><div className="preference-actions"><label className="check-label"><input type="checkbox" checked={prefs.remote_only} onChange={(e) => setPrefs({ ...prefs, remote_only: e.target.checked })} /> Tylko praca zdalna</label><label>CV do dopasowania<select value={prefs.preferred_resume_id ?? ''} onChange={(e) => setPrefs({ ...prefs, preferred_resume_id: e.target.value ? Number(e.target.value) : null })}><option value="">Najnowsze CV</option>{resumes.map((r) => <option key={r.id} value={r.id}>{r.filename}</option>)}</select></label><button className="primary-button compact" onClick={() => void savePreferences()} disabled={busy}>{busy ? 'Zapisywanie…' : 'Zapisz preferencje'}</button></div></section>
      <section className="section-heading" id="jobs"><div><h2>Oferty pracy</h2><p>Sortowane według wstępnego wyniku dopasowania. Kliknij źródło, aby przejść do oryginalnego ogłoszenia.</p></div><button className="primary-button compact" onClick={() => void syncJobs()} disabled={syncBusy}>{syncBusy ? 'Pobieranie…' : '↻ Pobierz nowe oferty'}</button></section>
      <section className="job-filters"><label>Język materiałów<select value={materialLanguage} onChange={(e) => setMaterialLanguage(e.target.value as 'pl' | 'en')}><option value="pl">Polski</option><option value="en">English</option></select></label><label>Imię i nazwisko do podpisu<input value={applicantName} onChange={(e) => setApplicantName(e.target.value)} placeholder="Opcjonalnie" /></label><label>Szukaj<input value={jobQuery} onChange={(e) => setJobQuery(e.target.value)} placeholder="np. Linux, support, DevOps" /></label><label>Źródło<select value={source} onChange={(e) => setSource(e.target.value)}><option value="all">Wszystkie źródła</option><option value="arbeitnow">Arbeitnow</option><option value="remotive">Remotive (zdalne)</option></select></label><label>Status aplikacji<select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}><option value="">Wszystkie statusy</option>{Object.entries(STATUS_LABELS).map(([key, value]) => <option key={key} value={key}>{value}</option>)}</select></label></section>
      <section className="jobs-list">{jobs.length === 0 ? <div className="empty-state"><div className="empty-icon">⌕</div><strong>Brak zapisanych ofert</strong><p>Kliknij „Pobierz nowe oferty”, aby pobrać ogłoszenia z publicznych źródeł i zapisać je w bazie.</p></div> : jobs.map((job) => <article className="job-card" key={job.id}><div className="job-card-top"><div className="job-heading"><h3>{job.title}</h3><p>{job.company} · {job.location || 'Lokalizacja niepodana'}{job.remote ? ' · Zdalnie' : ''}</p></div><div className="match-score"><strong>{Math.round(job.match_score)}%</strong><span>Dopasowanie</span></div></div><div className="job-meta"><span>{job.source}</span>{job.job_type && <span>{job.job_type}</span>}{job.published_at && <span>Data: {job.published_at.slice(0, 10)}</span>}<span className="job-status">{STATUS_LABELS[job.application_status] ?? job.application_status}</span></div><div className="match-reasons"><strong>Dlaczego ten wynik?</strong>{job.match_reasons.length ? <ul>{job.match_reasons.map((reason, i) => <li key={i}>{reason}</li>)}</ul> : <p>Brak szczegółów dopasowania.</p>}</div><div className="job-card-bottom"><a className="source-link" href={job.url} target="_blank" rel="noreferrer">Otwórz oryginalną ofertę ↗</a><label className="status-select-label">Status aplikacji<select value={job.application_status} onChange={(e) => void updateStatus(job, e.target.value)}>{Object.entries(STATUS_LABELS).map(([key, value]) => <option key={key} value={key}>{value}</option>)}</select></label><button className="primary-button compact" onClick={() => void prepareMaterials(job)} disabled={materialBusyId !== null}>{materialBusyId === job.id ? 'Analizuję…' : 'Analizuj i przygotuj materiały'}</button></div>{analysisByJob[job.id] && <div className="stage4-panel"><h4>Analiza wymagań · {analysisByJob[job.id].score}% zgodności słów kluczowych</h4><p><strong>Wykryte w obu źródłach:</strong> {analysisByJob[job.id].matched_skills.join(', ') || 'Brak wykrytych wspólnych słów kluczowych.'}</p><p><strong>Wymagania do zweryfikowania:</strong> {analysisByJob[job.id].missing_skills.join(', ') || 'Nie wykryto braków na liście kontrolnej.'}</p><ul>{analysisByJob[job.id].recommendations.map((item, i) => <li key={i}>{item}</li>)}</ul><small>{analysisByJob[job.id].disclaimer}</small></div>}{materialsByJob[job.id] && <div className="stage4-panel"><h4>Szkic materiałów aplikacyjnych</h4><p><strong>Podsumowanie CV — wersja robocza</strong></p><p>{materialsByJob[job.id].tailoring.summary_draft}</p>{materialsByJob[job.id].tailoring.actions.length > 0 && <><p><strong>Proponowane poprawki</strong></p><ul>{materialsByJob[job.id].tailoring.actions.map((item, i) => <li key={i}>{item}</li>)}</ul></>}<label className="cover-letter-label">List motywacyjny — edytowalny szkic<textarea rows={12} value={materialsByJob[job.id].cover_letter} onChange={(e) => setMaterialsByJob((old) => ({ ...old, [job.id]: { ...old[job.id], cover_letter: e.target.value } }))} /></label><div className="draft-actions"><button className="secondary-button" onClick={() => void saveMaterials(job.id)}>Zapisz szkic w MySQL</button><button className="secondary-button" onClick={() => { void navigator.clipboard?.writeText(materialsByJob[job.id].cover_letter); setMessage('Skopiowano szkic listu motywacyjnego (jeśli przeglądarka zezwoliła na dostęp do schowka).') }}>Kopiuj list motywacyjny</button></div>{materialsByJob[job.id].llm_note && <p>{materialsByJob[job.id].llm_note}</p>}<p className="analysis-note">{materialsByJob[job.id].disclaimer} Metoda: {materialsByJob[job.id].method === 'llm' ? 'model językowy' : 'szablon lokalny'}.</p></div>}</article>)}</section>
      <section className="section-heading next-heading" id="cv"><div><h2>Moje CV</h2><p>Obsługiwane formaty: PDF i DOCX. Maksymalny rozmiar: 5 MB.</p></div><label className={`primary-button upload-button ${busy ? 'is-busy' : ''}`}>{busy ? 'Przetwarzanie…' : '+ Prześlij CV'}<input type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={uploadResume} disabled={busy}/></label></section>
      <section className="resume-layout"><div className="resume-list">{resumes.length === 0 ? <div className="empty-state"><div className="empty-icon">▤</div><strong>Nie dodano jeszcze CV</strong><p>Prześlij plik PDF lub DOCX, aby rozpocząć budowanie profilu kandydata.</p></div> : resumes.map((resume) => <button className={`resume-row ${selected?.id === resume.id ? 'selected' : ''}`} key={resume.id} onClick={() => void showResume(resume.id)}><span className="file-icon">{resume.file_type.toUpperCase()}</span><span className="resume-meta"><strong>{resume.filename}</strong><small>{formatSize(resume.file_size)} · {new Date(resume.created_at).toLocaleDateString('pl-PL')}</small></span><span className="row-arrow">›</span></button>)}</div>
        <div className="profile-panel">{selected ? <><div className="profile-title"><div><p className="eyebrow">CANDIDATE PROFILE</p><h3>{selected.filename}</h3></div><span className="profile-badge">Wstępna analiza</span></div><div className="profile-section"><h4>Wykryte umiejętności</h4>{selected.profile?.skills_detected?.length ? <div className="skill-list">{selected.profile.skills_detected.map((skill) => <span className="skill-chip" key={skill}>{skill}</span>)}</div> : <p className="muted">Nie wykryto słów kluczowych z listy bazowej.</p>}</div><div className="profile-section"><h4>Wskazówki dotyczące edukacji</h4>{selected.profile?.education_hints?.length ? <ul>{selected.profile.education_hints.map((line, i) => <li key={i}>{line}</li>)}</ul> : <p className="muted">Brak oczywistych nagłówków edukacji.</p>}</div><div className="profile-section"><h4>Wskazówki dotyczące doświadczenia</h4>{selected.profile?.experience_hints?.length ? <ul>{selected.profile.experience_hints.map((line, i) => <li key={i}>{line}</li>)}</ul> : <p className="muted">Brak oczywistych nagłówków doświadczenia.</p>}</div>{selected.extracted_text && <details className="text-preview"><summary>Podgląd odczytanego tekstu</summary><pre>{selected.extracted_text}</pre></details>}<p className="analysis-note">{selected.profile?.note ?? 'Wstępna ekstrakcja. Zweryfikuj poprawność wykrytych danych.'}</p></> : <div className="empty-profile"><div className="profile-orb">✧</div><strong>Profil kandydata</strong><p>Wybierz CV z listy, aby zobaczyć wykryte umiejętności.</p></div>}</div></section>
      <section className="roadmap"><div className="roadmap-item complete"><span className="step-number">✓</span><div><strong>Etap 1 · Fundament</strong><p>React, FastAPI, MySQL i kontrola połączeń.</p></div><span className="step-tag done">Gotowe</span></div><div className="roadmap-item complete"><span className="step-number">✓</span><div><strong>Etap 2 · Profil kandydata</strong><p>Upload CV, ekstrakcja tekstu i podstawowe słowa kluczowe.</p></div><span className="step-tag done">Gotowe</span></div><div className="roadmap-item complete"><span className="step-number">✓</span><div><strong>Etap 3 · Oferty i dopasowanie</strong><p>Integracje źródeł, deduplikacja, ranking, wyjaśnienia i statusy aplikacji.</p></div><span className="step-tag done">Gotowe</span></div><div className="roadmap-item complete"><span className="step-number">✓</span><div><strong>Etap 4 · Asystent aplikowania</strong><p>Analiza wymagań, luki kompetencyjne, wskazówki do CV i edytowalny list motywacyjny.</p></div><span className="step-tag done">Gotowe</span></div></section>
      <footer>JobPilot AI · Projekt demonstracyjny · Analiza może pomijać synonimy; zweryfikuj wszystkie materiały i fakty przed wysłaniem.</footer>
    </main></div>
}
