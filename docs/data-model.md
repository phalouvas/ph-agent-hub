# Data Model — PH Agent Hub

This document defines the database schema for PH Agent Hub.  
The platform uses MariaDB as the primary relational database and Redis for caching, queues, and ephemeral memory.

Because MariaDB is the primary store, relationships that require joins or referential integrity are normalized into dedicated tables. JSON columns are reserved for flexible payloads that are typically stored and retrieved as complete documents.

The data model supports:
- multi‑tenant architecture
- user/role management
- model and tool configuration
- ERPNext instance routing
- template prompts
- chat sessions and messages
- memory and RAG documents

---

# 1. Core Entities

## 1.1 Users

Users belong to a single tenant and authenticate via JWT.

**Table: users**
- id (UUID, PK)
- tenant_id (UUID, FK → tenants.id)
- email (string, unique)
- password_hash (string)
- display_name (string)
- role (enum: admin, user)
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
- api_key (string, encrypted)
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
- api_key (string, encrypted)
- api_secret (string, encrypted)
- version (string)
- created_at (timestamp)
- updated_at (timestamp)

---

# 2. Templates & Prompts

## 2.1 Template Prompts

Templates can be:
- global to tenant
- user‑specific

**Table: templates**
- id (UUID, PK)
- tenant_id (UUID, FK → tenants.id)
- user_id (UUID, FK → users.id, nullable)
- title (string)
- description (string)
- system_prompt (text)
- default_model_id (UUID, FK → models.id, nullable)
- created_at (timestamp)
- updated_at (timestamp)

Allowed tools are normalized through a join table rather than stored as a JSON array.

**Table: template_allowed_tools**
- template_id (UUID, FK → templates.id)
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
- created_at (timestamp)
- updated_at (timestamp)

---

## 3.2 Messages

Messages belong to a session.

**Table: messages**
- id (UUID, PK)
- session_id (UUID, FK → sessions.id)
- sender (enum: user, assistant, system)
- content (text)
- model_id (UUID, FK → models.id, nullable)
- tool_calls (JSON)
- created_at (timestamp)

---

# 4. Memory & RAG

## 4.1 Memory Items

Memory is stored per session or per tenant.

**Table: memory**
- id (UUID, PK)
- tenant_id (UUID, FK → tenants.id)
- session_id (UUID, FK → sessions.id, nullable)
- key (string)
- value (text)
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

# 5. Audit & Logging

## 5.1 Usage Logs

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

# 6. Relationships Summary

```
Tenant
 ├── Users
 ├── Models
 ├── Tools
 │     └── ERPNext Instances
 ├── Templates
 │     └── Template Allowed Tools
 ├── Sessions
 │     └── Messages
 ├── Memory
 └── RAG Documents
```

---

# 7. Goals of the Data Model

- Support multi‑tenant isolation
- Support flexible model and tool configuration
- Enable DeepSeek‑compatible agent workflows
- Provide clean storage for sessions, messages, and memory
- Allow future expansion (billing, quotas, analytics)