# Multi-stage Dockerfile for Google Analytics MCP Server
# Based on aws-mcp-cloudwatch pattern

FROM python:3.10-alpine3.21 AS uv

# Install the project into `/app`
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Prefer the system python
ENV UV_PYTHON_PREFERENCE=only-system

# Run without updating the uv.lock file like running with `--frozen`
ENV UV_FROZEN=true

# Copy the required files first
COPY pyproject.toml uv.lock uv-requirements.txt ./

# Python optimization and uv configuration
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies and Python package manager
RUN apk update && \
    apk add --no-cache --virtual .build-deps \
    build-base \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    cargo

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    pip install --require-hashes --requirement uv-requirements.txt --no-cache-dir && \
    uv sync --python 3.10 --frozen --no-install-project --no-dev --no-editable

# Then, add the rest of the project source code and install it
# Installing separately from its dependencies allows optimal layer caching
COPY . /app
# Clean any stale bytecode to prevent cache issues
RUN find /app -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
RUN find /app -type f -name "*.pyc" -delete 2>/dev/null || true
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --python 3.10 --frozen --no-dev --no-editable

# Make the directory just in case it doesn't exist
RUN mkdir -p /root/.local

# Final stage
FROM python:3.10-alpine3.21

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    ANALYTICS_MCP_PORT=3334 \
    ANALYTICS_MCP_HOST=0.0.0.0 \
    FASTMCP_HTTP_HOST=0.0.0.0 \
    FASTMCP_HTTP_PORT=3334 \
    GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/credentials.json \
    PYTHONPATH="/app" \
    VIRTUAL_ENV="/app/.venv"

EXPOSE 3334

# Install runtime dependencies and create application user
RUN apk update && \
    apk add --no-cache ca-certificates && \
    update-ca-certificates && \
    addgroup -S app && \
    adduser -S app -G app -h /app

# Copy application artifacts from build stage
COPY --from=uv --chown=app:app /app /app

# Run as non-root
USER app

CMD ["python", "-m", "analytics_mcp.server"]
