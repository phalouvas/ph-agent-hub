# Frontend Architecture — PH Agent Hub

The frontend of PH Agent Hub is a single React web application that exposes two protected product areas:

- **Chat Area** for end users
- **Admin Area** for administrators

This document defines the shared frontend architecture that sits above both areas.

---

## 1. Frontend Role in the System

The frontend is a thin client over the backend and the Microsoft Agent Framework runtime.

The frontend is responsible for:

- authentication and token refresh UX
- route protection and role-aware navigation
- rendering chat conversations and streamed agent output
- rendering administrative resources and CRUD screens
- file upload UX
- prompt, template, skill, and configuration selection UIs

The frontend is **not** responsible for:

- running agents or workflows
- executing tools
- enforcing authorization rules
- storing authoritative conversation or configuration state

Those responsibilities remain in the backend.

---

## 2. Guiding Principles

### **2.1 One App, Two Areas**
- One React codebase
- One deployable frontend service
- Separate route domains, layouts, and feature modules for chat and admin

### **2.2 Backend-Authoritative Behavior**
- The backend owns sessions, prompts, templates, skills, tools, permissions, and agent execution
- Frontend role checks are for UX only; backend authorization is authoritative

### **2.3 Shared Foundation**
- Shared authentication provider
- Shared API client
- Shared design system and UI primitives
- Shared query, mutation, and error handling patterns

### **2.4 Controlled Specialization**
- Chat area uses fully custom React components
- Admin area may use Refine Core where it accelerates CRUD-heavy screens
- Analytics, logs, and agent-specific operational views remain custom when needed

---

## 3. Technology Stack

Recommended stack:

- **React**
- **TypeScript**
- **React Router**
- **TanStack Query** for data fetching and mutations
- **SSE or WebSockets** for streaming responses and agent events
- **TailwindCSS, Material UI, or another shared design system**
- **Refine Core** for the admin area only

The frontend should remain framework-light and avoid duplicating backend behavior.

---

## 4. High-Level Architecture

```
┌──────────────────────────────────────────────────────┐
│             Frontend React Web App                  │
│                                                      │
│  ┌────────────────────┐  ┌────────────────────────┐  │
│  │   Chat Area        │  │      Admin Area         │  │
│  │ - chat sessions    │  │ - users/tenants        │  │
│  │ - streaming UI     │  │ - models/tools         │  │
│  │ - files/templates  │  │ - templates/skills     │  │
│  │ - prompts/skills   │  │ - analytics/settings   │  │
│  │ - memory manager   │  │ role-aware: admin sees │  │
│  │ - tool activation  │  │ all; manager sees only │  │
│  │ - personal skills  │  │ their tenant scope     │  │
│  └────────────────────┘  └────────────────────────┘  │
│                                                      │
│  Shared: auth, API client, tenant context, routing   │
└───────────────────────────────┬──────────────────────┘
                                │ REST + SSE/WebSocket
                                ▼
┌──────────────────────────────────────────────────────┐
│          Backend + Microsoft Agent Framework        │
└──────────────────────────────────────────────────────┘
```

---

## 5. Route Structure

Suggested route domains:

```
/
/login
/chat
/chat/:sessionId
/admin
/admin/users
/admin/tenants
/admin/models
/admin/tools
/admin/templates
/admin/skills
/admin/analytics
/admin/settings
```

Admin routes under `/admin/tenants` and `/admin/settings` are visible to `admin` only. All other `/admin` routes are accessible to both `admin` and `manager`, with the backend enforcing tenant scope for managers.

---

## 6. Shared Frontend Modules

Suggested structure:

```
/frontend
  /src
    /app
      App.tsx
      router.tsx
    /providers
      AuthProvider.tsx
      QueryProvider.tsx
      TenantProvider.tsx
    /services
      api.ts
      auth.ts
    /shared
      /components
      /layouts
      /theme
      /utils
    /features
      /chat
      /admin
```

The chat and admin areas should share foundations, but not implementation details that make the code harder to reason about.

---

## 7. Authentication and Access Control

- JWT is stored in memory, not localStorage
- Initial app bootstrap loads authenticated user, role, and tenant context
- Three roles carried in JWT: `admin`, `manager`, `user`
- Route guards:
  - `user` role → chat area only
  - `manager` role → chat area + admin area (tenant-scoped)
  - `admin` role → full access to chat and admin areas
- Backend enforces all authorization rules on every protected endpoint

This keeps the frontend simple while preserving a strong security model.

---

## 8. Data Access and Streaming

### **8.1 Standard Resource Access**
- REST API for users, tenants, models, tools, templates, prompts, skills, logs, and settings
- Shared data layer for query caching, loading states, and mutation flows

### **8.2 Agent Interaction**
- Streaming responses are delivered from the backend to the chat area
- The frontend renders tokens, tool activity, progress states, and final results
- Agent sessions remain backend-owned and are rehydrated through backend APIs

---

## 9. Refine Usage

Refine should be used only inside the admin area for screens that are primarily:

- resource lists
- CRUD forms
- filters and tables
- audit and management views

Refine should not define the architecture of the chat area.

---

## 10. Goals of the Frontend Architecture

- keep the frontend thin and backend-driven
- avoid maintaining two separate frontend applications
- share authentication, routing, and UI foundations
- preserve strong separation between chat and admin experiences
- support future prompt, skill, and agent UX without re-architecting the app