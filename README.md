# FlowDocs

FlowDocs is a document compliance review workspace. Give it source documents and the rules or policy you want to check; it processes the material, surfaces claims and potential compliance findings, and lets a human reviewer decide what belongs in the final report.

### What the app does

1. **Start a review:** upload PDF, TXT,  files and enter the compliance rules for this review.
2. **Process the documents:** FlowDocs extracts claims, analyzes their supporting evidence, and runs verification against the supplied rules. The run timeline shows progress through each stage.
3. **Inspect the results:** browse the processed documents, extracted claims, and findings. Evidence snippets link findings back to their source documents so reviewers can check the context.
4. **Make the decision:** a human reviews each pending finding, approves or rejects it, and can leave a comment. The review gate holds the workflow until the findings are handled.
5. **Produce and trace the outcome:** the deliverable includes approved findings and evidence references. The run also provides an action history and model usage and cost information.

You can return to previous runs, add documents to a run, and resume a run that failed or was interrupted. The overview brings together run status, processed documents, findings, and pending reviews.

FlowDocs is a review aid: AI-generated findings are presented for human assessment, and the reviewer’s decisions shape the deliverable.

### What it uses

The project includes a React web app, a FastAPI API, and PostgreSQL with the `pgvector` extension. For AI analysis, it supports Google Gemini; a deterministic mock provider is available for trying the workflow without an API key.

## Run locally with Docker

### Requirements

- Docker Desktop (or Docker Engine) with Docker Compose v2
- A Gemini API key for live AI analysis. You can use the built-in mock provider to explore the app without a key.

### 1. Configure the environment

Copy the example environment file:

```powershell
Copy-Item .env.example .env
```

Open `.env` and set `POSTGRES_PASSWORD` to a password of your choice. For a first run without an API key, set:

```dotenv
LLM_PROVIDER=mock
```

For live Gemini analysis, set `LLM_PROVIDER=gemini` and provide your key in `GEMINI_API_KEY`.

### 2. Start the database and initialize its schema

Run these commands from the project root. The database must be ready and migrated before the API starts.

```bash
docker compose up -d postgres
docker compose run --rm backend alembic upgrade head
```

### 3. Start the web app and API

```bash
docker compose up -d --build
```

Open the app at **http://localhost:5173**. The API documentation is at **http://localhost:8000/docs**.

To check that the API and database are connected, open **http://localhost:8000/health**. A healthy response looks like:

```json
{"status":"ok","database":"ok"}
```

## Useful commands

Run these from the project root:

| Task | Command |
| --- | --- |
| View running services | `docker compose ps` |
| Follow API logs | `docker compose logs -f backend` |
| Follow all logs | `docker compose logs -f` |
| Apply new database migrations | `docker compose run --rm backend alembic upgrade head` |
| Stop services and keep database data | `docker compose down` |
| Stop services and delete database data | `docker compose down -v` |

The last command permanently deletes the local PostgreSQL volume, including saved runs and documents.

## Run services without Docker

Docker Compose is the recommended setup because it provides PostgreSQL and `pgvector`. For a host-based setup, install PostgreSQL with `pgvector`, Python 3.12+, and Node.js 20+ first. Configure `.env` with a database host reachable from your machine, then run the API and frontend in separate terminals:

```bash
cd backend
python -m venv .venv
```

Activate it, then install the backend, migrate the database, and start the API. On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`; on macOS or Linux, use `source .venv/bin/activate`.

```bash
python -m pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at **http://localhost:5173**. The API runs at **http://localhost:8000**.

## Project layout

```text
backend/    FastAPI API, document workflow, database models, and migrations
frontend/   React web application
docker-compose.yml  Local PostgreSQL, API, and frontend services
.env.example        Local configuration template
```
