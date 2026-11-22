"""El Recolector: recorre las Fuentes activas y guarda Items nuevos, registrando la Ejecución."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from tn import db
from tn.http import Http
from tn.modelo import Fuente
from tn.prefiltro import prefiltrar
from tn.recolectores import Recolector, recolectores


@dataclass
class ResultadoFuente:
    fuente_id: str
    recogidos: int = 0
    descartados: int = 0
    nuevos: int = 0
    error: str | None = None


@dataclass
class ResultadoEjecucion:
    ejecucion_id: int
    estado: str
    fuentes: list[ResultadoFuente] = field(default_factory=list)

    @property
    def nuevos(self) -> int:
        return sum(f.nuevos for f in self.fuentes)


def _estado(resultados: list[ResultadoFuente]) -> str:
    errores = sum(1 for r in resultados if r.error)
    if not resultados or errores == 0:
        return "ok"
    return "fallida" if errores == len(resultados) else "con_errores"


def recoger(
    conn: sqlite3.Connection,
    fuentes: list[Fuente],
    *,
    origen: str,
    http: Http,
    solo: set[str] | None = None,
    colectores: dict[str, Recolector] | None = None,
    al_terminar_fuente=None,
) -> ResultadoEjecucion:
    """Recoge de cada Fuente desde su última recogida con éxito.

    Una Fuente que falla no tumba la Ejecución: su error queda registrado, su cursor no
    avanza (la próxima vez se reintenta desde el mismo punto) y el resto sigue.
    """
    colectores = colectores or recolectores()
    inicio = db.ahora()
    comando = "recoger" + (f" --fuente {','.join(sorted(solo))}" if solo else "")
    ejecucion_id = db.abrir_ejecucion(conn, comando, origen, inicio)
    resultados: list[ResultadoFuente] = []

    for fuente in fuentes:
        if not fuente.la_recoge_el_recolector or (solo and fuente.id not in solo):
            continue
        res = ResultadoFuente(fuente_id=fuente.id)
        try:
            crudos = colectores[fuente.tipo](fuente, db.leer_cursor(conn, fuente.id), http)
            filtrado = prefiltrar(crudos)
            res.recogidos = len(crudos)
            res.descartados = filtrado.descartados
            res.nuevos = db.insertar_items(conn, ejecucion_id, filtrado.aceptados, inicio)
            # El cursor avanza al inicio de la Ejecución, no al final: lo publicado mientras
            # corría se verá en la siguiente.
            db.guardar_cursor(conn, fuente.id, inicio)
        except Exception as e:  # noqa: BLE001 — cualquier fallo de una Fuente se registra y se sigue
            conn.rollback()
            res = ResultadoFuente(fuente_id=fuente.id, error=f"{type(e).__name__}: {e}"[:500])
        db.registrar_fuente(
            conn, ejecucion_id, fuente.id,
            recogidos=res.recogidos, descartados=res.descartados, nuevos=res.nuevos, error=res.error,
        )
        conn.commit()
        resultados.append(res)
        if al_terminar_fuente:
            al_terminar_fuente(res)

    estado = _estado(resultados)
    db.cerrar_ejecucion(conn, ejecucion_id, estado)
    return ResultadoEjecucion(ejecucion_id=ejecucion_id, estado=estado, fuentes=resultados)
