# PeakCV

A placement-preparation platform for students. Upload a resume once, then check it against ATS standards and
real job descriptions, practise with MCQ tests, timed coding rounds and AI HR and technical interviews, and
follow a personalised learning path that updates after every attempt.

## Features

- **Resume:** PDF upload with safety checks (real PDF, size and page limits, no scanned or encrypted files). The
  LLM extracts skills, experience and education; skills are shown grouped into Languages, Frameworks & libraries,
  Databases, Dev tools & cloud, Concepts and Others. The resume is also indexed for RAG so other modules can
  personalise their questions.
- **ATS check:** pick a target role and experience level (student to lead). An honest, role-specific review gives
  an ATS score, a role-fit score, the five most important fixes and a line-by-line keep / fix / cut review. The
  model rates each criterion; the scores are calculated in code.
- **Job description analyzer:** paste or upload a job description. Requirements are extracted and matched against
  the resume with a deterministic, explainable score; every matched skill shows the resume text it came from.
- **MCQ tests:** role-specific questions, ten per skill, at three difficulties, with an anti-tab-switch guard.
- **Coding round:** timed DSA rounds built from real interview questions (about 3,400 LeetCode problems asked at
  656 companies), optionally for one company. Solve them in Python, JavaScript, C++, C, Java or Go in a browser
  editor; code runs against hidden tests, then the AI reviews it.
- **HR interview:** a six-stage adaptive behavioural interview with voice input and output and a STAR-based report.
- **Technical interview:** adaptive interviews on DSA, languages, OOP, DBMS, OS, networks, web, system design,
  your projects, or a mix, scored on a six-criterion rubric.
- **Learning path:** skill mastery from every MCQ, coding and interview result, prioritised by gap × importance
  with prerequisites first, turned into a day-by-day plan that fits your time and deadline and updates itself.
- **Dashboard:** score trends per module, weekly activity, skill mastery and an eight-card preparation journey.
- **Cold email:** a short recruiter email written only from facts in your resume, ready to copy.
- **Sign in:** email and password, or Sign in with Google.

## Tech stack

- **Frontend:** React 19, Vite 5, React Router 7, Tailwind utility classes, Monaco editor, Web Speech API,
  Google Identity Services, Vitest + Testing Library.
- **Backend:** Python 3.11, Django 5.2, Django REST Framework, Simple JWT, `google-auth`, SQLite.
- **AI:**
    - Groq (free tier): `openai/gpt-oss-20b` and `openai/gpt-oss-120b`
    - LangChain + ChromaDB + `all-MiniLM-L6-v2` embeddings (RAG)
    - pypdf
- **Code execution:** self-hosted Piston (Docker), or a local development-only executor.

## Setup

**Requirements:**
- Python 3.11. The pinned `torch` does not support newer Python; `uv venv --python 3.11 venv` works if your system
  Python is newer.
