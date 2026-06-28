FROM node:20 AS builder

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

# Build for production — compiles all JS, no dev server
RUN npm run build

# Serve with nginx
FROM nginx:alpine

# Copy built files
COPY --from=builder /app/dist /usr/share/nginx/html

# nginx config to handle React Router (all routes → index.html)
RUN printf 'server {\n\
    listen 5173;\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
\n\
    location /auth/ {\n\
        proxy_pass http://csa_backend:8000/auth/;\n\
        proxy_set_header Host $host;\n\
    }\n\
    location /tasks/ {\n\
        proxy_pass http://csa_backend:8000/tasks/;\n\
        proxy_set_header Host $host;\n\
    }\n\
    location /ws/ {\n\
        proxy_pass http://csa_backend:8000/ws/;\n\
        proxy_http_version 1.1;\n\
        proxy_set_header Upgrade $http_upgrade;\n\
        proxy_set_header Connection "upgrade";\n\
    }\n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
}' > /etc/nginx/conf.d/default.conf

EXPOSE 5173

CMD ["nginx", "-g", "daemon off;"]