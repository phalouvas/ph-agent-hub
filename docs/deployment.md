# Deployment Guide — PH Agent Hub

This document describes how PH Agent Hub is deployed using Docker, Docker Compose, and optional reverse-proxy components. The platform is designed for simple local development as well as scalable production deployment.

---

# 1. Deployment Overview

PH Agent Hub is deployed as a multi-service Docker stack consisting of:

- **Backend** — Agent Framework server
- **Frontend** — single React web app containing chat and admin areas
- **MariaDB** — primary relational database
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

Each application (`backend`, `frontend`) contains its own Dockerfile.

---

# 3. Docker Compose Architecture

The deployment uses a multi-container setup:

```
┌──────────────────────────────────────────────┐
│                  Nginx Proxy                 │
│  - SSL termination                           │
│  - Routing to backend and frontend           │
└───────────────────────────────┬──────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────┐
│                Application Layer             │
│               backend     frontend           │
└───────────────────────────────┬──────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────┐
│                Data Layer                    │
│  MariaDB  Redis  MinIO  Vector DB (optional)  │
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
    command: ["sh", "-c", "alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port 8000"]
    depends_on:
      mariadb:
        condition: service_healthy
      redis:
        condition: service_started
    ports:
      - "8000:8000"

  frontend:
    build: ../frontend
    env_file: ./env
    depends_on:
      - backend
    ports:
      - "3000:3000"

  mariadb:
    image: mariadb:11
    environment:
      MARIADB_ROOT_PASSWORD: root-secret
      MARIADB_DATABASE: phhub
      MARIADB_USER: phhub
      MARIADB_PASSWORD: phhub
    command: >
      --character-set-server=utf8mb4
      --collation-server=utf8mb4_unicode_ci
    volumes:
      - mariadb_data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7
    volumes:
      - redis_data:/data

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio_data:/data
    ports:
      - "9000:9000"
      - "9001:9001"  # MinIO web console (dev only; remove in production)
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 10s
      timeout: 5s
      retries: 5

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
      - frontend

volumes:
  mariadb_data:
  redis_data:
  minio_data:
```

---

# 5. Environment Variables

All services share a common `.env` file:

```
DATABASE_URL=mysql://phhub:phhub@mariadb:3306/phhub
REDIS_URL=redis://redis:6379/0

MINIO_ENDPOINT=http://minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_PREFIX=phhub-tenant

UPLOAD_MAX_SIZE_BYTES=20971520
UPLOAD_ALLOWED_TYPES=text/plain,text/csv,text/markdown,application/pdf,application/json,image/png,image/jpeg,image/gif,image/webp

JWT_SECRET=your-secret-key
JWT_EXPIRES_IN=3600

# Model provider keys
DEEPSEEK_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
```

The frontend may also include:

```
VITE_API_URL=/api
```

Using a relative API base keeps the frontend deployment simple behind a reverse proxy.

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
      proxy_http_version 1.1;

      # Required for SSE — disable buffering so tokens are flushed immediately
      proxy_buffering off;
      proxy_cache off;
      proxy_read_timeout 300s;

      # Keep-alive headers for SSE connections
      proxy_set_header Connection '';
      chunked_transfer_encoding on;
    }

    location / {
      proxy_pass http://frontend:3000/;
    }
  }
}
```

The frontend router handles `/chat/*` and `/admin/*` inside the same web app.

In production, SSL termination should be added.

---

# 7. Deployment Modes

## **7.1 Local Development**
```
docker compose up --build
```

Alembic migrations run automatically inside the backend container on startup before the application server starts.

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

### **Frontend**
- Static or SPA-style web frontend
- Easily replicated

### **MariaDB**
- Use managed DB or replication for production

### **Redis**
- Use persistent storage or managed Redis

### **Vector DB**
- Optional but recommended for RAG-heavy deployments

---

# 9. Backup Strategy

### **MariaDB**
- Nightly dumps
- Binary log backup (optional)

### **Redis**
- Snapshotting (RDB)
- AOF persistence (optional)

### **Configuration**
- Backup `/infrastructure/env`
- Backup `/backend/config`

---

# 10. Goals of the Deployment Architecture

- simple local development
- clean production deployment
- one backend and one frontend deployable
- easy scaling
- secure API routing
- support for multi-tenant workloads
- support for Microsoft Agent Framework-based workflows
