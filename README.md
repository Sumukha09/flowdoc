# FlowDocs

FlowDocs is a document processing application powered by LangGraph, LLMs (Gemini), and PostgreSQL (pgvector). It provides a full-stack experience (FastAPI backend + React frontend) to ingest documents, extract claims, analyze evidence against compliance rules, and allow human review.

## Architecture Stack

- **Language**: Python 3.12, JavaScript (React)
- **Web framework**: FastAPI (Backend), Vite/React (Frontend)
- **Database**: PostgreSQL 16 with the `pgvector` extension
- **ORM**: SQLAlchemy 2.x with `psycopg[binary]`
- **Migrations**: Alembic
- **Containerization**: Docker Compose

---

## 🚀 Getting Started

Anyone can completely run this application from scratch using Docker. Follow the steps below.

### 1. Prerequisites

- **Docker** 24+
- **Docker Compose** v2

*(Python 3.12 and Node.js are only required if you choose to run the services outside of Docker.)*

### 2. Environment Variables

Before starting the app, you need to configure your environment variables. 

1. Copy the provided `.env.example` file to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Open `.env` and fill in the required values. Below is a full explanation of the environment variables:

| Variable | Description | Default / Required |
|----------|-------------|--------------------|
| `POSTGRES_HOST` | Hostname for PostgreSQL. | `localhost` (Docker overrides this) |
| `POSTGRES_PORT` | Port for PostgreSQL. | `5432` |
| `POSTGRES_DB` | Name of the database. | `flowdocs` |
| `POSTGRES_USER` | Database user. | `flowdocs` |
| `POSTGRES_PASSWORD` | Secure password for the DB. | **Required** |
| `LLM_PROVIDER` | Which LLM to use. | `gemini` |
| `GEMINI_API_KEY` | Your Google Gemini API Key. |
| `GEMINI_MODEL` | The specific Gemini model to use. | `gemini-3.1-flash-lite` |
| `GEMINI_MAX_RPM` | Rate limit for Gemini API. | `10` |
| `LLM_TOKEN_BUDGET` | Max token budget for operations. | `50000` |
| `APP_ENV` | Application environment. | `local` |
| `APP_HOST` | Host for the backend. | `0.0.0.0` |
| `APP_PORT` | Port for the backend. | `8000` |

### 3. Start the Application

You can start the entire stack (Database, Backend, and Frontend) in one command:

Using Docker Compose:
```bash
docker compose up -d --build
```


### 4. Apply Database Migrations

Once the containers are running, you MUST apply the database schema migrations. This also enables the `pgvector` extension.

Run the following command:
```bash
docker compose exec backend alembic upgrade head
```
*(Or using the Makefile: `make migrate`)*

### 5. Access the Application

- **Frontend Application**: [http://localhost:5173](http://localhost:5173)
- **Backend API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Backend Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 🤖 Model Context Protocol (MCP) Server

FlowDocs includes a built-in MCP server that allows AI agents (such as Claude Desktop or other MCP clients) to programmatically interact with the workflow (start runs, approve findings, get reports, etc.).

### Running MCP Locally (Standalone)

To run the MCP server directly via standard I/O (stdio transport), you need a local Python environment:

1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows: .venv\Scripts\activate
   # Mac/Linux: source .venv/bin/activate
   ```
2. Run the MCP Server:
   ```bash
   python run_mcp.py
   ```

### Configuring Claude Desktop (or other clients)

To connect an AI client to this MCP server, you configure the client to spawn the `run_mcp.py` script. 

Example configuration (`mcp_config.json` or Claude config):
```json
{
  "mcpServers": {
    "flowdocs-mcp": {
      "command": "C:\\absolute\\path\\to\\flowdocs\\.venv\\Scripts\\python.exe",
      "args": ["C:\\absolute\\path\\to\\flowdocs\\backend\\run_mcp.py"],
      "env": {
        "POSTGRES_USER": "flowdocs",
        "POSTGRES_DB": "flowdocs",
        "POSTGRES_PASSWORD": "your_secure_password_here"
      }
    }
  }
}
```
*(Note: Ensure paths point to your local absolute paths and your `.venv` python executable. Mac/Linux will use `python` or `python3` instead of `.exe`)*

### Available MCP Tools

Once connected, your AI agent can use the following tools:
- `create_run(file_paths, compliance_rules)`: Start a new document processing run.
- `get_run(run_id)`: Fetch basic status of a run.
- `get_run_state(run_id)`: Retrieve the granular workflow execution trace.
- `resume_run(run_id)`: Resume a stalled or failed workflow run.
- `add_documents(run_id, file_paths)`: Incrementally add new documents to a run.
- `get_findings(run_id)`: List all compliance findings for a run.
- `review_finding(run_id, finding_id, decision, comment)`: Programmatically approve/reject a finding.
- `get_report(run_id)`: Retrieve the final compliance report metadata.

---

## 🛑 Useful Commands

- **Stop Services**: `docker compose down` (or `make down`)
- **View Backend Logs**: `docker compose logs -f backend` (or `make logs`)
- **Destroy Everything** (including database volumes): `docker compose down -v` (or `make clean`)
