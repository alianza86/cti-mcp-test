# MCP de ejemplo: Biblioteca de libros 📚

Un servidor **MCP (Model Context Protocol)** mínimo y de **solo lectura**, hecho en
Python, que consulta una base de datos **Postgres** con libros y autores.

El objetivo es aprender cómo un agente (por ejemplo en Azure AI Foundry)
descubre y llama herramientas expuestas por un MCP.

## ¿Qué hace?

Expone 5 herramientas (`tools`) que el agente puede llamar:

| Tool | Qué hace |
|------|----------|
| `search_books` | Busca libros por título y/o género, opcionalmente solo disponibles |
| `get_book` | Detalle completo de un libro por id |
| `books_by_author` | Libros de un autor (búsqueda por nombre) |
| `list_authors` | Todos los autores con su número de libros |
| `library_stats` | Resumen: totales de títulos, autores y copias |

## Requisitos

- Docker (para Postgres)
- Python 3.11+ (con `uv` no hace falta tenerlo instalado; él descarga uno)
- [uv](https://docs.astral.sh/uv/) (recomendado) o pip

## Puesta en marcha

### 1. Levantar Postgres

```bash
docker compose up -d
```

Esto crea la base `library` y carga `seed.sql` (tablas + datos de ejemplo)
automáticamente la primera vez.

Para reiniciar los datos desde cero:

```bash
docker compose down -v && docker compose up -d
```

### 2. Instalar dependencias

Con uv (recomendado):

```bash
uv sync
```

O con pip + venv:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

### 3. Probar el servidor

La forma más rápida de ver las tools sin escribir un cliente es el **MCP Inspector**:

```bash
uv run mcp dev server.py
```

Se abre una UI en el navegador donde puedes listar las tools y llamarlas a mano.

Para correrlo directamente (modo stdio, como lo lanzaría un agente):

```bash
uv run server.py
```

O usa el cliente de ejemplo incluido, que arranca el server, lista las tools
y llama algunas (es la forma más fácil de ver la mecánica del protocolo):

```bash
uv run test_client.py
```

## Conectarlo a un cliente MCP

Ejemplo de configuración para un cliente tipo Claude Desktop / Cursor
(`mcpServers`):

```json
{
  "mcpServers": {
    "library": {
      "command": "uv",
      "args": ["run", "server.py"],
      "env": {
        "DATABASE_URL": "postgresql://library:library@localhost:5433/library"
      }
    }
  }
}
```

## Configuración

Variables de entorno:

| Variable | Default | Para qué |
|----------|---------|----------|
| `DATABASE_URL` | `postgresql://library:library@localhost:5433/library` | Conexión a Postgres |
| `MCP_TRANSPORT` | `stdio` | `stdio` (local) o `streamable-http` (desplegado) |
| `PORT` | `8000` | Puerto HTTP (solo con `streamable-http`) |

## Despliegue en Coolify

El server ya soporta transporte HTTP. En modo `streamable-http` expone:

- `GET /health` → `ok` (para el health check)
- `POST /mcp` → el endpoint del protocolo MCP (lo consume el agente/cliente)

### Opción A — Docker Compose (recomendada, carga el seed sola)

Usa [`docker-compose.coolify.yml`](docker-compose.coolify.yml): levanta Postgres
+ MCP juntos y carga `seed.sql` en el primer arranque.

1. En Coolify crea un recurso **Docker Compose** apuntando a tu repo y a
   `docker-compose.coolify.yml`.
2. (Opcional) Define `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` como
   variables del recurso; si no, usa los defaults (`library`).
3. Asigna un **dominio** al servicio `mcp` (puerto **8000**). No expongas la DB.

> El endpoint MCP para el cliente/agente quedará en `https://<tu-dominio>/mcp`.

### Opción B — Application (Postgres por separado)

1. **Postgres**: provisiona un contenedor Postgres manualmente y ejecuta el
   contenido de [`seed.sql`](seed.sql) una vez.
2. **MCP**: crea un recurso *Application* apuntando a tu repo (usa el `Dockerfile`).
3. **Variables de entorno** del MCP:
   - `DATABASE_URL` → hostname **interno** del Postgres (no `localhost`),
     p. ej. `postgresql://library:library@<servicio-postgres>:5432/library`.
   - `MCP_TRANSPORT=streamable-http` (ya viene en el Dockerfile).
   - `PORT=8000`.
4. **Health check**: path `/health`, GET. **Puerto**: 8000.

### Probar la imagen en local (opcional)

```bash
docker build -t mcp-library .
docker run --rm -p 8000:8000 \
  -e DATABASE_URL="postgresql://library:library@host.docker.internal:5433/library" \
  mcp-library
curl http://localhost:8000/health   # -> ok
```

## Estructura

```
.
├── docker-compose.yml   # Postgres 16 para desarrollo local
├── seed.sql             # Esquema + datos de ejemplo (carga automática)
├── server.py            # El MCP: FastMCP + tools (stdio o streamable-http)
├── test_client.py       # Cliente de ejemplo para probar el MCP sin agente (stdio)
├── Dockerfile           # Imagen del MCP para desplegar (Coolify, etc.)
├── .dockerignore
├── pyproject.toml       # Dependencias
└── README.md
```

## Siguientes pasos (ideas)

- Agregar tools de escritura (crear/prestar libros) cuando quieras practicar acciones.
- Cambiar el transporte a HTTP/SSE para conectar desde Azure AI Foundry.
- Añadir recursos (`resources`) además de tools, p. ej. exponer el esquema de la DB.
