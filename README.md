# RepoVision AI

![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)
![Google ADK](https://img.shields.io/badge/Agents-Google%20ADK-4285F4?logo=google&logoColor=white)
![Gemini](https://img.shields.io/badge/Model-Gemini%202.5%20Flash-8E75B2?logo=googlegemini&logoColor=white)
![Vertex AI](https://img.shields.io/badge/Compute-Vertex%20AI-4285F4?logo=google&logoColor=white)
![Cloud Run](https://img.shields.io/badge/Deploy-Cloud%20Run-4285F4?logo=googlecloud&logoColor=white)
![Docker](https://img.shields.io/badge/Runtime-Docker-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-blue.svg)

> *"In Blue Lock, Isagi's Meta-Vision sees the entire field from above — every player, every gap, every possibility at once. RepoVision AI does the same for your codebase."*

RepoVision AI is a **13-agent GitHub intelligence platform** that sees your entire repository from above. Instead of reviewing one file or one PR at a time, it deploys a swarm of specialist agents that simultaneously review pull requests, triage bugs, and score repository health — giving you a complete picture in a single analysis.

**Live Demo:** https://repovision-frontend-174510296487.us-central1.run.app

---

## What It Does

Submit any GitHub `owner/repo` target and RepoVision AI:

- **Reviews pull requests** — code quality, security vulnerabilities, test coverage gaps, and auto-generated changelogs
- **Triages open bugs** — classifies issues, generates fixes, writes tests, judges the result in a loop, and drafts PRs
- **Scores repo health** — docs quality, dependency risks, contributor bus factor, and activity trends
- **Returns everything** in a unified dashboard with scores, grades, and actionable recommendations

---

## Architecture

```text
                         +---------------------------+
                         |     Frontend Dashboard    |
                         |  HTML / CSS / JS / Nginx  |
                         +-------------+-------------+
                                       |
                                       | POST /analyze
                                       v
                         +--------------------------+
                         |    FastAPI Backend       |
                         |  InMemoryRunner + ADK    |
                         +-----------+--------------+
                                     |
                                     v
                         +---------------------------+
                         | RepoVision Orchestrator   |
                         |   (Root LlmAgent)         |
                         +----+----------+-------+---+
                              |          |       |
               +--------------+    +-----+    +--+----------+
               v                   v              v
    +------------------+  +-------------+  +--------------+
    |  PR Review       |  | Bug Triage  |  | Repo Health  |
    |  ParallelAgent   |  | LoopAgent   |  | Parallel →   |
    |  4 specialists   |  | 5 agents    |  | Sequential   |
    |  + aggregator    |  | + judge     |  | 4 + scorer   |
    +------------------+  +-------------+  +--------------+
               |                   |              |
               +-------------------+--------------+
                                   |
                         +---------+----------+
                         |   GitHub REST API  |
                         |  (direct httpx)    |
                         +--------------------+
```

---

## The 13 Agents

| Module | Agent | Role |
|--------|-------|------|
| PR Review | `code_quality_agent` | Logic bugs, code smells, SOLID violations |
| PR Review | `security_agent` | Secrets, injection, XSS, dependency risks |
| PR Review | `test_coverage_agent` | Untested functions, missing edge cases |
| PR Review | `changelog_agent` | Auto-generated changelog from diff |
| PR Review | `pr_aggregator` | Combines all 4 into final score + verdict |
| Bug Triage | `issue_classifier_agent` | Classifies open issues by severity |
| Bug Triage | `fix_generator_agent` | Proposes concrete code fixes |
| Bug Triage | `test_writer_agent` | Writes unit tests for the fix |
| Bug Triage | `judge_agent` | Evaluates fix quality, exits loop on pass |
| Bug Triage | `pr_drafter_agent` | Drafts the GitHub PR |
| Repo Health | `docs_auditor_agent` | README quality, missing docs |
| Repo Health | `dependency_scanner_agent` | Outdated/risky dependencies |
| Repo Health | `contributor_health_agent` | Bus factor, contribution distribution |
| Repo Health | `activity_agent` | Maintenance activity, project freshness |
| Repo Health | `health_scorer` | Weighted score, grade A-F, recommendations |

---

## ADK Patterns Used

| Pattern | Where | Why |
|---------|--------|-----|
| `ParallelAgent` | PR Review Module | 4 review agents run simultaneously |
| `LoopAgent` | Bug Triage Module | Fix → Test → Judge → Retry (max 3x) |
| `SequentialAgent` | Repo Health Module | Parallel audits → scorer pipeline |
| `AgentTool` | Orchestrator | Each module wrapped as a callable tool |
| `FunctionTool` | All modules | Direct GitHub API calls via httpx |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Agent framework | Google ADK (`google-adk`) |
| LLM | Gemini 2.5 Flash via Vertex AI |
| API | FastAPI + Pydantic + Uvicorn |
| GitHub integration | GitHub REST API + `httpx` |
| Frontend | Vanilla HTML/CSS/JS + Nginx |
| Containerization | Docker + Docker Compose |
| Deployment | Google Cloud Run |
| Package management | `uv` |

---

## Repository Layout

```text
repovision-ai/
├── backend/
│   ├── agents/
│   │   ├── orchestrator.py    # Root agent — routes to all 3 modules
│   │   ├── pr_reviewer.py     # Module 1 — ParallelAgent + aggregator
│   │   ├── bug_triage.py      # Module 2 — LoopAgent pipeline
│   │   └── repo_health.py     # Module 3 — Parallel → Sequential
│   ├── main.py                # FastAPI app + InMemoryRunner
│   ├── mcp_server.py          # FastMCP tool server (local use)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── index.html             # Single-file production UI
│   ├── nginx.conf
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Setup

### Prerequisites

- Python 3.12+
- Docker + Docker Compose
- GitHub Personal Access Token (repo read scope)
- Google Cloud project with Vertex AI enabled
- Gemini API key (or Vertex AI credentials)

### 1. Clone

```bash
git clone https://github.com/OmkarAKadam/repovision-ai.git
cd repovision-ai
```

### 2. Configure environment

```bash
cp .env.example .env
```

```env
GITHUB_TOKEN=ghp_your_token_here
GEMINI_API_KEY=your_gemini_api_key
GOOGLE_CLOUD_PROJECT=your_project_id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_GENAI_USE_VERTEXAI=1
```

### 3. Run with Docker Compose

```bash
docker compose up --build
```

- Backend API: `http://localhost:8080`
- Frontend: `http://localhost:3000`

### 4. Run backend locally

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload
```

---

## API Usage

**Health check:**
```bash
curl https://repovision-backend-174510296487.us-central1.run.app/health
```

**Analyze a repository:**
```bash
curl -X POST https://repovision-backend-174510296487.us-central1.run.app/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "target": "cli/cli",
    "modules": ["repo_health"]
  }'
```

**Response:**
```json
{
  "session_id": "0b293d4f",
  "target": "cli/cli",
  "pr_review": null,
  "bug_triage": null,
  "repo_health": {
    "overall_health_score": 81.25,
    "grade": "B",
    "status_label": "Good Health",
    "summary": "...",
    "scores": {...},
    "top_strengths": [...],
    "top_risks": [...],
    "recommendations": [...]
  },
  "duration_seconds": 34.09,
  "status": "success"
}
```

---

## Module Selection

```json
{ "target": "owner/repo", "modules": ["repo_health"] }
{ "target": "owner/repo", "modules": ["pr_review"] }
{ "target": "owner/repo", "modules": ["bug_triage"] }
{ "target": "owner/repo", "modules": ["pr_review", "bug_triage", "repo_health"] }
```

---

## Deploy to Cloud Run

```bash
# Backend
gcloud run deploy repovision-backend \
  --source ./backend \
  --region us-central1 \
  --port 8080 \
  --memory 1Gi \
  --cpu 2 \
  --allow-unauthenticated

# Set env vars separately (critical — comma syntax merges them incorrectly)
gcloud run services update repovision-backend --region us-central1 --update-env-vars GITHUB_TOKEN=your_token
gcloud run services update repovision-backend --region us-central1 --update-env-vars GOOGLE_GENAI_USE_VERTEXAI=1
gcloud run services update repovision-backend --region us-central1 --update-env-vars GOOGLE_CLOUD_PROJECT=your_project

# Frontend
gcloud run deploy repovision-frontend \
  --source ./frontend \
  --region us-central1 \
  --port 8080 \
  --memory 256Mi \
  --allow-unauthenticated \
  --set-env-vars BACKEND_URL=https://your-backend-url.run.app
```

> **Note:** Always set Cloud Run env vars using separate `--update-env-vars` calls. Using comma-separated `--set-env-vars` in a single command merges all values into one variable.

---

## Security Notes

- Keep `.env` out of source control (already in `.gitignore`)
- Use GitHub tokens with minimum required scopes
- The `create_pull_request_direct` function is stubbed — enable with caution for write access
- Review all agent-generated fixes before merging

---

## Roadmap

- [ ] Real PR number parsing for `owner/repo/pull/N` targets
- [ ] Vertex AI Memory Bank for persistent repo history across sessions
- [ ] Streaming SSE responses for real-time agent activity in frontend
- [ ] Replace direct httpx calls with full FastMCP tool layer
- [ ] CI/CD pipeline with GitHub Actions

---

## Built For

Google Build with AI Series — Workshop 3  
*Stack: Google ADK · FastMCP · Gemini 2.5 Flash · Vertex AI · FastAPI · Cloud Run*

---

## License

MIT