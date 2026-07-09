# Imagen oficial de uv sobre Python 3.12 slim: rápida y reproducible.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# 1) Instalar dependencias primero (capa cacheada mientras no cambien).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# 2) Copiar el código de la app.
COPY server.py ./

# El server escucha en este puerto (streamable-http).
ENV MCP_TRANSPORT=streamable-http \
    PORT=8000 \
    PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Ejecuta dentro del venv creado por uv sync.
CMD ["python", "server.py"]
