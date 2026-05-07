# Prompt
You are implementing PH Agent Hub, a multi-tenant AI agent platform. Read all the documentation carefully before producing anything.

Task: Produce a detailed implementation plan for Phase X — BLA BLA BLA

The plan must:

List every file to create, in the order it should be created
For each file: the exact path, its purpose, what it must contain, and any constraints from the architecture docs (e.g. single-module rules)
Note dependencies between files (e.g. "encryption.py must exist before running the first migration")
List any third-party packages required with exact names
End with the exact steps to verify the exit condition is met
Do not write code yet. Do not make decisions that are already made in the docs — follow the docs exactly. If you find a conflict or ambiguity in the docs, flag it instead of resolving it silently.


# Implementation Phases — PH Agent Hub

This document defines the implementation order for PH Agent Hub. Each phase has a clear entry condition, a definition of done, and references to the architecture docs it implements.

Phases are sequential. Do not start a phase until its entry condition is met.

---

## ✅ Phase 0 — Monorepo Scaffold (Completed)

**What was built:**
- Repository directory structure: `/backend`, `/frontend`, `/infrastructure`, `/docs`
- `Dockerfile` for backend (Python/FastAPI)
- `Dockerfile` for frontend (Node/React)
- `docker-compose.yml` (dev) and `docker-compose.prod.yml` (production) with all services: backend, frontend, mariadb, redis, minio, nginx, phpMyAdmin
- `infrastructure/env.example` with all required env vars
- `infrastructure/nginx.conf` (basic reverse proxy, SSE-ready, phpMyAdmin route)
- `.gitignore`
- MariaDB, Redis, and MinIO health checks passing
- Backend container starts, reaches the `alembic upgrade head` step (no migrations yet — no crash)

**Exit condition verified:**
- ✅ `docker compose up --build` starts all containers without errors
- ✅ `docker compose ps` shows all 7 services healthy
- ✅ nginx routes `/` to frontend (200), `/api/` to backend (backend responds), `/pma/` to phpMyAdmin
- ✅ MinIO console reachable at `:9001` (200)
- ✅ Alembic runs cleanly: "Context impl MySQLImpl"
- ✅ phpMyAdmin reachable at `:8080`

**References:** [deployment.md](../deployment.md), [architecture-overview.md](../architecture-overview.md)

---

## ✅ Phase 1 — Backend Foundation (Completed)

**What was built:**
- FastAPI application skeleton (`src/main.py`, routers registered but empty)
- `src/core/config.py` — loads and validates all env vars via Pydantic Settings
- `src/core/encryption.py` — Fernet encrypt/decrypt; single module rule
- `src/core/jwt.py` — encode/decode JWT; single module rule
- `src/core/exceptions.py` — shared exception types and HTTP error handlers
- `src/core/security.py` — password hashing
- `src/db/base.py` — SQLAlchemy 2.0 async session factory (`aiomysql`)
- All SQLAlchemy ORM models under `src/db/orm/` (one file per entity group)
- First Alembic migration: all 19 tables created
- `alembic upgrade head` runs cleanly on container startup
- `src/storage/s3.py` — MinIO client singleton; `upload_object`, `delete_object`, `generate_presigned_url`, `ensure_bucket_exists`

**Entry condition:** Phase 0 complete — all containers healthy.

**Exit condition verified:**
- ✅ `alembic upgrade head` runs to completion with no errors
- ✅ All 19 tables exist in MariaDB (verified via `SHOW TABLES`)
- ✅ `GET /health` returns `200 OK`
- ✅ Encryption round-trip test passes: encrypt a string, decrypt it, get the original back
- ✅ MinIO bucket creation succeeds from `s3.py`

**References:** [backend-architecture.md](../backend-architecture.md), [data-model.md](../data-model.md), [file-upload-architecture.md](../file-upload-architecture.md)

---

## ✅ Phase 2 — Authentication (Completed)

