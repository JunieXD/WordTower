FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM openresty/openresty:alpine

COPY deploy/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/local/openresty/nginx/html

EXPOSE 8080
