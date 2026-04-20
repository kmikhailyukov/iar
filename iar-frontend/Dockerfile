FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
# Fallback nginx.conf for local docker-compose (uses internal hostname)
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
# nginx docker image auto-applies templates via envsubst on startup when
# /etc/nginx/templates/*.template files exist — so Railway sets API_UPSTREAM
# and local compose falls back to static nginx.conf
CMD ["/bin/sh", "-c", \
  "if [ -n \"$API_UPSTREAM\" ]; then \
     envsubst '$API_UPSTREAM' < /etc/nginx/templates/default.conf.template \
       > /etc/nginx/conf.d/default.conf; \
   fi && nginx -g 'daemon off;'"]