**What was built:**
- `POST /auth/login` — validate credentials, issue access token + refresh token (`httpOnly` cookie)
- `POST /auth/refresh` — validate refresh token cookie, issue new access token
- `GET /auth/me` — return authenticated user's profile
- `POST /auth/logout` — invalidate refresh token via Redis `jti` denylist
- JWT auth middleware (FastAPI dependency) injected on all protected endpoints
- Refresh token stored in `httpOnly` cookie; Redis denylist for revocation
- Password hashing via `bcrypt` in `security.py`
- Admin seed script: creates the first `admin` user and a default tenant on first run

**Entry condition:** Phase 1 complete — all tables exist, encryption and JWT modules working.

**Exit condition verified:**
- ✅ Login returns a valid JWT and sets `httpOnly` refresh cookie
- ✅ Expired or tampered JWT is rejected with `401`
- ✅ `/auth/refresh` issues a new access token without re-entering credentials
- ✅ Logout invalidates the refresh token; subsequent refresh attempts return `401`
- ✅ Seed script creates `admin` user and default tenant; subsequent runs are idempotent

**References:** [backend-architecture.md](../backend-architecture.md) §1.4, §7, [data-model.md](../data-model.md) §1.1

---

## ✅ Phase 3 — Admin: Tenants and Users (Completed)

**What gets built:**
- Tenant CRUD: `GET/POST/PUT/DELETE /admin/tenants` (admin only)
- User CRUD: `GET/POST/PUT/DELETE /admin/users` (admin sees all; manager scoped to own tenant)
- Role enforcement dependency: `require_admin`, `require_admin_or_manager` FastAPI dependencies
- Tenant-scope guard: manager requests filtered to own `tenant_id` from JWT
- Password reset by admin
- Activate / deactivate user accounts

**Entry condition:** Phase 2 complete — authentication working, JWT middleware injected.

**Exit condition verified:**
- ✅ Admin creates a tenant and a user in that tenant via API
- ✅ Manager lists and edits users within own tenant only; cross-tenant requests return `403`
- ✅ Admin-only endpoints return `403` for manager and user roles
- ✅ Deactivated users cannot log in
- ✅ Admin password reset — user logs in with new password
- ✅ Delete tenant with users returns clean `409`; empty tenant deletes successfully

**References:** [backend-architecture.md](../backend-architecture.md) §3.7, §3.8, [admin-area-architecture.md](../admin-area-architecture.md) §4.3, §4.4

---

## ✅ Phase 4 — Models and Tools (Completed)

**What was built:**
- Model CRUD: `GET/POST/PUT/DELETE /admin/models`
- `api_key` encrypted on write, decrypted on read via `EncryptedString` SQLAlchemy type
- Tool CRUD: `GET/POST/PUT/DELETE /admin/tools`
- ERPNext instance CRUD (stored in `erpnext_instances`; credentials encrypted)
- `GET /models` — user-facing endpoint returning enabled models for the requesting tenant
- MAF provider client factory in `src/models/` — resolves the correct `ChatClient` from a `models` row

**Entry condition:** Phase 3 complete — tenants and users exist.

**Exit condition verified:**
- ✅ Model `api_key` is stored encrypted; plaintext never appears in DB (verified by direct SQL inspection — `api_key` starts with `gAAAAAB` Fernet prefix)
- ✅ ERPNext `api_key` and `api_secret` both encrypted at rest
- ✅ `GET /models` returns only enabled models for the requesting user's tenant
- ✅ Disabled models are hidden from `GET /models`
- ✅ `api_key` never appears in any API response (`/models` or `/admin/models`)
- ✅ `api_secret` never appears in ERPNext responses
- ✅ Tool CRUD works with type validation (`erpnext`/`membrane`/`custom`)
- ✅ ERPNext instance CRUD at `/admin/tools/erpnext` with full admin/manager tenant scoping
- ✅ Backend starts without errors

