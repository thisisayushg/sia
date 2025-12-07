# ---------- Stage 1: Build ----------
FROM ghcr.io/astral-sh/uv:python3.13-bookworm AS build

WORKDIR /app

# Install curl and Node.js 24 from NodeSource
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
 && curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/*

# Verify node installed
RUN node -v && npm -v

COPY . /app

# ---------- Stage 2: Final ----------
FROM ghcr.io/astral-sh/uv:python3.13-bookworm AS final

WORKDIR /app

# Install Node.js again (final image must contain it too)
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
 && curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/*

# Verify node installed
RUN node -v && npm -v
RUN npm install @modelcontextprotocol/inspector@0.17.2

# Copy project files
COPY . /app

RUN uv sync
RUN pip install mcp[cli]
CMD ["mcp", "dev", "server.py"]

EXPOSE 8000
EXPOSE 6274