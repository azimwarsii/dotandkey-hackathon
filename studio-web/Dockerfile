FROM node:22-bookworm-slim AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY studio-web/package*.json ./
RUN npm ci
COPY studio-web/ ./
ARG STUDIO_BACKEND=http://api.railway.internal:8000
ENV STUDIO_BACKEND=$STUDIO_BACKEND
RUN npm run build

FROM node:22-bookworm-slim
WORKDIR /app
ARG STUDIO_BACKEND=http://api.railway.internal:8000
ENV STUDIO_BACKEND=$STUDIO_BACKEND
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=:: PORT=3000
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]
