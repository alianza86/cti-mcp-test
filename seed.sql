-- Esquema y datos de ejemplo para el MCP de biblioteca.
--
-- Es IDEMPOTENTE: se puede ejecutar muchas veces sin romper.
--   - CREATE TABLE IF NOT EXISTS  -> no falla si ya existe.
--   - INSERT ... ON CONFLICT DO NOTHING -> no duplica filas.
-- La app (server.py) lo ejecuta al arrancar, así no dependemos de mounts
-- ni de tocar el contenedor de Postgres a mano.

-- Búsquedas que ignoran acentos ("garcia" encuentra "García").
CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE TABLE IF NOT EXISTS authors (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    country     TEXT,
    birth_year  INT
);

CREATE TABLE IF NOT EXISTS books (
    id              SERIAL PRIMARY KEY,
    title           TEXT NOT NULL,
    author_id       INT NOT NULL REFERENCES authors(id),
    genre           TEXT,
    published_year  INT,
    isbn            TEXT UNIQUE,
    available_copies INT NOT NULL DEFAULT 0,
    total_copies     INT NOT NULL DEFAULT 0
);

INSERT INTO authors (name, country, birth_year) VALUES
    ('Gabriel García Márquez', 'Colombia', 1927),
    ('Isabel Allende',         'Chile',    1942),
    ('Jorge Luis Borges',      'Argentina',1899),
    ('Mario Vargas Llosa',     'Perú',     1936),
    ('Julio Cortázar',         'Argentina',1914),
    ('Octavio Paz',            'México',   1914)
ON CONFLICT (name) DO NOTHING;

INSERT INTO books (title, author_id, genre, published_year, isbn, available_copies, total_copies) VALUES
    ('Cien años de soledad',        1, 'Realismo mágico', 1967, '978-0307474728', 3, 5),
    ('El amor en los tiempos del cólera', 1, 'Romance',    1985, '978-0307389732', 0, 2),
    ('La casa de los espíritus',    2, 'Realismo mágico', 1982, '978-1501117015', 4, 4),
    ('Paula',                       2, 'Memorias',        1994, '978-0060927219', 1, 2),
    ('Ficciones',                   3, 'Cuento',          1944, '978-0307950925', 2, 3),
    ('El Aleph',                    3, 'Cuento',          1949, '978-8420633114', 1, 1),
    ('La ciudad y los perros',      4, 'Novela',          1963, '978-8466331906', 2, 2),
    ('La fiesta del chivo',         4, 'Novela histórica',2000, '978-8420471815', 0, 3),
    ('Rayuela',                     5, 'Novela',          1963, '978-8437604572', 5, 5),
    ('Bestiario',                   5, 'Cuento',          1951, '978-8420672069', 1, 1),
    ('El laberinto de la soledad',  6, 'Ensayo',          1950, '978-9681603496', 2, 2)
ON CONFLICT (isbn) DO NOTHING;