- Node.js 18+.
- A free [Groq API key](https://console.groq.com/keys).

```powershell
# backend (project root)
python -m venv venv            # or: uv venv --python 3.11 venv
venv\Scripts\activate          # Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env         # then fill in the values
python manage.py migrate       # also loads the skill taxonomy
python manage.py runserver     # http://localhost:8000

# frontend (new terminal)
cd frontend
npm install
npm run dev                    # http://localhost:5173 (or: npm run dev -- --port 5174)
```

Both must be running: the website calls the backend at `http://localhost:8000/api`. To use another address, set
`VITE_API_URL` for the frontend.

### Environment variables (`.env`)

| Variable | Purpose |
| --- | --- |
| `GROQ_API_KEY` | Groq key for all AI features |
| `SECRET_KEY`, `JWT_SECRET` | Django and JWT signing secrets (long random strings) |
| `CODE_EXECUTOR` | `piston` (sandbox, recommended), `local` (development only) or `off` (no code runner; the coding round is switched off) |
| `ALLOW_LOCAL_EXECUTOR` | must be `1` for `local` to run; also requires `DEBUG=True` |
| `PISTON_URL` | Piston address, default `http://localhost:2000` |
| `PISTON_TOKEN` | optional; sent as `Authorization: Bearer …` when Piston is on another server behind a reverse proxy |
| `GOOGLE_CLIENT_ID` | optional; turns on "Continue with Google" on the login page |
| `DEBUG` | `False` on a live server (default `True` for local development) |
| `ALLOWED_HOSTS` | live server: the backend's domain, comma-separated (default `*`) |
| `CORS_ALLOWED_ORIGINS` | live server: the frontend's address, e.g. `https://peakcv.up.railway.app` (default: any) |
| `DATA_DIR` | where `db.sqlite3` and `chroma_db/` are stored; on Railway, a volume such as `/data` |

Without a Groq key the app still runs: login, the dashboard, the learning path and history work, and AI features
return a clear "AI service not configured" error.

### Sign in with Google (optional)

1. In [Google Cloud Console](https://console.cloud.google.com/), configure the OAuth consent screen (Internal for
   one organisation's accounts, or External for anyone; add test users while it is in testing).
2. Create an **OAuth client ID** of type **Web application**. Under **Authorised JavaScript origins** add the site
   address, e.g. `http://localhost:5173` and `http://localhost:5174` (and the live `https://` domain later).
   Redirect URIs are not needed.
3. Put the client ID in `.env` as `GOOGLE_CLIENT_ID` and restart the backend. The client secret is not needed.

The backend verifies Google's ID token (signature, expiry, issuer, audience and verified email) with the
official `google-auth` library, then signs the user in or creates the account.

### Code-execution sandbox (Piston)

1. Install WSL2 by running `wsl --install` as admin, then reboot.
2. Install Docker Desktop.
3. Start Piston:
   ```powershell
   docker run -d --name piston -p 2000:2000 --privileged ghcr.io/engineer-man/piston
   ```
4. Install the runtimes you need (python, node, gcc, java, go) through Piston's `POST /api/v2/packages` endpoint.
5. Set `CODE_EXECUTOR=piston` in `.env`.

### Code runner on Railway (`runner/`)

Railway can't run Piston (it needs privileged Docker), so `runner/` is a small Piston-compatible service for
Railway. Deploy it as its own service (Root Directory `runner`, built from its Dockerfile, which installs Python,
Node, gcc/g++, a JDK and Go). It needs a `RUNNER_TOKEN` variable and is reached over Railway's private network.
Point the backend at it with `CODE_EXECUTOR=piston`, `PISTON_URL=http://<runner-service>.railway.internal:8080` and
`PISTON_TOKEN` = the same token. Submissions run as an unprivileged user with time, CPU, process, file-size and
memory limits; the runner has no database, volume or other secrets.

### Coding-round languages

Python always works. With the local executor, the other languages need their tools on `PATH`:
- JavaScript: Node.js
- C and C++: gcc / g++ (MinGW on Windows)
- Java: a JDK, 11 or newer
- Go: Go

A language that can't run is shown as "not installed" in the picker. For C, C++, Java and Go, each problem's
function signature is worked out from its test data (`coding/languages.py`); a problem whose data mixes types is
offered in Python and JavaScript only.

### Coding question bank

`coding/data/question_bank.json` lists about 3,400 LeetCode problems and the 656 companies that ask them, built
from the public [company-wise lists](https://github.com/snehasishroy/leetcode-companywise-interview-questions).

**How a round is built**
1. Suitable questions at the chosen difficulty are picked, skipping linked-list, tree, design and SQL problems.
   Frequently asked questions are more likely to be picked, and questions you have seen before are skipped.
2. For each question, the LLM writes its own statement, examples, tests and a reference solution.
3. The reference solution is run on every test; tests it disagrees with are dropped.

**Stored data:** only titles, difficulty and company frequency are kept. No LeetCode problem text is copied.

**Speed:** writing up a problem takes the free-tier LLM 15–80 seconds, so each one is saved after its first use
and reused by later rounds. After each round a few more are prepared in the background.

**Fallback:** if the file is missing, rounds use problems invented by the LLM.

## Management commands

| Command | Purpose |
| --- | --- |
| `python manage.py import_question_bank` | Download and rebuild the coding question bank |
| `python manage.py warm_questions --count 10` | Prepare coding problems in advance (add `--company amazon` for one company) |
| `python manage.py sync_skills` | Apply edits to the skill taxonomy in `learning/taxonomy_data.py` (prerequisite cycles are rejected) |

## Tests

```powershell
python manage.py test          # backend: 90 tests, LLM calls mocked, no API key needed
cd frontend
npm test                       # frontend: 8 tests (Vitest + Testing Library)
npm run lint                   # ESLint
npm run build                  # production build check
```

The backend suite covers:
- Google sign-in verification and account matching
- ATS score arithmetic, role and level handling, the cold email endpoint
- the code judge (six languages, timeouts, crashes, compile errors, fake result lines), type inference,
  question selection and problem caching
- job matching scores, weight normalisation and extraction validation
- EMA mastery, evidence idempotency, prerequisite cycles and gating, priorities and roadmap scheduling
- the technical-interview policy, concurrency and LLM-failure handling
- ownership of every object and the full job → roadmap → MCQ → mastery journey

Java and Go judge tests are skipped when those tools are not installed.

## Project structure

```
backend/        settings (JOB_MATCH and LEARNING_ENGINE tuning) and URLs
users/          signup, login, Sign in with Google (JWT)
resume/         PDF upload (pdf.py: safe extraction) and LLM parsing
ai_features/    shared LLM client (llm.py), RAG (rag.py), MCQ, ATS check, HR interview, cold email
coding/         question bank, problem generator and cache, multi-language judge (languages.py, judge.py),
                executors (local / Piston), scoring; data/question_bank.json
jobs/           job description analyzer: services/ (extraction, matching, analyzer)
learning/       skill taxonomy, evidence, mastery, recommender, scheduler, roadmap, insights
technical/      technical interview: services/ (plan, ai, session)
dashboard/      cross-module stats and the score timeline
frontend/src/   pages/, components/{shared,dashboard,coding,jobs,learning,technical}/, hooks/useSpeech.js,
                services/part2Api.js, utils/ (validation, skillGroups)
runner/         Piston-compatible code runner for Railway (Dockerfile + server.py)
samples/        a sample resume (PDF and HTML) for testing
```

## Before deploying

These settings are for local development and must change for a public site: `DEBUG=True`,
`ALLOWED_HOSTS=['*']`, allowing requests from any origin (CORS), and the local code executor (use Piston).
Run `python manage.py check --deploy` for the full list.
