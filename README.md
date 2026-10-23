# JobPilot AI — Etap 4: asystent aplikowania

JobPilot AI to lokalny prototyp wspierający organizację poszukiwania pracy. Stack: React + TypeScript + Vite, FastAPI, SQLAlchemy i MySQL.

## Funkcje etapów 1–4
- Panel statusu API i MySQL.
- Upload CV PDF/DOCX (maks. 5 MB), ekstrakcja tekstu i wstępny profil słów kluczowych.
- Preferencje: kierunki stanowisk, lokalizacja, tryb zdalny, słowa kluczowe i CV do porównania.
- Pobieranie ofert z publicznych API Arbeitnow i Remotive.
- Deduplikacja po źródle i identyfikatorze oferty; przechowywanie w tabeli `jobs` MySQL.
- Ranking dopasowania 0–100 z wyjaśnieniami: zgodność tytułu, słowa kluczowe, zdalność i lokalizacja.
- Śledzenie statusu oferty: Zapisana, Aplikowano, Rozmowa, Odrzucona, Oferta, Archiwum.
- Link do oryginalnego ogłoszenia i filtry ofert.
- Analiza wymagań stanowiska na podstawie słów kluczowych i porównanie z wybranym CV.
- Lista dopasowanych umiejętności, potencjalnych braków i wskazówek do ręcznej weryfikacji.
- Generowanie roboczego podsumowania CV, listy działań i listu motywacyjnego w języku polskim lub angielskim.
- Edytowanie listu motywacyjnego w interfejsie oraz zapisywanie szkiców w tabeli `application_drafts` MySQL.
- Opcjonalny provider zgodny z API OpenAI Chat Completions; gdy nie jest skonfigurowany, działa lokalny generator szablonowy. CV nie jest wysyłane do zewnętrznego modelu bez skonfigurowania integracji.

## Wymagania
- Python 3.11+
- Node.js 20+
- MySQL 8+
- npm

## Uruchomienie backendu
Z katalogu głównego repozytorium:

