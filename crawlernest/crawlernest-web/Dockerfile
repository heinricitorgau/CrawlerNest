# The Next.js frontend.
#
# Three stages: dependencies, build, run. The runtime stage carries the standalone
# output (server plus only the node_modules it traced), not the full tree.
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Both are read at build time as well as at run time; the browser bundle needs
# whatever is NEXT_PUBLIC_*, so they are build arguments too.
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_AGENT_API_BASE_URL
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# node:alpine already provides an unprivileged "node" user.
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node

EXPOSE 3000
CMD ["node", "server.js"]
