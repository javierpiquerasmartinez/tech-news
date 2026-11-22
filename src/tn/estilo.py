"""Revisión de la Guía de estilo de edición a partir de las Fichas de feedback.

Igual que `tn.perfil`: el agente `estilo` solo deja el fichero propuesto en `data/borradores/`;
la persona editora lo acepta o lo rechaza. `estilo-edicion.md` nunca cambia solo.
"""

from __future__ import annotations

import difflib
import shutil
import sqlite3

from tn import config, feedback
from tn.db import _iso, ahora

ESQUEMA = """
CREATE TABLE IF NOT EXISTS revisiones_estilo (
    id       INTEGER PRIMARY KEY,
    momento  TEXT NOT NULL,
    estado   TEXT NOT NULL      -- aceptada | rechazada
);
"""
MINIMO_NOTAS = 3


class SinPropuesta(RuntimeError):
    pass


def ruta_guia():
    return config.raiz() / "estilo-edicion.md"


def ruta_propuesta():
    return config.ruta_db().parent / "borradores" / "estilo-edicion.propuesto.md"


def ultima_revision(conn: sqlite3.Connection) -> str:
    conn.executescript(ESQUEMA)
    fila = conn.execute("SELECT MAX(momento) AS m FROM revisiones_estilo").fetchone()
    return (fila["m"] or "")[:10]


def notas_pendientes(conn: sqlite3.Connection) -> list[dict]:
    """Notas de las Fichas desde la última revisión (por fecha de la nota)."""
    return [n.como_dict() for n in feedback.todas(desde=ultima_revision(conn))]


def hay_propuesta() -> bool:
    return ruta_propuesta().is_file()


def diff() -> str:
    if not hay_propuesta():
        raise SinPropuesta("No hay ninguna propuesta de cambios a la Guía de estilo de edición")
    actual = ruta_guia().read_text(encoding="utf-8").splitlines(keepends=True)
    nuevo = ruta_propuesta().read_text(encoding="utf-8").splitlines(keepends=True)
    return "".join(difflib.unified_diff(actual, nuevo, "estilo-edicion.md (actual)", "estilo-edicion.md (propuesto)"))


def aceptar(conn: sqlite3.Connection) -> None:
    if not hay_propuesta():
        raise SinPropuesta("No hay ninguna propuesta de cambios a la Guía de estilo de edición")
    shutil.copy2(ruta_guia(), config.ruta_db().parent / f"estilo-edicion.{ahora().strftime('%Y%m%dT%H%M%S')}.md")
    shutil.move(ruta_propuesta(), ruta_guia())
    _registrar(conn, "aceptada")


def rechazar(conn: sqlite3.Connection) -> None:
    if not hay_propuesta():
        raise SinPropuesta("No hay ninguna propuesta de cambios a la Guía de estilo de edición")
    ruta_propuesta().unlink()
    _registrar(conn, "rechazada")


def _registrar(conn: sqlite3.Connection, estado: str) -> None:
    conn.executescript(ESQUEMA)
    conn.execute("INSERT INTO revisiones_estilo (momento, estado) VALUES (?, ?)", (_iso(ahora()), estado))
    conn.commit()
