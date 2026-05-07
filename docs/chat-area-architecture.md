# Chat Area Architecture — PH Agent Hub

The chat area is the end-user experience inside the single React frontend of PH Agent Hub. It provides a clean, modern interface for interacting with AI agents while keeping all administrative and operational logic out of the user's view.

This document defines the structure, responsibilities, and integration points of the chat area.

---

## 1. Purpose of the Chat Area

The chat area is designed for end users who interact with AI agents. It focuses on:

- fast, responsive chat experience
- real-time streaming responses and agent events
- model selection based on tenant permissions
- template, prompt, and skill selection
- file uploads
- optional memory display
- multi-session chat history
- authentication via backend-issued JWT

It does **not** include any admin functionality.

---

## 2. Technology Approach

The chat area should be implemented with custom React components inside the shared frontend application.

Recommended stack:

- **React**
- **TypeScript**
- **TanStack Query**
- **WebSockets or SSE** for streaming
- **REST API client** for backend communication
- **JWT authentication** shared with the rest of the frontend

Refine is **not** used for the chat area.

---

## 3. High-Level Architecture

```
┌──────────────────────────────────────────────┐
│         Chat Area (Frontend Route Space)     │
│  - Chat window                               │
│  - Model selector                            │
│  - Template / prompt / skill selectors       │
│  - File uploads                              │
│  - Session history                           │
│  - Streaming renderer                        │
└───────────────────────────────┬──────────────┘
                                │ REST + SSE/WebSocket
                                ▼
┌──────────────────────────────────────────────┐
│   Backend + Microsoft Agent Framework        │
│  - Agent loop                                │
│  - DeepSeek stabilizer                       │
│  - Model routing                             │
│  - Tool execution                            │
│  - Sessions + messages                       │
└──────────────────────────────────────────────┘
```

The chat area is a thin client. It renders state returned by the backend but does not run agents directly.

---

## 4. Core Features

### **4.1 Authentication**
- Login page shared with the rest of the frontend
- JWT stored in memory, not localStorage
- Automatic token refresh
- Tenant and role loaded from backend claims

### **4.2 Chat Interface**
- Markdown rendering
- Code block highlighting
- Streaming token display
- Support for images and file attachments
- Smooth auto-scrolling
- Retry last message
- Stop generation button
- Rendering of tool activity and other agent-side progress states when exposed by the backend

### **4.3 Model Selection**
- Dropdown listing models available to the tenant
- Default model pre-selected
- Disabled models hidden automatically

### **4.4 Templates & Prompts**
- Dropdown or library view listing templates available to the user or tenant
- Personal prompt library for reusable user-authored prompts
- Selected template or prompt can influence system prompt, default model, and allowed tools

### **4.5 Skills**
- Dropdown or launcher for skills available to the user
- A skill can map to a predefined Microsoft Agent Framework agent or workflow
- A selected skill can set defaults such as model, template, prompt, and allowed tools

### **4.6 File Uploads**
- Upload files to backend
- Backend handles extraction, embedding, and tool-based processing

### **4.7 Session Management**
- Create new session
- Rename session
- Delete session
- View session history
- Load previous messages

### **4.8 Memory Display (Optional)**
- Show memory items associated with the session
- Allow user actions only when supported by the backend API

---

## 5. UI Layout Structure

```
/frontend
  /src
    /features
      /chat
        /routes
        /components
          ChatWindow.tsx
          MessageBubble.tsx
          ModelSelector.tsx
          TemplateSelector.tsx
          PromptLibrary.tsx
          SkillSelector.tsx
          FileUpload.tsx
          SessionSidebar.tsx
        /hooks
        /services
          chat.ts
        /state
```

Shared app-level providers, auth logic, and theme configuration live outside the feature module.

---

## 6. Navigation Structure

### **Sidebar**
- New Chat
- Sessions list
- User settings
- Logout

### **Main Area**
- Chat window
- Input box
- Model selector
- Template selector
- Prompt library / quick prompt actions
- Skill selector
- File upload button

---

## 7. API Integration

### **Authentication**
```
POST /auth/login
GET  /auth/me
```

### **Sessions**
```
POST   /chat/session
GET    /chat/session/:id
DELETE /chat/session/:id
```

### **Messages**
```
POST /chat/session/:id/message
GET  /chat/session/:id/messages
```

### **Streaming**
```
GET /chat/session/:id/stream
```

### **User Configuration**
```
GET /models
GET /templates
```

### **Prompts**
```
GET    /prompts
POST   /prompts
PUT    /prompts/:id
DELETE /prompts/:id
```

### **Skills**
```
GET    /skills
POST   /skills
PUT    /skills/:id
DELETE /skills/:id
```

### **Files**
```
POST /files/upload
```

---

## 8. Security Considerations

- JWT stored in memory only
- No admin endpoints exposed in the chat area
- Tenant context enforced by backend
- File uploads validated server-side
- No sensitive data stored in browser
- Frontend feature visibility does not replace backend authorization

---

## 9. Goals of the Chat Area

- provide a clean, intuitive chat experience
- support real-time agent interactions
- allow users to select models, templates, prompts, and skills easily
- keep all admin logic out of the user experience
- integrate cleanly with the backend and Microsoft Agent Framework runtime
