# Admin Area Architecture — PH Agent Hub

The admin area is the operational control surface inside the single React frontend of PH Agent Hub. It provides administrators with visibility and control over tenants, users, models, tools, templates, skills, and system configuration.

This document defines the structure, responsibilities, and integration points of the admin area.

---

## 1. Purpose of the Admin Area

The admin area enables platform administrators to:

- manage users and roles
- configure models and API keys
- enable and disable tools
- manage tenants and tenant defaults
- create and manage curated templates
- create and manage shared skills
- view usage analytics and logs
- configure system-level settings
- monitor agent activity and operational errors

It is designed for clarity, security, and operational efficiency.

---

## 2. Technology Stack

The admin area lives inside the shared React frontend application.

Recommended stack:

- **React**
- **TypeScript**
- **Refine Core** for CRUD-heavy admin resources
- **REST API client** for backend communication
- **Material UI or Ant Design** for administrative components
- **JWT authentication** shared with the rest of the frontend

Refine should be used where it accelerates resource management. It should not be treated as the architecture for the entire web app.

---

## 3. High-Level Architecture

```
┌──────────────────────────────────────────────┐
│      Admin Area (Frontend Route Space)       │
│  - User management                           │
│  - Model configuration                       │
│  - Tool configuration                        │
│  - Tenant settings                           │
│  - Templates & skills                        │
│  - Analytics                                 │
└───────────────────────────────┬──────────────┘
                                │ REST API
                                ▼
┌──────────────────────────────────────────────┐
│        Backend + Agent Runtime Services      │
│  - Auth                                      │
│  - Models                                    │
│  - Tools                                     │
│  - Tenants                                   │
│  - Templates                                 │
│  - Skills                                    │
│  - Usage logs                                │
└──────────────────────────────────────────────┘
```

---

## 4. Core Features

### **4.1 Authentication**
- Login page shared with the main frontend
- JWT-based session
- Role-based access for administrators only

### **4.2 User Management**
- Create and delete users
- Assign roles
- Reset passwords
- Activate and deactivate accounts
- Assign users to tenants

### **4.3 Tenant Management**
- Create tenants
- Configure tenant defaults
- Assign models and tools to tenants
- Manage tenant-specific settings

### **4.4 Model Management**
- Add and remove models
- Configure API keys and base URLs
- Enable and disable models per tenant
- Set routing priority
- Set default model per tenant

### **4.5 Tool Management**
- Add and remove tools
- Configure ERPNext instances
- Configure Membrane tools
- Upload custom tool definitions
- Enable and disable tools per tenant

### **4.6 Template Management**
- Create, edit, and delete curated templates
- Assign templates to tenants, roles, or specific users
- Mark templates available for chat sessions and skill composition
- Set default templates

### **4.7 Skill Management**
- Create, edit, and delete skills
- Map skills to Microsoft Agent Framework agents or workflows
- Configure default template, prompt, model, and allowed tools for a skill
- Publish skills tenant-wide or restrict them to specific users later

### **4.8 Usage Analytics**
- Tokens per user
- Tokens per tenant
- Model usage breakdown
- Tool usage statistics
- Error logs

### **4.9 System Settings**
- Global configuration
- Logging level
- Vector DB settings (optional)
- Maintenance mode

---

## 5. UI Layout Structure

```
/frontend
  /src
    /features
      /admin
        /resources
          /users
          /tenants
          /models
          /tools
          /templates
          /skills
        /pages
          /analytics
          /settings
        /components
        /services
          admin.ts
        /layouts
```

Refine resources should be defined inside the admin feature module, while shared auth, routing, and theming stay at the app level.

---

## 6. Navigation Structure

### **Sidebar**
- Dashboard
- Users
- Tenants
- Models
- Tools
- Templates
- Skills
- Analytics
- Settings
- Logout

### **Top Bar**
- Tenant selector when relevant
- User profile
- Notifications (optional)

---

## 7. API Integration

The admin area communicates with the backend via REST endpoints:

### **Authentication**
```
POST /auth/login
GET  /auth/me
```

### **Users**
```
GET    /admin/users
POST   /admin/users
PUT    /admin/users/:id
DELETE /admin/users/:id
```

### **Tenants**
```
GET    /admin/tenants
POST   /admin/tenants
PUT    /admin/tenants/:id
DELETE /admin/tenants/:id
```

### **Models**
```
GET    /admin/models
POST   /admin/models
PUT    /admin/models/:id
DELETE /admin/models/:id
```

### **Tools**
```
GET    /admin/tools
POST   /admin/tools
PUT    /admin/tools/:id
DELETE /admin/tools/:id
```

### **Templates**
```
GET    /admin/templates
POST   /admin/templates
PUT    /admin/templates/:id
DELETE /admin/templates/:id
```

### **Skills**
```
GET    /admin/skills
POST   /admin/skills
PUT    /admin/skills/:id
DELETE /admin/skills/:id
```

### **Analytics**
```
GET /admin/usage
GET /admin/logs
```

---

## 8. Security Considerations

- Admin routes are visible only to authorized users
- Backend role enforcement remains authoritative
- JWT is stored in memory, not localStorage
- Sensitive fields such as API keys and secrets are masked by default
- Audit logs are recorded for administrative actions

---

## 9. Goals of the Admin Area

- provide a clean, intuitive interface for managing the platform
- support multi-tenant operations at scale
- let administrators configure models and tools without backend code changes
- provide visibility into system usage and performance
- remain clearly separated from the end-user chat experience