```bash
cd backend
python -m venv .venv
```
Aktywacja Windows PowerShell: ` .\.venv\Scripts\Activate.ps1 `; Linux/macOS: `source .venv/bin/activate`.

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```
Skopiuj `backend/.env.example` do `backend/.env` i ustaw `DATABASE_URL`, np.:

```env
APP_NAME=JobPilot AI
APP_ENV=development
API_PREFIX=/api
CORS_ORIGINS=http://localhost:5173
DATABASE_URL=mysql+pymysql://jobpilot_user:twoje_haslo@127.0.0.1:3306/jobpilot
# Opcjonalne — pozostaw puste, aby używać lokalnego generatora szablonowego
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=gpt-4o-mini
```

Baza i użytkownik MySQL muszą już istnieć. Przykład jednorazowego przygotowania bazy:

```sql
CREATE DATABASE jobpilot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'jobpilot_user'@'localhost' IDENTIFIED BY 'twoje_haslo';
GRANT ALL PRIVILEGES ON jobpilot.* TO 'jobpilot_user'@'localhost';
FLUSH PRIVILEGES;
```

Uruchom API z katalogu `backend`:

```bash
uvicorn app.main:app --reload
```

- Swagger: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/api/health
- MySQL health: http://127.0.0.1:8000/api/health/db

Tabele `resumes`, `jobs`, `job_preferences` i `application_drafts` są tworzone przy starcie aplikacji przez `create_all`. Dla produkcji należy wdrożyć migracje Alembic.

## Uruchomienie frontendu
W drugim terminalu:

```bash
cd frontend
npm install
npm run dev
```

Domyślny adres: http://localhost:5173. Jeśli backend działa pod innym adresem, ustaw `VITE_API_BASE_URL` w `frontend/.env`.

## Jak użyć etapów 3–4
1. Otwórz aplikację i prześlij CV w sekcji „Moje CV”.
2. W preferencjach wpisz stanowiska (oddzielone przecinkami), lokalizację i słowa kluczowe; wybierz CV, jeśli chcesz wskazać konkretne.
3. W sekcji „Oferty pracy” wybierz źródło lub „Wszystkie źródła”, opcjonalnie wpisz frazę i kliknij „Pobierz nowe oferty”.
4. Oceniaj oferty po wyniku i wyjaśnieniach. Link otwiera oryginalne ogłoszenie.
5. Zmieniaj status aplikacji w karcie oferty. Statusy i oferty są zapisywane w MySQL.
6. Kliknij „Analizuj i przygotuj materiały”, aby porównać wymagania z CV.
7. Wybierz język materiałów; możesz edytować szkic listu i zapisać go w MySQL.
8. Przed użyciem sprawdź wszystkie twierdzenia i usuń elementy, które nie odpowiadają Twojemu rzeczywistemu doświadczeniu.

## API etapów 3–4
- `GET /api/jobs/preferences` — odczyt preferencji.
- `PUT /api/jobs/preferences` — zapis preferencji i ponowne przeliczenie dopasowania.
- `GET /api/jobs/sources` — źródła i krótki opis.
- `POST /api/jobs/sync` — pobranie i zapis ofert; body np. `{"source":"all","query":"IT support","location":"Kraków, Poland","remote_only":false,"limit":50}`.
- `GET /api/jobs` — lista, filtry `q`, `status`, `source`, `remote_only`, `min_score`, `limit`.
- `PATCH /api/jobs/{id}/status` — aktualizacja statusu, body np. `{"status":"applied"}`.
- `GET /api/analysis/jobs/{id}?resume_id=1` — analiza wymagań i luk kompetencyjnych.
- `POST /api/analysis/jobs/{id}/materials` — wygenerowanie szkicu CV i listu motywacyjnego; body np. `{"resume_id":1,"language":"pl","applicant_name":""}`.
- `PUT /api/analysis/jobs/{id}/materials/save` — zapis edytowanego szkicu do MySQL.
- `GET /api/analysis/jobs/{id}/materials/saved?resume_id=1&language=pl` — odczyt zapisanego szkicu.

## Jak działa asystent aplikowania

Domyślnie działa lokalny generator szablonowy i jawna analiza słów kluczowych. Nie jest to autonomiczna ocena kandydata ani pełna semantyczna analiza CV. Dopasowanie nie określa szans na zatrudnienie. Jeśli skonfigurujesz `LLM_API_KEY`, `LLM_BASE_URL` (bazowy URL API zgodnego z OpenAI, np. kończący się na `/v1`) i `LLM_MODEL`, szkice mogą być ulepszane przez model zewnętrzny. Wtedy fragment CV i ogłoszenia zostają wysłane do wskazanego dostawcy — rób to tylko, gdy masz podstawę i zgodę na takie przetwarzanie. Klucz API przechowuj w `backend/.env`, nie w kodzie. Wygenerowane treści są szkicami, nie wysyłają aplikacji automatycznie i nie powinny dodawać niepotwierdzonych kompetencji.

## Źródła i ograniczenia
- Arbeitnow: publiczne API tablicy ofert, https://www.arbeitnow.com/.
- Remotive: publiczne API ofert zdalnych, https://remotive.com/.

Zakres i dostępność danych są zależne od dostawcy. To nie jest pełny indeks rynku pracy w Polsce; oferty z obu źródeł mogą być ograniczone geograficznie lub nie odpowiadać dokładnie lokalizacji użytkownika. Aplikacja zapisuje oryginalny URL. Nie scrapuje stron wymagających logowania i nie omija zabezpieczeń. Dostawcy mogą zmieniać API lub zasady dostępu.

## Jak działa dopasowanie
Wynik 0–100 jest heurystyką, a nie modelem AI ani oceną szans na zatrudnienie. Uwzględnia dopasowanie tytułu do preferowanych ról, obecność słów kluczowych z CV/preferencji, zdalność i lokalizację. Opisy ogłoszeń są upraszczane do tekstu. Sprawdź ręcznie wymagania, lokalizację, datę i warunki oferty.

## Ważne przed wdrożeniem
Prototyp działa bez logowania, więc nie wystawiaj go publicznie ani nie zapisuj cudzych CV. Przed wdrożeniem należy dodać uwierzytelnianie, autoryzację, ochronę plików i danych osobowych, rate limiting, walidację źródeł, migracje bazy, testy i politykę retencji danych. Nie wysyłaj CV do zewnętrznych usług bez wyraźnej zgody.
