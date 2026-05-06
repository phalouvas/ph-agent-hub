# PH Agent Hub — Architecture Overview

PH Agent Hub is a modular, multi‑tenant AI platform designed to provide a stable, extensible environment for agent‑driven applications. The system is structured as a monorepo containing three core applications:

- **Backend (Agent Framework Server)**
- **User Chat UI**
- **Admin Management UI**

The platform is fully containerized using Docker and includes supporting services such as Postgres and Redis.

---

## 1. High‑Level Architecture

PH Agent Hub is built around a clean separation of responsibilities:

### **1. Backend (Agent Framework Server)**
The backend is the core of the platform. It provides:

- Multi‑model orchestration (DeepSeek, OpenAI, Anthropic, etc.)
- Agent loop execution and tool calling
- DeepSeek‑compatible stabilization layer (JSON repair, retry logic, output filtering)
- Multi‑tenant routing
- User authentication (JWT)
- Session + message storage
- Memory + RAG
- ERPNext and external system integrations (via tools)
- REST API for both UIs

The backend is fully patchable and extensible, allowing custom model adapters, tool runners, and agent behaviors.

---

## 2. User Chat UI

A lightweight, modern chat interface used by end‑users.  
It provides:

- Chat sessions
- Model selection
- Template prompt selection
- File uploads
- Memory display
- Authentication via backend‑issued JWT
- Real‑time streaming responses

The Chat UI contains **no admin logic** and does not store any data locally.

---

## 3. Admin Management UI

A dedicated control panel for platform administrators.  
It provides:

- User management (create, delete, roles)
- Tenant management
- Model configuration (API keys, routing rules, enable/disable)
- Tool configuration (ERPNext instances, Membrane, custom tools)
- Template prompt management
- Usage analytics and logs
- System configuration

This UI communicates exclusively with the backend API.

---

## 4. Monorepo Structure

The repository is organized as:

```
/backend
/chat-ui
/admin-ui
/infrastructure
/docs
```

Each component has its own Dockerfile and is orchestrated via `docker-compose`.

---

## 5. Deployment Architecture

PH Agent Hub is deployed as a set of Docker services:

- **backend** — Agent Framework server
- **chat-ui** — user-facing chat interface
- **admin-ui** — administrator interface
- **postgres** — primary database
- **redis** — caching, queues, memory store
- **optional vector DB** — for RAG
- **nginx** — reverse proxy

This structure supports both single‑server and multi‑server deployments.

---

## 6. Multi‑Tenant Design

The backend supports multiple tenants, each with:

- isolated users
- isolated models
- isolated tools
- isolated ERPNext instances (optional)
- isolated template prompts

Tenants are enforced at the backend level using JWT claims.

---

## 7. Extensibility and Monkey‑Patching

PH Agent Hub is designed to allow:

- custom model adapters
- DeepSeek stabilization patches
- custom tool runners
- custom agent behaviors
- custom routing logic

This ensures compatibility with evolving LLM behaviors and enterprise integrations.

---

## 8. Goals of the Platform

PH Agent Hub aims to provide:

- A stable alternative to monolithic chat systems
- A clean architecture for agent‑driven workflows
- A flexible backend for multi‑model orchestration
- A scalable foundation for enterprise AI applications
- A modular system that can be extended without breaking core functionality

---

## 9. Next Steps

Additional documentation is provided in:

- `backend-architecture.md`
- `data-model.md`
- `admin-ui-architecture.md`
- `chat-ui-architecture.md`
- `deployment.md`
- `deepseek-stabilizer.md`

These documents define the detailed implementation plan for PH Agent Hub.
