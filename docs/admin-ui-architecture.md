# Admin UI Architecture — PH Agent Hub

The Admin Management UI is the control center of PH Agent Hub.  
It provides administrators with full visibility and control over tenants, users, models, tools, templates, and system configuration.  
This UI is separate from the Chat UI and communicates exclusively with the backend API.

---

## 1. Purpose of the Admin UI

The Admin UI enables platform administrators to:

- Manage users and roles
- Configure models and API keys
- Enable/disable tools (ERPNext, Membrane, custom tools)
- Manage tenants and their settings
- Create and manage template prompts
- View usage analytics and logs
- Configure system‑level settings
- Monitor agent activity and errors

It is designed for clarity, security, and operational efficiency.

---

## 2. Technology Stack

The Admin UI is built as a standalone frontend application.  
Recommended stack:

- **React + Refine.dev** (ideal for admin dashboards)
- **TypeScript**
- **REST API client** for backend communication
- **Ant Design or Material UI** for components
- **JWT authentication** (token stored in memory)

The Admin UI is deployed as a Docker container and served behind Nginx.

---

## 3. High‑Level Architecture

```
┌──────────────────────────────────────────────┐
│                Admin UI (Frontend)           │
│  - User management                           │
│  - Model configuration                       │
│  - Tool configuration                        │
│  - Tenant settings                           │
│  - Templates                                 │
│  - Analytics                                 │
└───────────────────────────────┬──────────────┘
                                │ REST API
                                ▼
┌──────────────────────────────────────────────┐
│           Backend (Agent Framework)          │
│  - Auth                                      │
│  - Models                                    │
│  - Tools                                     │
│  - Tenants                                   │
│  - Templates                                 │
│  - Usage logs                                │
└──────────────────────────────────────────────┘
```

---

## 4. Core Features

### **4.1 Authentication**
- Login page
- JWT‑based session
- Role‑based access (admin only)

### **4.2 User Management**
- Create/delete users
- Assign roles (admin/user)
- Reset passwords
- Activate/deactivate accounts
- Assign users to tenants

### **4.3 Tenant Management**
- Create tenants
- Configure tenant defaults
- Assign models and tools to tenants
- Manage tenant‑specific settings

### **4.4 Model Management**
- Add/remove models
- Configure API keys and base URLs
- Enable/disable models per tenant
- Set routing priority
- Set default model per tenant

### **4.5 Tool Management**
- Add/remove tools
- Configure ERPNext instances
- Configure Membrane tools
- Upload custom tool definitions
- Enable/disable tools per tenant

### **4.6 Template Prompt Management**
- Create/edit/delete templates
- Assign templates to tenants or users
- Restrict templates by role
- Set default templates

### **4.7 Usage Analytics**
- Tokens per user
- Tokens per tenant
- Model usage breakdown
- Tool usage statistics
- Error logs

### **4.8 System Settings**
- Global configuration
- Logging level
- Vector DB settings (optional)
- Maintenance mode

---

## 5. UI Layout Structure

```
/admin-ui
  /src
    /pages
      /auth
      /users
      /tenants
      /models
      /tools
      /templates
      /analytics
      /settings
    /components
    /hooks
    /services
    /layouts
    /theme
  Dockerfile
```

---

## 6. Navigation Structure

### **Sidebar**
- Dashboard
- Users
- Tenants
- Models
- Tools
- Templates
- Analytics
- Settings
- Logout

### **Top Bar**
- Tenant selector
- User profile
- Notifications (optional)

---

## 7. API Integration

The Admin UI communicates with the backend via REST endpoints:

### **Authentication**
```
POST /auth/login
GET  /auth/me
```

### **Users**
```
GET  /admin/users
POST /admin/users
PUT  /admin/users/:id
DELETE /admin/users/:id
```

### **Tenants**
```
GET  /admin/tenants
POST /admin/tenants
PUT  /admin/tenants/:id
DELETE /admin/tenants/:id
```

### **Models**
```
GET  /admin/models
POST /admin/models
PUT  /admin/models/:id
DELETE /admin/models/:id
```

### **Tools**
```
GET  /admin/tools
POST /admin/tools
PUT  /admin/tools/:id
DELETE /admin/tools/:id
```

### **Templates**
```
GET  /admin/templates
POST /admin/templates
PUT  /admin/templates/:id
DELETE /admin/templates/:id
```

### **Analytics**
```
GET /admin/usage
GET /admin/logs
```

---

## 8. Security Considerations

- Admin UI is accessible only to users with `role = admin`
- JWT stored in memory (not localStorage) to reduce XSS risk
- All API calls include tenant context
- Sensitive fields (API keys, secrets) masked by default
- Audit logs recorded for all admin actions

---

## 9. Goals of the Admin UI

- Provide a clean, intuitive interface for managing the entire platform
- Support multi‑tenant operations at scale
- Allow administrators to configure models and tools without backend changes
- Provide visibility into system usage and performance
- Maintain strict separation from the Chat UI
