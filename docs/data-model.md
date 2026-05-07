# Data Model — PH Agent Hub

This document defines the database schema for PH Agent Hub.  
The platform uses MariaDB as the primary relational database and Redis for caching, queues, and ephemeral memory.

The schema is implemented as **SQLAlchemy 2.0 ORM models** (one file per entity group under `/backend/src/db/orm/`). Schema changes are versioned and applied via **Alembic** migration scripts. The tables, columns, and constraints defined below map directly to those ORM models.

Because MariaDB is the primary store, relationships that require joins or referential integrity are normalized into dedicated tables. JSON columns are reserved for flexible payloads that are typically stored and retrieved as complete documents.

The data model supports:
- multi‑tenant architecture
- user/role management (admin, manager, user)
- model and tool configuration
- ERPNext instance routing
- curated templates, user prompts, and reusable skills
- personal user-owned skills
- chat sessions and messages
- memory and RAG documents
- session-level tool activation per user

---

# 1. Core Entities

## 1.1 Users

Users belong to a single tenant and authenticate via JWT.
Roles:
- **admin** — platform-wide superuser; manages all tenants, platform settings, and global configuration
- **manager** — tenant-scoped operator; can create and manage tools, models, templates, skills, and users within their own tenant only
- **user** — end user; accesses the chat area within their tenant
**Table: users**
- id (UUID, PK)
- tenant_id (UUID, FK → tenants.id)
- email (string, unique)
- password_hash (string)
- display_name (string)
- role (enum: admin, manager, user)
- is_active (boolean)
- created_at (timestamp)
- updated_at (timestamp)

---

## 1.2 Tenants

Tenants isolate:
- users
- models
- tools
- ERPNext instances
- templates
- prompts
- skills
- sessions

**Table: tenants**
- id (UUID, PK)
- name (string, unique)
- created_at (timestamp)
- updated_at (timestamp)

---

## 1.3 Models

Administrators configure models per tenant.

**Table: models**
- id (UUID, PK)
- tenant_id (UUID, FK → tenants.id)
- name (string) — e.g., "deepseek-r1"
- provider (string) — e.g., "deepseek", "openai", "anthropic"
- api_key (string) — stored encrypted using Fernet symmetric encryption; decrypted in memory at runtime by `/backend/src/core/encryption.py`
- base_url (string, nullable)
- enabled (boolean)
- max_tokens (int)
- temperature (float)
- routing_priority (int)
- created_at (timestamp)
- updated_at (timestamp)

---

## 1.4 Tools

Tools represent external integrations (ERPNext, Membrane, custom tools).

**Table: tools**
- id (UUID, PK)
- tenant_id (UUID, FK → tenants.id)
- name (string)
- type (enum: erpnext, membrane, custom)
- config (JSON)
- enabled (boolean)
- created_at (timestamp)
- updated_at (timestamp)

---

## 1.5 ERPNext Instances (Tool Subtype)

Stored as a tool config, but also available as a dedicated table for convenience.

**Table: erpnext_instances**
- id (UUID, PK)
- tenant_id (UUID, FK → tenants.id)
- base_url (string)
- api_key (string) — stored encrypted using Fernet symmetric encryption
- api_secret (string) — stored encrypted using Fernet symmetric encryption
- version (string)
- created_at (timestamp)
- updated_at (timestamp)

---

# 2. Templates, Prompts & Skills

## 2.1 Templates

Templates are curated prompt assets managed by administrators. They provide approved starting configurations for end users and skills.

Templates can be:
- tenant‑wide
- role‑restricted
- explicitly assigned to a specific user

**Table: templates**
- id (UUID, PK)
- tenant_id (UUID, FK → tenants.id)
- title (string)
- description (string)
- system_prompt (text)
- default_model_id (UUID, FK → models.id, nullable)
- scope (enum: tenant, role, user)
- assigned_user_id (UUID, FK → users.id, nullable)
- created_at (timestamp)
- updated_at (timestamp)

Allowed tools are normalized through a join table rather than stored as a JSON array.

**Table: template_allowed_tools**
- template_id (UUID, FK → templates.id)
- tool_id (UUID, FK → tools.id)
- created_at (timestamp)

