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
import time
from contextlib import contextmanager
from pathlib import Path

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
# Al arrancar, crea el esquema y carga datos de ejemplo si faltan.
AUTO_INIT_DB = os.environ.get("AUTO_INIT_DB", "true").lower() == "true"
SEED_FILE = Path(__file__).parent / "seed.sql"

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


def init_db(retries: int = 15, delay: float = 2.0) -> None:
    """Crea el esquema y carga los datos de ejemplo si aún no existen.

    Ejecuta seed.sql, que es idempotente (CREATE ... IF NOT EXISTS + INSERT ...
    ON CONFLICT DO NOTHING), así que correrlo en cada arranque es seguro.

    Reintenta mientras Postgres termina de arrancar (útil en Coolify, donde
    los contenedores levantan en paralelo). Si tras los reintentos no conecta,
    avisa pero deja arrancar el server (el health check sigue funcionando).
    """
    if not AUTO_INIT_DB:
        return
    sql = SEED_FILE.read_text(encoding="utf-8")
    for attempt in range(1, retries + 1):
        try:
            with psycopg.connect(DATABASE_URL) as conn:
                conn.execute(sql)
            print("[init_db] esquema y datos de ejemplo verificados", flush=True)
            return
        except psycopg.OperationalError as exc:
            print(
                f"[init_db] Postgres aún no responde "
                f"(intento {attempt}/{retries}): {exc}",
                flush=True,
            )
            time.sleep(delay)
    print("[init_db] no se pudo inicializar la DB tras varios intentos", flush=True)


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

    La búsqueda por título es PARCIAL y no distingue mayúsculas ni acentos
    (ej. "soledad" o "SOLEDAD" encuentran "Cien años de soledad"). No necesitas
    el título exacto; pasa el texto que dio el usuario.

    Args:
        query: Texto a buscar dentro del título (parcial, sin importar acentos).
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
        WHERE unaccent(b.title) ILIKE unaccent(%(q)s)
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
    """Lista los libros de un autor buscando por su nombre.

    Acepta nombres PARCIALES o aproximados y no distingue mayúsculas ni acentos
    (ej. "garcia" o "GARCÍA" encuentran "Gabriel García Márquez"). No necesitas
    el nombre completo ni exacto; pasa el texto que dio el usuario.

    Args:
        author_name: Nombre o parte del nombre del autor (ej. "Borges", "garcia").
    """
    sql = """
        SELECT b.id, b.title, b.genre, b.published_year, b.available_copies
        FROM books b
        JOIN authors a ON a.id = b.author_id
        WHERE unaccent(a.name) ILIKE unaccent(%(name)s)
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
    # Asegura esquema + datos antes de servir (idempotente; se puede desactivar
    # con AUTO_INIT_DB=false en el proyecto real).
    init_db()
    # stdio (local) o streamable-http (desplegado). Ver MCP_TRANSPORT arriba.
    mcp.run(transport=TRANSPORT)
