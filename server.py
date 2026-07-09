"""
MCP de ejemplo: una biblioteca de libros (solo lectura) sobre Postgres.

Expone herramientas ("tools") que un agente puede descubrir y llamar para
consultar libros y autores. Usa FastMCP (SDK oficial de MCP) + psycopg 3.

Transporte configurable por entorno (MCP_TRANSPORT):
    stdio           -> desarrollo local (un cliente lo lanza como subproceso)
    streamable-http -> despliegue (servicio HTTP en Coolify, Foundry, etc.)

Ejecutar local:   uv run server.py
Ejecutar HTTP:    MCP_TRANSPORT=streamable-http uv run server.py

La conexión a la DB se lee de DATABASE_URL (ver README).
"""

import os
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://library:library@localhost:5433/library",
)

# stdio para local; streamable-http para desplegar como servicio de red.
TRANSPORT = os.environ.get("MCP_TRANSPORT", "stdio")
# Coolify (y la mayoría de PaaS) inyectan el puerto por env.
PORT = int(os.environ.get("PORT", "8000"))

# El nombre es lo que verá el agente al listar servidores MCP.
mcp = FastMCP(
    "library",
    host="0.0.0.0",           # escuchar en todas las interfaces dentro del contenedor
    port=PORT,
    streamable_http_path="/mcp",
    stateless_http=True,      # sin estado de sesión: más simple de escalar/desplegar
)


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> PlainTextResponse:
    """Endpoint simple para el health check de Coolify."""
    return PlainTextResponse("ok")


@contextmanager
def get_cursor():
    """Abre una conexión y un cursor que devuelve filas como diccionarios.

    Usamos un context manager para que la conexión siempre se cierre,
    incluso si la consulta falla.
    """
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            yield cur


# ---------------------------------------------------------------------------
# Tools (herramientas de solo lectura)
#
# Cada función decorada con @mcp.tool() se expone al agente. El docstring y
# los type hints son lo que el agente lee para decidir cuándo y cómo llamarla,
# así que conviene que sean claros.
# ---------------------------------------------------------------------------


@mcp.tool()
def search_books(query: str = "", genre: str = "", available_only: bool = False) -> list[dict]:
    """Busca libros por título y/o género.

    Args:
        query: Texto a buscar dentro del título (búsqueda parcial, ignora mayúsculas).
        genre: Filtra por género exacto (ej. "Cuento", "Novela"). Vacío = todos.
        available_only: Si es True, solo devuelve libros con copias disponibles.

    Returns:
        Lista de libros con su autor. Vacía si no hay coincidencias.
    """
    sql = """
        SELECT b.id, b.title, a.name AS author, b.genre,
               b.published_year, b.available_copies, b.total_copies
        FROM books b
        JOIN authors a ON a.id = b.author_id
        WHERE b.title ILIKE %(q)s
          AND (%(genre)s = '' OR b.genre = %(genre)s)
          AND (NOT %(avail)s OR b.available_copies > 0)
        ORDER BY b.title
    """
    with get_cursor() as cur:
        cur.execute(sql, {"q": f"%{query}%", "genre": genre, "avail": available_only})
        return cur.fetchall()


@mcp.tool()
def get_book(book_id: int) -> dict | None:
    """Devuelve el detalle completo de un libro por su id.

    Returns:
        El libro con todos sus campos y el nombre del autor, o None si no existe.
    """
    sql = """
        SELECT b.id, b.title, a.name AS author, a.country AS author_country,
               b.genre, b.published_year, b.isbn,
               b.available_copies, b.total_copies
        FROM books b
        JOIN authors a ON a.id = b.author_id
        WHERE b.id = %(id)s
    """
    with get_cursor() as cur:
        cur.execute(sql, {"id": book_id})
        return cur.fetchone()


@mcp.tool()
def books_by_author(author_name: str) -> list[dict]:
    """Lista los libros de un autor buscando por su nombre (búsqueda parcial).

    Args:
        author_name: Nombre o parte del nombre del autor (ej. "Borges").
    """
    sql = """
        SELECT b.id, b.title, b.genre, b.published_year, b.available_copies
        FROM books b
        JOIN authors a ON a.id = b.author_id
        WHERE a.name ILIKE %(name)s
        ORDER BY b.published_year
    """
    with get_cursor() as cur:
        cur.execute(sql, {"name": f"%{author_name}%"})
        return cur.fetchall()


@mcp.tool()
def list_authors() -> list[dict]:
    """Devuelve todos los autores con cuántos libros tiene cada uno."""
    sql = """
        SELECT a.id, a.name, a.country, a.birth_year,
               COUNT(b.id) AS book_count
        FROM authors a
        LEFT JOIN books b ON b.author_id = a.id
        GROUP BY a.id
        ORDER BY a.name
    """
    with get_cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


@mcp.tool()
def library_stats() -> dict:
    """Devuelve un resumen de la biblioteca: totales y disponibilidad."""
    sql = """
        SELECT
            (SELECT COUNT(*) FROM books)                       AS total_titles,
            (SELECT COUNT(*) FROM authors)                     AS total_authors,
            (SELECT COALESCE(SUM(total_copies), 0) FROM books) AS total_copies,
            (SELECT COALESCE(SUM(available_copies), 0) FROM books) AS available_copies
    """
    with get_cursor() as cur:
        cur.execute(sql)
        return cur.fetchone()


if __name__ == "__main__":
    # stdio (local) o streamable-http (desplegado). Ver MCP_TRANSPORT arriba.
    mcp.run(transport=TRANSPORT)
