# =============================================================================
# PH Agent Hub — Frontend Dockerfile (Development)
# =============================================================================
FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm install

# Copy application code
COPY . .

EXPOSE 3000

# Development mode: start Vite dev server with HMR
CMD ["npm", "run", "dev"]
