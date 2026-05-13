# Epic: General Tools (Priority 2)

## Checklist

### Phase 2a — High Impact
- [ ] **`code_interpreter`** — Docker-sandboxed Python execution. Agent-authored code for data analysis, charts, file transforms. AST-validated (no os/eval/exec), timeout-limited, no network by default. Output artifacts to MinIO/S3.

### Phase 2b — Enterprise
- [ ] **`sql_query`** — Read-only SQL against tenant-configured database. AST-validated (DML/DROP/GRANT rejected). Per-tenant encrypted connection strings. Row-limited results.
- [ ] **`document_generation`** — Markdown → PDF (weasyprint), list-of-dicts → Excel (openpyxl, already installed), CSV export. Output to MinIO/S3.
- [ ] **`browser`** — Playwright headless Chromium in sandbox container. Screenshot pages, extract rendered text, extract tables. IP-restricted (no internal network access).

### Phase 2c — Integrations
- [ ] **`rag_search`** — Semantic search across uploaded documents. Embedding (OpenAI or local sentence-transformers) + vector store (pgvector or Qdrant). Chunked document indexing.
- [ ] **`github`** — Search code, list issues/PRs, read files from GitHub/GitLab repos. PAT stored encrypted. Repo allowlist.
- [ ] **`calendar`** — Google Calendar or CalDAV. List/create events, find free slots. OAuth per user or service account at tenant level.

### Phase 2d — Communication
- [ ] **`image_generation`** — DALL·E / Stable Diffusion / Flux via API. Prompt → image URL. Stored in MinIO/S3.
- [ ] **`slack`** / **`email`** — Send messages to Slack channels, send emails via SMTP or SendGrid API.

## New Dependencies
```txt
# code_interpreter: Docker infrastructure (new)
# sql_query: SQLAlchemy (already installed), encryption (already installed)
weasyprint, markdown  # document_generation
playwright            # browser (+ playwright install chromium)
sentence-transformers, pgvector  # rag_search
PyGithub, python-gitlab  # github
```

## Implementation Pattern
Each tool follows the standard 5-step pattern:
1. Create `backend/src/tools/TOOL_NAME.py` with `build_TOOL_NAME_tools(tool_config)` factory
2. Add type string to `VALID_TOOL_TYPES` in `backend/src/services/tool_service.py`
3. Create Alembic migration: `ALTER TYPE tool_type_enum ADD VALUE 'new_type'`
4. Add `elif tool.type == "new_type":` branch in `_build_tool_callables()` in `backend/src/agents/runner.py`
5. (Optional) Add config fields in `frontend/src/features/admin/resources/tools/ToolForm.tsx`

## Reference
Full details in `docs/planning/tools.md` → General Tools section.