## 2.2 Prompts

Prompts are reusable user-authored instruction assets. They are personal by default, but the model allows future tenant sharing.

**Table: prompts**
- id (UUID, PK)
- tenant_id (UUID, FK → tenants.id)
- user_id (UUID, FK → users.id)
- template_id (UUID, FK → templates.id, nullable)
- title (string)
- description (string)
- content (text)
- visibility (enum: private, tenant)
- created_at (timestamp)
- updated_at (timestamp)

## 2.3 Skills

Skills are reusable execution profiles for the Microsoft Agent Framework. A skill can point to a registered agent or workflow and bundle together defaults such as model, prompt, template, and allowed tools.

Skills can be:
- tenant‑shared and administrator managed
- user‑specific and privately owned

**Table: skills**
- id (UUID, PK)
- tenant_id (UUID, FK → tenants.id)
- user_id (UUID, FK → users.id, nullable)
- title (string)
- description (string)
- execution_type (enum: agent, workflow)
- maf_target_key (string) — registered Microsoft Agent Framework agent or workflow identifier
- template_id (UUID, FK → templates.id, nullable)
- default_prompt_id (UUID, FK → prompts.id, nullable)
- default_model_id (UUID, FK → models.id, nullable)
- visibility (enum: tenant, user)
- enabled (boolean)
- created_at (timestamp)
- updated_at (timestamp)

**Table: skill_allowed_tools**
- skill_id (UUID, FK → skills.id)
- tool_id (UUID, FK → tools.id)
- created_at (timestamp)

---

# 3. Chat Sessions & Messages

## 3.1 Sessions

A session belongs to a user and a tenant.

**Table: sessions**
- id (UUID, PK)
- tenant_id (UUID, FK → tenants.id)
- user_id (UUID, FK → users.id)
- title (string)
- is_temporary (boolean, default false) — temporary sessions are not persisted to MariaDB; they are stored in Redis with a TTL and purged on logout or expiry
- is_pinned (boolean, default false) — pinned sessions appear at the top of the session list
- selected_template_id (UUID, FK → templates.id, nullable)
- selected_prompt_id (UUID, FK → prompts.id, nullable)
- selected_skill_id (UUID, FK → skills.id, nullable)
- created_at (timestamp)
- updated_at (timestamp)

Active tools for a session are tracked via a join table. A user can only activate tools that are enabled for their tenant.

**Table: session_active_tools**
- session_id (UUID, FK → sessions.id)
- tool_id (UUID, FK → tools.id)
- created_at (timestamp)

---

## 3.2 Messages

Messages belong to a session and support branching. Editing a message or regenerating a response creates a new branch rather than overwriting the original. The active branch is tracked per session.

Message content is a structured JSON array of parts to support multi-modal messages (text, images, tool output). This allows mixed content and rich rendering without a schema migration later.

**Table: messages**
- id (UUID, PK)
- session_id (UUID, FK → sessions.id)
- parent_message_id (UUID, FK → messages.id, nullable) — null for the root message of each branch
- branch_index (int, default 0) — position within sibling branches sharing the same parent
- sender (enum: user, assistant, system)
- content (JSON array of parts) — each part has a `type` (text | image | tool_output) and corresponding payload
- model_id (UUID, FK → models.id, nullable)
- tool_calls (JSON)
- is_deleted (boolean, default false) — soft delete; message is hidden but branch integrity is preserved
- created_at (timestamp)
- updated_at (timestamp)

**Table: message_feedback**
- id (UUID, PK)
- message_id (UUID, FK → messages.id)
- user_id (UUID, FK → users.id)
- rating (enum: up, down)
- comment (text, nullable)
- created_at (timestamp)

Feedback is recorded for assistant messages only and is used for model quality analytics.

---

## 3.3 Search

Full-text search across a user's sessions and messages is supported via MariaDB full-text indexes on `sessions.title` and the text parts within `messages.content`. Search is scoped to the authenticated user's own data within their tenant.

---

# 4. Memory & RAG

## 4.1 Memory Items

Memory is stored per user and optionally scoped to a session. Users can view, delete, and manually add memory entries via the chat area.

