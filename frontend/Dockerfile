# =============================================================================
# PH Agent Hub — Frontend Dockerfile
# =============================================================================
FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package.json ./
RUN npm install

# Copy application code
COPY . .

EXPOSE 3000

# Development mode: start Vite dev server
CMD ["npm", "run", "dev"]
