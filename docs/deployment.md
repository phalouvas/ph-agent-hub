# Deployment Guide — PH Agent Hub

This document describes how PH Agent Hub is deployed using Docker, Docker Compose, and optional reverse‑proxy components.  
The platform is designed for simple local development as well as scalable production deployment.

---

# 1. Deployment Overview

PH Agent Hub is deployed as a **multi‑service Docker stack** consisting of:

- **Backend** — Agent Framework server
- **Chat UI** — user‑facing interface
- **Admin UI** — administrator interface
- **Postgres** — primary database
- **Redis** — caching, queues, memory store
- **Optional Vector DB** — for RAG (Qdrant, Milvus, Weaviate)
- **Nginx** — reverse proxy for production

All services run inside a single Docker Compose environment.

---

# 2. Repository Structure for Deployment

```
/infrastructure
  docker-compose.yml
  nginx.conf
  env.example
  scripts/
```

Each application (backend, chat-ui, admin-ui) contains its own Dockerfile.

---

# 3. Docker Compose Architecture

The deployment uses a multi‑container setup:

```
┌──────────────────────────────────────────────┐
│                  Nginx Proxy                 │
│  - SSL termination                            │
│  - Routing to backend, chat-ui, admin-ui     │
└───────────────────────────────┬──────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────┐
│                Application Layer             │
│  backend     chat-ui     admin-ui            │
└───────────────────────────────┬──────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────┐
│                Data Layer                    │
│  Postgres     Redis     Vector DB (optional) │
└──────────────────────────────────────────────┘
```

---

# 4. Example `docker-compose.yml`

Below is the recommended structure (values omitted for clarity):

```yaml
version: "3.9"

services:
  backend:
    build: ../backend
    env_file: ./env
    depends_on:
      - postgres
      - redis
    ports:
      - "8000:8000"

  chat-ui:
    build: ../chat-ui
    env_file: ./env
    depends_on:
      - backend
    ports:
      - "3000:3000"

  admin-ui:
    build: ../admin-ui
    env_file: ./env
    depends_on:
      - backend
    ports:
      - "3001:3001"

  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: phhub
      POSTGRES_PASSWORD: phhub
      POSTGRES_DB: phhub
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    volumes:
      - redis_data:/data

  # Optional vector DB
  # qdrant:
  #   image: qdrant/qdrant
  #   ports:
  #     - "6333:6333"

  nginx:
    image: nginx:latest
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - backend
      - chat-ui
      - admin-ui

volumes:
  postgres_data:
  redis_data:
```

---

# 5. Environment Variables

All services share a common `.env` file:

```
DATABASE_URL=postgresql://phhub:phhub@postgres:5432/phhub
REDIS_URL=redis://redis:6379/0

JWT_SECRET=your-secret-key
JWT_EXPIRES_IN=3600

# Model provider keys
DEEPSEEK_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
```

Each UI may also include:

```
VITE_API_URL=http://backend:8000
```

---

# 6. Nginx Reverse Proxy

A minimal `nginx.conf`:

```nginx
events {}

http {
  server {
    listen 80;

    location /api/ {
      proxy_pass http://backend:8000/;
    }

    location /chat/ {
      proxy_pass http://chat-ui:3000/;
    }

    location /admin/ {
      proxy_pass http://admin-ui:3001/;
    }
  }
}
```

In production, SSL termination should be added (Let’s Encrypt or custom certificates).

---

# 7. Deployment Modes

## **7.1 Local Development**
```
docker compose up --build
```

## **7.2 Production Deployment**
Recommended options:

- Docker Compose on a single VPS
- Portainer or Coolify
- Kubernetes (optional for scaling)
- Traefik or Nginx for SSL

---

# 8. Scaling Considerations

### **Backend**
- Can be horizontally scaled
- Stateless except for DB + Redis

### **Chat UI / Admin UI**
- Pure static frontends
- Easily replicated

### **Postgres**
- Use managed DB or replication for production

### **Redis**
- Use persistent storage or managed Redis

### **Vector DB**
- Optional but recommended for RAG

---

# 9. Backup Strategy

### **Postgres**
- Nightly dumps
- WAL archiving (optional)

### **Redis**
- Snapshotting (RDB)
- AOF persistence (optional)

### **Configuration**
- Backup `/infrastructure/env`
- Backup `/backend/config`

---

# 10. Goals of the Deployment Architecture

- Simple local development
- Clean production deployment
- Full isolation between services
- Easy scaling
- Secure API routing
- Support for multi‑tenant workloads
- Support for DeepSeek‑compatible agent workflows