**References:** [backend-architecture.md](../backend-architecture.md) §1.2, §1.3, [data-model.md](../data-model.md) §1.3, §1.4, §1.5, [agent-framework-integration.md](../agent-framework-integration.md) §3

---

## Phase 5 — Templates, Prompts and Skills

**What gets built:**
- Template CRUD: `GET/POST/PUT/DELETE /admin/templates` (admin + manager)
- Prompt CRUD: `GET/POST/PUT/DELETE /prompts` (user-owned)
- Skill CRUD: `GET/POST/PUT/DELETE /admin/skills` (admin + manager) and `GET/POST/PUT/DELETE /skills` (user-owned personal skills)
- `template_allowed_tools` and `skill_allowed_tools` join tables managed via CRUD
- MAF agent/workflow registry: `src/agents/registry.py` — scans `src/agents/skills/` and `src/agents/workflows/` at startup; warns on unknown `maf_target_key` values in DB

**Entry condition:** Phase 4 complete — models and tools exist.

**Exit condition (done when):**
- Admin can create a template with allowed tools; user can retrieve it via `GET /templates`
- User can create, edit, and delete their own personal skill
- Registry startup scan completes without errors; unknown `maf_target_key` emits a warning, not a crash

**References:** [data-model.md](../data-model.md) §2, [agent-framework-integration.md](../agent-framework-integration.md) §7

---

## Phase 6 — Chat: Basic Round-Trip (Non-Streaming)

**What gets built:**
- Session CRUD: `POST/GET/PUT/DELETE /chat/session`
- `POST /chat/session/:id/message` — sends a message, runs the MAF agent, returns the completed response as JSON (no streaming yet)
- MAF agent assembly in `src/agents/runner.py`: resolves model client, system prompt, skill, and active tools from session state; calls `agent.run()`
- DeepSeek stabilizer middleware (`src/agents/stabilizer.py`, `src/agents/deepseek_patch.py`)
- Message persistence: user message + assistant response written to `messages` table with `branch_index = 0`
- Session active tools: `GET/POST/DELETE /chat/session/:id/tools`
- Temporary session support (Redis TTL, no MariaDB write)

**Entry condition:** Phase 5 complete — templates, prompts, skills, and MAF registry working.

**Exit condition (done when):**
- Send a message to a session → receive a valid assistant response
- Response is persisted to `messages` table in MariaDB
- DeepSeek stabilizer strips `<think>` tokens from response
- Temporary session is stored in Redis only; verified by checking MariaDB (row must not exist)
- Tool call round-trip works: agent calls at least one tool and includes result in response

**References:** [agent-framework-integration.md](../agent-framework-integration.md), [deepseek-stabilizer.md](../deepseek-stabilizer.md), [data-model.md](../data-model.md) §3

---

## Phase 7 — Streaming

**What gets built:**
- `POST /chat/session/:id/message` upgraded to return `text/event-stream` when `Accept: text/event-stream` is set
- `DELETE /chat/session/:id/stream` — abort active stream
- All SSE event types implemented: `token`, `tool_start`, `tool_result`, `step_complete`, `message_complete`, `error`, `heartbeat`
- `sse-starlette` integrated into FastAPI response layer
- DeepSeek stabilizer filters `<think>` tokens from the token stream before SSE emission
- Heartbeat emitted every 15 seconds on idle connections

**Entry condition:** Phase 6 complete — non-streaming round-trip working end-to-end.

**Exit condition (done when):**
- Client receives a stream of `token` events followed by `message_complete`
- `tool_start` and `tool_result` events are emitted during a tool-calling run
- `DELETE /chat/session/:id/stream` cancels generation mid-stream
- `heartbeat` events are emitted on a 15-second interval
- No `<think>` content ever appears in any emitted event

**References:** [streaming-protocol.md](../streaming-protocol.md), [agent-framework-integration.md](../agent-framework-integration.md) §6

---

## Phase 8 — Chat: Remaining Features

