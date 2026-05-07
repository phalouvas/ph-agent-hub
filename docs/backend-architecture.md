# Backend Architecture — PH Agent Hub

The backend of PH Agent Hub is the core service responsible for agent execution, model orchestration, tool integration, authentication, multi-tenant routing, and all persistent data operations. It exposes the APIs and streaming interfaces consumed by the single React frontend, which contains separate chat and admin areas.

This document defines the backend's responsibilities, internal structure, and integration points.

---

## 1. Backend Responsibilities

The backend provides the following core capabilities:

### **1.1 Agent Execution**
- Runs agent loops using the Microsoft Agent Framework
- Supports multi‑step reasoning and tool calling
- Provides a DeepSeek‑compatible stabilization layer (JSON repair, retries, output filtering)
- Supports streaming responses and agent events to the chat area

### **1.2 Model Orchestration**
- Supports multiple model providers (DeepSeek, OpenAI, Anthropic, local models, etc.)
- Allows per‑tenant model configuration
- Allows administrators to enable/disable models
- Provides routing logic for selecting the correct model per request

### **1.3 Tool Execution**
- ERPNext API tools (per‑tenant)
- Membrane tools
- Custom tools (Python modules)
- Tool permission enforcement based on user roles and tenant settings

### **1.4 Authentication & Authorization**
- JWT‑based authentication
- User roles (admin, user)
- Tenant isolation
- Per‑tenant model and tool access rules

### **1.5 Data Storage**
- Users, roles, tenants
- Models and tool configurations
- Templates, user prompts, and skills
- Chat sessions and messages
- Memory and RAG documents
- ERPNext instance configurations

### **1.6 Multi‑Tenant Routing**
Each request is routed based on:
- JWT tenant claim
- Tenant‑specific model list
- Tenant‑specific tool list
- Tenant‑specific ERPNext instance (optional)
- Tenant‑specific templates and shared skills
- User‑owned prompts and personal skills within the tenant boundary

### **1.7 Extensibility**
The backend is designed to be fully patchable:
- Custom model adapters
- DeepSeek monkey‑patching
- Custom tool runners
- Custom agent behaviors
- Skill definitions mapped to Microsoft Agent Framework agents and workflows
- Middleware for request/response processing

---

## 2. High‑Level Backend Architecture

```
┌──────────────────────────────────────────────┐
│                API Layer (REST)              │
│  - Auth endpoints                             │
│  - Chat endpoints                             │
│  - Admin endpoints                            │
└──────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────┐
│          Agent Orchestration Layer           │
│  - Agent loop                                │
│  - Tool calling                              │
│  - DeepSeek stabilizer                       │
│  - Model routing                             │
└──────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────┐
│              Integration Layer               │
│  - Model adapters                            │
│  - ERPNext client                            │
│  - Membrane client                           │
│  - Custom tools                              │
└──────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────┐
│               Persistence Layer              │
│  - MariaDB (primary DB)                      │
│  - Redis (cache, queues, memory)             │
│  - Optional vector DB                        │
└──────────────────────────────────────────────┘
```

---

## 3. API Structure

### **3.1 Authentication**
```
POST /auth/login
POST /auth/refresh
GET  /auth/me
```

### **3.2 Chat**
```
POST /chat/session
GET  /chat/session/:id
POST /chat/session/:id/message
GET  /chat/session/:id/messages
GET  /chat/session/:id/stream
DELETE /chat/session/:id
```

### **3.3 User-Facing Configuration**
```
GET  /models
GET  /templates
GET  /prompts
POST /prompts
PUT  /prompts/:id
DELETE /prompts/:id
GET  /skills
POST /skills
PUT  /skills/:id
DELETE /skills/:id
```

### **3.4 Admin Users**
```
GET    /admin/users
POST   /admin/users
PUT    /admin/users/:id
DELETE /admin/users/:id
```

### **3.5 Admin Tenants**
```
GET    /admin/tenants
POST   /admin/tenants
PUT    /admin/tenants/:id
DELETE /admin/tenants/:id
```

### **3.6 Admin Models**
```
GET    /admin/models
POST   /admin/models
PUT    /admin/models/:id
DELETE /admin/models/:id
```

### **3.7 Admin Tools**
```
GET    /admin/tools
POST   /admin/tools
PUT    /admin/tools/:id
DELETE /admin/tools/:id
```

### **3.8 Admin Templates**
```
GET    /admin/templates
POST   /admin/templates
PUT    /admin/templates/:id
DELETE /admin/templates/:id
```

### **3.9 Admin Skills**
```
GET    /admin/skills
POST   /admin/skills
PUT    /admin/skills/:id
DELETE /admin/skills/:id
```

### **3.10 Admin Analytics**
```
GET /admin/usage
GET /admin/logs
```

---

## 4. Backend Folder Structure

```
/backend
  /src
    /api
      auth.py
      chat.py
      prompts.py
      skills.py
      admin.py
    /agents
      runner.py
      stabilizer.py
      deepseek_patch.py
    /models
      base.py
      deepseek.py
      openai.py
      anthropic.py
    /tools
      erpnext.py
      membrane.py
      custom/
    /services
      user_service.py
      tenant_service.py
      model_service.py
      tool_service.py
      template_service.py
      prompt_service.py
      skill_service.py
    /db
      schema.sql
      migrations/
    /core
      config.py
      security.py
      jwt.py
      exceptions.py
  Dockerfile
```

---

## 5. DeepSeek Stabilization Layer

The backend includes a dedicated stabilization module responsible for:

- Stripping `<think>` reasoning tokens
- Repairing invalid JSON
- Validating tool calls
- Retrying failed model outputs
- Enforcing schema compliance
- Filtering hallucinated tool names
- Preventing infinite agent loops

This module is fully monkey‑patchable.

---

## 6. Multi‑Tenant Logic

Each request includes a JWT with:

- `user_id`
- `tenant_id`
- `roles`
- `permissions`

The backend enforces:

- tenant‑specific model lists
- tenant‑specific tool lists
- tenant‑specific ERPNext instance
- tenant‑specific templates and shared skills
- user‑scoped prompts and personal skills

No data is shared across tenants.

---

## 7. Deployment

The backend runs as a Docker container and depends on:

- MariaDB
- Redis
- Optional vector DB
- Nginx reverse proxy

It is designed for both single‑server and multi‑server deployments.

---

## 8. Goals of the Backend

- Provide a stable, extensible agent runtime
- Support DeepSeek and other advanced models
- Enable multi‑tenant AI applications
- Provide clean APIs for both frontend areas
- Allow safe monkey‑patching and customization
- Maintain strict separation of concerns