**Table: memory**
- id (UUID, PK)
- tenant_id (UUID, FK → tenants.id)
- user_id (UUID, FK → users.id)
- session_id (UUID, FK → sessions.id, nullable)
- key (string)
- value (text)
- source (enum: automatic, manual) — whether the entry was created by the agent or manually by the user
- created_at (timestamp)

---

## 4.2 RAG Documents

Optional vector DB integration (Qdrant, Milvus, etc.).

**Table: rag_documents**
- id (UUID, PK)
- tenant_id (UUID, FK → tenants.id)
- title (string)
- content (text)
- metadata (JSON)
- vector_id (string) — reference to vector DB
- created_at (timestamp)

---

# 5. File Uploads

Files are stored in MinIO (S3-compatible object storage). The `file_uploads` table tracks metadata; the actual objects live in MinIO.

**Table: file_uploads**
- id (UUID, PK)
- tenant_id (UUID, FK → tenants.id)
- user_id (UUID, FK → users.id)
- session_id (UUID, FK → sessions.id, nullable)
- message_id (UUID, FK → messages.id, nullable) — linked after the message is persisted
- original_filename (string)
- content_type (string) — MIME type
- size_bytes (int)
- storage_key (string) — full object key within the tenant bucket
- bucket (string) — MinIO bucket name
- is_temporary (boolean, default false) — mirrors the parent session's temporary flag
- created_at (timestamp)

> Uploads are blocked for temporary sessions at the API level. The `is_temporary` flag is stored for auditing purposes only.

---

# 6. Audit & Logging

## 6.1 Usage Logs

Tracks model usage for analytics and quotas.

**Table: usage_logs**
- id (UUID, PK)
- tenant_id (UUID, FK → tenants.id)
- user_id (UUID, FK → users.id)
- model_id (UUID, FK → models.id)
- tokens_in (int)
- tokens_out (int)
- created_at (timestamp)

---

# 7. Relationships Summary

```
Tenant
 ├── Users (admin | manager | user)
 ├── Models
 ├── Tools
 │     └── ERPNext Instances
 ├── Templates
 │     └── Template Allowed Tools
 ├── Prompts
 ├── Skills (tenant-shared or user-owned)
 │     └── Skill Allowed Tools
 ├── Sessions (permanent or temporary)
 │     ├── Messages (branching tree)
 │     │     └── Message Feedback
 │     ├── Session Active Tools
 │     └── File Uploads
 ├── Memory (per user, optionally per session)
 └── RAG Documents
```

---

---

# 9. Encryption of Sensitive Fields

Fields marked as encrypted in this schema use **application-level Fernet symmetric encryption** (AES-128-CBC with HMAC-SHA256) provided by the Python [`cryptography`](https://cryptography.io) library.

- The encryption key is derived from the `ENCRYPTION_KEY` environment variable using `base64.urlsafe_b64encode`
- Encryption and decryption are performed exclusively in `/backend/src/core/encryption.py`
- No other module in the codebase calls the `cryptography` library directly
- Encrypted values are stored as base64-encoded ciphertext strings in the database
- The encryption key must be 32 bytes, base64url-encoded; generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- If the `ENCRYPTION_KEY` is rotated, all encrypted fields must be re-encrypted; a migration utility must be provided

**Encrypted fields:**
- `models.api_key`
- `erpnext_instances.api_key`
- `erpnext_instances.api_secret`

---

# 8. Goals of the Data Model

- Support multi‑tenant isolation
- Support three-tier role model (admin, manager, user)
- Support flexible model and tool configuration
- Support curated templates, personal prompts, and reusable skills (tenant-shared and user-owned)
- Enable session-level tool activation by end users within tenant-approved boundaries
- Enable user-managed memory (view, delete, manually add)
- Support temporary sessions via Redis with TTL alongside permanent MariaDB sessions
- Support session pinning and title editing
- Support message branching for edits and regeneration without data loss
- Support multi-modal message content via structured JSON parts
- Support message feedback (thumbs up/down) for analytics
- Enable full-text search across sessions and messages
- Enable DeepSeek‑compatible agent workflows
- Provide clean storage for sessions, messages, and memory
- Allow future expansion (billing, quotas, analytics)