# AI Job Assistant

面向求职全流程的 Next.js + FastAPI 应用。AI 模拟面试作为第 11 个业务模块集成在现有用户、简历、职位和数据体系中。

用户系统现支持欢迎页、QQ 邮箱注册、密码/验证码登录、找回密码、退出登录和多用户数据隔离。QQ SMTP 与安全配置见 [`docs/AUTHENTICATION.md`](docs/AUTHENTICATION.md)。本机历史数据管理员为 `admin`，首次测试密码为 `admin123`；公网启动必须更换默认密码。

The project is implemented one module at a time. The current step includes:

- Next.js + React + TypeScript + Tailwind frontend
- FastAPI backend
- PostgreSQL and Redis services
- Health-check and module-map APIs
- User center with PostgreSQL-backed profile CRUD APIs
- User center form for personal details and job preferences
- Resume management with version CRUD APIs and a primary-resume flag
- Resume editor for target roles, status, content, and notes
- Job records with CRUD APIs and database-level search filters
- Job search UI for title, company, city, salary, degree, experience, and company size
- Company blacklist rules with exact/contains matching and reason checks
- Automatic blacklist filtering in job search results
- Explainable JD match scoring with keyword coverage, gaps, and saved analyses
- Resume optimization drafts with user-confirmed application to the source resume
- Recruiter greeting drafts with tone options, editing, approval, and copy support
- Application records with explicit confirmation, follow-ups, and status timelines
- Analytics dashboard for funnel rates, status/channel distributions, match scores, and trends
- Plugin-friendly platform adapter registry with preview and confirmed job import
- Compliance-first rule: the system prepares suggestions, but applications require user confirmation
- Resume-aware AI mock interviews with contextual follow-up questions and pressure levels
- Live browser voice interviews with automatic listening, barge-in, silence-based answer submission, mute/repeat/end controls, cute/standard voice styles, plus MediaRecorder + local Whisper fallback when SpeechRecognition is unavailable
- Evidence-based interview scoring, detailed reports, history, and operations metrics
- PDF, DOCX, TXT, and Markdown resume upload parsing
- Deterministic local AI fallback so the complete interview flow works without an API key
- Browser-assisted Zhaopin application tasks with login checks, previews, one-time confirmation tokens, and conservative manual verification
- Zhaopin official-site search/import driven by the user profile, with JD enrichment and hard-rule filtering
- One-click profile/resume matching that queues eligible Zhaopin jobs as draft tasks and lets the user exclude jobs before submission
- Automatic exact-company blacklisting when Zhaopin explicitly reports a zero or unpaid salary
- Post-application greeting attempts after success verification, with a clear Zhaopin App fallback when the PC site exposes no message input

## Run With Docker

```powershell
cd ai-job-assistant
copy .env.example .env
docker compose up --build
```

Open:

- Frontend: http://localhost:3000
- Backend health: http://localhost:8000/api/health
- Backend modules: http://localhost:8000/api/modules
- User profile API: http://localhost:8000/api/user-profile
- Resume API: http://localhost:8000/api/resumes
- Job search API: http://localhost:8000/api/jobs
- Company blacklist API: http://localhost:8000/api/blacklist
- JD match API: http://localhost:8000/api/matches
- Resume optimization API: http://localhost:8000/api/optimizations
- Greeting generation API: http://localhost:8000/api/greetings
- Application records API: http://localhost:8000/api/applications
- Analytics API: http://localhost:8000/api/analytics/overview
- Platform adapters API: http://localhost:8000/api/platform-adapters
- Mock interview API: http://localhost:8000/api/interviews
- Application automation API: http://localhost:8000/api/application-automation/tasks
- Resume upload API: http://localhost:8000/api/resume-uploads
- API documentation: http://localhost:8000/docs

## Module Roadmap

1. User center (completed)
2. Resume management (completed)
3. Job search and filters (completed)
4. Company blacklist (completed)
5. JD match scoring (completed)
6. Resume optimization (completed)
7. Greeting generation (completed)
8. Application records (completed)
9. Data statistics (completed)
10. Platform adapters and plugin extension points (completed)
11. AI mock interviews (completed)
12. Zhaopin search/import and single-job application assistance (partial: real resume-dialog validation and broader city coverage remain)

## Completed Modules

The user center stores one current user profile with contact details, target roles, cities, salary range, education, experience, company-size preferences, portfolio URL, and summary.

The frontend saves through `PUT /api/user-profile`, which creates the profile when it does not exist. The backend also exposes explicit `POST`, `GET`, and `DELETE` operations.

Resume management stores independent resume versions with a target role, version number, draft/ready status, plain-text content, notes, and one optional primary version. Its API is available at `/api/resumes`.

Job search stores manually entered or adapter-provided job records and filters them by keyword, city, salary overlap, degree, experience, and company size. External recruitment-platform collection is intentionally deferred to the platform-adapter module.

Company blacklist stores active or inactive exact-name and contains-name rules. Open jobs matched by an active rule are excluded from normal job search results. The `/api/blacklist/check?company_name=...` endpoint returns the matching rule and reason.

