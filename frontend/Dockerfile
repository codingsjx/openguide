# OpenGuide frontend image: build the Vite bundle, then serve it with nginx
# (nginx also reverse-proxies /api to the backend service).
FROM node:24-slim AS build

WORKDIR /app
RUN corepack enable

# Dependency layer first so source edits don't bust the cache.
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm build

FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
