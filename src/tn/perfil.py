"""Revisión del Perfil editorial a partir de las decisiones de la persona editora.

El agente `perfil` solo deja una propuesta (el fichero completo) en `data/borradores/`; la
persona editora la acepta o la rechaza. `perfil-editorial.md` nunca cambia solo.
"""

from __future__ import annotations

import difflib
import json
import shutil
import sqlite3

from tn import config
from tn.db import _iso, ahora

ESQUEMA = """
CREATE TABLE IF NOT EXISTS revisiones_perfil (
    id       INTEGER PRIMARY KEY,
    momento  TEXT NOT NULL,
    estado   TEXT NOT NULL      -- aceptada | rechazada
);
"""


class SinPropuesta(RuntimeError):
    pass


def ruta_perfil():
    return config.raiz() / "perfil-editorial.md"


def ruta_propuesta():
    return config.ruta_db().parent / "borradores" / "perfil-editorial.propuesto.md"


def _preparar(conn: sqlite3.Connection) -> None:
    conn.executescript(ESQUEMA)


def ultima_revision(conn: sqlite3.Connection) -> str | None:
    _preparar(conn)
    fila = conn.execute("SELECT MAX(momento) AS m FROM revisiones_perfil").fetchone()
    return fila["m"]


def decisiones_pendientes(conn: sqlite3.Connection) -> list[dict]:
    """Correcciones de la persona editora desde la última revisión aceptada o rechazada."""
    desde = ultima_revision(conn) or ""
    filas = conn.execute(
        """SELECT d.accion, d.detalle, d.origen, d.momento, h.id AS historia, h.titulo, h.area, h.estado,
                  h.urgencia, h.valor_didactico, h.peso_semanal
           FROM decisiones d JOIN historias h ON h.id = d.historia_id
           WHERE d.momento > ? ORDER BY d.momento""",
        (desde,),
    ).fetchall()
    res = []
    for f in filas:
        d = dict(f)
        d["detalle"] = json.loads(d["detalle"]) if d["detalle"] else {}
        res.append(d)
    return res


def hay_propuesta() -> bool:
    return ruta_propuesta().is_file()


def diff() -> str:
    if not hay_propuesta():
        raise SinPropuesta("No hay ninguna propuesta de cambios al Perfil editorial")
    actual = ruta_perfil().read_text(encoding="utf-8").splitlines(keepends=True)
    nuevo = ruta_propuesta().read_text(encoding="utf-8").splitlines(keepends=True)
    return "".join(difflib.unified_diff(actual, nuevo, "perfil-editorial.md (actual)", "perfil-editorial.md (propuesto)"))


def aceptar(conn: sqlite3.Connection) -> None:
    if not hay_propuesta():
        raise SinPropuesta("No hay ninguna propuesta de cambios al Perfil editorial")
    copia = config.ruta_db().parent / f"perfil-editorial.{ahora().strftime('%Y%m%dT%H%M%S')}.md"
    shutil.copy2(ruta_perfil(), copia)
    shutil.move(ruta_propuesta(), ruta_perfil())
    _registrar(conn, "aceptada")


def rechazar(conn: sqlite3.Connection) -> None:
    if not hay_propuesta():
        raise SinPropuesta("No hay ninguna propuesta de cambios al Perfil editorial")
    ruta_propuesta().unlink()
    _registrar(conn, "rechazada")


def _registrar(conn: sqlite3.Connection, estado: str) -> None:
    _preparar(conn)
    conn.execute("INSERT INTO revisiones_perfil (momento, estado) VALUES (?, ?)", (_iso(ahora()), estado))
    conn.commit()
