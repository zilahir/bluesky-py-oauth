FROM node:20

# Enable pnpm
RUN corepack enable && corepack prepare pnpm@9.9.0 --activate

WORKDIR /app

# Copy package files
COPY package.json pnpm-lock.yaml ./

# Install dependencies with all platform-specific binaries
RUN pnpm install --frozen-lockfile

# Copy the rest of the application
COPY . .

EXPOSE 5174

# For development with hot reload
CMD ["pnpm", "run", "dev", "--host", "0.0.0.0", "--port", "5174"]
