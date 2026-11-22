"""Capa máquina (ADR-0003): SQLite local, fuera de git."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from tn.prefiltro import ItemFiltrado

ESQUEMA = """
CREATE TABLE IF NOT EXISTS ejecuciones (
    id       INTEGER PRIMARY KEY,
    comando  TEXT NOT NULL,
    origen   TEXT NOT NULL,              -- manual | horario | claude | web
    inicio   TEXT NOT NULL,
    fin      TEXT,
    estado   TEXT NOT NULL               -- en_curso | ok | con_errores | fallida
);

CREATE TABLE IF NOT EXISTS ejecucion_fuentes (
    ejecucion_id  INTEGER NOT NULL REFERENCES ejecuciones(id),
    fuente_id     TEXT NOT NULL,
    recogidos     INTEGER NOT NULL DEFAULT 0,
    descartados   INTEGER NOT NULL DEFAULT 0,
    nuevos        INTEGER NOT NULL DEFAULT 0,
    error         TEXT,
    PRIMARY KEY (ejecucion_id, fuente_id)
);

CREATE TABLE IF NOT EXISTS items (
    id               INTEGER PRIMARY KEY,
    fuente_id        TEXT NOT NULL,
    url              TEXT NOT NULL,
    url_normalizada  TEXT NOT NULL,
    titulo           TEXT NOT NULL,
    resumen          TEXT,
    seccion          TEXT,
    origen           TEXT,
    publicado_en     TEXT,
    recogido_en      TEXT NOT NULL,
    ejecucion_id     INTEGER NOT NULL REFERENCES ejecuciones(id),
    UNIQUE (fuente_id, url_normalizada)
);
CREATE INDEX IF NOT EXISTS items_url ON items(url_normalizada);
CREATE INDEX IF NOT EXISTS items_recogido ON items(recogido_en);

-- Última recogida con éxito por Fuente: la siguiente recoge "desde" aquí (ADR-0002).
CREATE TABLE IF NOT EXISTS cursores (
    fuente_id  TEXT PRIMARY KEY,
    ultima_ok  TEXT NOT NULL
);

-- Items que enlazan a la misma URL, aunque vengan de Fuentes distintas.
CREATE VIEW IF NOT EXISTS grupos_url AS
SELECT url_normalizada,
       COUNT(*)                   AS items,
       COUNT(DISTINCT fuente_id)  AS fuentes,
       MIN(recogido_en)           AS primera_vez,
       GROUP_CONCAT(id)           AS item_ids
FROM items
GROUP BY url_normalizada;
"""


def ahora() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime | None) -> str | None:
    return dt.astimezone(UTC).isoformat(timespec="seconds") if dt else None


def conectar(ruta: Path) -> sqlite3.Connection:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ruta)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(ESQUEMA)
    return conn


def abrir_ejecucion(conn: sqlite3.Connection, comando: str, origen: str, inicio: datetime) -> int:
    cur = conn.execute(
        "INSERT INTO ejecuciones (comando, origen, inicio, estado) VALUES (?, ?, ?, 'en_curso')",
        (comando, origen, _iso(inicio)),
    )
    conn.commit()
    return int(cur.lastrowid)


def cerrar_ejecucion(conn: sqlite3.Connection, ejecucion_id: int, estado: str) -> None:
    conn.execute(
        "UPDATE ejecuciones SET fin = ?, estado = ? WHERE id = ?",
        (_iso(ahora()), estado, ejecucion_id),
    )
    conn.commit()


def registrar_fuente(
    conn: sqlite3.Connection,
    ejecucion_id: int,
    fuente_id: str,
    *,
    recogidos: int = 0,
    descartados: int = 0,
    nuevos: int = 0,
    error: str | None = None,
) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO ejecucion_fuentes "
        "(ejecucion_id, fuente_id, recogidos, descartados, nuevos, error) VALUES (?, ?, ?, ?, ?, ?)",
        (ejecucion_id, fuente_id, recogidos, descartados, nuevos, error),
    )


def insertar_items(
    conn: sqlite3.Connection, ejecucion_id: int, items: list[ItemFiltrado], recogido_en: datetime
) -> int:
    """Inserta los Items que no existían ya para su Fuente. Devuelve cuántos son nuevos."""
    nuevos = 0
    for f in items:
        it = f.item
        cur = conn.execute(
            "INSERT OR IGNORE INTO items (fuente_id, url, url_normalizada, titulo, resumen, seccion, "
            "origen, publicado_en, recogido_en, ejecucion_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                it.fuente_id, it.url, f.url_normalizada, it.titulo, it.resumen, it.seccion,
                it.origen, _iso(it.publicado_en), _iso(recogido_en), ejecucion_id,
            ),
        )
        nuevos += cur.rowcount
    return nuevos


def leer_cursor(conn: sqlite3.Connection, fuente_id: str) -> datetime | None:
    fila = conn.execute("SELECT ultima_ok FROM cursores WHERE fuente_id = ?", (fuente_id,)).fetchone()
    return datetime.fromisoformat(fila["ultima_ok"]) if fila else None


def guardar_cursor(conn: sqlite3.Connection, fuente_id: str, momento: datetime) -> None:
    conn.execute(
        "INSERT INTO cursores (fuente_id, ultima_ok) VALUES (?, ?) "
        "ON CONFLICT(fuente_id) DO UPDATE SET ultima_ok = excluded.ultima_ok",
        (fuente_id, _iso(momento)),
    )


def ultimas_ejecuciones(conn: sqlite3.Connection, limite: int = 10) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT e.*, COALESCE(SUM(f.nuevos), 0) AS nuevos,
               COUNT(f.fuente_id) AS fuentes,
               SUM(CASE WHEN f.error IS NOT NULL THEN 1 ELSE 0 END) AS errores
        FROM ejecuciones e LEFT JOIN ejecucion_fuentes f ON f.ejecucion_id = e.id
        GROUP BY e.id ORDER BY e.id DESC LIMIT ?
        """,
        (limite,),
    ).fetchall()


def detalle_ejecucion(conn: sqlite3.Connection, ejecucion_id: int) -> tuple[sqlite3.Row | None, list[sqlite3.Row]]:
    cab = conn.execute("SELECT * FROM ejecuciones WHERE id = ?", (ejecucion_id,)).fetchone()
    filas = conn.execute(
        "SELECT * FROM ejecucion_fuentes WHERE ejecucion_id = ? ORDER BY error IS NULL, fuente_id",
        (ejecucion_id,),
    ).fetchall()
    return cab, filas
