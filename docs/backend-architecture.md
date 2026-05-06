# Backend Architecture — PH Agent Hub

The backend of PH Agent Hub is the core service responsible for agent execution, model orchestration, tool integration, authentication, multi‑tenant routing, and all persistent data operations. It exposes a clean REST API consumed by both the Chat UI and the Admin UI.

This document defines the backend’s responsibilities, internal structure, and integration points.

---

## 1. Backend Responsibilities

The backend provides the following core capabilities:

### **1.1 Agent Execution**
- Runs agent loops using the Microsoft Agent Framework
- Supports multi‑step reasoning and tool calling
- Provides a DeepSeek‑compatible stabilization layer (JSON repair, retries, output filtering)
- Supports streaming responses to the Chat UI

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
- Template prompts
- Chat sessions and messages
- Memory and RAG documents
- ERPNext instance configurations

### **1.6 Multi‑Tenant Routing**
Each request is routed based on:
- JWT tenant claim
- Tenant‑specific model list
- Tenant‑specific tool list
- Tenant‑specific ERPNext instance (optional)

### **1.7 Extensibility**
The backend is designed to be fully patchable:
- Custom model adapters
- DeepSeek monkey‑patching
- Custom tool runners
- Custom agent behaviors
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
```

### **3.3 Models**
```
GET  /models
POST /models
PUT  /models/:id
DELETE /models/:id
```

### **3.4 Tools**
```
GET  /tools
POST /tools
PUT  /tools/:id
DELETE /tools/:id
```

### **3.5 Tenants**
```
GET  /tenants
POST /tenants
PUT  /tenants/:id
DELETE /tenants/:id
```

### **3.6 Template Prompts**
```
GET  /templates
POST /templates
PUT  /templates/:id
DELETE /templates/:id
```

---

## 4. Backend Folder Structure

```
/backend
  /src
    /api
      auth.py
      chat.py
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
- tenant‑specific template prompts

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
- Provide clean APIs for both UIs
- Allow safe monkey‑patching and customization
- Maintain strict separation of concerns
