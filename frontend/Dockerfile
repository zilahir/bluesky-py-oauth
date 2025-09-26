FROM node:20-alpine

RUN corepack enable && corepack prepare pnpm@9.9.0 --activate

WORKDIR /app

COPY package.json pnpm-lock.yaml ./

RUN pnpm install --frozen-lockfile

COPY . .

EXPOSE 5174

# For development with hot reload using host node_modules
# The dev command will use the node_modules from the host via volume mount
CMD ["pnpm", "run", "dev", "--host", "0.0.0.0", "--port", "5174"]
