# PH Agent Hub — End-to-End Testing Plan

> **Purpose:** Track all manual browser-based tests covering Admin and Chat functionality.
> **Status symbols:** ⬜ Not started | 🟡 In progress | ✅ Passed | ❌ Failed

---

## 1. Authentication

| # | Test | Status | Notes |
|---|------|--------|-------|
| 1.1 | Login with valid credentials (admin@phagent.local / admin) | ✅ | |
| 1.2 | Login with invalid credentials shows error | ⬜ | |
| 1.3 | Logout redirects to login page | ⬜ | |
| 1.4 | Protected routes redirect unauthenticated users to /login | ⬜ | |
| 1.5 | Non-admin users cannot access /admin routes | ⬜ | |
| 1.6 | Admin link visible in sidebar for admin/manager users | ✅ | Clicking navigates to /admin |

---

## 2. Admin — Models CRUD

| # | Test | Status | Notes |
|---|------|--------|-------|
| 2.1 | **CREATE** — Add a new model (deepseek-v4-flash) via form | ✅ | |
| 2.2 | **READ** — Model appears in the list after creation | ✅ | |
| 2.3 | **UPDATE** — Edit model fields (name, URL, API key) | ✅ | Max Tokens 4096→8192 |
| 2.4 | **DELETE** — Remove a model | ✅ | Confirmation popover works |
| 2.5 | Model form validation (required fields) | ✅ | "Please enter Model ID" shown when model_id left empty |

---

## 3. Admin — Users CRUD

| # | Test | Status | Notes |
|---|------|--------|-------|
| 3.1 | **CREATE** — Add a new user | ✅ | testuser2@phagent.local created |
| 3.2 | **READ** — User appears in list | ✅ | |
| 3.3 | **UPDATE** — Edit user role/display name | ✅ | Display name changed successfully |
| 3.4 | **DELETE** — Remove a user | ✅ | Confirmation popover works |
| 3.5 | User form validation | ⬜ | Skipped — same pattern as models |

---

## 4. Admin — Tenants CRUD (admin only)

| # | Test | Status | Notes |
|---|------|--------|-------|
| 4.1 | **CREATE** — Add a new tenant | ✅ | |
| 4.2 | **READ** — Tenant appears in list | ✅ | |
| 4.3 | **UPDATE** — Edit tenant settings | ✅ | Name changed successfully |
| 4.4 | **DELETE** — Remove a tenant | ✅ | Only Default remains |

---

## 5. Admin — Tools CRUD

| # | Test | Status | Notes |
|---|------|--------|-------|
| 5.1 | **CREATE** — Add a new tool | ✅ | |
| 5.2 | **READ** — Tool appears in list | ✅ | |
| 5.3 | **UPDATE** — Edit tool configuration | ✅ | |
| 5.4 | **DELETE** — Remove a tool | ✅ | |

---

## 6. Admin — Templates CRUD

| # | Test | Status | Notes |
|---|------|--------|-------|
| 6.1 | **CREATE** — Add a new template | ✅ | System Prompt shows validation but still created |
| 6.2 | **READ** — Template appears in list | ✅ | |
| 6.3 | **UPDATE** — Edit template content | ✅ | Title changed successfully |
| 6.4 | **DELETE** — Remove a template | ✅ | Fixed FK constraint bug |

---

## 7. Admin — Skills CRUD

| # | Test | Status | Notes |
|---|------|--------|-------|
| 7.1 | **CREATE** — Add a new skill | ✅ | Fixed execution_type enum bug |
| 7.2 | **READ** — Skill appears in list | ✅ | |
| 7.3 | **UPDATE** — Edit skill | ⬜ | |
| 7.4 | **DELETE** — Remove a skill | ✅ | |

---

## 8. Admin — Analytics & Settings

| # | Test | Status | Notes |
|---|------|--------|-------|
| 8.1 | Analytics page loads with data | ⬜ | |
| 8.2 | Settings page loads and is editable | ⬜ | |

---

## 9. Chat — Session Management

| # | Test | Status | Notes |
|---|------|--------|-------|
| 9.1 | Create a new chat session | ✅ | |
| 9.2 | Session appears in sidebar | ✅ | |
| 9.3 | Pin / Unpin a session | ✅ | |
| 9.4 | Delete a session | ✅ | |
| 9.5 | Search sessions | ⬜ | |
| 9.6 | Navigate between sessions | ✅ | |

---

## 10. Chat — Messaging

| # | Test | Status | Notes |
|---|------|--------|-------|
| 10.1 | Send a message and receive a response | ✅ | "Hello world" from DeepSeek via OpenAIChatCompletionClient |
| 10.2 | Streaming response works (tokens appear progressively) | ✅ | Tokens streamed progressively |
| 10.3 | Select a different model from dropdown | ✅ | Model selection persists to session via updateSession API |
| 10.4 | Select a template | ⬜ | |
| 10.5 | Select a skill | ⬜ | |
| 10.6 | Select a prompt | ⬜ | |
| 10.7 | Memory management (view/add/delete memories) | ⬜ | |

---

## 11. Results Summary

| Area | Passed | Failed | Not Tested |
|------|--------|--------|------------|
| Authentication | 2 | 0 | 4 |
| Models CRUD | 5 | 0 | 0 |
| Users CRUD | 4 | 0 | 1 |
| Tenants CRUD | 4 | 0 | 0 |
| Tools CRUD | 4 | 0 | 0 |
| Templates CRUD | 4 | 0 | 0 |
| Skills CRUD | 3 | 0 | 1 |
| Analytics & Settings | 0 | 0 | 2 |
| Session Management | 5 | 0 | 1 |
| Chat Messaging | 3 | 0 | 4 |
| **TOTAL** | **34** | **0** | **13** |

---

## Bugs Found (All Fixed ✅)

| # | Severity | Area | Description | Status |
|---|----------|------|-------------|--------|
| B1 | 🔴 Critical | Chat | Model selection not persisted to session | ✅ Fixed — handleSessionUpdate now calls updateSession API |
| B2 | 🟡 Medium | Templates | DELETE fails with FK constraint error | ✅ Fixed — clear sessions.selected_template_id before delete |
| B3 | 🟡 Medium | Skills | CREATE fails — execution_type enum mismatch | ✅ Fixed — added prompt_based/workflow_based to DB enum |
| B4 | 🔴 Critical | Chat | 404 from DeepSeek API — OpenAIChatClient uses Responses API | ✅ Fixed — switched to OpenAIChatCompletionClient + /v1 URL |

---

## Changes Made During Testing

1. **Added `model_id` column to models** — Separate display `name` from API `model_id` (required field)
2. **Fixed model DELETE FK constraint** — Clear sessions/model references before deleting
3. **Made `tenant_id` optional in UserCreate** — Defaults to current user's tenant
4. **Fixed `_get_client_ip` infinite recursion** — Fallback now uses `request.client.host`
5. **Made "Admin" text a clickable link** — Navigates to `/admin` for admin/manager users
6. **Fixed chat model persistence (B1)** — handleSessionUpdate now calls updateSession API
7. **Fixed template DELETE FK (B2)** — Clear sessions.selected_template_id before delete
8. **Fixed skill execution_type enum (B3)** — Added prompt_based/workflow_based to DB enum
9. **Fixed DeepSeek API client (B4)** — Switched from OpenAIChatClient (Responses API) to OpenAIChatCompletionClient (Chat Completions API) with /v1 URL suffix
10. **Fixed runner execution_type normalization** — Maps workflow_based→workflow, prompt_based→agent

---

> **Last updated:** 2026-05-07
> **Tester:** GitHub Copilot (browser automation)
