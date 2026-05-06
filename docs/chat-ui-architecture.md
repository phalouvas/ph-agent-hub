# Chat UI Architecture — PH Agent Hub

The Chat UI is the user‑facing interface of PH Agent Hub.  
It provides a clean, modern chat experience for interacting with AI agents while keeping all administrative and configuration logic out of the user’s view.

This document defines the structure, responsibilities, and integration points of the Chat UI.

---

## 1. Purpose of the Chat UI

The Chat UI is designed for end‑users who interact with AI agents.  
It focuses on:

- Fast, responsive chat experience
- Real‑time streaming responses
- Model selection (based on tenant permissions)
- Template prompt selection
- File uploads
- Memory display (optional)
- Multi‑session chat history
- Authentication via backend‑issued JWT

It does **not** include any admin functionality.

---

## 2. Technology Stack

Recommended stack:

- **React** (Next.js optional)
- **TypeScript**
- **TailwindCSS or Material UI**
- **WebSockets or SSE** for streaming
- **REST API client** for backend communication
- **JWT authentication**

The Chat UI is deployed as a Docker container and served behind Nginx.

---

## 3. High‑Level Architecture

```
┌──────────────────────────────────────────────┐
│                Chat UI (Frontend)            │
│  - Chat window                               │
│  - Model selector                             │
│  - Template selector                          │
│  - File uploads                               │
│  - Session history                            │
│  - Streaming renderer                         │
└───────────────────────────────┬──────────────┘
                                │ REST + SSE
                                ▼
┌──────────────────────────────────────────────┐
│           Backend (Agent Framework)          │
│  - Agent loop                                │
│  - DeepSeek stabilizer                       │
│  - Model routing                             │
│  - Tool execution                            │
│  - Sessions + messages                       │
└──────────────────────────────────────────────┘
```

---

## 4. Core Features

### **4.1 Authentication**
- Login page
- JWT stored in memory (not localStorage)
- Automatic token refresh
- Tenant and role included in JWT claims

### **4.2 Chat Interface**
- Markdown rendering
- Code block highlighting
- Streaming token display
- Support for images and file attachments
- Smooth auto‑scrolling
- Retry last message
- Stop generation button

### **4.3 Model Selection**
- Dropdown listing models available to the tenant
- Default model pre‑selected
- Disabled models hidden automatically

### **4.4 Template Prompt Selection**
- Dropdown listing templates available to the user or tenant
- When selected:
  - System prompt is applied to the session
  - Default model may change
  - Allowed tools may change

### **4.5 File Uploads**
- Upload files to backend
- Backend handles:
  - text extraction
  - embedding (optional)
  - tool‑based processing

### **4.6 Session Management**
- Create new session
- Rename session
- Delete session
- View session history
- Load previous messages

### **4.7 Memory Display (Optional)**
- Show memory items associated with the session
- Allow user to delete memory items

---

## 5. UI Layout Structure

```
/chat-ui
  /src
    /pages
      /auth
      /chat
    /components
      ChatWindow.tsx
      MessageBubble.tsx
      ModelSelector.tsx
      TemplateSelector.tsx
      FileUpload.tsx
      SessionSidebar.tsx
    /hooks
    /services
      api.ts
      auth.ts
      chat.ts
    /context
      AuthContext.tsx
      SessionContext.tsx
    /theme
  Dockerfile
```

---

## 6. Navigation Structure

### **Sidebar**
- New Chat
- Sessions list
- Settings (user‑level only)
- Logout

### **Main Area**
- Chat window
- Input box
- Model selector
- Template selector
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
POST /chat/session
GET  /chat/session/:id
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

### **Models**
```
GET /models
```

### **Templates**
```
GET /templates
```

### **Files**
```
POST /files/upload
```

---

## 8. Security Considerations

- JWT stored in memory only
- No admin endpoints exposed
- Tenant context enforced by backend
- File uploads validated server‑side
- No sensitive data stored in browser

---

## 9. Goals of the Chat UI

- Provide a clean, intuitive chat experience
- Support real‑time agent interactions
- Allow users to select models and templates easily
- Keep all admin logic out of the user interface
- Integrate seamlessly with the backend agent framework
