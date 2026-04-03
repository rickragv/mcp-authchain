FROM node:22-slim AS build

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
# .env is copied with COPY . . for Vite build-time env vars
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html

# Nginx config to proxy /chat and /health to agent-api
RUN printf 'server {\n\
  listen 80;\n\
  location / {\n\
    root /usr/share/nginx/html;\n\
    try_files $uri $uri/ /index.html;\n\
  }\n\
  location /chat {\n\
    proxy_pass http://agent-api:8000;\n\
    proxy_set_header Host $host;\n\
    proxy_set_header Authorization $http_authorization;\n\
  }\n\
  location /health {\n\
    proxy_pass http://agent-api:8000;\n\
  }\n\
}\n' > /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
