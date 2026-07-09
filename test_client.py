"""
Cliente de ejemplo para probar el MCP sin un agente.

Arranca server.py como subproceso (transporte stdio), igual que haría un
agente, lista las herramientas disponibles y llama algunas. Sirve para ver
la mecánica del protocolo: initialize -> list_tools -> call_tool.

Ejecutar:  uv run test_client.py
"""

import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    # Cómo se lanza el server. Un agente hace exactamente esto por debajo.
    params = StdioServerParameters(command="uv", args=["run", "server.py"])

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1) Descubrir qué herramientas expone el server.
            tools = await session.list_tools()
            print("Tools disponibles:", [t.name for t in tools.tools])

            # 2) Llamar herramientas (nombre + argumentos como dict).
            stats = await session.call_tool("library_stats", {})
            print("\nlibrary_stats ->", stats.content[0].text)

            found = await session.call_tool("search_books", {"query": "sole"})
            print("\nsearch_books(query='sole') ->", found.content[0].text)

            borges = await session.call_tool("books_by_author", {"author_name": "Borges"})
            print("\nbooks_by_author('Borges') ->", borges.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())
