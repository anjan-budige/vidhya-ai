
FROM node:24-alpine AS builder
WORKDIR /app

COPY package*.json ./
RUN npm ci --no-audit --no-fund

COPY . .
RUN npm run build

# Serve stage — patched Nginx, no Node runtime in production
FROM nginx:1.31.8-alpine3.24-slim

COPY --from=builder /app/dist /usr/share/nginx/html
RUN printf '%s\n' \
    'server {' \
    '    listen 3000;' \
    '    listen [::]:3000;' \
    '    server_name _;' \
    '    root /usr/share/nginx/html;' \
    '    index index.html;' \
    '    location / {' \
    '        try_files $uri $uri/ /index.html;' \
    '    }' \
    '    location /assets/ {' \
    '        try_files $uri =404;' \
    '        expires 1y;' \
    '        add_header Cache-Control "public, immutable";' \
    '    }' \
    '}' > /etc/nginx/conf.d/default.conf

EXPOSE 3000