JD matching uses a transparent operations keyword set. It compares a selected job with a selected resume, returns a 0-100 score, matched keywords, missing keywords, reasons, and recommendations, and stores each analysis at `/api/matches`.

Resume optimization creates an editable draft from a match record. Missing skills are only shown as warnings and are never inserted automatically. Applying a draft requires an explicit confirmation request and then updates the source resume.

Greeting generation uses a selected job and resume, plus the latest matching evidence when available. Drafts support concise, professional, and warm tones and remain editable until explicitly approved. A greeting is never sent as a standalone or unconfirmed action; an application task may attempt to send its saved snapshot only after the user confirms that job and the site displays an application-success marker.

Application records start in a prepared state. The confirmation endpoint only marks a record as submitted after explicit user confirmation; it never performs an external platform action. Subsequent stages use a controlled status transition timeline.

Analytics is computed read-only from local job, resume, match, and application records. It includes response/interview/offer rates, due follow-ups, distributions, a 14-day submission trend, and recent application activity.

Platform adapters use a registry and a common normalization contract. The built-in manual-import adapter supports preview and explicitly confirmed local job import only; it does not search external platforms or submit applications.

AI mock interviews reuse existing resume and job records, save immutable snapshots for history, support contextual and pressure follow-ups, and generate an idempotent evidence-based report. The default `local` provider is fully functional; set `AI_PROVIDER=openai` and `OPENAI_API_KEY` to enable model-generated questions, reports, transcription, and speech. Provider failures automatically fall back to local question and report generation.

Application automation currently enables Zhaopin only and reuses a manually authenticated Edge session through the local browser bridge. It can search the official site from the user profile, enrich near matches with the detail JD, import eligible jobs, and queue draft tasks. It does not store credentials, solve verification challenges, or silently submit batches. Each task must be previewed and explicitly confirmed immediately before the external action. Only “已投递/投递成功” is accepted as a success marker; otherwise the task remains `verification_required`. See `docs/APPLICATION_AUTOMATION.md`.

The submission panel checks the Zhaopin connection automatically when opened. No open Zhaopin tab is reported as an actionable `unknown` state rather than a false logout; clicking “打开登录” or “搜索并生成清单” opens the required page. A successful search refreshes the panel to the current logged-in state.

The one-click flow calls `/api/application-automation/auto-apply/run`, which validates the completed user profile and primary `ready` resume before searching Zhaopin, importing matched jobs, and creating the local draft plan in one request. It applies the salary floor, blacklist, Zhaopin URL, city, role/JD, degree, experience, seniority, and company-size rules. Explicit zero/unpaid salary results are rejected and their exact company names are added to the active blacklist; unknown or negotiable salaries are rejected but are not automatically classified as zero salary. The frontend displays eligible jobs under “即将投递”, supports a per-job “不投递” checkbox, and opens the normal preview/confirmation flow for “预览并确认”. It never bypasses the per-job confirmation gate.

On the standalone job-search page, a manually entered keyword is used as the role target for that search only and does not overwrite the user profile. New keywords are entered through the browser's real text-insertion path so Zhaopin's controlled search input accepts them. Matching/imported candidates are prioritized in the visible results and labeled as “新导入” or “已存在并更新” instead of being hidden behind the first ten filtered cards.

If a Zhaopin resume-selection dialog appears, the automation selects the requested resume by name; if the site applies directly, it uses the account's default resume. After the site displays “已投递/投递成功”, the automation attempts to open a communication entry and send the task's greeting snapshot only when a real message input and send control exist. The current Zhaopin PC site exposes an App download prompt instead of a message input, so the task remains successfully submitted while communication is marked `manual_required`; the frontend provides the exact text for copying into the Zhaopin App. The system never reports that message as sent.

Application automation also blocks duplicate tasks for the same platform and job. External submission attempts are limited across all supported platforms to 20 per UTC day with a 60-second cooldown by default. Configure these safeguards with `APPLICATION_AUTOMATION_DAILY_LIMIT` and `APPLICATION_AUTOMATION_COOLDOWN_SECONDS`; failed attempts that entered the submitting state still count.

## Local Development Without Docker

Docker is the recommended production-like path. For local development without Docker, run the backend with SQLite:

```powershell
cd backend
$env:DATABASE_URL="sqlite:///./dev.db"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

In another terminal:

```powershell
cd frontend
pnpm dev
```

## Verification

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
pnpm typecheck
pnpm build
```

Detailed product, data, API, AI-safety, and state-machine decisions are documented in `docs/INTERVIEW_MODULE.md`. Deployment guidance is in `docs/DEPLOYMENT.md`.

The current Windows online mode uses a password-protected Cloudflare Quick Tunnel. Run `scripts/start-online.ps1`, inspect it with `scripts/status-online.ps1`, and stop it with `scripts/stop-online.ps1`. The public URL is ephemeral; see `docs/DEPLOYMENT.md` for limitations.
