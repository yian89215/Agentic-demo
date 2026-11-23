FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# File System reference server 由課程使用的 npx 啟動；uv/uvx 管理 Python 與 Fetch server。
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project \
    && npm install --global @modelcontextprotocol/server-filesystem \
    && uvx --with "mcp<2" mcp-server-fetch --help >/dev/null

COPY config ./config
COPY src ./src
RUN uv sync --frozen --no-dev \
    && mkdir -p /app/data/papers

CMD ["uv", "run", "--frozen", "mcp-demo"]
