FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
EXPOSE 80
# API_UPSTREAM defaults to internal docker-compose hostname; override on Railway
CMD ["/bin/sh", "-c", \
  "API_UPSTREAM=${API_UPSTREAM:-http://iar-api:8000} \
   envsubst '$API_UPSTREAM' \
   < /etc/nginx/templates/default.conf.template \
   > /etc/nginx/conf.d/default.conf \
   && nginx -g 'daemon off;'"]
