# ╔══════════════════════════════════════════════════════════════════╗
# ║  VIDHYA BOT — Frontend Dockerfile (React + Vite)               ║
# ║  Phase 7: Full React dashboard implementation                  ║
# ╚══════════════════════════════════════════════════════════════════╝

# Build stage
FROM node:20-alpine as builder
WORKDIR /app

# Copy package files and install dependencies
COPY package*.json ./
RUN npm ci

# Copy source and build
COPY . .
RUN npm run build

# Serve stage
FROM node:20-alpine
WORKDIR /app

# Install serve to run the static bundle
RUN npm install -g serve@14

# Copy built assets from builder
COPY --from=builder /app/dist ./dist

# Expose port
EXPOSE 3000

CMD ["serve", "-s", "dist", "-l", "tcp://0.0.0.0:3000"]
