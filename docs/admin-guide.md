# Administrator Guide — PH Agent Hub

This guide is for platform administrators (`admin` role) and tenant managers (`manager` role) who operate a PH Agent Hub instance. It covers deployment, configuration, and day-to-day management of tenants, users, AI models, tools, templates, and skills.

---

## 1. Roles and Permissions

PH Agent Hub has three roles:

| Role | Scope | Capabilities |
|---|---|---|
| **admin** | Platform-wide | Manage all tenants, users, models, tools, templates, skills. View all analytics and audit logs. |
| **manager** | Single tenant | Manage users, models, tools, templates, and skills within their own tenant. View tenant-scoped analytics. |
| **user** | Single tenant | Chat only. Access the chat area within their tenant. No admin access. |

All authorization is enforced by the backend. Frontend route guards are for UX only.

---

## 2. Deployment

### 2.1 Prerequisites

- Docker and Docker Compose v2
- A domain name (production only, for Traefik + Let's Encrypt)

### 2.2 First-Time Setup

```bash
cd infrastructure
cp env.example env
```

Edit the `env` file and set the following **required** values:

| Variable | Purpose |
|---|---|
| `JWT_SECRET` | Random string (≥32 chars) for signing JWTs |
| `ENCRYPTION_KEY` | Fernet key for encrypting API keys at rest. Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `ADMIN_EMAIL` | Initial admin user email (default: `admin@phagent.local`) |
| `ADMIN_PASSWORD` | Initial admin password — **change before production** |

### 2.3 Start the Platform

**Development:**
```bash
docker compose up --build
```

**Production:**
```bash
docker compose -f docker-compose.prod.yml up -d
```

The seed script runs automatically on first start, creating the default tenant and admin user. Subsequent runs are idempotent.

### 2.4 Access

| Service | Dev URL | Production |
|---|---|---|
| App (frontend) | http://localhost | Your configured `APP_DOMAIN` |
| phpMyAdmin | http://localhost:8080 | Your configured `PMA_DOMAIN` |
| MinIO Console | http://localhost:9001 | Not exposed (use CLI) |

---

## 3. Managing Tenants

Tenants are isolated environments. Each tenant has its own users, models, tools, templates, skills, and sessions.

### 3.1 Create a Tenant

1. Go to **Admin Area → Tenants**
2. Click **Create**
3. Enter a unique tenant name
4. Save

### 3.2 Delete a Tenant

A tenant can only be deleted if it has no users. Remove or reassign all users first, then delete the tenant.

### 3.3 Tenant Isolation

- Users in Tenant A cannot see or access Tenant B's models, tools, sessions, or data
- Managers are scoped to their own tenant — they cannot create tenants or see cross-tenant data
- Admins have full visibility across all tenants

---

## 4. Managing Users

### 4.1 Create a User

1. Go to **Admin Area → Users**
2. Click **Create**
3. Fill in email, display name, role, and select a tenant
4. The user can log in immediately with the password you set

### 4.2 User Roles

- **admin**: Platform superuser. Assign sparingly.
- **manager**: Tenant operator. Can manage their tenant's resources and users.
- **user**: End user. Chat access only.

### 4.3 Deactivate a User

Toggle the user's **Active** status off. Deactivated users cannot log in. Their data is preserved.

### 4.4 Reset a User's Password

1. Go to the user's edit screen
2. Enter a new password
3. Save — the user can log in with the new password immediately

---

## 5. Managing AI Models

Models are configured per tenant. Each model row represents an AI provider + API key combination.

### 5.1 Add a Model

1. Go to **Admin Area → Models**
2. Click **Create**
3. Configure:

| Field | Description |
|---|---|
| **Name** | Display name, e.g. "DeepSeek R1" |
| **Provider** | `deepseek`, `openai`, or `anthropic` |
| **API Key** | Provider API key — **encrypted at rest** (Fernet). Never appears in API responses. |
| **Base URL** | Optional. Custom endpoint for self-hosted or proxied models. |
| **Enabled** | Toggle on to make available to users |
| **Max Tokens** | Maximum output tokens per response |
| **Temperature** | 0.0–2.0. Lower = more deterministic. |
| **Routing Priority** | Integer. Lower numbers are preferred when multiple models match. |
| **Tenant** | Which tenant this model belongs to |

### 5.2 Enable / Disable Models

Toggle the **Enabled** flag. Disabled models are hidden from the user-facing model selector. Existing sessions that had the model selected will continue to work until the user switches.

### 5.3 API Key Security

- API keys are stored encrypted with Fernet symmetric encryption
- The encryption key is the `ENCRYPTION_KEY` env variable — **never lose this key**
- API keys are **never returned in API responses** (even to admins)
- To rotate a key, edit the model and enter the new key

---

## 6. Managing Tools

Tools extend agent capabilities — they can call external APIs, query ERPNext instances, or run custom code.

### 6.1 Tool Types

| Type | Description |
|---|---|
| **erpnext** | ERPNext instance integration. Requires an ERPNext instance record. |
| **membrane** | Membrane framework tools for web scraping and browser automation. |
| **custom** | Custom tools defined by your organization. |

### 6.2 Add a Tool

1. Go to **Admin Area → Tools**
2. Click **Create**
3. Set the tool name, type, and tenant
4. If type is `erpnext`, also create an ERPNext instance record under **Tools → ERPNext Instances**

### 6.3 ERPNext Instances

ERPNext instances store connection details:
- **URL**: Your ERPNext site URL
- **API Key & API Secret**: Both encrypted at rest
- **Tenant**: Which tenant this instance belongs to

---

## 7. Managing Templates & Skills

### 7.1 Templates

Templates define reusable system prompts and default configurations for agent sessions. They include:
- System prompt text
- Default model selection
- Default skill
- Allowed tools

Users select templates when creating or configuring chat sessions.

### 7.2 Skills

Skills are named agent execution profiles that bundle model, template, and tool defaults. There are two types:

**Prompt Based** (`execution_type = prompt_based`):
- Runs a single conversational agent using the MAF `Agent` class.
- Requires a **Template** (provides the system prompt that defines the agent's behavior).
- Optionally link a **Default Model** and **Tools**.
- MAF Target Key is hidden — not used at runtime for this type.

**Workflow Based** (`execution_type = workflow_based`):
- Delegates to a registered MAF Workflow module for multi-step orchestration.
- Requires a **MAF Target Key** that matches a registered workflow module in the backend (`src/agents/workflows/`).
- Template is hidden — workflows carry their own orchestration logic.

Both types share:
- **Title** (required) and **Description** (optional)
- **Visibility**: `tenant` (available to all users in the tenant) or `personal` (owned by the creating user)
- **Enabled** toggle

**Tenant skills** (created in Admin Area, `visibility=tenant`) are available to all users in the tenant. **Personal skills** (created by users in the chat area) are owned by the creating user.

### 7.3 MAF Target Keys

The `maf_target_key` is only required for **Workflow Based** skills. It must match a registered workflow module in the backend codebase (`src/agents/workflows/`). If the key doesn't match any registered target, the backend logs a warning on startup but does not crash.

For Prompt Based skills, the key is auto-generated from the title if left empty (e.g., "Sales Assistant" → `sales_assistant`). It is not used at runtime for this execution type.

---

## 8. Analytics & Monitoring

### 8.1 Usage Analytics

**Admin Area → Analytics** shows token usage:
- **Admins**: See all tenants
- **Managers**: See their own tenant only

Usage logs are written automatically on every completed agent run (both streaming and non-streaming).

### 8.2 Audit Logs

**Admin Area → Audit** shows a read-only log of all administrative mutations:
- Who performed the action
- What was changed (tenant, user, model, tool, template, skill)
- When it happened

Audit logs are **immutable** — they cannot be deleted or modified. Only admins can view them.

### 8.3 System Logs

**Admin Area → Logs** provides a view of agent activity and error logs. (Currently a stub — detailed log strategy is planned for a future release.)

---

## 9. Security Best Practices

1. **Change the default admin password** immediately after first deployment
2. **Use strong, unique values** for `JWT_SECRET` and `ENCRYPTION_KEY`
3. **Back up your `ENCRYPTION_KEY`** — losing it means all stored API keys are unrecoverable
4. **Never share your `env` file** — it contains secrets
5. **Rotate JWT secrets periodically** — this invalidates all existing tokens
6. **Use HTTPS in production** — Traefik handles this automatically with Let's Encrypt
7. **Restrict admin role** — only assign `admin` to trusted operators
8. **Review audit logs regularly** for suspicious activity

---

## 10. Troubleshooting

### Backend won't start

Check the logs:
```bash
docker compose logs backend
```

Common issues:
- **Missing `ENCRYPTION_KEY`**: Generate one and add it to `env`
- **Database connection refused**: Ensure MariaDB is healthy (`docker compose ps`)
- **Import errors**: Rebuild the image (`docker compose up --build`)

### Migration fails

```bash
docker compose exec backend alembic upgrade head
```

Check for manual migration conflicts in `backend/src/db/migrations/versions/`.

### Can't log in

- Verify the seed script ran: `docker compose logs backend | grep "\[seed\]"`
- If no `[seed]` output, run manually: `docker compose exec backend python scripts/seed.py`
- Check that the user is active in the database (phpMyAdmin → `users` table → `is_active`)

### Models don't appear in the chat

- Verify the model is **enabled** in Admin Area → Models
- Verify the model belongs to the correct tenant
- Verify the user's tenant matches the model's tenant