**What gets built:**
- Message branching: edit and regenerate create new branches; `GET /chat/session/:id/messages` returns the branch tree
- Message soft-delete
- Message feedback: `POST /chat/session/:id/message/:msgId/feedback`
- Memory: `GET/POST/DELETE /memory`
- Full-text search: `GET /chat/sessions/search`
- File uploads: `POST/GET/DELETE /chat/session/:id/upload`, presigned URL endpoint
- Session pinning and title editing

**Entry condition:** Phase 7 complete — streaming working.

**Exit condition (done when):**
- Editing a message creates a new branch; original branch remains accessible
- Memory entries are created automatically by the agent and manually by the user
- Full-text search returns relevant sessions and messages scoped to the user
- File upload stores object in MinIO; presigned URL is valid and returns the file
- Uploads blocked for temporary sessions (`403` returned)

**References:** [chat-area-architecture.md](../chat-area-architecture.md), [file-upload-architecture.md](../file-upload-architecture.md), [data-model.md](../data-model.md) §3, §4, §5

---

## Phase 9 — Admin: Analytics and Audit

**What gets built:**
- Usage log writes on every completed agent run (tokens in/out, model, user, tenant)
- `GET /admin/usage` — token usage analytics (admin: all tenants; manager: own tenant)
- `GET /admin/logs` — error and agent activity logs
- `GET /admin/audit` — audit log (admin only; read-only)
- Audit log writes on all mutating admin operations (user create/delete, model add, tool enable/disable, etc.)
- System settings endpoints (admin only)

**Entry condition:** Phase 8 complete — full chat flow working.

**Exit condition (done when):**
- Every completed message writes a `usage_logs` row
- Every admin mutation writes an `audit_logs` row
- `GET /admin/audit` returns audit entries; manager role receives `403`
- Audit log has no delete endpoint (verified: `DELETE /admin/audit` returns `405`)

**References:** [backend-architecture.md](../backend-architecture.md) §3.13, [data-model.md](../data-model.md) §6, [admin-area-architecture.md](../admin-area-architecture.md) §4.9

---

## Phase 10 — Frontend

**What gets built:**
- React + TypeScript app scaffold with Vite
- Shared: `AuthProvider`, `QueryProvider`, `TenantProvider`, API client (`api.ts`), route guards
- Chat area: all components from [chat-area-architecture.md](../chat-area-architecture.md)
  - SSE streaming client using `@microsoft/fetch-event-source`
  - Session sidebar, message thread, branch navigation, feedback controls
  - Model selector, template/prompt/skill selectors
  - Memory manager, tool activation, file upload, session search
- Admin area: Refine-based CRUD screens for users, tenants, models, tools, templates, skills, analytics

**Entry condition:** Phase 9 complete — all backend APIs stable.

**Exit condition (done when):**
- User can log in, start a chat session, send a message, and see a streaming response
- Admin can manage users, models, and tools via the admin area
- JWT is stored in memory (not `localStorage`); verified via browser devtools
- `user` role cannot reach any `/admin` route

**References:** [frontend-architecture.md](../frontend-architecture.md), [chat-area-architecture.md](../chat-area-architecture.md), [admin-area-architecture.md](../admin-area-architecture.md), [streaming-protocol.md](../streaming-protocol.md)

---

## Phase 11 — RAG (Optional)

**What gets built:**
- Vector DB service added to both `docker-compose.yml` (dev) and `docker-compose.prod.yml` (production with Traefik labels) — Qdrant recommended
- Document ingestion pipeline: upload → extract text → embed → store in vector DB + `rag_documents` table
- Retrieval integrated into agent context assembly (top-k similarity search before agent run)
- Admin UI for RAG document management

**Entry condition:** Phase 10 complete. Vector DB provider decided.

**Exit condition (done when):**
- Uploaded document is embedded and retrievable
- Agent includes relevant document chunks in context when answering a related question
- Retrieval is scoped to tenant (no cross-tenant document access)

**References:** [data-model.md](../data-model.md) §4.2, [architecture-overview.md](../architecture-overview.md)
