FROM python:3.11-slim

# Install OS dependencies needed for psycopg, SSL, and other Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    pkg-config \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Update CA certificates to ensure SSL/TLS connections work
RUN update-ca-certificates

# Set environment variables for SSL/TLS
ENV PYTHONHTTPSVERIFY=1
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# Set working directory
WORKDIR /app

# Copy dependency files first (for better Docker layer caching)
COPY pyproject.toml uv.lock ./

# Install uv for faster dependency management (optional - can use pip instead)
RUN pip install uv

# Install dependencies using uv (faster) or fallback to pip
RUN uv pip install --system --no-cache -r pyproject.toml || \
    (pip install --no-cache-dir authlib dnspython requests requests-hardened redis rq alembic sqlalchemy atproto fastapi uvicorn python-multipart pydantic-settings "psycopg[binary,pool]" itsdangerous)

# Test SSL connectivity to ensure certificates work
RUN python -c "import ssl; import urllib.request; urllib.request.urlopen('https://plc.directory', timeout=10)" || \
    curl -s --connect-timeout 10 https://plc.directory > /dev/null

# Copy all application files
COPY . .

# Create a non-root user for security (optional but recommended)
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Expose the correct port
EXPOSE 5000

# For local development with hot reload
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000", "--reload", "--reload-dir", "/app"]